"""Qué ficheros de recetas se indexan.

Los JSON completos del rastreo (data/kukinhas.json, data/receitario.json) no se
suben al repositorio: se generan con `python main.py`. Si no existen, se usa la
muestra pequeña de data/muestra/, que sí está en el repositorio.
"""

import os

COMPLETOS = ["data/kukinhas.json", "data/receitario.json"]
MUESTRA = ["data/muestra/kukinhas.json", "data/muestra/receitario.json"]


def ficheros_de_datos():
    if all(os.path.exists(p) for p in COMPLETOS):
        return COMPLETOS
    print("--> Aviso: no están los datos completos; se usa la muestra de data/muestra/. "
          "Para obtenerlos: python main.py")
    return MUESTRA
