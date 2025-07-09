#!/bin/bash

# Script de inicialización para el proyecto de optimización

set -e  # Salir si hay algún error

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Inicializando Proyecto de Optimización ===${NC}"

# 1. Crear estructura de directorios
echo -e "${YELLOW}1. Creando estructura de directorios...${NC}"
mkdir -p archivos_estaticos/{2022,2023}/{criterioI,criterioII}
mkdir -p resultados_generados/{instancias_magdalena,resultados_magdalena,instancias_camila,resultados_camila}
mkdir -p codigos
mkdir -p gurobi_license

# 2. Verificar licencia de Gurobi
echo -e "${YELLOW}2. Verificando licencia de Gurobi...${NC}"
if [ ! -f "gurobi_license/gurobi.lic" ]; then
    echo -e "${RED}❌ No se encontró el archivo de licencia de Gurobi${NC}"
    echo -e "${YELLOW}   Por favor, copia tu archivo gurobi.lic al directorio gurobi_license/${NC}"
    echo -e "${YELLOW}   Puedes obtener una licencia académica en: https://www.gurobi.com/academia/${NC}"
else
    echo -e "${GREEN}✓ Licencia de Gurobi encontrada${NC}"
fi

# 3. Crear archivo .env si no existe
echo -e "${YELLOW}3. Configurando variables de entorno...${NC}"
if [ ! -f ".env" ]; then
    cat > .env << EOF
# Configuración de PostgreSQL
POSTGRES_SERVER=host.docker.internal
POSTGRES_USER=terminal_user
POSTGRES_PASSWORD=terminal_pass
POSTGRES_DB=terminal_db
POSTGRES_PORT=5432

# Configuración de la aplicación
PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
EOF
    echo -e "${GREEN}✓ Archivo .env creado${NC}"
else
    echo -e "${GREEN}✓ Archivo .env ya existe${NC}"
fi

# 4. Verificar que el backend está corriendo
echo -e "${YELLOW}4. Verificando servicios del backend...${NC}"
if command -v docker &> /dev/null; then
    # Buscar contenedor de postgres
    if docker ps | grep -q "terminal_postgres"; then
        echo -e "${GREEN}✓ PostgreSQL del backend está corriendo${NC}"
    else
        echo -e "${RED}❌ No se detectó PostgreSQL del backend${NC}"
        echo -e "${YELLOW}   Asegúrate de que el backend esté corriendo con: cd /path/to/backend && docker-compose up -d${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Docker no está instalado o no está en el PATH${NC}"
fi

# 5. Construir imagen de Docker
echo -e "${YELLOW}5. Construyendo imagen Docker...${NC}"
if command -v docker-compose &> /dev/null; then
    docker-compose -f docker-compose-optimization.yml build
    echo -e "${GREEN}✓ Imagen construida exitosamente${NC}"
else
    echo -e "${RED}❌ docker-compose no está instalado${NC}"
fi

# 6. Verificar conexión a la base de datos
echo -e "${YELLOW}6. Verificando conexión a PostgreSQL...${NC}"
if command -v docker-compose &> /dev/null; then
    docker-compose -f docker-compose-optimization.yml run --rm optimization python -c "
from db_integration import DatabaseIntegration
try:
    db = DatabaseIntegration()
    print('✓ Conexión exitosa a PostgreSQL')
    db.create_tables()
    print('✓ Tablas creadas/verificadas')
except Exception as e:
    print(f'✗ Error: {e}')
    exit(1)
"
fi

# 7. Crear archivo de ejemplo de datos si no existe
echo -e "${YELLOW}7. Verificando archivos de datos...${NC}"
if [ ! -f "archivos_estaticos/Flujos.csv" ]; then
    echo -e "${YELLOW}⚠ No se encontró archivos_estaticos/Flujos.csv${NC}"
    echo -e "${YELLOW}  Asegúrate de copiar tus archivos de datos estáticos${NC}"
fi

# 8. Resumen
echo -e "${GREEN}=== Resumen de Inicialización ===${NC}"
echo -e "Estructura de directorios: ${GREEN}✓${NC}"
echo -e "Archivo .env: ${GREEN}✓${NC}"

if [ -f "gurobi_license/gurobi.lic" ]; then
    echo -e "Licencia Gurobi: ${GREEN}✓${NC}"
else
    echo -e "Licencia Gurobi: ${RED}✗${NC}"
fi

if docker ps | grep -q "terminal_postgres" 2>/dev/null; then
    echo -e "PostgreSQL backend: ${GREEN}✓${NC}"
else
    echo -e "PostgreSQL backend: ${RED}✗${NC}"
fi

echo -e "\n${GREEN}=== Próximos pasos ===${NC}"
echo -e "1. Si falta la licencia de Gurobi, cópiala a gurobi_license/"
echo -e "2. Asegúrate de que el backend esté corriendo"
echo -e "3. Copia tus archivos de datos a archivos_estaticos/"
echo -e "4. Ejecuta: ${YELLOW}make run${NC} o ${YELLOW}make run-db${NC}"
echo -e "\nPara ver todos los comandos disponibles: ${YELLOW}make help${NC}"