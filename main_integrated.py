#!/usr/bin/env python3
# coding: utf-8

import os
import argparse
from datetime import date
import pandas as pd
from instancias_coloracion import generar_instancias_coloracion
from instancias_gruas import generar_instancias_gruas
from modelo_coloracion import ejecutar_instancias_coloracion
from modelo_gruas_maxmin import ejecutar_instancias_camila
from db_integration import DatabaseIntegration
import logging
import time

# Configurar logging
logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def generar_semanas_iso(year: int):
    """Devuelve cada lunes ISO (YYYY-MM-DD) del año dado."""
    last_week = date(year, 12, 28).isocalendar()[1]
    return [
        date.fromisocalendar(year, week, 1).isoformat()
        for week in range(1, last_week + 1)
    ]

def main():
    parser = argparse.ArgumentParser(
        description="Procesa instancias y guarda resultados de semanas"
    )
    parser.add_argument("--anio", type=int, default=2022,
                        help="Año para generar automáticamente las semanas ISO")
    parser.add_argument("--semanas", nargs="+",
                        help="Lista fija de lunes (YYYY-MM-DD). Si se omite, se generan todas las ISO.")
    parser.add_argument("--participacion", type=int, default=68,
                        help="Valor de participación")
    parser.add_argument("--criterio", type=str, default="criterioII",
                        help="Criterio a usar en instancias de coloración")
    parser.add_argument("--usar-db", action="store_true",
                        help="Guardar resultados en la base de datos PostgreSQL")
    parser.add_argument("--exportar-excel", type=str,
                        help="Exportar resultados de la DB a un archivo Excel")
    args = parser.parse_args()

    # Inicializar integración con DB si está habilitada
    db = None
    if args.usar_db:
        try:
            db = DatabaseIntegration()
            db.create_tables()
            logger.info("Conexión a base de datos establecida")
        except Exception as e:
            logger.error(f"Error conectando a la base de datos: {e}")
            logger.warning("Continuando sin guardar en base de datos")
            db = None

    # Si se solicita exportar, hacerlo y salir
    if args.exportar_excel and db:
        db.exportar_resultados_a_excel(args.exportar_excel)
        return

    BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
    ESTATICOS  = os.path.join(BASE_DIR, "archivos_estaticos")
    RESULTADOS = os.path.join(BASE_DIR, "resultados_generados")
    os.makedirs(RESULTADOS, exist_ok=True)

    TURNOS     = [f"{i:02d}" for i in range(1, 22)]
    BASE_INST  = os.path.join(RESULTADOS, "instancias_camila")
    BASE_RES   = os.path.join(RESULTADOS, "resultados_camila")

    # 1) Decidir semanas
    if args.semanas:
        semanas = args.semanas
        print(f"Usando lista fija de {len(semanas)} semanas.")
    else:
        semanas = generar_semanas_iso(args.anio)
        print(f"Se generaron {len(semanas)} semanas ISO para el año {args.anio}.")

    # 2) Instancias de coloración
    generar_instancias_coloracion(
        semanas, args.criterio, args.anio,
        args.participacion, RESULTADOS, ESTATICOS
    )
    
    # Ejecutar coloración y guardar en DB
    logger.info("Ejecutando modelo de coloración...")
    inicio_coloracion = time.time()
    semanas_filtradas, semanas_infactibles = ejecutar_instancias_coloracion(
        semanas, args.participacion, RESULTADOS
    )
    tiempo_coloracion = time.time() - inicio_coloracion
    
    print(f"Procesamiento OK = {len(semanas_filtradas)}")
    print(f"Semanas infactibles = {len(semanas_infactibles)}")
    print(f"Tiempo total coloración: {tiempo_coloracion:.2f} segundos")

    # Guardar resultados de coloración en DB
    if db:
        # Marcar semanas factibles
        for semana in semanas_filtradas:
            db.marcar_semana_procesada(semana, args.participacion, True, False)
            
            # Leer y guardar resultados detallados si existen
            archivo_distancias = os.path.join(
                RESULTADOS, "resultados_magdalena", semana,
                f"Distancias_Modelo_{semana}_{args.participacion}.xlsx"
            )
            if os.path.exists(archivo_distancias):
                try:
                    df_resumen = pd.read_excel(archivo_distancias, sheet_name='Resumen Semanal')
                    if not df_resumen.empty:
                        resultado = df_resumen.iloc[0].to_dict()
                        resultado.update({
                            'semana': semana,
                            'participacion': args.participacion,
                            'criterio': args.criterio,
                            'estado': 'factible'
                        })
                        db.guardar_resultado_coloracion(semana, args.participacion, resultado)
                        
                        # Guardar detalles de segregaciones
                        df_segregaciones = pd.read_excel(archivo_distancias, sheet_name='Resultados por Segregación')
                        for _, row in df_segregaciones.iterrows():
                            db.Session().execute(text("""
                                INSERT INTO optimization_segregaciones 
                                (semana, segregacion, distancia_total, distancia_dlvr, 
                                 distancia_load, movimientos_dlvr, movimientos_load)
                                VALUES (:semana, :segregacion, :distancia_total, 
                                        :distancia_dlvr, :distancia_load, 
                                        :movimientos_dlvr, :movimientos_load)
                            """), {
                                'semana': semana,
                                'segregacion': row['Segregacion'],
                                'distancia_total': row['Distancia_Total'],
                                'distancia_dlvr': row['Distancia_DLVR'],
                                'distancia_load': row['Distancia_LOAD'],
                                'movimientos_dlvr': row['Movimientos_DLVR'],
                                'movimientos_load': row['Movimientos_LOAD']
                            })
                        db.Session().commit()
                except Exception as e:
                    logger.error(f"Error guardando resultados de coloración para {semana}: {e}")
        
        # Marcar semanas infactibles
        for semana in semanas_infactibles:
            db.marcar_semana_procesada(semana, args.participacion, False, False)
            db.guardar_resultado_coloracion(semana, args.participacion, {
                'semana': semana,
                'participacion': args.participacion,
                'criterio': args.criterio,
                'distancia_total': None,
                'distancia_load': None,
                'distancia_dlvr': None,
                'movimientos_dlvr': None,
                'movimientos_load': None,
                'estado': 'infactible'
            })

    # 3) Guardar listados a CSV
    df_ok = pd.DataFrame({"semana": semanas_filtradas})
    df_no = pd.DataFrame({"semana": semanas_infactibles})
    df_ok.to_csv(os.path.join(RESULTADOS, "semanas_filtradas.csv"), index=False)
    df_no.to_csv(os.path.join(RESULTADOS, "semanas_infactibles.csv"), index=False)
    print(f"CSV guardados en {RESULTADOS}:" 
          "\n - semanas_filtradas.csv" 
          "\n - semanas_infactibles.csv")

    # 4) Instancias de grúas
    logger.info("Generando instancias de grúas...")
    generar_instancias_gruas(semanas_filtradas, args.participacion, RESULTADOS)
    
    logger.info("Ejecutando modelo de grúas...")
    inicio_gruas = time.time()
    ejecutar_instancias_camila(
        semanas_filtradas, TURNOS, args.participacion, BASE_INST, BASE_RES
    )
    tiempo_gruas = time.time() - inicio_gruas
    print(f"Tiempo total grúas: {tiempo_gruas:.2f} segundos")
    
    # Guardar resultados de grúas en DB
    if db:
        for semana in semanas_filtradas:
            # Marcar como procesado en grúas
            db.marcar_semana_procesada(semana, args.participacion, True, True)
            
            # Leer resultados de grúas para cada turno
            for turno in TURNOS:
                archivo_resultado = os.path.join(
                    BASE_RES, f"resultados_turno_{semana}",
                    f"resultados_{semana}_{args.participacion}_T{turno}.xlsx"
                )
                if os.path.exists(archivo_resultado):
                    try:
                        df_resultado = pd.read_excel(archivo_resultado)
                        # Extraer métricas clave
                        min_diff_val = df_resultado[df_resultado['var'] == 'min_diff_val']['val'].iloc[0] if 'min_diff_val' in df_resultado['var'].values else None
                        gruas_utilizadas = len(df_resultado[df_resultado['var'] == 'ygbt']['val'].unique()) if 'ygbt' in df_resultado['var'].values else 0
                        
                        db.guardar_resultado_gruas(semana, int(turno), args.participacion, {
                            'semana': semana,
                            'turno': int(turno),
                            'participacion': args.participacion,
                            'min_diff_val': float(min_diff_val) if min_diff_val else None,
                            'gruas_utilizadas': gruas_utilizadas,
                            'bloques_activos': None,  # Calcular si es necesario
                            'tiempo_resolucion': None,  # Se puede extraer del log
                            'estado': 'optimo',
                            'detalles': {}  # Agregar más detalles si es necesario
                        })
                    except Exception as e:
                        logger.error(f"Error guardando resultado de grúas para {semana} turno {turno}: {e}")

    logger.info("Proceso completado exitosamente")
    
    # Resumen final
    print("\n=== RESUMEN FINAL ===")
    print(f"Semanas procesadas: {len(semanas_filtradas)}")
    print(f"Semanas infactibles: {len(semanas_infactibles)}")
    print(f"Tiempo total: {(tiempo_coloracion + tiempo_gruas):.2f} segundos")
    if db:
        print("Resultados guardados en base de datos PostgreSQL")

if __name__ == "__main__":
    main()