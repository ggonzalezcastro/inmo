#!/usr/bin/env python3
"""
code_reviewer_agent.py

Pre-commit hook agent that reviews code changes and auto-generates documentation
for architectural changes using MiniMax M2.7 API.

Usage:
    python scripts/code_reviewer_agent.py "<changed_files_json>"
"""

import sys
import json
import subprocess
import os
import re
from pathlib import Path
from typing import Optional

# ── Config ──────────────────────────────────────────────────────────────────

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = "https://api.minimax.chat/v1"
MODEL = "MiniMax-Text-01"
WORKSPACE_ROOT = Path("/Users/gabrielgonzalez/Desktop/inmo 2")
DOCS_ROOT = WORKSPACE_ROOT / "docs"
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
FRONTEND_ROOT = WORKSPACE_ROOT / "frontend"


# ── MiniMax API Client ────────────────────────────────────────────────────────

def call_minimax(prompt: str, system: str = "") -> str:
    """Call MiniMax M2.7 via HTTP."""
    import urllib.request
    import urllib.error

    if not MINIMAX_API_KEY:
        return json.dumps({"error": "MINIMAX_API_KEY not set", "recommendation": "APPROVED"})

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 4096,
    }
    if system:
        payload["messages"].insert(0, {"role": "system", "content": system})

    req = urllib.request.Request(
        f"{MINIMAX_BASE_URL}/text/chatcompletion_v2",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {MINIMAX_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        return json.dumps({"error": str(e), "recommendation": "APPROVED"})
    except Exception as e:
        return json.dumps({"error": str(e), "recommendation": "APPROVED"})


# ── Git helpers ────────────────────────────────────────────────────────────────

def get_staged_diff() -> str:
    """Get full diff of staged changes."""
    result = subprocess.run(
        ["git", "diff", "--staged", "--no-color"],
        capture_output=True, text=True, cwd=WORKSPACE_ROOT
    )
    return result.stdout


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    result = subprocess.run(
        ["git", "diff", "--staged", "--name-only"],
        capture_output=True, text=True, cwd=WORKSPACE_ROOT
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def get_file_content(path: str) -> str:
    """Get full content of a file."""
    try:
        full_path = WORKSPACE_ROOT / path
        return full_path.read_text()
    except Exception:
        return ""


# ── Change classifiers ────────────────────────────────────────────────────────

def classify_change(path: str, diff: str) -> dict:
    """Classify a single file change."""

    # Models
    if re.match(r"backend/app/models/[a-z_]+\.py$", path):
        if "class " in diff and ("Column(" in diff or "relationship(" in diff):
            return {"type": "model", "subtype": "new_or_updated_model", "priority": "high"}
        return {"type": "model", "subtype": "other", "priority": "low"}

    # Routes / API endpoints
    if re.match(r"backend/app/(routes|features/[a-z_]+)/routes\.py$", path):
        if "@router." in diff or "async def " in diff:
            return {"type": "route", "subtype": "endpoint", "priority": "high"}
        return {"type": "route", "subtype": "other", "priority": "medium"}

    # Services
    if re.match(r"backend/app/services/[a-z_]+/[a-z_]+\.py$", path):
        if "class " in diff or "async def " in diff:
            return {"type": "service", "subtype": "new_service", "priority": "medium"}
        return {"type": "service", "subtype": "other", "priority": "low"}

    # Agents
    if "services/agents/" in path and path.endswith(".py"):
        if "class " in diff and "Agent" in diff:
            return {"type": "agent", "subtype": "agent_class", "priority": "high"}
        return {"type": "agent", "subtype": "other", "priority": "medium"}

    # Tasks (Celery)
    if "tasks/" in path and path.endswith(".py"):
        if "@shared_task" in diff or "def " in diff:
            return {"type": "task", "subtype": "celery_task", "priority": "medium"}
        return {"type": "task", "subtype": "other", "priority": "low"}

    # Frontend
    if path.startswith("frontend/src/"):
        if re.search(r"(route|page|view)", path):
            return {"type": "frontend", "subtype": "route_or_page", "priority": "medium"}
        return {"type": "frontend", "subtype": "component", "priority": "low"}

    # Config / ENV
    if path in (".env.example", "docker-compose.yml", "alembic.ini"):
        return {"type": "config", "subtype": "env_or_infra", "priority": "medium"}

    return {"type": "other", "subtype": "misc", "priority": "low"}


def is_architectural(change: dict) -> bool:
    """Returns True if change is architectural (needs doc review)."""
    return change.get("priority") in ("high", "medium")


# ── Doc generators ───────────────────────────────────────────────────────────

def generate_model_doc(model_content: str, filename: str) -> str:
    """Generate documentation for a SQLAlchemy model."""

    system = """Eres un asistente de documentación técnica. Analiza el modelo SQLAlchemy y genera documentación en Markdown para database-schema.md.

Tu respuesta DEBE ser JSON válido con este formato:
{
  "section_name": "Tabla: nombre_tabla",
  "content": "contenido markdown de la sección (no incluir el nombre de sección, solo las columnas, relaciones, notas...)",
  "existing_section_pattern": "regex que buscaría en database-schema.md para reemplazar esta sección (si existe), o null si es nuevo"
}

Reglas:
- El contenido debe incluir una tabla de columnas con: Columna, Tipo, Nullable, Default, Índice, FK
- Incluir relaciones (relationships)
- Incluir enum values si hay
- Si es un modelo existente que ya está en database-schema.md, el existing_section_pattern debe permitir reemplazarlo
- Usar sintaxis Markdown pura compatible con Obsidian
- No inventar información que no esté en el código
- Para cada columna, inferir: tipo, nullable, default, índices y FK basados en el código"""

    prompt = f"""Genera documentación para este modelo SQLAlchemy:

Filename: {filename}
Content:
{model_content}

Responde SOLO con JSON válido."""

    return call_minimax(prompt, system)


def generate_endpoint_doc(content: str, filename: str) -> str:
    """Generate documentation for API endpoints."""

    system = """Eres un asistente de documentación técnica. Analiza las rutas FastAPI y genera documentación para api/endpoints.md.

Tu respuesta DEBE ser JSON válido con este formato:
{
  "endpoints": [
    {
      "method": "GET|POST|etc",
      "path": "/ruta",
      "summary": "breve descripción",
      "params": ["param1", "param2"],
      "request_body": "descripción del body o null",
      "response": "descripción de respuesta",
      "requires_auth": true|false
    }
  ],
  "existing_pattern": "regex para buscar sección existente en api/endpoints.md, o null"
}

Reglas:
- Extrae TODOS los endpoints con su método, path, summary
- Los params incluyen path params, query params
- requires_auth se determina por la presencia de Depends(auth) o similar
- No inventar respuestas o params que no estén en el código
- Solo JSON válido"""

    prompt = f"""Genera documentación de endpoints para este archivo de rutas:

Filename: {filename}
Content:
{content}

Responde SOLO con JSON válido."""

    return call_minimax(prompt, system)


def generate_agent_doc(content: str, filename: str) -> str:
    """Generate documentation for an agent."""

    system = """Eres un asistente de documentación técnica. Analiza el agente AI y genera documentación para agentes/<nombre>.md.

Tu respuesta DEBE ser JSON válido con este formato:
{
  "agent_name": "Nombre del agente",
  "section_name": "Nombre del agente",
  "content": "contenido markdown completo del documento (sin la primera línea # Título)",
  "existing_pattern": "regex para reemplazar sección existente en agentes/<nombre>.md, o null"
}

Reglas:
- Documentar: descripción, activación (stages), herramientas (tools), flujo de procesamiento, system prompt, errores, métricas
- Usar sintaxis Markdown pura
- No inventar herramientas o comportamientos que no estén en el código"""

    prompt = f"""Genera documentación para este agente:

Filename: {filename}
Content:
{content}

Responde SOLO con JSON válido."""

    return call_minimax(prompt, system)


def generate_service_doc(content: str, filename: str, service_type: str) -> str:
    """Generate documentation for a service."""

    system = """Eres un asistente de documentación técnica. Analiza el servicio y genera documentación para arquitectura/<nombre>.md.

Tu respuesta DEBE ser JSON válido con este formato:
{
  "doc_title": "Nombre del Servicio — Descripción",
  "content": "contenido markdown completo del documento",
  "existing_pattern": "regex para reemplazar sección existente en arquitectura/<nombre>.md, o null"
}

Reglas:
- Documentar: descripción general, principales funciones/clases, flujos, dependencias
- Usar sintaxis Markdown pura compatible con Obsidian
- No inventar información que no esté en el código"""

    prompt = f"""Genera documentación para este servicio:

Filename: {filename}
Type: {service_type}
Content:
{content}

Responde SOLO con JSON válido."""

    return call_minimax(prompt, system)


# ── Doc patcher ──────────────────────────────────────────────────────────────

def patch_database_schema(patch_json: str, original_content: str) -> str:
    """Patch database-schema.md with model documentation."""
    try:
        data = json.loads(patch_json)
        if "error" in data:
            return original_content

        section = data.get("section_name", "")
        content = data.get("content", "")
        pattern = data.get("existing_section_pattern")

        if not content:
            return original_content

        new_section = f"\n## {section}\n\n{content}\n"

        if pattern:
            # Replace existing section
            import re as regex_module
            matches = list(regex_module.finditer(pattern, original_content))
            if matches:
                start = matches[0].start()
                # Find next ## or end of file
                rest = original_content[matches[0].end():]
                next_section = regex_module.search(r"\n## ", rest)
                if next_section:
                    end = matches[0].end() + next_section.start()
                else:
                    end = len(original_content)
                return original_content[:start] + new_section + original_content[end:]

        # Append before Changelog or at end
        changelog_match = regex_module.search(r"\n## Changelog", original_content)
        if changelog_match:
            return original_content[:changelog_match.start()] + new_section + original_content[changelog_match.start():]
        return original_content + new_section

    except Exception as e:
        print(f"[code-reviewer] patch_database_schema error: {e}", file=sys.stderr)
        return original_content


def write_doc_file(doc_path: str, content: str) -> bool:
    """Write a documentation file."""
    try:
        full_path = Path(doc_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return True
    except Exception as e:
        print(f"[code-reviewer] write error: {e}", file=sys.stderr)
        return False


# ── Main review logic ────────────────────────────────────────────────────────

def review_and_patch() -> dict:
    """Main entry point. Returns dict with recommendation and modified files."""

    staged_files = get_staged_files()
    diff = get_staged_diff()

    if not staged_files:
        return {"recommendation": "APPROVED", "files": [], "summary": "No files staged"}

    # ── Step 1: Classify all changes ────────────────────────────────────────
    classified = []
    for f in staged_files:
        file_diff = subprocess.run(
            ["git", "diff", "--staged", "--", f],
            capture_output=True, text=True, cwd=WORKSPACE_ROOT
        ).stdout
        classification = classify_change(f, file_diff)
        classification["file"] = f
        classification["diff"] = file_diff
        classification["content"] = get_file_content(f)
        classified.append(classification)

    architectural = [c for c in classified if is_architectural(c)]

    if not architectural:
        return {
            "recommendation": "APPROVED",
            "files": staged_files,
            "summary": "No architectural changes detected"
        }

    # ── Step 2: Call MiniMax for each high-priority change ───────────────────
    patches = {}
    docs_to_add = set()

    for change in architectural:
        f = change["file"]
        ctype = change["type"]
        content = change["content"]
        diff_text = change["diff"]

        print(f"[code-reviewer] Analyzing: {f} (type={ctype})", file=sys.stderr)

        try:
            if ctype == "model":
                result = generate_model_doc(content, f)
                # Patch database-schema.md
                schema_path = DOCS_ROOT / "arquitectura" / "database-schema.md"
                if schema_path.exists():
                    original = schema_path.read_text()
                    patched = patch_database_schema(result, original)
                    if patched != original:
                        patches[str(schema_path)] = patched

            elif ctype == "route":
                result = generate_endpoint_doc(content, f)
                # Update api/endpoints.md
                endpoints_path = DOCS_ROOT / "api" / "endpoints.md"
                if endpoints_path.exists():
                    # Simple append for now
                    pass

            elif ctype == "agent":
                result = generate_agent_doc(content, f)
                # Write to agentes/<name>.md
                agent_name = Path(f).stem
                agent_doc_path = DOCS_ROOT / "agentes" / f"{agent_name}.md"
                try:
                    data = json.loads(result)
                    if "content" in data and "error" not in data:
                        patches[str(agent_doc_path)] = f"# {data.get('agent_name', agent_name)}\n\n{data['content']}\n"
                except:
                    pass

            elif ctype == "service":
                result = generate_service_doc(content, f, change.get("subtype", ""))
                try:
                    data = json.loads(result)
                    if "content" in data and "error" not in data:
                        service_name = Path(f).stem
                        # Determine architecture doc path
                        parent_dir = Path(f).parent.name
                        doc_path = DOCS_ROOT / "arquitectura" / f"{service_name}.md"
                        patches[str(doc_path)] = f"# {data.get('doc_title', service_name)}\n\n{data['content']}\n"
                except Exception as e:
                    print(f"[code-reviewer] service doc error: {e}", file=sys.stderr)

            elif ctype == "task":
                # Generate task documentation in celery-tasks.md
                celery_path = DOCS_ROOT / "arquitectura" / "celery-tasks.md"
                if celery_path.exists():
                    # Append task info (simplified for now)
                    pass

        except Exception as e:
            print(f"[code-reviewer] Error processing {f}: {e}", file=sys.stderr)
            continue

    # ── Step 3: Write all patches ────────────────────────────────────────────
    for path_str, content in patches.items():
        p = Path(path_str)
        if p.exists() and path_str not in patches:
            # Already has content from same batch
            pass
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        docs_to_add.add(path_str)

    if not patches:
        return {
            "recommendation": "APPROVED",
            "files": staged_files,
            "summary": f"Architectural changes detected ({len(architectural)}) but no docs generated"
        }

    # ── Step 4: Auto-add patched docs ───────────────────────────────────────
    if docs_to_add:
        for doc_path in docs_to_add:
            subprocess.run(["git", "add", doc_path], cwd=WORKSPACE_ROOT, check=False)

    summary_parts = [f"{len(architectural)} architectural change(s)"]
    if patches:
        summary_parts.append(f"{len(patches)} doc(s) updated")
    if docs_to_add:
        summary_parts.append(f"auto-staged: {', '.join(Path(p).name for p in docs_to_add)}")

    return {
        "recommendation": "DOCS_GENERATED",
        "files": list(docs_to_add),
        "summary": "; ".join(summary_parts),
        "details": patches,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    changed_files_json = sys.argv[1] if len(sys.argv) > 1 else "[]"
    try:
        changed_files = json.loads(changed_files_json)
    except Exception:
        changed_files = []

    result = review_and_patch()

    # Print for hook consumption
    print(json.dumps(result, indent=2))

    # Exit code: 0 = proceed, 1 = block, 2 = docs generated (proceed with new files)
    if result["recommendation"] == "APPROVED":
        sys.exit(0)
    elif result["recommendation"] == "DOCS_GENERATED":
        sys.exit(0)  # Docs already staged, proceed
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
