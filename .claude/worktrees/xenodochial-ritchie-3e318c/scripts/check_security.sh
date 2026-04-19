#!/bin/bash
# Verificar que no haya secrets expuestos en el repositorio
set -e

echo "Verificando seguridad..."

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Check .gitignore protects sensitive files
for pattern in "*.env.bak" ".env" "token.pickle" "credentials.json"; do
  if ! grep -q "$pattern" .gitignore 2>/dev/null; then
    echo "ERROR: .gitignore no protege $pattern"
    exit 1
  fi
done

# Check for .env or .env.bak tracked in git
if git ls-files | grep -E "\.env$|\.env\.bak$" 2>/dev/null; then
  echo "ERROR: Archivos .env o .env.bak rastreados en git"
  exit 1
fi

# Check for obvious hardcoded OpenAI-style keys (sk-...)
if grep -r "sk-[a-zA-Z0-9]\{20,\}" --include="*.py" --include="*.js" --include="*.jsx" . 2>/dev/null | grep -v ".git" | grep -v "test" | grep -v "example"; then
  echo "ERROR: Posibles API keys hardcodeadas (sk-...) detectadas"
  exit 1
fi

echo "Verificacion de seguridad completada"
