# Buscador de Recetas Gallegas

Proyecto de la asignatura **Recuperación de Información y Web Semántica** (Máster Universitario en Ingeniería Informática, Universidade da Coruña).

Buscador web sobre recetas tradicionales de Galicia: crawling de dos fuentes, indexación con Elasticsearch e integración de un LLM para respuestas enriquecidas.

---

## Dominio

Recetas tradicionales gallegas, escritas en gallego. Hoy están repartidas entre blogs y sitios pequeños; el buscador permite encontrarlas en un solo lugar por nombre (tarta de Santiago) o por ingrediente (castañas).

**Fuentes de datos:**

| Fuente | Tipo | Semilla | Recetas |
|--------|------|---------|---------|
| [kukinhas.com](https://kukinhas.com) | Blog de una autora, textos largos | https://kukinhas.com/receitas-z-recipes/ | 201 |
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

Todos los comandos se ejecutan desde la **raíz del repositorio**.

### Requisitos y versiones

Solo hay que instalar **Docker**; Python, Elasticsearch y las dependencias van dentro de los contenedores.

| Componente | Versión |
|---|---|
| Docker Engine | 24 o superior (probado con 29.9.3) |
| Docker Compose | 2.24 o superior (probado con 5.7.0) |
| Python (imagen `python:3.11-slim`) | 3.11 |
| Elasticsearch (imagen oficial) | 8.19.3 |
| Dependencias de Python | fijadas en [`requirements.txt`](requirements.txt) (Scrapy 2.19.0, elasticsearch 8.19.3, FastAPI 0.162.0, Uvicorn 0.54.0, openai 3.49.0) |

### Pasos

**1. Obtener el código e instalar las dependencias** (construye la imagen con `requirements.txt`):

```bash
git clone https://github.com/nathcarnevalli/recipe-search.git
cd recipe-search
docker compose build
```

**2. Configurar** (opcional; el buscador funciona sin `.env`):

```bash
cp .env.example .env    # y editar los valores (ver «Configuración»)
```

**3. Obtener los datos.** En el repositorio solo va una muestra de 65 recetas en `data/muestra/`. Para tener las 295 recetas completas hay que rastrear las dos fuentes (unos 7 minutos, por el retardo entre peticiones):

```bash
docker compose up -d elasticsearch
docker compose run --rm indexer python main.py    # rastrea, guarda data/*.json e indexa
```

Sin este paso, el sistema indexa la muestra.

**4. Indexar.** El paso 3 ya indexa. Para volver a indexar los datos que hay en `data/` (o la muestra), sin rastrear:

```bash
docker compose run --rm indexer python main.py --sin-crawl
```

**5. Arrancar la aplicación:**

```bash
docker compose up -d
```

Abre http://localhost:8000. `docker compose up` arranca tres servicios definidos en [`compose.yaml`](compose.yaml):

| Servicio | Qué hace |
|---|---|
| `elasticsearch` | Elasticsearch 8.19.3, un nodo, sin seguridad, solo en `localhost:9200`. Los datos se guardan en un volumen. |
| `indexer` | Indexa las recetas de `data/` (o la muestra) y termina. |
| `web` | Backend FastAPI + interfaz en `localhost:8000`. Arranca cuando la indexación ha terminado. |

```bash
docker compose stop       # parar
docker compose logs web   # ver mensajes
```

### Configuración

Todo se cambia con variables de entorno en `.env`, sin tocar el código:

| Variable | Por defecto | Para qué |
|---|---|---|
| `INDEX_NAME` | `receitas_galegas` | Nombre del índice de Elasticsearch |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | Host de Elasticsearch al ejecutar los scripts fuera de Docker (dentro de Docker Compose es `http://elasticsearch:9200`) |
| `IRLAB_API_KEY` | (ninguno) | Token del servidor de LLM de la asignatura |
| `IRLAB_BASE_URL` | `https://inference.irlab.org/v1` | Dirección del servidor de LLM |
| `IRLAB_POLL_SECONDS` | `15` | Cada cuántos segundos se consulta el estado de un lote |

El puerto de la web (`8000`) y el de Elasticsearch (`9200`) se cambian en [`compose.yaml`](compose.yaml).

### Token del LLM

Solo hace falta para clasificar recetas con el LLM; el buscador funciona sin él.

1. Entra en https://inference.irlab.org/portal/ con la cuenta de la UDC y genera un token.
2. Ponlo en `.env` como `IRLAB_API_KEY`.

`.env` está en `.gitignore` y `.dockerignore`: el token **nunca** se sube al repositorio ni entra en la imagen de Docker. Generar un token nuevo en el portal invalida el anterior, así que hay que actualizar `.env` cada vez.

Comprobar la conexión (no gasta tokens):

```bash
docker compose run --rm indexer python -m llm.irlab_client
```

La clasificación ya hecha está en `data/enriquecido.json`, así que no hace falta volver a ejecutar el LLM. El indexador añade a cada receta los campos `categoria` y `etiquetas`.

La web permite filtrar por fuente, dificultad, categoría y etiquetas; la dificultad (fácil, media o difícil) se calcula sin LLM en [`indexer/dificultade.py`](indexer/dificultade.py) a partir del número de ingredientes, los tiempos y las técnicas de la preparación.

---

## Autores
- Nathalia
- Rafael
- Alex
