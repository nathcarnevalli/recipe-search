import os
import json
from collections import Counter

from elasticsearch import Elasticsearch

from dificultade import calcular as calcular_dificultade

es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
client = Elasticsearch(es_url)

#client = Elasticsearch(os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"))
print("--> A ligar ao Elasticsearch em:", es_url)
index_name = "receitas_galegas"

# Leer las recetas de los archivos JSON: una lista de recetas por fuente
recipes = []

for path in ["data/kukinhas.json", "data/receitario.json"]:
    with open(path, encoding="utf-8") as f:
        recipes.extend(json.load(f))

if not recipes:
    raise SystemExit("Los archivos JSON no contienen recetas.")

# Añadir la categoría y las etiquetas del LLM si se ha ejecutado llm/enrich.py
enriched_path = "data/enriquecido.json"
enriched = {}
if os.path.exists(enriched_path):
    with open(enriched_path, encoding="utf-8") as f:
        enriched = json.load(f)
else:
    print(f"--> Aviso: no existe {enriched_path}; los filtros de categoría y etiquetas no darán resultados.")

for recipe in recipes:
    extra = enriched.get(recipe["recipe_id"], {})
    recipe["categoria"] = extra.get("categoria")
    recipe["etiquetas"] = extra.get("etiquetas", [])
    # Dificultad por reglas (indexer/dificultade.py): no gasta tokens
    recipe.update(calcular_dificultade(recipe))

# Comprobar que las recetas tienen los campos necesarios
required_fields = [
    "recipe_id",
    "title",
    "ingredients",
    "preparation",
    "url",
    "source",
]

for i, recipe in enumerate(recipes, start=1):
    missing = [field for field in required_fields if field not in recipe]
    if missing:
        raise SystemExit(
            f"Receta {i} incompleta. Faltan los campos: {missing}"
        )

# Crear el índice desde cero para esta prueba
if client.indices.exists(index=index_name):
    client.indices.delete(index=index_name)

STD = {"std": {"type": "text", "analyzer": "standard"}}

client.indices.create(
    index=index_name,
    mappings={
        "properties": {
            "recipe_id": {"type": "keyword"},
            # Analizador gallego: minúsculas, stopwords y stemming ("tortiñas" y
            # "tortiña" comparten raíz). El subcampo .std guarda las palabras enteras
            # para la búsqueda difusa: sobre raíces cortas confunde términos
            # ("milo" -> "mil" quedaría a una letra de "mel")
            "title": {"type": "text", "analyzer": "galician", "fields": STD},
            "ingredients": {"type": "text", "analyzer": "galician", "fields": STD},
            "preparation": {"type": "text", "analyzer": "galician", "fields": STD},
            "url": {"type": "keyword"},
            "source": {"type": "keyword"},
            "categoria": {"type": "keyword"},
            "etiquetas": {"type": "keyword"},
            "dificultade": {"type": "keyword"},
            "puntos_dificultade": {"type": "integer"},
            "motivo_dificultade": {"type": "keyword", "index": False},
            "n_ingredientes": {"type": "integer"},
            "minutos": {"type": "integer"},
            "tecnicas": {"type": "keyword"},
        }
    },
)

# Indexar las recetas
for recipe in recipes:
    client.index(
        index=index_name,
        id=recipe["recipe_id"],
        document=recipe,
    )

client.indices.refresh(index=index_name)

print("Recetas leídas:", len(recipes))
print("Documentos indexados:", client.count(index=index_name)["count"])
print("Recetas con categoría del LLM:", sum(1 for r in recipes if r["categoria"]))
print("Dificultad (por reglas):", dict(Counter(r["dificultade"] for r in recipes)))
