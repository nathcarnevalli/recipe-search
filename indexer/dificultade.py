"""Dificultad de una receta calculada con reglas, sin LLM (0 tokens).

Puntos (0-7):
  - ingredientes:  <=4 -> 0 | 5-8 -> 1 | 9-12 -> 2 | >12 -> 3
  - tiempo citado en la preparación (suma de "N minutos"/"N horas"):
                   <30 min -> 0 | 30-90 min -> 1 | >90 min -> 2
  - técnicas laboriosas (reposo, amasado, levadura...): +1 cada una, máximo 2

Nivel: 0-1 fácil, 2-3 media, 4 o más difícil.
"""

import re

TIEMPO = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:(?:-|a|ou)\s*\d+(?:[.,]\d+)?\s*)?(minutos?|min\b|horas?|h\b)"
)

# Patrones en gallego sobre el texto de la preparación
TECNICAS = {
    "reposo": r"repous|toda a noite|dun día para outro",
    "amasado": r"amas",
    "levadura": r"lévedo|levedar|levedura",
    "punto de nieve": r"punto de neve",
    "baño maría": r"baño[ -]maría",
    "caramelo": r"caramel",
    "fritura": r"fritir|fritid|fritar",
}


def contar_ingredientes(ingredients):
    # Las líneas que acaban en ":" son encabezados ("Ingredientes para 4 persoas:")
    if not isinstance(ingredients, list):
        ingredients = [ingredients] if ingredients else []
    return sum(1 for i in ingredients if i and i.strip() and not i.strip().endswith(":"))


def minutos_citados(texto):
    total = 0.0
    for numero, unidad in TIEMPO.findall(texto):
        valor = float(numero.replace(",", "."))
        total += valor * 60 if unidad.startswith("h") else valor
    return int(total)


def formato_tiempo(minutos):
    if minutos >= 60:
        horas = round(minutos / 60, 1)
        return f"~{horas:g} h"
    return f"~{minutos} min"


def calcular(recipe):
    texto = (recipe.get("preparation") or "").lower()
    n = contar_ingredientes(recipe.get("ingredients"))
    minutos = minutos_citados(texto)
    tecnicas = [nombre for nombre, patron in TECNICAS.items() if re.search(patron, texto)]

    puntos = 0 if n <= 4 else 1 if n <= 8 else 2 if n <= 12 else 3
    puntos += 0 if minutos < 30 else 1 if minutos <= 90 else 2
    puntos += min(len(tecnicas), 2)

    nivel = "facil" if puntos <= 1 else "media" if puntos <= 3 else "dificil"

    motivo = [f"{n} ingredientes"]
    if minutos:
        motivo.append(formato_tiempo(minutos))
    if tecnicas:
        motivo.append(", ".join(tecnicas))

    return {
        "dificultade": nivel,
        "puntos_dificultade": puntos,
        "motivo_dificultade": " · ".join(motivo),
        # Datos sueltos para el panel de la web
        "n_ingredientes": n,
        "minutos": minutos,
        "tecnicas": tecnicas,
    }
