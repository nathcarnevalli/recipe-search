import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from llm.irlab_client import build_request, resume_batch, run_batch

ROOT = Path(__file__).resolve().parent.parent
DATA_FILES = [ROOT / "data/kukinhas.json", ROOT / "data/receitario.json"]
ENRICHED_PATH = ROOT / "data/enriquecido.json"
# Qué recetas van en cada petición agrupada, para poder usar --retomar
GROUPS_PATH = ROOT / "llm/grupos_enrich.json"

# Listas cerradas: las respuestas fuera de ellas se descartan
CATEGORIAS = [
    "sobremesa",
    "repostaria",
    "pan_e_empanadas",
    "sopas_e_caldos",
    "carne",
    "peixe_e_marisco",
    "verduras_e_legumes",
    "ovos",
    "salsas_e_conservas",
    "bebidas",
    "outros",
]
ETIQUETAS = ["vexetariano", "sen_gluten", "sen_lactose", "picante", "forno", "rapida"]

# Varias recetas por petición: el prompt de sistema se envía una vez por grupo
# y no una vez por receta, lo que reduce los tokens de entrada a la mitad
GROUP_SIZE = 10
SYSTEM = (
    "Clasificas receitas galegas numeradas. Responde SO unha liña por receita, "
    "co formato N. categoria|etiqueta1,etiqueta2 sen explicacións.\n"
    f"categoria (unha): {', '.join(CATEGORIAS)}\n"
    f"etiquetas (cero ou máis): {', '.join(ETIQUETAS)}\n"
    "Exemplo:\n1. sobremesa|vexetariano,forno\n2. carne|"
)

MAX_INGREDIENT_CHARS = 400
MAX_TOKENS_POR_RECEITA = 22

LINEA_NUMERADA = re.compile(r"^\s*(\d+)\s*[.):-]\s*(.*)$")


def load_recipes():
    recipes = []
    for path in DATA_FILES:
        with open(path, encoding="utf-8") as f:
            recipes.extend(json.load(f))
    return recipes


# Caché por recipe_id: lo ya clasificado no se vuelve a enviar
def load_enriched():
    if ENRICHED_PATH.exists():
        return json.loads(ENRICHED_PATH.read_text(encoding="utf-8"))
    return {}


def load_groups():
    if GROUPS_PATH.exists():
        return json.loads(GROUPS_PATH.read_text(encoding="utf-8"))
    return {}


# Solo título e ingredientes: la preparación multiplicaría el coste
def recipe_line(n, recipe):
    ingredients = recipe.get("ingredients") or []
    if not isinstance(ingredients, list):
        ingredients = [ingredients]
    texto = "; ".join(i.strip() for i in ingredients if i and i.strip())
    return f"{n}. {recipe['title']} | {texto[:MAX_INGREDIENT_CHARS]}"


# Normaliza "categoria|etiqueta1,etiqueta2" y valida contra las listas
def parse_answer(content):
    linea = content.strip().splitlines()[0] if content.strip() else ""
    linea = linea.strip().strip("`").strip(".").lower()
    categoria, _, etiquetas = linea.partition("|")
    categoria = categoria.strip().replace(" ", "_")
    tags = [t.strip().replace(" ", "_") for t in etiquetas.split(",") if t.strip()]
    valido = categoria in CATEGORIAS and all(t in ETIQUETAS for t in tags)
    return {
        "categoria": categoria if categoria in CATEGORIAS else None,
        "etiquetas": sorted({t for t in tags if t in ETIQUETAS}),
        "valido": valido,
        "raw": content,
    }


# Reparte la respuesta de un grupo ("1. ...\n2. ...") entre sus recetas
def parse_group(content, ids):
    por_receta = {}
    for linea in content.splitlines():
        m = LINEA_NUMERADA.match(linea)
        if not m:
            continue
        n = int(m.group(1))
        if 1 <= n <= len(ids) and ids[n - 1] not in por_receta:
            por_receta[ids[n - 1]] = parse_answer(m.group(2))
    return por_receta


def build_groups(pendentes):
    stamp = f"{datetime.now():%Y%m%d%H%M%S}"
    peticions, grupos = [], {}
    for g in range(0, len(pendentes), GROUP_SIZE):
        grupo = pendentes[g : g + GROUP_SIZE]
        cid = f"{stamp}-g{g // GROUP_SIZE:03d}"
        user = "\n".join(recipe_line(n, r) for n, r in enumerate(grupo, start=1))
        peticions.append(
            build_request(cid, SYSTEM, user, max_tokens=MAX_TOKENS_POR_RECEITA * len(grupo))
        )
        grupos[cid] = [r["recipe_id"] for r in grupo]
    return peticions, grupos


def main():
    parser = argparse.ArgumentParser(description="Clasifica as receitas co LLM do IRLab.")
    parser.add_argument("--piloto", type=int, metavar="N", help="procesar só N receitas novas")
    parser.add_argument("--retomar", metavar="BATCH_ID", help="recoller un lote xa enviado")
    parser.add_argument("--estimar", action="store_true", help="só estimar o custo, sen enviar nada")
    args = parser.parse_args()

    recipes = load_recipes()
    enriched = load_enriched()
    grupos = load_groups()

    if args.retomar:
        resultados = resume_batch(args.retomar)
    else:
        pendentes = [r for r in recipes if r["recipe_id"] not in enriched]
        if args.piloto:
            pendentes = pendentes[: args.piloto]
        peticions, novos = build_groups(pendentes)

        # Estimación aproximada: ~3 caracteres por token (el máximo de salida casi nunca se alcanza)
        chars = sum(len(SYSTEM) + len(p["body"]["messages"][1]["content"]) for p in peticions)
        saida = sum(p["body"]["max_tokens"] for p in peticions)
        print(
            f"Receitas: {len(recipes)} | xa enriquecidas: {len(enriched)} | "
            f"a enviar: {len(pendentes)} en {len(peticions)} peticións de ata {GROUP_SIZE}"
        )
        print(f"Custo estimado: ~{chars // 3 + saida} tokens (entrada ~{chars // 3} + saída máx. {saida})")

        if args.estimar or not peticions:
            return

        # Guardar los grupos antes de enviar: si se interrumpe, --retomar los necesita
        grupos.update(novos)
        GROUPS_PATH.write_text(json.dumps(grupos, ensure_ascii=False, indent=2), encoding="utf-8")
        resultados = run_batch(peticions, nombre=f"enrich_{len(pendentes)}")

    invalidas = enviadas = 0
    novas = []
    for cid, r in resultados.items():
        # Lotes antiguos: una receta por petición, el custom_id es el recipe_id
        ids = grupos.get(cid, [cid])
        enviadas += len(ids)
        if not r["ok"]:
            continue
        datos = parse_group(r["content"], ids) if cid in grupos else {cid: parse_answer(r["content"])}
        for rid, d in datos.items():
            invalidas += not d["valido"]
            enriched[rid] = d
            novas.append(rid)

    ENRICHED_PATH.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Gardadas {len(enriched)} receitas en {ENRICHED_PATH.relative_to(ROOT)}")
    print(f"Respostas fóra do formato: {invalidas}")
    if enviadas - len(novas):
        print(f"Sen resposta: {enviadas - len(novas)} receitas (envíanse na próxima execución)")

    titulos = {r["recipe_id"]: r["title"] for r in recipes}
    for rid in novas[:10]:
        e = enriched[rid]
        print(f"  {titulos.get(rid, rid)[:50]:50} -> {e['categoria']} {e['etiquetas']}  (raw: {e['raw']!r})")


if __name__ == "__main__":
    main()
