# Makefile para gestionar la aplicación de optimización

# Variables
DOCKER_COMPOSE = docker-compose -f docker-compose-optimization.yml
PYTHON_CMD = python main.py
PYTHON_DB_CMD = python main_integrated.py

# Colores para output
GREEN = \033[0;32m
RED = \033[0;31m
NC = \033[0m # No Color

.PHONY: help build up down logs bash run run-db clean test verify-db

help: ## Muestra esta ayuda
	@echo "Comandos disponibles:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Construir la imagen Docker
	@echo "$(GREEN)Construyendo imagen de optimización...$(NC)"
	$(DOCKER_COMPOSE) build

up: ## Levantar el contenedor en modo daemon
	@echo "$(GREEN)Levantando servicio de optimización...$(NC)"
	$(DOCKER_COMPOSE) up -d

down: ## Detener y eliminar contenedores
	@echo "$(RED)Deteniendo servicios...$(NC)"
	$(DOCKER_COMPOSE) down

logs: ## Ver logs del contenedor
	$(DOCKER_COMPOSE) logs -f

bash: ## Acceder al bash del contenedor
	$(DOCKER_COMPOSE) run --rm optimization bash

run: ## Ejecutar optimización con parámetros por defecto
	@echo "$(GREEN)Ejecutando optimización...$(NC)"
	$(DOCKER_COMPOSE) run --rm optimization $(PYTHON_CMD)

run-db: ## Ejecutar optimización con integración a DB
	@echo "$(GREEN)Ejecutando optimización con DB...$(NC)"
	$(DOCKER_COMPOSE) run --rm optimization $(PYTHON_DB_CMD) --usar-db

run-custom: ## Ejecutar con parámetros personalizados (uso: make run-custom ARGS="--anio 2023 --participacion 70")
	@echo "$(GREEN)Ejecutando optimización con parámetros: $(ARGS)$(NC)"
	$(DOCKER_COMPOSE) run --rm optimization $(PYTHON_CMD) $(ARGS)

run-semanas: ## Ejecutar semanas específicas (uso: make run-semanas SEMANAS="2022-05-23 2022-05-30")
	@echo "$(GREEN)Ejecutando semanas: $(SEMANAS)$(NC)"
	$(DOCKER_COMPOSE) run --rm optimization $(PYTHON_CMD) --semanas $(SEMANAS)

export-excel: ## Exportar resultados de DB a Excel
	@echo "$(GREEN)Exportando resultados a Excel...$(NC)"
	$(DOCKER_COMPOSE) run --rm optimization $(PYTHON_DB_CMD) --usar-db --exportar-excel /app/resultados_generados/resumen_$(shell date +%Y%m%d_%H%M%S).xlsx

verify-db: ## Verificar conexión a la base de datos
	@echo "$(GREEN)Verificando conexión a PostgreSQL...$(NC)"
	@$(DOCKER_COMPOSE) run --rm optimization python -c "\
	from db_integration import DatabaseIntegration; \
	try: \
	    db = DatabaseIntegration(); \
	    print('✓ Conexión exitosa a PostgreSQL'); \
	    db.create_tables(); \
	    print('✓ Tablas verificadas/creadas'); \
	except Exception as e: \
	    print('✗ Error:', e)"

clean: ## Limpiar resultados generados
	@echo "$(RED)Limpiando resultados...$(NC)"
	rm -rf resultados_generados/*
	@echo "$(GREEN)Limpieza completada$(NC)"

clean-db: ## Limpiar tablas de la base de datos
	@echo "$(RED)Limpiando tablas de optimización en DB...$(NC)"
	@$(DOCKER_COMPOSE) run --rm optimization python -c "\
	from sqlalchemy import create_engine, text; \
	import os; \
	db_url = f\"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_SERVER')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}\"; \
	engine = create_engine(db_url); \
	with engine.connect() as conn: \
	    conn.execute(text('TRUNCATE TABLE optimization_coloracion_results, optimization_gruas_results, optimization_semanas_procesadas, optimization_segregaciones CASCADE')); \
	    conn.commit(); \
	print('✓ Tablas limpiadas')"

test-connection: ## Probar conexión a PostgreSQL con psql
	@echo "$(GREEN)Probando conexión a PostgreSQL...$(NC)"
	$(DOCKER_COMPOSE) run --rm optimization sh -c "apt-get update -qq && apt-get install -y postgresql-client > /dev/null 2>&1 && psql -h host.docker.internal -U terminal_user -d terminal_db -c 'SELECT version();'"

status: ## Ver estado de los servicios
	@echo "$(GREEN)Estado de los servicios:$(NC)"
	$(DOCKER_COMPOSE) ps

# Comandos de desarrollo
dev-install: ## Instalar dependencias localmente (para desarrollo)
	pip install -r requirements.txt

dev-freeze: ## Actualizar requirements.txt con las dependencias actuales
	pip freeze > requirements.txt

# Comandos compuestos
full-run: build verify-db run-db ## Build + Verificar DB + Ejecutar con DB
	@echo "$(GREEN)Proceso completo finalizado$(NC)"

restart: down up logs ## Reiniciar servicios y ver logs