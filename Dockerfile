# Dockerfile para la aplicación de optimización con Gurobi
FROM python:3.12.3

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements.txt primero para aprovechar el cache de Docker
COPY requirements.txt .

# Instalar Gurobi (versión académica)
# Nota: Necesitarás proporcionar tu licencia de Gurobi
RUN pip install gurobipy==11.0.0

# Instalar otras dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Crear directorios necesarios
RUN mkdir -p /app/archivos_estaticos \
             /app/resultados_generados \
             /app/codigos \
             /opt/gurobi/

# Copiar el código de la aplicación
COPY . /app/

# Variables de entorno para Gurobi
ENV GRB_LICENSE_FILE=/opt/gurobi/gurobi.lic
ENV GUROBI_HOME=/opt/gurobi
ENV PATH="${PATH}:${GUROBI_HOME}/bin"
ENV LD_LIBRARY_PATH="${GUROBI_HOME}/lib:${LD_LIBRARY_PATH:-}"

# Hacer ejecutable el script principal
RUN chmod +x /app/main.py

# Puerto por defecto (si tu aplicación expone alguno)
EXPOSE 8080

# Comando por defecto
CMD ["python", "main.py", "--anio", "2022", "--participacion", "68"]