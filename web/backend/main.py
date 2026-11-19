from pathlib import Path
from typing import Literal

from elasticsearch import ConnectionError as ESConnectionError
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from search.search import INDEX_NAME, client, search_page

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
SNIPPET_LENGTH = 300

app = FastAPI(title="Buscador de recetas gallegas")


class Recipe(BaseModel):
    recipe_id: str | None = None
    title: str
    ingredients: list[str]
    snippet: str
    url: str
    source: str
    score: float
    categoria: str | None = None
    etiquetas: list[str] = []
    dificultade: str | None = None
    puntos_dificultade: int | None = None
    motivo_dificultade: str | None = None
    n_ingredientes: int | None = None
    minutos: int | None = None
    tecnicas: list[str] = []


class SearchResponse(BaseModel):
    query: str
    total: int  # coincidencias en el índice, no solo las de esta página
    offset: int
    results: list[Recipe]


def to_recipe(hit):
    recipe = hit["_source"]
    ingredients = recipe.get("ingredients", [])
    if not isinstance(ingredients, list):
        ingredients = [ingredients]

    preparation = recipe.get("preparation", "")
    snippet = preparation[:SNIPPET_LENGTH]
    if len(preparation) > SNIPPET_LENGTH:
        snippet += "..."

    return Recipe(
        recipe_id=recipe.get("recipe_id"),
        title=recipe.get("title", "Sin título"),
        ingredients=ingredients,
        snippet=snippet,
        url=recipe.get("url", ""),
        source=recipe.get("source", "Desconocida"),
        score=hit["_score"] or 0.0,
        categoria=recipe.get("categoria"),
        etiquetas=recipe.get("etiquetas") or [],
        dificultade=recipe.get("dificultade"),
        puntos_dificultade=recipe.get("puntos_dificultade"),
        motivo_dificultade=recipe.get("motivo_dificultade"),
        n_ingredientes=recipe.get("n_ingredientes"),
        minutos=recipe.get("minutos"),
        tecnicas=recipe.get("tecnicas") or [],
    )


@app.get("/api/health")
def health():
    return {"elasticsearch": client.ping()}


# Indica si hay recetas enriquecidas por el LLM, para mostrar u ocultar sus filtros
@app.get("/api/filtros")
def filtros():
    try:
        count = client.count(
            index=INDEX_NAME,
            query={
                "bool": {
                    "should": [
                        {"exists": {"field": "categoria"}},
                        {"exists": {"field": "etiquetas"}},
                    ]
                }
            },
        )["count"]
    except ESConnectionError:
        raise HTTPException(status_code=503, detail="No se pudo conectar con Elasticsearch.")
    return {"llm": count > 0}


@app.get("/api/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, description="Texto de búsqueda"),
    size: int = Query(10, ge=1, le=50),
    # Elasticsearch no pagina más allá de 10 000 resultados por defecto
    offset: int = Query(0, ge=0, le=9950, description="Resultados que se saltan (paginación)"),
    source: str | None = Query(None, description="Filtra por fuente"),
    categoria: str | None = Query(None, description="Filtra por categoría (generada por el LLM)"),
    etiqueta: list[str] = Query([], description="Filtra por etiquetas (generadas por el LLM)"),
    dificultade: Literal["facil", "media", "dificil"] | None = Query(
        None, description="Filtra por dificultad (calculada por reglas, sin LLM)"
    ),
):
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="La búsqueda no puede estar vacía.")

    try:
        hits, total = search_page(
            query,
            size=size,
            offset=offset,
            source=source,
            categoria=categoria,
            etiquetas=etiqueta,
            dificultade=dificultade,
        )
    except ESConnectionError:
        raise HTTPException(status_code=503, detail="No se pudo conectar con Elasticsearch.")

    results = [to_recipe(hit) for hit in hits]
    return SearchResponse(query=query, total=total, offset=offset, results=results)


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
