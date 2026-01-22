#!/bin/bash

# Script para verificar que el proyecto está listo para deployment
# Uso: bash check_deployment_readiness.sh

echo "🔍 Verificando preparación para Vercel..."
echo ""

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para verificar archivos
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅${NC} $1 existe"
        return 0
    else
        echo -e "${RED}❌${NC} $1 NO existe"
        return 1
    fi
}

# Función para verificar directorios
check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✅${NC} Directorio $1 existe"
        return 0
    else
        echo -e "${RED}❌${NC} Directorio $1 NO existe"
        return 1
    fi
}

# Contador de errores
errors=0

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Verificando archivos de configuración"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file "vercel.json" || ((errors++))
check_file ".vercelignore" || ((errors++))
check_file "Procfile" || ((errors++))
check_file "railway.json" || ((errors++))
check_file "render.yaml" || ((errors++))
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📚 Verificando documentación"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file "README.md" || ((errors++))
check_file "README_VERCEL_QUICKSTART.md" || ((errors++))
check_file "DEPLOYMENT_VERCEL.md" || ((errors++))
check_file "DEPLOYMENT_CHECKLIST.md" || ((errors++))
check_file "PROYECTO_LISTO_PARA_VERCEL.md" || ((errors++))
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎨 Verificando Frontend"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_dir "frontend" || ((errors++))
check_file "frontend/package.json" || ((errors++))
check_file "frontend/vite.config.js" || ((errors++))
check_file "frontend/.env.production.example" || ((errors++))

# Verificar que node_modules existe
if [ -d "frontend/node_modules" ]; then
    echo -e "${GREEN}✅${NC} Node modules instalados"
else
    echo -e "${YELLOW}⚠️${NC}  Node modules NO instalados (ejecuta: cd frontend && npm install)"
fi

# Intentar build
echo ""
echo "🔨 Intentando build del frontend..."
cd frontend
if npm run build > /dev/null 2>&1; then
    echo -e "${GREEN}✅${NC} Build del frontend exitoso"
    cd ..
else
    echo -e "${RED}❌${NC} Build del frontend FALLÓ"
    echo -e "${YELLOW}💡${NC} Ejecuta: cd frontend && npm run build"
    cd ..
    ((errors++))
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚙️  Verificando Backend"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_dir "backend" || ((errors++))
check_file "backend/requirements.txt" || ((errors++))
check_file "backend/app/main.py" || ((errors++))
check_file "backend/app/config.py" || ((errors++))
check_file "backend/.env.production.example" || ((errors++))

# Verificar que ALLOWED_ORIGINS está en config.py
if grep -q "ALLOWED_ORIGINS" backend/app/config.py; then
    echo -e "${GREEN}✅${NC} ALLOWED_ORIGINS configurado en config.py"
else
    echo -e "${RED}❌${NC} ALLOWED_ORIGINS NO encontrado en config.py"
    ((errors++))
fi

# Verificar que CORS está configurado en main.py
if grep -q "ALLOWED_ORIGINS" backend/app/main.py; then
    echo -e "${GREEN}✅${NC} CORS configurado dinámicamente en main.py"
else
    echo -e "${RED}❌${NC} CORS NO configurado correctamente en main.py"
    ((errors++))
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 Verificando Seguridad"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verificar que .env no está en Git
if git ls-files --error-unmatch .env > /dev/null 2>&1; then
    echo -e "${RED}❌${NC} .env está en Git (¡PELIGRO! Remuévelo)"
    ((errors++))
else
    echo -e "${GREEN}✅${NC} .env NO está en Git"
fi

# Verificar que .gitignore existe
check_file ".gitignore" || ((errors++))

# Verificar que .env está en .gitignore
if grep -q "\.env" .gitignore; then
    echo -e "${GREEN}✅${NC} .env está en .gitignore"
else
    echo -e "${YELLOW}⚠️${NC}  .env NO está en .gitignore"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 Verificando Git"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verificar si Git está inicializado
if [ -d ".git" ]; then
    echo -e "${GREEN}✅${NC} Git inicializado"
    
    # Verificar remote
    if git remote -v | grep -q "origin"; then
        echo -e "${GREEN}✅${NC} Remote 'origin' configurado"
        git remote -v | head -2
    else
        echo -e "${YELLOW}⚠️${NC}  Remote 'origin' NO configurado"
        echo -e "${YELLOW}💡${NC} Ejecuta: git remote add origin https://github.com/tu-usuario/tu-repo.git"
    fi
    
    # Verificar cambios sin commit
    if git diff-index --quiet HEAD --; then
        echo -e "${GREEN}✅${NC} No hay cambios sin commit"
    else
        echo -e "${YELLOW}⚠️${NC}  Hay cambios sin commit"
        echo -e "${YELLOW}💡${NC} Ejecuta: git add . && git commit -m 'Ready for deployment'"
    fi
else
    echo -e "${YELLOW}⚠️${NC}  Git NO inicializado"
    echo -e "${YELLOW}💡${NC} Ejecuta: git init"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Resumen"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $errors -eq 0 ]; then
    echo -e "${GREEN}🎉 ¡PROYECTO LISTO PARA DEPLOYMENT!${NC}"
    echo ""
    echo "Próximos pasos:"
    echo "1. Sube a GitHub: git push origin main"
    echo "2. Deploy backend en Railway: https://railway.app"
    echo "3. Deploy frontend en Vercel: https://vercel.com"
    echo ""
    echo "📚 Consulta: README_VERCEL_QUICKSTART.md"
else
    echo -e "${RED}❌ Hay $errors errores que debes corregir${NC}"
    echo ""
    echo "Por favor, revisa los errores arriba y corrígelos."
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
