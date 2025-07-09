#!/usr/bin/env python3
# coding: utf-8

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import subprocess
import json
import os
from datetime import datetime
import uuid
from enum import Enum
from sqlalchemy import text
app = FastAPI(title="API de Optimización Terminal")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica los orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos de datos
class EstadoOptimizacion(str, Enum):
    PENDIENTE = "pendiente"
    EJECUTANDO = "ejecutando"
    COMPLETADO = "completado"
    ERROR = "error"

class SolicitudOptimizacion(BaseModel):
    anio: int
    participacion: int
    criterio: str = "criterioII"
    semanas: Optional[List[str]] = None
    usar_db: bool = True

class RespuestaOptimizacion(BaseModel):
    id_tarea: str
    estado: EstadoOptimizacion
    mensaje: str

class EstadoTarea(BaseModel):
    id_tarea: str
    estado: EstadoOptimizacion
    progreso: int
    mensaje: str
    resultado: Optional[dict] = None
    error: Optional[str] = None
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None

# Almacenamiento en memoria de tareas (en producción usar Redis o DB)
tareas = {}

def ejecutar_optimizacion_async(id_tarea: str, solicitud: SolicitudOptimizacion):
    """Ejecuta la optimización en segundo plano"""
    try:
        # Actualizar estado
        tareas[id_tarea]["estado"] = EstadoOptimizacion.EJECUTANDO
        tareas[id_tarea]["mensaje"] = "Iniciando optimización..."
        
        # Construir comando
        cmd = ["python", "main_integrated.py"]
        cmd.extend(["--anio", str(solicitud.anio)])
        cmd.extend(["--participacion", str(solicitud.participacion)])
        cmd.extend(["--criterio", solicitud.criterio])
        
        if solicitud.usar_db:
            cmd.append("--usar-db")
        
        if solicitud.semanas:
            cmd.extend(["--semanas"] + solicitud.semanas)
        
        # Ejecutar proceso
        proceso = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="/app"
        )
        
        # Capturar salida
        stdout, stderr = proceso.communicate()
        
        if proceso.returncode == 0:
            # Éxito
            tareas[id_tarea]["estado"] = EstadoOptimizacion.COMPLETADO
            tareas[id_tarea]["mensaje"] = "Optimización completada exitosamente"
            tareas[id_tarea]["resultado"] = {
                "salida": stdout,
                "codigo_retorno": proceso.returncode
            }
            
            # Intentar parsear resultados específicos
            try:
                # Buscar líneas con información relevante
                lines = stdout.split('\n')
                for line in lines:
                    if "Procesamiento OK" in line:
                        tareas[id_tarea]["resultado"]["semanas_ok"] = int(line.split("=")[1].strip())
                    elif "Semanas infactibles" in line:
                        tareas[id_tarea]["resultado"]["semanas_infactibles"] = int(line.split("=")[1].strip())
            except:
                pass
                
        else:
            # Error
            tareas[id_tarea]["estado"] = EstadoOptimizacion.ERROR
            tareas[id_tarea]["mensaje"] = "Error durante la optimización"
            tareas[id_tarea]["error"] = stderr
            
        tareas[id_tarea]["fecha_fin"] = datetime.now()
        
    except Exception as e:
        tareas[id_tarea]["estado"] = EstadoOptimizacion.ERROR
        tareas[id_tarea]["mensaje"] = "Error inesperado"
        tareas[id_tarea]["error"] = str(e)
        tareas[id_tarea]["fecha_fin"] = datetime.now()

@app.get("/")
async def root():
    return {"mensaje": "API de Optimización Terminal - Activa"}

@app.post("/optimizar", response_model=RespuestaOptimizacion)
async def iniciar_optimizacion(
    solicitud: SolicitudOptimizacion,
    background_tasks: BackgroundTasks
):
    """Inicia una nueva tarea de optimización"""
    # Generar ID único
    id_tarea = str(uuid.uuid4())
    
    # Crear registro de tarea
    tareas[id_tarea] = {
        "id_tarea": id_tarea,
        "estado": EstadoOptimizacion.PENDIENTE,
        "progreso": 0,
        "mensaje": "Tarea en cola",
        "resultado": None,
        "error": None,
        "fecha_inicio": datetime.now(),
        "fecha_fin": None,
        "parametros": solicitud.dict()
    }
    
    # Ejecutar en segundo plano
    background_tasks.add_task(ejecutar_optimizacion_async, id_tarea, solicitud)
    
    return RespuestaOptimizacion(
        id_tarea=id_tarea,
        estado=EstadoOptimizacion.PENDIENTE,
        mensaje="Tarea de optimización iniciada"
    )

@app.get("/tarea/{id_tarea}", response_model=EstadoTarea)
async def obtener_estado_tarea(id_tarea: str):
    """Obtiene el estado de una tarea de optimización"""
    if id_tarea not in tareas:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    
    return EstadoTarea(**tareas[id_tarea])

@app.get("/tareas")
async def listar_tareas():
    """Lista todas las tareas de optimización"""
    return {
        "tareas": list(tareas.values()),
        "total": len(tareas)
    }
@app.get("/db/status")
async def verificar_conexion_db():
    """Verifica el estado de la conexión a PostgreSQL"""
    try:
        from db_integration import DatabaseIntegration
        db = DatabaseIntegration()
        
        # Intentar una consulta simple
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            
        return {
            "estado": "conectado",
            "mensaje": "Conexión exitosa a PostgreSQL",
            "version": version,
            "host": os.getenv('POSTGRES_SERVER'),
            "database": os.getenv('POSTGRES_DB')
        }
    except Exception as e:
        return {
            "estado": "desconectado",
            "mensaje": "Error al conectar con PostgreSQL",
            "error": str(e),
            "host": os.getenv('POSTGRES_SERVER'),
            "database": os.getenv('POSTGRES_DB')
        }

@app.get("/db/tables")
async def verificar_tablas():
    """Lista TODAS las tablas en la base de datos"""
    try:
        from db_integration import DatabaseIntegration
        db = DatabaseIntegration()
        
        with db.engine.connect() as conn:
            # Mostrar TODAS las tablas públicas
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            
        return {
            "estado": "ok",
            "tablas": tables,
            "total": len(tables),
            "nota": "Mostrando todas las tablas en la base de datos"
        }
    except Exception as e:
        return {
            "estado": "error",
            "mensaje": str(e)
        }

@app.get("/db/tables/optimization")
async def verificar_tablas_optimization():
    """Lista solo las tablas de optimización"""
    try:
        from db_integration import DatabaseIntegration
        db = DatabaseIntegration()
        
        with db.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE 'optimization_%'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            
        return {
            "estado": "ok",
            "tablas": tables,
            "total": len(tables),
            "nota": "Tablas específicas de optimización (optimization_*)"
        }
    except Exception as e:
        return {
            "estado": "error",
            "mensaje": str(e)
        }
        
        
@app.delete("/tarea/{id_tarea}")
async def eliminar_tarea(id_tarea: str):
    """Elimina una tarea del registro"""
    if id_tarea not in tareas:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    
    del tareas[id_tarea]
    return {"mensaje": "Tarea eliminada"}

@app.get("/resultados/{id_tarea}/excel")
async def descargar_resultados_excel(id_tarea: str):
    """Descarga los resultados en formato Excel"""
    if id_tarea not in tareas:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    
    tarea = tareas[id_tarea]
    if tarea["estado"] != EstadoOptimizacion.COMPLETADO:
        raise HTTPException(status_code=400, detail="La tarea no ha completado")
    
    # Aquí podrías generar y devolver el archivo Excel
    # Por ahora, devolvemos la ruta donde se guardaron los resultados
    return {
        "mensaje": "Resultados disponibles",
        "rutas": {
            "semanas_filtradas": "/app/resultados_generados/semanas_filtradas.csv",
            "semanas_infactibles": "/app/resultados_generados/semanas_infactibles.csv"
        }
    }

@app.get("/parametros/disponibles")
async def obtener_parametros_disponibles():
    """Devuelve los parámetros disponibles para la optimización"""
    return {
        "anios": list(range(2020, 2025)),
        "participaciones": [50, 60, 68, 70, 80, 90, 100],
        "criterios": ["criterioI", "criterioII", "criterioIII"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)