#!/bin/bash
# install_precommit_hook.sh — Instala el pre-commit hook de revisión arquitectónica

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_SRC="$REPO_ROOT/scripts/pre-commit-hook.sh"
HOOK_DEST="$REPO_ROOT/.git/hooks/pre-commit"
BACKUP="$REPO_ROOT/.git/hooks/pre-commit.bak"

echo "=== Pre-Commit Doc Review Agent Installer ==="

# Backup existing hook
if [[ -f "$HOOK_DEST" ]]; then
    cp "$HOOK_DEST" "$BACKUP"
    echo "[✓] Backup saved to $BACKUP"
fi

# Link or copy
if [[ -L "$HOOK_DEST" ]]; then
    rm "$HOOK_DEST"
fi
ln -s "$HOOK_SRC" "$HOOK_DEST"

# Make executable
chmod +x "$HOOK_DEST"
chmod +x "$HOOK_SRC"
chmod +x "$REPO_ROOT/scripts/code_reviewer_agent.py"

echo "[✓] Hook installed → $HOOK_DEST"
echo ""
echo "Next steps:"
echo "  1. Add to .env:"
echo "       MINIMAX_API_KEY=your_key_here"
echo "  2. Test:"
echo "       git commit -m 'test' --dry-run"
echo ""
echo "To skip the hook:"
echo "  git commit --no-verify -m 'chore: deps'"
