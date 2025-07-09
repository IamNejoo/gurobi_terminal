#!/usr/bin/env python3
# coding: utf-8

import pandas as pd
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)

class OptimizationDataLoader:
    def __init__(self):
        # Crear conexión a la base de datos
        db_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_SERVER')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
    
    def verificar_run_existente(self, semana: str, participacion: int, con_dispersion: bool = True) -> Optional[Dict]:
        """Verifica si ya existe una corrida para esta configuración"""
        # Convertir fecha a número de semana
        fecha_obj = datetime.strptime(semana, '%Y-%m-%d')
        num_semana = fecha_obj.isocalendar()[1]
        
        with self.Session() as session:
            result = session.execute(text("""
                SELECT id, total_movimientos, total_bloques, total_segregaciones, fecha_carga
                FROM magdalena_runs
                WHERE semana = :semana 
                AND participacion = :participacion 
                AND con_dispersion = :con_dispersion
                ORDER BY fecha_carga DESC
                LIMIT 1
            """), {
                'semana': num_semana,
                'participacion': participacion,
                'con_dispersion': con_dispersion
            })
            
            row = result.fetchone()
            if row:
                logger.info(f"Run existente encontrado para S{num_semana}_P{participacion}_{'K' if con_dispersion else 'N'}")
                return {
                    'id': str(row[0]),
                    'total_movimientos': row[1],
                    'total_bloques': row[2],
                    'total_segregaciones': row[3],
                    'fecha_carga': row[4]
                }
            return None
    
    def cargar_resultado_coloracion(self, semana: str, participacion: int, archivo_distancias: str) -> Dict:
        """Carga los resultados del modelo de coloración a la base de datos"""
        fecha_obj = datetime.strptime(semana, '%Y-%m-%d')
        num_semana = fecha_obj.isocalendar()[1]
        
        # Determinar si es con dispersión basándose en el nombre del archivo
        con_dispersion = '_K' in archivo_distancias
        
        # Verificar si ya existe
        run_existente = self.verificar_run_existente(semana, participacion, con_dispersion)
        if run_existente:
            logger.warning(f"Ya existe un run para esta configuración. ID: {run_existente['id']}")
            return run_existente
        
        with self.Session() as session:
            try:
                # Crear nueva corrida
                result = session.execute(text("""
                    INSERT INTO magdalena_runs (semana, participacion, con_dispersion)
                    VALUES (:semana, :participacion, :con_dispersion)
                    RETURNING id
                """), {
                    'semana': num_semana,
                    'participacion': participacion,
                    'con_dispersion': con_dispersion
                })
                run_id = result.scalar()
                
                # Leer archivo de resultados
                archivo_resultado = os.path.join(
                    "resultados_generados", "resultados_magdalena", semana,
                    f"resultado_{semana}_{participacion}_{'K' if con_dispersion else 'N'}.xlsx"
                )
                
                if os.path.exists(archivo_resultado):
                    excel_data = pd.ExcelFile(archivo_resultado)
                    
                    # Cargar hoja General
                    if 'General' in excel_data.sheet_names:
                        df_general = pd.read_excel(archivo_resultado, sheet_name='General')
                        bloques_set = set()
                        periodos_set = set()
                        
                        for _, row in df_general.iterrows():
                            if pd.notna(row.get('Bloque')):
                                session.execute(text("""
                                    INSERT INTO magdalena_general 
                                    (run_id, bloque, periodo, segregacion, recepcion, carga, descarga, entrega)
                                    VALUES (:run_id, :bloque, :periodo, :segregacion, :recepcion, :carga, :descarga, :entrega)
                                """), {
                                    'run_id': run_id,
                                    'bloque': str(row['Bloque']),
                                    'periodo': int(row.get('Periodo', 0)),
                                    'segregacion': str(row.get('Segregación', '')),
                                    'recepcion': int(row.get('Recepción', 0)),
                                    'carga': int(row.get('Carga', 0)),
                                    'descarga': int(row.get('Descarga', 0)),
                                    'entrega': int(row.get('Entrega', 0))
                                })
                                bloques_set.add(str(row['Bloque']))
                                periodos_set.add(int(row.get('Periodo', 0)))
                        
                        # Actualizar metadatos
                        session.execute(text("""
                            UPDATE magdalena_runs 
                            SET total_bloques = :total_bloques, periodos = :periodos
                            WHERE id = :run_id
                        """), {
                            'run_id': run_id,
                            'total_bloques': len(bloques_set),
                            'periodos': max(periodos_set) if periodos_set else 0
                        })
                    
                    # Cargar Ocupación Bloques
                    if 'Ocupación Bloques' in excel_data.sheet_names:
                        df_ocupacion = pd.read_excel(archivo_resultado, sheet_name='Ocupación Bloques')
                        for _, row in df_ocupacion.iterrows():
                            if pd.notna(row.get('Bloque')):
                                session.execute(text("""
                                    INSERT INTO magdalena_ocupacion
                                    (run_id, bloque, periodo, volumen_teus, capacidad_bloque)
                                    VALUES (:run_id, :bloque, :periodo, :volumen_teus, :capacidad_bloque)
                                """), {
                                    'run_id': run_id,
                                    'bloque': str(row['Bloque']),
                                    'periodo': int(row.get('Periodo', 0)),
                                    'volumen_teus': float(row.get('Volumen bloques (TEUs)', 0)),
                                    'capacidad_bloque': float(row.get('Capacidad Bloque', 1155))
                                })
                    
                    # Cargar Workload
                    if 'Workload bloques' in excel_data.sheet_names:
                        df_workload = pd.read_excel(archivo_resultado, sheet_name='Workload bloques')
                        for _, row in df_workload.iterrows():
                            if pd.notna(row.get('Bloque')):
                                session.execute(text("""
                                    INSERT INTO magdalena_workload
                                    (run_id, bloque, periodo, carga_trabajo)
                                    VALUES (:run_id, :bloque, :periodo, :carga_trabajo)
                                """), {
                                    'run_id': run_id,
                                    'bloque': str(row['Bloque']),
                                    'periodo': int(row.get('Periodo', 0)),
                                    'carga_trabajo': float(row.get('Carga de trabajo', 0))
                                })
                    
                session.commit()
                logger.info(f"Resultados de coloración cargados. Run ID: {run_id}")
                
                return {
                    'id': str(run_id),
                    'semana': num_semana,
                    'participacion': participacion,
                    'con_dispersion': con_dispersion,
                    'archivo_procesado': archivo_resultado
                }
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error cargando resultados: {e}")
                raise
    
    def cargar_resultado_gruas(self, semana: str, turno: int, participacion: int, archivo_resultado: str):
        """Carga los resultados del modelo de grúas"""
        fecha_obj = datetime.strptime(semana, '%Y-%m-%d')
        num_semana = fecha_obj.isocalendar()[1]
        
        with self.Session() as session:
            try:
                # Verificar si ya existe
                result = session.execute(text("""
                    SELECT COUNT(*) FROM camila_runs
                    WHERE semana = :semana AND turno = :turno AND participacion = :participacion
                """), {
                    'semana': num_semana,
                    'turno': turno,
                    'participacion': participacion
                })
                
                if result.scalar() > 0:
                    logger.warning(f"Ya existe resultado de grúas para S{num_semana}_T{turno}_P{participacion}")
                    return
                
                # Leer archivo de resultados
                df_resultado = pd.read_excel(archivo_resultado)
                
                # Extraer métricas clave
                min_diff_val = None
                gruas_utilizadas = 0
                
                for _, row in df_resultado.iterrows():
                    if row['var'] == 'min_diff_val':
                        min_diff_val = float(row['val'])
                    elif row['var'] == 'ygbt':
                        gruas_utilizadas += 1
                
                # Insertar en la base de datos
                session.execute(text("""
                    INSERT INTO camila_runs 
                    (semana, turno, participacion, min_diff_val, gruas_utilizadas, fecha_carga)
                    VALUES (:semana, :turno, :participacion, :min_diff_val, :gruas_utilizadas, NOW())
                """), {
                    'semana': num_semana,
                    'turno': turno,
                    'participacion': participacion,
                    'min_diff_val': min_diff_val,
                    'gruas_utilizadas': gruas_utilizadas
                })
                
                session.commit()
                logger.info(f"Resultado de grúas cargado para S{num_semana}_T{turno}_P{participacion}")
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error cargando resultado de grúas: {e}")
                raise
    
    def obtener_resumen_semana(self, semana: str) -> Dict:
        """Obtiene un resumen de los datos procesados para una semana"""
        fecha_obj = datetime.strptime(semana, '%Y-%m-%d')
        num_semana = fecha_obj.isocalendar()[1]
        
        with self.Session() as session:
            # Runs de Magdalena
            result_magdalena = session.execute(text("""
                SELECT participacion, con_dispersion, total_movimientos, fecha_carga
                FROM magdalena_runs
                WHERE semana = :semana
                ORDER BY participacion, con_dispersion
            """), {'semana': num_semana})
            
            magdalena_runs = [
                {
                    'participacion': row[0],
                    'con_dispersion': row[1],
                    'total_movimientos': row[2],
                    'fecha_carga': row[3]
                }
                for row in result_magdalena
            ]
            
            # Runs de Camila
            result_camila = session.execute(text("""
                SELECT turno, participacion, min_diff_val, gruas_utilizadas
                FROM camila_runs
                WHERE semana = :semana
                ORDER BY turno, participacion
            """), {'semana': num_semana})
            
            camila_runs = [
                {
                    'turno': row[0],
                    'participacion': row[1],
                    'min_diff_val': row[2],
                    'gruas_utilizadas': row[3]
                }
                for row in result_camila
            ]
            
            return {
                'semana': num_semana,
                'fecha': semana,
                'magdalena_runs': magdalena_runs,
                'camila_runs': camila_runs,
                'total_magdalena': len(magdalena_runs),
                'total_camila': len(camila_runs)
            }