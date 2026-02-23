#!/usr/bin/env bash
# Levanta backend (Docker) y frontend para probar en local.
# Uso: ./scripts/run-dev.sh
# Requiere: Docker, Node.js, .env en la raíz (con SECRET_KEY mínimo).

set -e
cd "$(dirname "$0")/.."

echo "=== 1. Levantando DB, Redis y Backend (Docker) ==="
docker-compose up -d db redis backend

echo ""
echo "Esperando a que backend esté listo (health check)..."
for i in {1..30}; do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null | grep -q 200; then
    echo "Backend OK en http://localhost:8000"
    break
  fi
  sleep 2
  echo "  intento $i/30..."
done

echo ""
echo "=== 2. Levantando Frontend (Vite) ==="
cd frontend
npm run dev
