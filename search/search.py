import os
from elasticsearch import Elasticsearch

# Conexión con Elasticsearch
client = Elasticsearch(os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"))

INDEX_NAME = "receitas_galegas"


def search_recipes(query, size=10, **filtros):
    return search_page(query, size=size, **filtros)[0]


# Una página de resultados y el total de coincidencias (para paginar en la web)
def search_page(query, size=10, offset=0, source=None, categoria=None, etiquetas=None, dificultade=None):
    filters = [{"term": {"source": source}}] if source else []

    # Calculada por reglas en la indexación (indexer/dificultade.py)
    if dificultade:
        filters.append({"term": {"dificultade": dificultade}})

    # Campos generados por el LLM (llm/enrich.py)
    if categoria:
        filters.append({"term": {"categoria": categoria}})
    for etiqueta in etiquetas or []:
        filters.append({"term": {"etiquetas": etiqueta}})

    response = client.search(
        index=INDEX_NAME,
        size=size,
        from_=offset,
        query={
            "bool": {
                "filter": filters,
                "should": [

                    # 1. Coincidencia de frase exacta en título
                    {
                        "match_phrase": {
                            "title": {
                                "query": query,
                                "boost": 5
                            }
                        }
                    },

                    # 2. Coincidencia de frase en ingredientes
                    {
                        "match_phrase": {
                            "ingredients": {
                                "query": query,
                                "boost": 3
                            }
                        }
                    },

                    # 3. Búsqueda general en varios campos, con raíces en gallego
                    {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "title^3",
                                "ingredients^2",
                                "preparation"
                            ],
                            "type": "best_fields"
                        }
                    },

                    # 3b. Lo mismo con tolerancia a erratas, sobre palabras enteras
                    # (subcampos .std): la búsqueda difusa sobre raíces cortas
                    # confunde términos distintos
                    {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "title.std^3",
                                "ingredients.std^2",
                                "preparation.std"
                            ],
                            "type": "best_fields",
                            "fuzziness": "AUTO"
                        }
                    },

                    # 4. Coincidencia de frase en preparación
                    {
                        "match_phrase": {
                            "preparation": {
                                "query": query,
                                "boost": 1.5
                            }
                        }
                    }
                ],
                "minimum_should_match": 1
            }
        }
    )

    return response["hits"]["hits"], response["hits"]["total"]["value"]


def show_results(results):
    if not results:
        print("\nNo se encontraron recetas.")
        return

    print(f"\nSe encontraron {len(results)} recetas:\n")

    for i, hit in enumerate(results, start=1):
        recipe = hit["_source"]

        print("=" * 60)
        print(f"Resultado {i}")
        print(f"Puntuación: {hit['_score']:.2f}")
        print(f"Título: {recipe.get('title', 'Sin título')}")

        ingredients = recipe.get("ingredients", [])
        print("\nIngredientes:")

        if isinstance(ingredients, list):
            for ingredient in ingredients:
                print(f"  - {ingredient}")
        else:
            print(f"  {ingredients}")

        preparation = recipe.get("preparation", "")
        print("\nPreparación:")
        print(preparation[:500] + ("..." if len(preparation) > 500 else ""))

        print(f"\nFuente: {recipe.get('source', 'Desconocida')}")
        print(f"URL: {recipe.get('url', 'Sin URL')}")
        print()


def main():
    if not client.ping():
        print("No se pudo conectar con Elasticsearch.")
        return

    print("======================================")
    print("     BUSCADOR DE RECETAS GALLEGAS")
    print("======================================")
    print("Escribe una búsqueda o 'salir' para terminar.")

    while True:
        query = input("\n¿Qué receta estás buscando? ").strip()

        if query.lower() in ("salir", "exit", "quit"):
            print("¡Hasta luego!")
            break

        if not query:
            print("Introduce algún término para buscar.")
            continue

        try:
            results = search_recipes(query)
            show_results(results)

        except Exception as error:
            print(f"Error durante la búsqueda: {error}")


if __name__ == "__main__":
    main()
