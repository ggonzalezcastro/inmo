"""
Benchmark Gemini models — text latency + tool calling support.
Usage: python benchmark_models.py
"""
import asyncio
import time
from google import genai
from google.genai import types

API_KEY = "AIzaSyBAMfykdVFsVpopPZi0iCiV43jT6hFds9M"

MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.1-pro-preview",
]

TEXT_PROMPT = 'Di solo "hola" en español.'
TOOL_PROMPT = "Busca departamentos en Providencia de hasta 3000 UF."
RUNS = 2

TOOL = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="search_properties",
        description="Busca propiedades disponibles según criterios",
        parameters={
            "type": "object",
            "properties": {
                "commune": {"type": "string", "description": "Comuna"},
                "max_uf":  {"type": "number",  "description": "Precio máximo UF"},
            },
            "required": ["commune"],
        },
    )
])


async def test_text(client, model):
    latencies, errors = [], []
    for i in range(RUNS):
        t0 = time.monotonic()
        try:
            r = await client.aio.models.generate_content(model=model, contents=TEXT_PROMPT)
            latencies.append((time.monotonic() - t0) * 1000)
            _ = r.text
        except Exception as e:
            errors.append(str(e)[:60])
    ok = len(latencies)
    return {
        "ok": ok, "fail": RUNS - ok,
        "avg_ms": round(sum(latencies) / ok) if ok else None,
        "min_ms": round(min(latencies)) if ok else None,
        "errors": errors,
    }


async def test_tools(client, model):
    t0 = time.monotonic()
    try:
        config = types.GenerateContentConfig(
            tools=[TOOL],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            ),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        r = await client.aio.models.generate_content(
            model=model, contents=TOOL_PROMPT, config=config
        )
        ms = round((time.monotonic() - t0) * 1000)

        # Extract tool calls
        calls = []
        if r.candidates:
            for part in r.candidates[0].content.parts:
                fc = getattr(part, "function_call", None)
                if fc and fc.name:
                    calls.append(fc.name)

        return {"ok": True, "called": bool(calls), "tools": calls, "ms": ms, "error": None}
    except Exception as e:
        ms = round((time.monotonic() - t0) * 1000)
        return {"ok": False, "called": False, "tools": [], "ms": ms, "error": str(e)[:80]}


async def main():
    client = genai.Client(api_key=API_KEY)

    # ── Text benchmark ──────────────────────────────────────────────────────
    print(f"\n── Text ({RUNS} runs each) ──────────────────────────────────────────")
    text_results = []
    for model in MODELS:
        print(f"  {model}...", end=" ", flush=True)
        r = await test_text(client, model)
        r["model"] = model
        if r["ok"]:
            print(f"avg={r['avg_ms']}ms min={r['min_ms']}ms")
        else:
            print(f"FAILED ({r['errors'][0] if r['errors'] else '?'})")
        text_results.append(r)

    available = [r for r in text_results if r["ok"]]
    available.sort(key=lambda r: r["avg_ms"])

    print(f"\n{'MODEL':<38} {'OK':>3} {'AVG ms':>7} {'MIN ms':>7}")
    print("─" * 55)
    for r in available:
        print(f"{r['model']:<38} {r['ok']:>3} {r['avg_ms']:>7} {r['min_ms']:>7}")
    for r in text_results:
        if not r["ok"]:
            print(f"{r['model']:<38}  ✗  {r['errors'][0][:30] if r['errors'] else ''}")

    # ── Tool calling test ───────────────────────────────────────────────────
    print(f"\n── Tool calling (mode=ANY, 1 run each) ─────────────────────────────")
    print(f"{'MODEL':<38} {'CALLED':>7} {'MS':>6}  TOOLS / ERROR")
    print("─" * 70)

    tool_winners = []
    for r in text_results:
        model = r["model"]
        if not r["ok"]:
            print(f"{model:<38} {'skip':>7}  (text failed)")
            continue
        tr = await test_tools(client, model)
        called = "✓ yes" if tr["called"] else ("✗ no" if tr["ok"] else "✗ ERR")
        detail = ", ".join(tr["tools"]) if tr["tools"] else (tr["error"] or "no tool call in response")
        print(f"{model:<38} {called:>7} {tr['ms']:>6}ms  {detail}")
        if tr["called"]:
            tool_winners.append((model, tr["ms"]))

    print("─" * 70)
    if tool_winners:
        tool_winners.sort(key=lambda x: x[1])
        print(f"\n🏆 Best for tool calling: {tool_winners[0][0]} ({tool_winners[0][1]}ms)")
        print(f"   All that support tools: {', '.join(m for m,_ in tool_winners)}\n")
    else:
        print("\n⚠️  Ningún modelo llamó la herramienta con mode=ANY\n")
        print("   Esto puede significar:")
        print("   • El modelo no soporta function calling")
        print("   • La API key no tiene acceso al feature")
        print("   • Problema con el formato del tool definition\n")


asyncio.run(main())
