import getpass
import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

# .env en la raíz: token y configuración opcional del servidor
load_dotenv(find_dotenv())

# Servidor del IRLab (API compatible con OpenAI, solo por lotes)
BASE_URL = os.getenv("IRLAB_BASE_URL", "https://inference.irlab.org/v1")
POLL_SECONDS = int(os.getenv("IRLAB_POLL_SECONDS", "15"))
TERMINAL_STATES = {"completed", "failed", "cancelled", "expired"}

# Salidas en bruto por lote y registro de consumo de tokens
LLM_DIR = Path(__file__).resolve().parent
RUNS_DIR = LLM_DIR / "runs"
USAGE_LOG = LLM_DIR / "usage_log.jsonl"

_client = None


# El token se lee de .env (IRLAB_API_KEY); nunca va en el código
def get_client():
    global _client
    if _client is None:
        load_dotenv(find_dotenv())
        api_key = os.environ.get("IRLAB_API_KEY") or getpass.getpass("Token IRLab: ")
        _client = OpenAI(api_key=api_key.strip(), base_url=BASE_URL)
    return _client


# Una línea del JSONL de entrada; el modelo lo fija el servidor
def build_request(custom_id, system, user, max_tokens, temperature=0):
    return {
        "custom_id": str(custom_id),
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
    }


# Empareja las respuestas por custom_id (el orden no está garantizado)
def _parse_output(salida):
    resultados = {}
    for linea in salida.splitlines():
        if not linea.strip():
            continue
        r = json.loads(linea)
        cid = r["custom_id"]
        resp = r.get("response") or {}
        if r.get("error") or resp.get("status_code") != 200:
            resultados[cid] = {"ok": False, "error": r.get("error") or resp.get("body")}
            continue
        cuerpo = resp["body"]
        choice = cuerpo["choices"][0]
        resultados[cid] = {
            "ok": True,
            "content": (choice["message"]["content"] or "").strip(),
            "finish_reason": choice.get("finish_reason"),
            "truncated": choice.get("finish_reason") == "length",
            "usage": cuerpo.get("usage", {}),
        }
    return resultados


# Sube el JSONL, crea el lote y espera el resultado
def run_batch(peticiones, nombre="lote", verbose=True):
    ids = [p["custom_id"] for p in peticiones]
    if len(ids) != len(set(ids)):
        raise ValueError("Los custom_id tienen que ser únicos")

    client = get_client()
    carpeta = RUNS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}_{nombre}"
    carpeta.mkdir(parents=True, exist_ok=True)

    input_path = carpeta / "input.jsonl"
    with input_path.open("w", encoding="utf-8") as f:
        for p in peticiones:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    with input_path.open("rb") as f:
        subido = client.files.create(file=f, purpose="batch")
    batch = client.batches.create(
        input_file_id=subido.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    (carpeta / "batch_id.txt").write_text(batch.id, encoding="utf-8")
    if verbose:
        print(f"Batch {batch.id} enviado ({len(peticiones)} peticiones). Estado: {batch.status}")
        print(f"Si lo interrumpes, sigue en el servidor. Para retomarlo: --retomar {batch.id}")

    return _wait_and_collect(batch.id, carpeta, nombre, ids, verbose)


# Recoge un lote ya enviado sin volver a enviarlo
def resume_batch(batch_id, verbose=True):
    carpeta = next(
        (f.parent for f in RUNS_DIR.glob("*/batch_id.txt") if f.read_text().strip() == batch_id),
        None,
    )
    if carpeta is None:
        carpeta = RUNS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}_{batch_id}"
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "batch_id.txt").write_text(batch_id, encoding="utf-8")
    ids = None
    if (carpeta / "input.jsonl").exists():
        lineas = (carpeta / "input.jsonl").read_text(encoding="utf-8").splitlines()
        ids = [json.loads(l)["custom_id"] for l in lineas if l.strip()]
    return _wait_and_collect(batch_id, carpeta, f"retomar_{batch_id}", ids, verbose)


def _wait_and_collect(batch_id, carpeta, nombre, ids, verbose):
    client = get_client()
    batch = client.batches.retrieve(batch_id)
    while batch.status not in TERMINAL_STATES:
        if verbose:
            print(f"  estado: {batch.status}  {batch.request_counts}")
        time.sleep(POLL_SECONDS)
        batch = client.batches.retrieve(batch.id)

    if batch.status != "completed":
        raise RuntimeError(f"Batch {batch.id} terminó como '{batch.status}': {batch.errors}")

    # Guardar la salida en bruto antes de procesarla
    salida = client.files.content(batch.output_file_id).text
    (carpeta / "output.jsonl").write_text(salida, encoding="utf-8")
    if batch.error_file_id:
        errores = client.files.content(batch.error_file_id).text
        (carpeta / "errors.jsonl").write_text(errores, encoding="utf-8")

    resultados = _parse_output(salida)

    prompt_t = sum(r["usage"].get("prompt_tokens", 0) for r in resultados.values() if r["ok"])
    compl_t = sum(r["usage"].get("completion_tokens", 0) for r in resultados.values() if r["ok"])
    resumen = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "nombre": nombre,
        "batch_id": batch.id,
        "peticiones": len(ids) if ids else len(resultados),
        "ok": sum(r["ok"] for r in resultados.values()),
        "errores": sum(not r["ok"] for r in resultados.values()),
        "cortadas": sum(r.get("truncated", False) for r in resultados.values()),
        "sin_respuesta": len(set(ids or []) - set(resultados)),
        "prompt_tokens": prompt_t,
        "completion_tokens": compl_t,
        "total_tokens": prompt_t + compl_t,
        "carpeta": str(carpeta.relative_to(LLM_DIR.parent)),
    }
    with USAGE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(resumen, ensure_ascii=False) + "\n")
    if verbose:
        print(json.dumps(resumen, ensure_ascii=False, indent=2))

    return resultados


# Comprueba token y conexión sin gastar tokens
def check_connection():
    client = get_client()
    lotes = client.batches.list(limit=5)
    print("Conexión OK. Últimos lotes:")
    for b in lotes.data:
        print(f"  {b.id}  {b.status}  {b.request_counts}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "smoke":
        res = run_batch(
            [build_request("smoke", "Responde en una palabra.", "Di hola en gallego.", max_tokens=5)],
            nombre="smoke",
        )
        print(res)
    else:
        check_connection()
