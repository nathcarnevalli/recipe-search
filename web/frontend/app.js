const form = document.getElementById("search-form");
const queryInput = document.getElementById("query");
const sourceSelect = document.getElementById("source");
const categoriaSelect = document.getElementById("categoria");
const etiquetasBox = document.getElementById("etiquetas");
const dificultadeSelect = document.getElementById("dificultade");
const dicasEl = document.getElementById("dicas");

const NIVEL = { facil: "Fácil", media: "Media", dificil: "Difícil" };

const label = (value) => value.replaceAll("_", " ");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");

// Los filtros del LLM empiezan ocultos y solo se muestran si hay recetas enriquecidas
async function loadFilters() {
  try {
    const response = await fetch("/api/filtros");
    if (!response.ok) return;
    const { llm } = await response.json();
    document.querySelectorAll(".llm-filter").forEach((el) => { el.hidden = !llm; });
  } catch {
    // Sin respuesta: se dejan ocultos y la búsqueda sigue funcionando
  }
}

loadFilters();

// Resaltar los desplegables que tienen un filtro elegido
document.querySelectorAll(".filter-row select").forEach((select) => {
  const update = () => select.classList.toggle("activo", select.value !== "");
  select.addEventListener("change", update);
  update();
});

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function renderRecipe(recipe) {
  const card = document.createElement("li");
  card.className = "card";

  const title = document.createElement("h2");
  const link = document.createElement("a");
  link.href = recipe.url;
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = recipe.title;
  title.appendChild(link);

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `Fuente: ${recipe.source} · Puntuación: ${recipe.score.toFixed(2)}`;
  if (recipe.dificultade) {
    const nivel = document.createElement("span");
    nivel.className = `nivel nivel-${recipe.dificultade}`;
    nivel.textContent = NIVEL[recipe.dificultade];
    nivel.title = recipe.motivo_dificultade || "";
    meta.append(" · ", nivel);
  }

  const llm = document.createElement("div");
  llm.className = "llm-tags";
  if (recipe.categoria || recipe.etiquetas.length) {
    llm.title = "Generado por el LLM a partir del título y los ingredientes";
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = "LLM";
    llm.appendChild(badge);
    [recipe.categoria, ...recipe.etiquetas].filter(Boolean).forEach((value) => {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = label(value);
      llm.appendChild(tag);
    });
  }

  const ingredients = document.createElement("ul");
  recipe.ingredients.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    ingredients.appendChild(li);
  });

  const snippet = document.createElement("p");
  snippet.textContent = recipe.snippet;

  card.append(title, meta, llm, ingredients, snippet);
  return card;
}

// Panel de dificultad del primer resultado, con los datos ya indexados: no se llama al LLM
const shortTitle = (recipe) => recipe.title.split(" / ")[0];

function formatTime(minutos) {
  if (!minutos) return null;
  if (minutos >= 60) return `~${Math.round((minutos / 60) * 10) / 10} h`.replace(".", ",");
  return `~${minutos} min`;
}

function listJoin(items) {
  return items.length > 1 ? `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}` : items[0];
}

function explain(recipe) {
  const partes = [`lleva ${recipe.n_ingredientes} ingredientes`];
  const tiempo = formatTime(recipe.minutos);
  if (tiempo) partes.push(`unos ${tiempo.slice(1)} de preparación`);
  partes.push(recipe.tecnicas.length ? `requiere ${listJoin(recipe.tecnicas)}` : "no requiere técnicas especiales");
  return `Receta ${NIVEL[recipe.dificultade].toLowerCase()}: ${listJoin(partes)}.`;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function link(recipe) {
  const a = el("a", null, shortTitle(recipe));
  a.href = recipe.url;
  a.target = "_blank";
  a.rel = "noopener";
  return a;
}

function renderDicas(results) {
  dicasEl.replaceChildren();
  const top = results[0];
  dicasEl.hidden = !top || !top.dificultade;
  if (dicasEl.hidden) return;

  const eyebrow = el("p", "panel-eyebrow", "Dificultad estimada");
  eyebrow.title = "Calculada con reglas a partir de los ingredientes, los tiempos y las técnicas del texto de preparación";

  const titulo = el("p", "panel-titulo");
  titulo.appendChild(link(top));

  const medidor = el("span", `medidor ${top.dificultade}`);
  medidor.setAttribute("aria-hidden", "true");
  medidor.append(el("i"), el("i"), el("i"));
  const nivel = el("p", "panel-nivel");
  nivel.append(medidor, el("strong", null, NIVEL[top.dificultade]));

  const dato = (label, value) => {
    const span = el("span", null, label);
    span.prepend(el("strong", null, value));
    return span;
  };
  const datos = el("div", "panel-datos");
  datos.append(
    dato("ingredientes", String(top.n_ingredientes)),
    dato("tiempo indicado", formatTime(top.minutos) || "—"),
    dato("técnicas", top.tecnicas.length ? listJoin(top.tecnicas) : "ninguna"),
  );

  dicasEl.append(eyebrow, titulo, nivel, el("p", null, explain(top)), datos);

  // Alternativa más sencilla entre los demás resultados (sort es estable: a igual
  // dificultad gana la más relevante)
  const masFacil = results
    .slice(1)
    .filter((r) => r.puntos_dificultade !== null && r.puntos_dificultade < top.puntos_dificultade)
    .sort((a, b) => a.puntos_dificultade - b.puntos_dificultade)[0];
  if (masFacil) {
    const alt = el("p", "panel-alternativa", "¿Buscas algo más sencillo? ");
    alt.append(link(masFacil), ` — ${NIVEL[masFacil.dificultade]}, ${masFacil.motivo_dificultade}`);
    dicasEl.appendChild(alt);
  }
}

// Paginación: se piden 10 recetas cada vez y "Ver más" añade las siguientes
const PAGE_SIZE = 10;
const moreButton = document.getElementById("more");
let currentParams = null;
let loaded = 0;
let lastTotal = 0;
let searchId = 0; // descarta respuestas de una búsqueda anterior

async function fetchPage(params, offset) {
  const pageParams = new URLSearchParams(params);
  pageParams.set("size", PAGE_SIZE);
  pageParams.set("offset", offset);
  const response = await fetch(`/api/search?${pageParams}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "Error en la búsqueda.");
  }
  return response.json();
}

function updateMore(total) {
  lastTotal = total;
  const faltan = total - loaded;
  moreButton.hidden = faltan <= 0;
  moreButton.textContent = `Ver más recetas (${Math.min(PAGE_SIZE, faltan)} de ${faltan} restantes)`;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const params = new URLSearchParams({ q: queryInput.value.trim() });
  if (sourceSelect.value) params.set("source", sourceSelect.value);
  if (!categoriaSelect.hidden && categoriaSelect.value) params.set("categoria", categoriaSelect.value);
  if (!etiquetasBox.hidden) etiquetasBox.querySelectorAll("input:checked").forEach((box) => params.append("etiqueta", box.value));
  if (dificultadeSelect.value) params.set("dificultade", dificultadeSelect.value);

  const id = ++searchId;
  currentParams = params;
  loaded = 0;
  resultsEl.replaceChildren();
  dicasEl.hidden = true;
  moreButton.hidden = true;
  setStatus("Buscando...");

  try {
    const data = await fetchPage(params, 0);
    if (id !== searchId) return;
    if (data.total === 0) {
      setStatus("No se encontraron recetas.");
      return;
    }

    setStatus(data.total === 1 ? "1 receta encontrada." : `${data.total} recetas encontradas.`);
    renderDicas(data.results);
    data.results.forEach((recipe) => resultsEl.appendChild(renderRecipe(recipe)));
    loaded = data.results.length;
    updateMore(data.total);
  } catch (error) {
    if (id === searchId) setStatus(error.message, true);
  }
});

moreButton.addEventListener("click", async () => {
  const id = searchId;
  moreButton.disabled = true;
  moreButton.textContent = "Cargando...";
  try {
    const data = await fetchPage(currentParams, loaded);
    if (id !== searchId) return;
    data.results.forEach((recipe) => resultsEl.appendChild(renderRecipe(recipe)));
    loaded += data.results.length;
    // Si el índice devuelve menos de lo esperado, no seguir ofreciendo más
    updateMore(data.results.length ? data.total : loaded);
  } catch (error) {
    if (id === searchId) {
      setStatus(error.message, true);
      updateMore(lastTotal);
    }
  } finally {
    moreButton.disabled = false;
  }
});
