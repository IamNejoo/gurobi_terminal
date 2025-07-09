import os
from codigos.leer_lineas import extraer_filas_por_fecha
from codigos.analisis_flujos import run_analysis_flujos
from codigos.evolucion_turnos import criterioII_a_evolucion
from codigos.instancias import generar_instancias

def _process_semana(semana, criterio, anio, participacion, resultados_dir, estaticos_dir, todas_semanas):
    print(f"\n(Generar instancia magdalena) ===== PROCESANDO SEMANA: {semana} =====")
    
    # 1. Extraer líneas de Flujos.csv
    extraer_filas_por_fecha(semana)
    # 2. Análisis de flujos
    run_analysis_flujos(semana)

    # 3. Evolución por turnos (CriterioII)
    try:
        idx = todas_semanas.index(semana)
        numero_sem = idx + 1  # base 1
    except ValueError:
        print(f"ERROR: La semana {semana} no está en la lista.")
        return

    input_crit = os.path.join(estaticos_dir, f"{anio}", f"{criterio}", f"Semana {numero_sem} - {semana}")
    output_evo = os.path.join(resultados_dir, "instancias_magdalena", semana, f"evolucion_turnos_w{semana}.xlsx")

    if not os.path.isdir(input_crit):
        print(f"ADVERTENCIA: No existe {input_crit}. Saltando evolución por turnos.")
    else:
        criterioII_a_evolucion(semana, input_crit, output_evo)
        print("Evolución por turnos completada.")

    # 4. Generación de instancias
    print("Paso 4: Generando instancias...")
    generar_instancias(semana, participacion)
    print("Generación de instancias completada.")


def generar_instancias_coloracion(semanas, criterio, anio, participacion, resultados_dir, estaticos_dir):

    # 0. Prepara directorios de instancias
    inst_base = os.path.join(resultados_dir, "instancias_magdalena")
    os.makedirs(inst_base, exist_ok=True)

    # 1. Crea subcarpetas por semana
    print("\n(Generar instancia magdalena) ===== CREANDO CARPETAS SEMANALES =====")
    for sem in semanas:
        path = os.path.join(inst_base, sem)
        os.makedirs(path, exist_ok=True)
        print(f" - {path}")
    print("(Generar instancia magdalena) ===== CARPETAS SEMANALES CREADAS =====")

    # 2. Procesa cada semana
    for sem in semanas:
        _process_semana(sem, criterio, anio, participacion, resultados_dir, estaticos_dir, semanas)

    print("\n(Generar instancia magdalena) ===== PROCESO COMPLETADO PARA TODAS LAS SEMANAS =====")
