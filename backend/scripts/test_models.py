"""
Test script: verify all LLM providers and embedding model work.

Run from backend/:
    source .venv/bin/activate
    python scripts/test_models.py

Tests:
  1. Google gemini-embedding-001 (direct API)
  2. OpenRouter → anthropic/claude-haiku-4-5-20251001  (chat)
  3. OpenRouter → google/gemini-2.5-pro                (property search)
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

# ── Load .env ────────────────────────────────────────────────────────────────
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
OPENROUTER_KEY   = os.getenv("OPENROUTER_API_KEY", "")
CHAT_MODEL       = os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-4.5")
PROPERTY_MODEL   = os.getenv("PROPERTY_LLM_MODEL", "google/gemini-2.5-pro")

OPENROUTER_URL       = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"

OK  = "\033[92m✓\033[0m"
ERR = "\033[91m✗\033[0m"
INF = "\033[94m→\033[0m"


async def test_google_embeddings(client: httpx.AsyncClient) -> bool:
    print(f"\n{INF} [1/3] OpenRouter — google/gemini-embedding-001")
    if not OPENROUTER_KEY:
        print(f"  {ERR} OPENROUTER_API_KEY not set")
        return False

    payload = {"model": "google/gemini-embedding-001", "input": "departamento 2 dormitorios Las Condes"}
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "HTTP-Referer": "https://captame.cl",
        "X-Title": "Captame Inmo",
    }
    try:
        r = await client.post(OPENROUTER_EMBED_URL, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            values = r.json()["data"][0]["embedding"]
            print(f"  {OK} Embedding OK — dim={len(values)}")
            return True
        else:
            data = r.json()
            print(f"  {ERR} HTTP {r.status_code}: {data.get('error', {}).get('message', r.text[:200])}")
            return False
    except Exception as e:
        print(f"  {ERR} Exception: {e}")
        return False


async def test_openrouter(client: httpx.AsyncClient, model: str, label: str, prompt: str) -> bool:
    print(f"\n{INF} {label} — {model}")
    if not OPENROUTER_KEY:
        print(f"  {ERR} OPENROUTER_API_KEY not set")
        return False

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 80,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "HTTP-Referer": "https://captame.cl",
        "X-Title": "Captame Inmo",
        "Content-Type": "application/json",
    }
    try:
        r = await client.post(OPENROUTER_URL, json=payload, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            text = data["choices"][0]["message"]["content"].strip()
            usage = data.get("usage", {})
            print(f"  {OK} Response OK")
            print(f"     Tokens: prompt={usage.get('prompt_tokens','?')} completion={usage.get('completion_tokens','?')}")
            print(f"     Reply:  {text[:120]}")
            return True
        else:
            data = r.json()
            err = data.get("error", {})
            print(f"  {ERR} HTTP {r.status_code}: {err.get('message', r.text[:300])}")
            return False
    except Exception as e:
        print(f"  {ERR} Exception: {e}")
        return False


async def main():
    print("=" * 60)
    print("  Model connectivity test")
    print("=" * 60)
    print(f"  GEMINI_API_KEY   : {'set (' + GEMINI_API_KEY[:8] + '...)' if GEMINI_API_KEY else 'NOT SET'}")
    print(f"  OPENROUTER_KEY   : {'set (' + OPENROUTER_KEY[:12] + '...)' if OPENROUTER_KEY else 'NOT SET'}")
    print(f"  Chat model       : {CHAT_MODEL}")
    print(f"  Property model   : {PROPERTY_MODEL}")

    results = []
    async with httpx.AsyncClient() as client:
        results.append(await test_google_embeddings(client))

        results.append(await test_openrouter(
            client,
            model=CHAT_MODEL,
            label="[2/3] OpenRouter — Chat (Haiku 4.5)",
            prompt="Responde en una sola frase: ¿Cuántos dormitorios tiene un departamento estudio?",
        ))

        results.append(await test_openrouter(
            client,
            model=PROPERTY_MODEL,
            label="[3/3] OpenRouter — Property search (Gemini 2.5 Pro)",
            prompt=(
                "Extrae en JSON los parámetros de búsqueda: "
                "'busco depa de 2 dormitorios en Ñuñoa hasta 3000 UF'. "
                "Campos: bedrooms, commune, max_price_uf."
            ),
        ))

    print("\n" + "=" * 60)
    passed = sum(results)
    total  = len(results)
    status = OK if passed == total else ERR
    print(f"  {status} {passed}/{total} tests passed")
    print("=" * 60)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
