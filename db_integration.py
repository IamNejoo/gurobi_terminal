#!/usr/bin/env python3
# coding: utf-8

import os
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime, Date, JSON, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DatabaseIntegration:
    def __init__(self):
        # Obtener configuración de la base de datos desde variables de entorno
        self.db_config = {
            'host': os.getenv('POSTGRES_SERVER', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', '5432'),
            'database': os.getenv('POSTGRES_DB', 'terminal_db'),
            'user': os.getenv('POSTGRES_USER', 'terminal_user'),
            'password': os.getenv('POSTGRES_PASSWORD', 'terminal_pass')
        }
        
        # Crear URL de conexión
        self.db_url = f"postgresql://{self.db_config['user']}:{self.db_config['password']}@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
        
        # Crear engine
        self.engine = create_engine(self.db_url)
        self.Session = sessionmaker(bind=self.engine)
        
    def create_tables(self):
        """Crear tablas necesarias para almacenar los resultados de optimización"""
        with self.engine.connect() as conn:
            # Tabla para resultados de coloración
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS optimization_coloracion_results (
                    id SERIAL PRIMARY KEY,
                    semana DATE NOT NULL,
                    participacion INTEGER NOT NULL,
                    criterio VARCHAR(50),
                    distancia_total FLOAT,
                    distancia_load FLOAT,
                    distancia_dlvr FLOAT,
                    movimientos_dlvr INTEGER,
                    movimientos_load INTEGER,
                    estado VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(semana, participacion, criterio)
                )
            """))
            
            # Tabla para resultados de grúas
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS optimization_gruas_results (
                    id SERIAL PRIMARY KEY,
                    semana DATE NOT NULL,
                    turno INTEGER NOT NULL,
                    participacion INTEGER NOT NULL,
                    min_diff_val FLOAT,
                    gruas_utilizadas INTEGER,
                    bloques_activos INTEGER,
                    tiempo_resolucion FLOAT,
                    estado VARCHAR(20),
                    detalles JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(semana, turno, participacion)
                )
            """))
            
            # Tabla para tracking de semanas procesadas
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS optimization_semanas_procesadas (
                    id SERIAL PRIMARY KEY,
                    semana DATE NOT NULL,
                    participacion INTEGER NOT NULL,
                    coloracion_factible BOOLEAN,
                    gruas_procesado BOOLEAN DEFAULT FALSE,
                    fecha_procesamiento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(semana, participacion)
                )
            """))
            
            # Tabla para segregaciones
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS optimization_segregaciones (
                    id SERIAL PRIMARY KEY,
                    semana DATE NOT NULL,
                    segregacion VARCHAR(100) NOT NULL,
                    distancia_total FLOAT,
                    distancia_dlvr FLOAT,
                    distancia_load FLOAT,
                    movimientos_dlvr INTEGER,
                    movimientos_load INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            conn.commit()
            logger.info("Tablas creadas exitosamente")
    
    def guardar_resultado_coloracion(self, semana, participacion, resultado):
        """Guardar resultado de coloración en la base de datos"""
        with self.Session() as session:
            try:
                session.execute(text("""
                    INSERT INTO optimization_coloracion_results 
                    (semana, participacion, criterio, distancia_total, distancia_load, 
                     distancia_dlvr, movimientos_dlvr, movimientos_load, estado)
                    VALUES (:semana, :participacion, :criterio, :distancia_total, 
                            :distancia_load, :distancia_dlvr, :movimientos_dlvr, 
                            :movimientos_load, :estado)
                    ON CONFLICT (semana, participacion, criterio) 
                    DO UPDATE SET
                        distancia_total = EXCLUDED.distancia_total,
                        distancia_load = EXCLUDED.distancia_load,
                        distancia_dlvr = EXCLUDED.distancia_dlvr,
                        movimientos_dlvr = EXCLUDED.movimientos_dlvr,
                        movimientos_load = EXCLUDED.movimientos_load,
                        estado = EXCLUDED.estado,
                        created_at = CURRENT_TIMESTAMP
                """), resultado)
                session.commit()
                logger.info(f"Resultado de coloración guardado para semana {semana}")
            except Exception as e:
                logger.error(f"Error guardando resultado de coloración: {e}")
                session.rollback()
    
    def guardar_resultado_gruas(self, semana, turno, participacion, resultado):
        """Guardar resultado de grúas en la base de datos"""
        with self.Session() as session:
            try:
                session.execute(text("""
                    INSERT INTO optimization_gruas_results 
                    (semana, turno, participacion, min_diff_val, gruas_utilizadas, 
                     bloques_activos, tiempo_resolucion, estado, detalles)
                    VALUES (:semana, :turno, :participacion, :min_diff_val, 
                            :gruas_utilizadas, :bloques_activos, :tiempo_resolucion, 
                            :estado, :detalles)
                    ON CONFLICT (semana, turno, participacion) 
                    DO UPDATE SET
                        min_diff_val = EXCLUDED.min_diff_val,
                        gruas_utilizadas = EXCLUDED.gruas_utilizadas,
                        bloques_activos = EXCLUDED.bloques_activos,
                        tiempo_resolucion = EXCLUDED.tiempo_resolucion,
                        estado = EXCLUDED.estado,
                        detalles = EXCLUDED.detalles,
                        created_at = CURRENT_TIMESTAMP
                """), resultado)
                session.commit()
                logger.info(f"Resultado de grúas guardado para semana {semana}, turno {turno}")
            except Exception as e:
                logger.error(f"Error guardando resultado de grúas: {e}")
                session.rollback()
    
    def marcar_semana_procesada(self, semana, participacion, coloracion_factible, gruas_procesado=False):
        """Marcar una semana como procesada"""
        with self.Session() as session:
            try:
                session.execute(text("""
                    INSERT INTO optimization_semanas_procesadas 
                    (semana, participacion, coloracion_factible, gruas_procesado)
                    VALUES (:semana, :participacion, :coloracion_factible, :gruas_procesado)
                    ON CONFLICT (semana, participacion) 
                    DO UPDATE SET
                        coloracion_factible = EXCLUDED.coloracion_factible,
                        gruas_procesado = EXCLUDED.gruas_procesado,
                        fecha_procesamiento = CURRENT_TIMESTAMP
                """), {
                    'semana': semana,
                    'participacion': participacion,
                    'coloracion_factible': coloracion_factible,
                    'gruas_procesado': gruas_procesado
                })
                session.commit()
            except Exception as e:
                logger.error(f"Error marcando semana procesada: {e}")
                session.rollback()
    
    def obtener_semanas_pendientes(self, participacion):
        """Obtener semanas que no han sido procesadas"""
        with self.Session() as session:
            result = session.execute(text("""
                SELECT semana 
                FROM optimization_semanas_procesadas 
                WHERE participacion = :participacion 
                AND coloracion_factible = true 
                AND gruas_procesado = false
                ORDER BY semana
            """), {'participacion': participacion})
            return [row[0].strftime('%Y-%m-%d') for row in result]
    
    def exportar_resultados_a_excel(self, archivo_salida):
        """Exportar todos los resultados a un archivo Excel"""
        with pd.ExcelWriter(archivo_salida, engine='openpyxl') as writer:
            # Exportar resultados de coloración
            df_coloracion = pd.read_sql("""
                SELECT * FROM optimization_coloracion_results 
                ORDER BY semana, participacion
            """, self.engine)
            df_coloracion.to_excel(writer, sheet_name='Coloracion', index=False)
            
            # Exportar resultados de grúas
            df_gruas = pd.read_sql("""
                SELECT * FROM optimization_gruas_results 
                ORDER BY semana, turno, participacion
            """, self.engine)
            df_gruas.to_excel(writer, sheet_name='Gruas', index=False)
            
            # Exportar resumen de semanas
            df_semanas = pd.read_sql("""
                SELECT * FROM optimization_semanas_procesadas 
                ORDER BY semana, participacion
            """, self.engine)
            df_semanas.to_excel(writer, sheet_name='Semanas', index=False)
            
            # Exportar segregaciones
            df_segregaciones = pd.read_sql("""
                SELECT * FROM optimization_segregaciones 
                ORDER BY semana, segregacion
            """, self.engine)
            df_segregaciones.to_excel(writer, sheet_name='Segregaciones', index=False)
        
        logger.info(f"Resultados exportados a {archivo_salida}")