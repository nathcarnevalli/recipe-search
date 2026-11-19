import argparse
import json
from pathlib import Path

from llm.irlab_client import build_request, resume_batch, run_batch

ROOT = Path(__file__).resolve().parent.parent
DATA_FILES = [ROOT / "data/kukinhas.json", ROOT / "data/receitario.json"]
ENRICHED_PATH = ROOT / "data/enriquecido.json"

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

# Respuesta en una sola línea para gastar pocos tokens de salida
SYSTEM = (
    "Clasificas receitas galegas. Responde SO nunha liña co formato "
    "categoria|etiqueta1,etiqueta2 sen explicacións.\n"
    f"categoria (unha): {', '.join(CATEGORIAS)}\n"
    f"etiquetas (cero ou máis): {', '.join(ETIQUETAS)}\n"
    "Exemplo: sobremesa|vexetariano,forno"
)

MAX_INGREDIENT_CHARS = 400
MAX_TOKENS = 20


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


# Solo título e ingredientes: la preparación multiplicaría el coste
def user_prompt(recipe):
    ingredients = recipe.get("ingredients") or []
    if not isinstance(ingredients, list):
        ingredients = [ingredients]
    texto = "; ".join(i.strip() for i in ingredients if i and i.strip())
    return f"Título: {recipe['title']}\nIngredientes: {texto[:MAX_INGREDIENT_CHARS]}"


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


def main():
    parser = argparse.ArgumentParser(description="Clasifica as receitas co LLM do IRLab.")
    parser.add_argument("--piloto", type=int, metavar="N", help="procesar só N receitas novas")
    parser.add_argument("--retomar", metavar="BATCH_ID", help="recoller un lote xa enviado")
    parser.add_argument("--estimar", action="store_true", help="só estimar o custo, sen enviar nada")
    args = parser.parse_args()

    recipes = load_recipes()
    enriched = load_enriched()
    pendentes = [r for r in recipes if r["recipe_id"] not in enriched]
    if args.piloto:
        pendentes = pendentes[: args.piloto]

    peticions = [
        build_request(r["recipe_id"], SYSTEM, user_prompt(r), max_tokens=MAX_TOKENS)
        for r in pendentes
    ]

    # Estimación aproximada: ~3 caracteres por token
    chars = sum(len(SYSTEM) + len(p["body"]["messages"][1]["content"]) for p in peticions)
    estimacion = chars // 3 + MAX_TOKENS * len(peticions)
    print(f"Receitas: {len(recipes)} | xa enriquecidas: {len(enriched)} | a enviar: {len(peticions)}")
    print(f"Custo estimado: ~{estimacion} tokens (máximo de saída incluído)")

    if args.retomar:
        resultados = resume_batch(args.retomar)
    elif args.estimar or not peticions:
        return
    else:
        resultados = run_batch(peticions, nombre=f"enrich_{len(peticions)}")

    invalidas = 0
    for cid, r in resultados.items():
        if not r["ok"]:
            continue
        datos = parse_answer(r["content"])
        invalidas += not datos["valido"]
        enriched[cid] = datos

    ENRICHED_PATH.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Gardadas {len(enriched)} receitas en {ENRICHED_PATH.relative_to(ROOT)}")
    print(f"Respostas fóra do formato: {invalidas}")

    titulos = {r["recipe_id"]: r["title"] for r in recipes}
    for cid in list(resultados)[:10]:
        e = enriched.get(cid)
        if e:
            print(f"  {titulos.get(cid, cid)[:50]:50} -> {e['categoria']} {e['etiquetas']}  (raw: {e['raw']!r})")


if __name__ == "__main__":
    main()
