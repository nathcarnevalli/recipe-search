# Evaluación de la búsqueda

Juicios binarios en `search/qrels.json` (10 consultas). Métricas: P@5, R@10 y MRR (sobre los 10 primeros).

- **Inicial**: `match` solo sobre `preparation`.
- **Final**: `search_recipes` (frases en título e ingredientes, `multi_match` con pesos y `fuzziness`).

## Media

| Estrategia | P@5 | R@10 | MRR |
|---|---|---|---|
| Inicial | 0.320 | 0.775 | 0.648 |
| Final | 0.500 | 1.000 | 1.000 |

P@5 tiene un techo bajo en las consultas con pocas recetas relevantes (con 1 relevante, el máximo es 0.2); por eso se dan también R@10 y MRR.

## Por consulta

| Consulta | Relevantes | Inicial P@5 / R@10 / RR | Final P@5 / R@10 / RR |
|---|---|---|---|
| tarta de santiago | 1 | 0.20 / 1.00 / 0.50 | 0.20 / 1.00 / 1.00 |
| filloas | 1 | 0.20 / 1.00 / 1.00 | 0.20 / 1.00 / 1.00 |
| empanada | 4 | 0.40 / 0.50 / 1.00 | 0.80 / 1.00 / 1.00 |
| castañas | 5 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| caldo galego | 4 | 0.00 / 0.00 / 0.00 | 0.80 / 1.00 / 1.00 |
| lacón con grelos | 1 | 0.20 / 1.00 / 1.00 | 0.20 / 1.00 / 1.00 |
| bica | 2 | 0.40 / 1.00 / 0.50 | 0.40 / 1.00 / 1.00 |
| cocido | 2 | 0.00 / 0.50 / 0.14 | 0.40 / 1.00 / 1.00 |
| augardente | 4 | 0.60 / 0.75 / 1.00 | 0.80 / 1.00 / 1.00 |
| torta de milo | 1 | 0.20 / 1.00 / 0.33 | 0.20 / 1.00 / 1.00 |
