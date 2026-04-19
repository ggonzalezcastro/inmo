# Gestión de Secrets

## Reglas Fundamentales

1. **NUNCA** hacer commit de archivos `.env`
2. **NUNCA** hardcodear API keys en el código
3. **SIEMPRE** usar variables de entorno
4. **SIEMPRE** rotar keys si son expuestas

## Variables de Entorno por Ambiente

### Desarrollo Local

- Usar `.env` local (git ignored)
- Copiar desde `.env.example`
- Nunca crear backups con extensiones obvias (`.env.bak`, `.env.backup`)

### Producción

- Usar variables de entorno de la plataforma:
  - **Vercel**: Dashboard → Settings → Environment Variables
  - **Railway**: Dashboard → Variables
  - **Render**: Dashboard → Environment

## Rotación de Keys

Si una key es expuesta:

1. Revocar inmediatamente en la plataforma del proveedor
2. Generar nueva key
3. Actualizar en todos los ambientes (local, staging, producción)
4. Si fue commiteada: limpiar historial de git (ver abajo)

## Detectar Secrets Expuestos

```bash
# Escanear repositorio (si tienes detect-secrets instalado)
detect-secrets scan

# Verificar con script del proyecto
./scripts/check_security.sh
```

## Limpiar Historial de Git

Si un archivo con secrets fue commiteado:

```bash
# Eliminar archivo del historial (requiere git-filter-repo o filter-branch)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env.bak" \
  --prune-empty --tag-name-filter cat -- --all
```

Después de limpiar: forzar push y notificar al equipo. Todos deben hacer fresh clone.

## Prevención

- Usar pre-commit hooks con `detect-secrets`
- Revisar `.gitignore` antes de agregar archivos
- No crear backups de `.env` en el repositorio
- Usar gestores de secrets (1Password, AWS Secrets Manager) para equipos
