const form = document.getElementById("search-form");
const queryInput = document.getElementById("query");
const sourceSelect = document.getElementById("source");
const categoriaSelect = document.getElementById("categoria");
const etiquetasBox = document.getElementById("etiquetas");

const label = (value) => value.replaceAll("_", " ");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");

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

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const params = new URLSearchParams({ q: queryInput.value.trim() });
  if (sourceSelect.value) params.set("source", sourceSelect.value);
  if (categoriaSelect.value) params.set("categoria", categoriaSelect.value);
  etiquetasBox.querySelectorAll("input:checked").forEach((box) => params.append("etiqueta", box.value));

  resultsEl.replaceChildren();
  setStatus("Buscando...");

  try {
    const response = await fetch(`/api/search?${params}`);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === "string" ? body.detail : "Error en la búsqueda.");
    }

    const data = await response.json();
    if (data.total === 0) {
      setStatus("No se encontraron recetas.");
      return;
    }

    setStatus(`${data.total} recetas encontradas.`);
    data.results.forEach((recipe) => resultsEl.appendChild(renderRecipe(recipe)));
  } catch (error) {
    setStatus(error.message, true);
  }
});
