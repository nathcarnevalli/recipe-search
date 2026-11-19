# Buscador de Recetas Gallegas

Proyecto de la asignatura **Recuperación de Información y Web Semántica** (Máster Universitario en Ingeniería Informática, Universidade da Coruña).

Buscador web sobre recetas tradicionales de Galicia: crawling de dos fuentes, indexación con Elasticsearch e integración de un LLM para respuestas enriquecidas.

---

## Dominio

Recetas tradicionales gallegas, escritas en gallego. Hoy están repartidas entre blogs y sitios pequeños; el buscador permite encontrarlas en un solo lugar por nombre (tarta de Santiago) o por ingrediente (castañas).

**Fuentes de datos:**

| Fuente | Tipo | Semilla | Recetas |
|--------|------|---------|---------|
| [kukinhas.com](https://kukinhas.com) | Blog de una autora, textos largos | https://kukinhas.com/receitas-tradicionais/ | 201 |
| [receitario.gal](https://receitario.gal) | Wiki colaborativo, recetas breves | https://receitario.gal/category/receitas-tradicionais/ | 94 |

**Esquema común** (el mismo en las dos fuentes):

| Campo | Descripción |
|-------|-------------|
| `recipe_id` | Identificador estable: SHA-1 de la URL (16 caracteres) |
| `title` | Título de la receta |
| `ingredients` | Lista de ingredientes |
| `preparation` | Texto de la preparación |
| `url` | URL de la receta |
| `source` | Sitio de origen (`Kukinhas`, `Receitario`) |

---

## Arquitectura

```
Crawlers (Scrapy)
      │
      ▼
Indexación (Elasticsearch)
      │
      ▼
Backend (API de búsqueda + integración LLM)
      │
      ▼
Interfaz web
```

---

## Estructura del proyecto

```
recipes-search/
├── crawlers/          # Spiders de Scrapy para cada fuente
├── data/              # Datos crudos y procesados (excluidos del repo)
├── indexer/           # Scripts de mapping e indexación en Elasticsearch
├── search/            # Lógica de búsqueda y estrategia de ranking
├── llm/               # Integración con el servidor LLM (enriquecimiento por lotes)
├── web/               # Aplicación web
│   ├── backend/       # API con FastAPI (búsqueda y, más adelante, LLM)
│   └── frontend/      # Interfaz en HTML, CSS y JS
├── main.py            # Rastrea las fuentes e indexa las recetas
└── README.md
```

---

## Tecnologías

- **Python 3.x** — crawling, procesamiento e indexación
- **Scrapy** — rastreo y extracción de las fuentes
- **Elasticsearch** — índice y estrategia de búsqueda (BM25 + campos ponderados, analizador gallego)
- **LLM del servidor de la asignatura** — clasificación de las recetas (categoría y etiquetas) durante la indexación
- **FastAPI + Uvicorn** — backend de la aplicación web
- **HTML, CSS y JavaScript** — interfaz web (sin build), servida por el propio backend
- **Docker Compose** — Elasticsearch, indexación y web con un solo comando

---

## Instalación

Todos los comandos se ejecutan desde la **raíz del repositorio** (la carpeta `recipes-search`).

### Requisitos

Solo hace falta **Docker** (con Docker Compose). No hay que instalar Python, Elasticsearch ni dependencias en el sistema.

```bash
git clone https://github.com/nathcarnevalli/recipes-search.git
cd recipes-search
docker compose up -d --build
```

Abre http://localhost:8000.

`docker compose up` arranca tres servicios definidos en [`compose.yaml`](compose.yaml):

| Servicio | Qué hace |
|---|---|
| `elasticsearch` | Elasticsearch 8.19.3, un nodo, sin seguridad, solo en `localhost:9200`. Los datos se guardan en un volumen. |
| `indexer` | Indexa las recetas de `data/` y termina. |
| `web` | Backend FastAPI + interfaz en `localhost:8000`. Arranca cuando la indexación ha terminado. |

La primera vez tarda unos minutos (descarga de imágenes e instalación de dependencias). Después:

```bash
docker compose up -d      # arrancar
docker compose stop       # parar
docker compose logs web   # ver mensajes
```

Los datos ya vienen en `data/kukinhas.json` y `data/receitario.json`, así que **no hace falta rastrear**. Si se quiere rastrear de nuevo (unos 7 minutos por el retardo entre peticiones de receitario):

```bash
docker compose run --rm indexer python main.py
```

### Token del LLM

Solo hace falta para usar el LLM; el buscador funciona sin él.

1. Entra en https://inference.irlab.org/portal/ con la cuenta de la UDC y genera un token.
2. Copia la plantilla y pega el token:

```bash
cp .env.example .env
# edita .env:  IRLAB_API_KEY=sk-...
```

`.env` está en `.gitignore` y `.dockerignore`: el token **nunca** se sube al repositorio ni entra en la imagen de Docker. Generar un token nuevo en el portal invalida el anterior, así que hay que actualizar `.env` cada vez.

Comprobar la conexión (no gasta tokens):

```bash
docker compose run --rm indexer python -m llm.irlab_client
```

Si existe `data/enriquecido.json`, el indexador añade a cada receta los campos `categoria` y `etiquetas`. Si no existe, indexa las recetas sin ellos.

La web permite filtrar por fuente, dificultad, categoría y etiquetas; la dificultad (fácil, media o difícil) se calcula sin LLM en [`indexer/dificultade.py`](indexer/dificultade.py) a partir del número de ingredientes, los tiempos y las técnicas de la preparación.

---

## Autores
- Nathalia
- Rafael
- Alex
