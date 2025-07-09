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
    args = parser.parse_args()

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
    semanas_filtradas, semanas_infactibles = ejecutar_instancias_coloracion(
        semanas, args.participacion, RESULTADOS
    )
    print("Procesamiento OK =", len(semanas_filtradas))
    print("Semanas infactibles =", len(semanas_infactibles))

    # 3) Guardar listados a CSV
    df_ok = pd.DataFrame({"semana": semanas_filtradas})
    df_no = pd.DataFrame({"semana": semanas_infactibles})
    df_ok.to_csv(os.path.join(RESULTADOS, "semanas_filtradas.csv"), index=False)
    df_no.to_csv(os.path.join(RESULTADOS, "semanas_infactibles.csv"), index=False)
    print(f"CSV guardados en {RESULTADOS}:" 
          "\n - semanas_filtradas.csv" 
          "\n - semanas_infactibles.csv")

    # 4) Instancias de grúas
    generar_instancias_gruas(semanas_filtradas, args.participacion, RESULTADOS)
    ejecutar_instancias_camila(
        semanas_filtradas, TURNOS, args.participacion, BASE_INST, BASE_RES
    )

if __name__ == "__main__":
    main()
