"""Evaluación de la búsqueda con juicios de relevancia (search/qrels.json).

Compara la línea base (match sobre la preparación) con la estrategia final
(search_recipes) usando P@5, R@10 y MRR. No usa el LLM.

    docker compose run --rm indexer python -m search.evaluate
"""

import json
from pathlib import Path

from search.compare import busqueda_inicial
from search.search import client, search_recipes

QRELS = Path(__file__).resolve().parent / "qrels.json"
SALIDA = Path(__file__).resolve().parent / "evaluacion.md"
K_PRECISION = 5
K_RECALL = 10
PROFUNDIDAD = 10


def precision_at(ranking, relevantes, k):
    return sum(1 for rid in ranking[:k] if rid in relevantes) / k


def recall_at(ranking, relevantes, k):
    return sum(1 for rid in ranking[:k] if rid in relevantes) / len(relevantes)


def reciprocal_rank(ranking, relevantes):
    for posicion, rid in enumerate(ranking, start=1):
        if rid in relevantes:
            return 1 / posicion
    return 0.0


def ids(hits):
    return [h["_source"]["recipe_id"] for h in hits]


ESTRATEGIAS = {
    "Inicial": lambda q: ids(busqueda_inicial(q, size=PROFUNDIDAD)),
    "Final": lambda q: ids(search_recipes(q, size=PROFUNDIDAD)),
}


def evaluar():
    consultas = json.loads(QRELS.read_text(encoding="utf-8"))["consultas"]
    filas = {nombre: [] for nombre in ESTRATEGIAS}
    for consulta, juicio in consultas.items():
        relevantes = set(juicio["relevantes"])
        for nombre, buscar in ESTRATEGIAS.items():
            ranking = buscar(consulta)
            filas[nombre].append(
                {
                    "consulta": consulta,
                    "relevantes": len(relevantes),
                    "p": precision_at(ranking, relevantes, K_PRECISION),
                    "r": recall_at(ranking, relevantes, K_RECALL),
                    "rr": reciprocal_rank(ranking, relevantes),
                }
            )
    return filas


def media(filas, clave):
    return sum(f[clave] for f in filas) / len(filas)


def main():
    if not client.ping():
        raise SystemExit("No se pudo conectar con Elasticsearch.")

    filas = evaluar()
    nombres = list(ESTRATEGIAS)

    lineas = [
        "# Evaluación de la búsqueda",
        "",
        f"Juicios binarios en `search/qrels.json` ({len(filas[nombres[0]])} consultas). "
        f"Métricas: P@{K_PRECISION}, R@{K_RECALL} y MRR (sobre los {PROFUNDIDAD} primeros).",
        "",
        "- **Inicial**: `match` solo sobre `preparation`.",
        "- **Final**: `search_recipes` (frases en título e ingredientes, `multi_match` con pesos y `fuzziness`).",
        "",
        "## Media",
        "",
        f"| Estrategia | P@{K_PRECISION} | R@{K_RECALL} | MRR |",
        "|---|---|---|---|",
    ]
    for nombre in nombres:
        f = filas[nombre]
        lineas.append(f"| {nombre} | {media(f, 'p'):.3f} | {media(f, 'r'):.3f} | {media(f, 'rr'):.3f} |")

    lineas += [
        "",
        f"P@{K_PRECISION} tiene un techo bajo en las consultas con pocas recetas relevantes "
        f"(con 1 relevante, el máximo es {1 / K_PRECISION:.1f}); por eso se dan también R@{K_RECALL} y MRR.",
        "",
        "## Por consulta",
        "",
        "| Consulta | Relevantes | "
        + " | ".join(f"{n} P@{K_PRECISION} / R@{K_RECALL} / RR" for n in nombres)
        + " |",
        "|---|---|" + "---|" * len(nombres),
    ]
    for i, fila in enumerate(filas[nombres[0]]):
        celdas = [
            f"{filas[n][i]['p']:.2f} / {filas[n][i]['r']:.2f} / {filas[n][i]['rr']:.2f}" for n in nombres
        ]
        lineas.append(f"| {fila['consulta']} | {fila['relevantes']} | " + " | ".join(celdas) + " |")

    SALIDA.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas[9 : 11 + len(nombres)]))
    print(f"\nInforme completo en {SALIDA.relative_to(SALIDA.parent.parent)}")


if __name__ == "__main__":
    main()
