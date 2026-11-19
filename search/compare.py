from pathlib import Path

from search.search import INDEX_NAME, client, search_recipes

# Consultas de ejemplo; la última tiene una errata a propósito
CONSULTAS = [
    "tarta de santiago",
    "filloas",
    "empanada",
    "castañas",
    "caldo galego",
    "lacón con grelos",
    "bica",
    "cocido",
    "augardente",
    "torta de milo",
]
TOP = 5
SALIDA = Path(__file__).resolve().parent / "comparacion.md"


# Línea base: match simple solo sobre la preparación
def busqueda_inicial(consulta, size=TOP):
    respuesta = client.search(
        index=INDEX_NAME,
        size=size,
        query={"match": {"preparation": consulta}},
    )
    return respuesta["hits"]["hits"]


def titulos(hits):
    return [h["_source"]["title"] for h in hits]


def main():
    if not client.ping():
        raise SystemExit("No se pudo conectar con Elasticsearch.")

    lineas = [
        "# Comparación: búsqueda inicial vs. estrategia final",
        "",
        "- **Inicial**: `match` solo sobre `preparation`.",
        "- **Final**: `search_recipes` (frases en título e ingredientes, `multi_match` con pesos y `fuzziness`).",
        f"- Se muestran los {TOP} primeros resultados de cada una.",
        "",
    ]

    for consulta in CONSULTAS:
        inicial = titulos(busqueda_inicial(consulta))
        final = titulos(search_recipes(consulta, size=TOP))
        comunes = len(set(inicial) & set(final))

        lineas += [f"## «{consulta}»", "", "| # | Inicial | Final |", "|---|---|---|"]
        for i in range(max(len(inicial), len(final), 1)):
            a = inicial[i] if i < len(inicial) else "—"
            b = final[i] if i < len(final) else "—"
            lineas.append(f"| {i + 1} | {a} | {b} |")
        lineas += ["", f"Resultados en común: {comunes}/{TOP}", ""]

        print(f"\n== {consulta}")
        for i in range(TOP):
            a = inicial[i] if i < len(inicial) else "—"
            b = final[i] if i < len(final) else "—"
            print(f"  {i + 1}. {a[:38]:38} | {b[:38]}")

    SALIDA.write_text("\n".join(lineas), encoding="utf-8")
    print(f"\nTabla guardada en {SALIDA}")


if __name__ == "__main__":
    main()
