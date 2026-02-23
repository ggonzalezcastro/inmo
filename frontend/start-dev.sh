#!/usr/bin/env bash
# Libera el puerto 5173 si está en uso y levanta el frontend.
# Uso: ./start-dev.sh   (ejecutar desde la carpeta frontend)

PORT=5173
if command -v lsof >/dev/null 2>&1; then
  PID=$(lsof -ti :$PORT 2>/dev/null)
  if [ -n "$PID" ]; then
    echo "Liberando puerto $PORT (PID $PID)..."
    kill $PID 2>/dev/null || true
    sleep 1
  fi
fi
echo "Iniciando frontend en http://localhost:$PORT"
npm run dev
