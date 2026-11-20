"""Corrige la etiqueta «vexetariano» del LLM con reglas, sin gastar tokens.

El LLM solo ve el título y parte de los ingredientes, y a veces marca como
vegetariana una receta con carne o pescado (por ejemplo, una torta con atún).
Si algún ingrediente nombra carne, pescado o marisco, se quita la etiqueta.
"""

import re

# Términos en gallego (y alguno en castellano, que aparece en las fuentes)
CARNE_PEIXE = [
    # carne y embutidos
    "carne", "polo", "pito", "galiña", "pavo", "pato", "porco", "tenreira", "vaca", "boi",
    "cordeiro", "coello", "perdiz", "xamón", "jamón", "lacón", "chourizo", "chorizo",
    "touciño", "tocino", "bacon", "beicon", "panceta", "unto", "costela", "raxo", "zorza",
    "morcilla", "androlla", "botelo", "salchicha", "salchichas", "pepperoni", "sobrasada",
    "solombo", "solombiño", "peituga", "albóndega", "orella", "orellas", "morro", "cacheira",
    "fígado", "callos", "rixóns", "torresmos",
    # pescado y marisco
    "peixe", "pescado", "atún", "bonito", "bacallau", "bacalao", "pescada", "merluza",
    "salmón", "sardiña", "sardiñas", "xurelo", "anchoa", "anchoas", "boquerón", "rodaballo",
    "linguado", "rape", "polbo", "pulpo", "lura", "luras", "chocos", "choco", "calamar",
    "lagostino", "lagostinos", "gamba", "gambas", "camarón", "camaróns", "cigala", "nécora",
    "centola", "ameixa", "ameixas", "berberecho", "berberechos", "mexillón", "mexillóns",
    "vieira", "vieiras", "zamburiña", "zamburiñas", "navalla", "navallas", "marisco",
]

# Palabra completa, sin distinguir mayúsculas («atún» sí, «atuneira» no)
PATRON = re.compile(r"\b(" + "|".join(map(re.escape, CARNE_PEIXE)) + r")\b", re.IGNORECASE)

# Expresiones con esos términos que no son carne ni pescado (vistas en las fuentes)
NON_CARNE = re.compile(
    r"manteiga de vaca|leite de vaca|queixo de vaca|sen carne|seitán \(carne|carne de marmelo"
    r"|\w+ (?:vegan|vexetal)\w*",  # «chourizo vegano», «carne vexetal»
    re.IGNORECASE,
)


def leva_carne_ou_peixe(ingredients):
    if not isinstance(ingredients, list):
        ingredients = [ingredients] if ingredients else []
    texto = NON_CARNE.sub(" ", " ".join(i for i in ingredients if i))
    m = PATRON.search(texto)
    return m.group(1) if m else None


def corrixir_etiquetas(recipe):
    """Devuelve el término encontrado si se quitó «vexetariano», o None."""
    if "vexetariano" not in recipe.get("etiquetas", []):
        return None
    termo = leva_carne_ou_peixe(recipe.get("ingredients"))
    if termo:
        recipe["etiquetas"] = [e for e in recipe["etiquetas"] if e != "vexetariano"]
    return termo
