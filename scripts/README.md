# Pre-Commit Doc Review Agent

Sistema de revisión automática de cambios arquitectónicos que genera y actualiza documentación usando **MiniMax M2.7**.

## Setup

### 1. Instalar hook

```bash
cp .git/hooks/pre-commit .git/hooks/pre-commit.bak 2>/dev/null || true
ln -sf ../../scripts/pre-commit-hook-wrapper.sh .git/hooks/pre-commit
# O si prefieres symlink directo:
ln -sf ../../.git/hooks/pre-commit .git/hooks/pre-commit
```

### 2. Configurar API key

```bash
# En .env (no hagas commit de esto)
MINIMAX_API_KEY=your_key_aqui

# Verificar que esté disponible:
echo $MINIMAX_API_KEY
```

### 3. Instalar dependencias (si no están)

El script usa solo stdlib de Python. No necesita packages extra.

---

## Cómo funciona

```
git commit -m "feat: agregar modelo Property"
        │
        ▼
pre-commit hook
        │
        ▼
code_reviewer_agent.py
        │
        ├─ git diff --staged (archivos modificados)
        ├─ Clasifica cambios (model, route, agent, service, task)
        ├─ Cambios arquitectónicos → llama MiniMax M2.7
        │     ├─ Modelo nuevo → database-schema.md
        │     ├─ Endpoint nuevo → api/endpoints.md
        │     ├─ Agent nuevo → agentes/<name>.md
        │     └─ Servicio nuevo → arquitectura/<name>.md
        └─ Retorna {recommendation, summary, files}
        │
        ▼
hook decide:
  APPROVED        → commit proceed
  DOCS_GENERATED  → docs auto-staged + commit proceed
  NEEDS_CONFIRMATION → commit bloqueado
```

## Tipos de cambio detectados

| Tipo | Archivos | Prioridad | Acción |
|---|---|---|---|
| `model` | `app/models/*.py` | **high** | Actualiza database-schema.md |
| `route` | `app/routes/*.py`, `features/*/routes.py` | **high** | Actualiza api/endpoints.md |
| `agent` | `app/services/agents/*.py` | **high** | Crea/actualiza agentes/<name>.md |
| `service` | `app/services/*/*.py` | medium | Crea arquitectura/<name>.md |
| `task` | `app/tasks/*.py` | medium | Actualiza celery-tasks.md |
| `config` | `.env.example`, `docker-compose.yml` | medium | Alertar |
| `frontend` | `frontend/src/**` | medium | Actualizar docs de frontend |

## Skip conditions

El hook se salta en estos casos:

- `MINIMAX_API_KEY` no está configurada → skip
- Mensaje de commit empieza con `hotfix|chore|deps|version-bump|bump` → skip
- No hay archivos staged → skip

Para hacer commit sin el hook:

```bash
git commit --no-verify -m "tu mensaje"
```

## Logs

```bash
tail -f .git/hooks/pre-commit.log
```

## Ejemplo de output

```
[pre-commit] Running architectural doc review...
[code-reviewer] Analyzing: backend/app/models/property.py (type=model)
[code-reviewer] Analyzing: backend/app/services/agents/property.py (type=agent)
[pre-commit] Docs auto-generated — 2 architectural change(s); 2 doc(s) updated; auto-staged: database-schema.md, property-agent.md
[pre-commit] Proceeding with commit (docs auto-staged)
```

## Solución de problemas

**Error: MINIMAX_API_KEY not set**
```bash
export MINIMAX_API_KEY=tu_key
```

**Error: module not found**
El script usa solo stdlib. Si falla, revisa la versión de Python:
```bash
python3 --version  # necesita 3.9+
```

**El hook no se ejecuta**
```bash
ls -la .git/hooks/pre-commit     # debe ser executable
git config core.hooksPath        # debe apuntar a .git/hooks o no estar seteado
```

---

## Notas

- El agente solo **genera/parcha** docs — no borra secciones existentes a menos que Use `existing_pattern`
- Si MiniMax falla, el hook retorna `APPROVED` por seguridad (no bloquea commits)
- Los docs generados son **completos** (todo el contenido del archivo) para poder hacer diff limpio
