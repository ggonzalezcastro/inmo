#!/bin/bash
# pre-commit-hook.sh — Architectural Doc Review Agent
# Runs before each git commit to check for architectural changes
# and auto-generate documentation using MiniMax M2.7

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$REPO_ROOT/scripts"
AGENT_SCRIPT="$SCRIPT_DIR/code_reviewer_agent.py"
HOOK_LOG="$REPO_ROOT/.git/hooks/pre-commit.log"

# ── Guards ──────────────────────────────────────────────────────────────────

# Skip if no API key
if [[ -z "$MINIMAX_API_KEY" ]]; then
    echo "[pre-commit] MINIMAX_API_KEY not set — skipping doc review"
    exit 0
fi

# Skip for specific commit messages
COMMIT_MSG=$(git log -1 --format="%s" 2>/dev/null || echo "")
if [[ "$COMMIT_MSG" =~ ^(hotfix|chore|deps|version-bump|bump) ]]; then
    echo "[pre-commit] Skipping for: $COMMIT_MSG"
    exit 0
fi

# ── Main ──────────────────────────────────────────────────────────────────

echo "[pre-commit] Running architectural doc review..." | tee -a "$HOOK_LOG"

STAGED_FILES=$(git diff --staged --name-only 2>/dev/null || echo "")
if [[ -z "$STAGED_FILES" ]]; then
    echo "[pre-commit] Nothing staged — OK"
    exit 0
fi

STAGED_JSON="[$(echo "$STAGED_FILES" | tr '\n' ',' | sed 's/,$//' | sed 's/,/\\",\\"/g; s/^/\\"/; s/\\$/\"/')]"

RESULT=$(python3 "$AGENT_SCRIPT" "$STAGED_JSON" 2>&1 | tee -a "$HOOK_LOG")
echo "" >> "$HOOK_LOG"

RECOMMENDATION=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('recommendation','APPROVED'))" 2>/dev/null || echo "APPROVED")
SUMMARY=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary',''))" 2>/dev/null || echo "")

case "$RECOMMENDATION" in
    APPROVED)
        echo "[pre-commit] Approved — $SUMMARY"
        exit 0
        ;;
    DOCS_GENERATED)
        echo "[pre-commit] Docs auto-generated — $SUMMARY"
        exit 0
        ;;
    NEEDS_CONFIRMATION)
        echo "[pre-commit] Architectural change requires documentation review"
        echo "[pre-commit] Summary: $SUMMARY"
        echo "[pre-commit] Aborting commit. Run 'git commit --no-verify' to skip."
        exit 1
        ;;
    *)
        echo "[pre-commit] Unexpected result — proceeding: $RECOMMENDATION"
        exit 0
        ;;
esac
