import pandas as pd
from pathlib import Path
import sys


def get_size_from_segregation(seg_string):
    try:
        parts = str(seg_string).split('-')
        size = int(parts[2]) if len(parts) > 2 else None
        return size if size in (20, 40) else None
    except Exception:
        return None

def generar_instancias_gruas(semanas, participacion, resultados_dir):
    
    resultados_dir = Path(resultados_dir)
    inst_magdalena_root = resultados_dir / "instancias_magdalena"
    res_magdalena_root  = resultados_dir / "resultados_magdalena"
    inst_camila_root    = resultados_dir / "instancias_camila" # / "mu30k_b08"
    
    for semana in semanas:
        
        carpeta_inst = inst_magdalena_root / semana
        carpeta_res  = res_magdalena_root  / semana
        out_dir      = inst_camila_root    / f"instancias_turno_{semana}"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        file_instancia = carpeta_inst / f"Instancia_{semana}_{participacion}_K.xlsx"
        file_resultado = carpeta_res  / f"resultado_{semana}_{participacion}_K.xlsx"
        
        
        if not file_instancia.exists():
            print(f"✗ No encontré {file_instancia}. Saltando semana.")
            continue
        if not file_resultado.exists():
            print(f"✗ No encontré {file_resultado}. Saltando semana.")
            continue
        
        print(f"\n➡️ Semana {semana}")
        print("  • Instancia:", file_instancia.name)
        print("  • Resultado:", file_resultado.name)
        print("  • Salida   :", out_dir)
        
        
        # --- Datos base ---
        try:
            print("Leyendo datos base de:", file_instancia.name)
            df_S = pd.read_excel(file_instancia, sheet_name="S")
            print("   ✓ Hoja 'S' leída.")
        
            df_S["S_low"] = df_S["S"].str.lower()
            df_S["Size"] = df_S["Segregacion"].apply(get_size_from_segregation)
            size_map = df_S.set_index("S_low")["Size"].to_dict()
            print("   ✓ Tamaños (20/40) extraídos de 'Segregacion'.")
        
            null_sizes = df_S[df_S["Size"].isnull()]
            if not null_sizes.empty:
                print("   ! Advertencia: Algunas segregaciones no tienen tamaño 20 o 40 definido:")
                print(null_sizes[["S", "Segregacion"]])
        
            df_S_E = df_S[df_S["Segregacion"].str.contains("expo", case=False, na=False)].copy()
            df_S_I = df_S[df_S["Segregacion"].str.contains("impo", case=False, na=False)].copy()
            print("   ✓ DataFrames S_E y S_I creados.")
        
            dpar = pd.read_excel(file_instancia, sheet_name="D_params_168h")
            dpar["S_low"] = dpar["S"].str.lower()
            print("   ✓ Hoja 'D_params_168h' leída.")
        
        except FileNotFoundError:
            print(f"Error Crítico: No se encontró '{file_instancia.name}'. Abortando.")
            sys.exit(1)
        except Exception as e:
            print(f"Error al leer '{file_instancia.name}': {e}. Abortando.")
            sys.exit(1)
        
        # --- Datos de resultados ---
        try:
            print(f"Leyendo datos de resultados de: {file_resultado.name}")
            df_cargar = pd.read_excel(file_resultado, sheet_name="Cargar")
            df_entregar = pd.read_excel(file_resultado, sheet_name="Entregar")
            df_recibir = pd.read_excel(file_resultado, sheet_name="Recibir")
            print("   ✓ Hojas 'Cargar', 'Entregar', 'Recibir' leídas.")
        
            # Volumen bloques (TEUs)
            SHEET_VOLUMEN = "Volumen bloques (TEUs)"
            df_volumen = pd.read_excel(file_resultado, sheet_name=SHEET_VOLUMEN)
            print(f"   ✓ Hoja '{SHEET_VOLUMEN}' leída.")
        
            required_vol_cols = ["Segregación", "Bloque", "Periodo", "Volumen"]
            if not all(col in df_volumen.columns for col in required_vol_cols):
                missing = [col for col in required_vol_cols if col not in df_volumen.columns]
                raise ValueError(f"Faltan columnas en '{SHEET_VOLUMEN}': {missing}")
        
            # Mapear bloques C -> b
            map_block = {f"C{i}": f"b{i}" for i in range(1, 10)}
            df_volumen["B"] = df_volumen["Bloque"].map(map_block)
            if df_volumen["B"].isnull().any():
                unmapped = df_volumen[df_volumen["B"].isnull()]["Bloque"].unique()
                print(f"   ! Advertencia: Bloques no mapeados: {unmapped}")
                df_volumen.dropna(subset=["B"], inplace=True)
        
            df_volumen["S"] = df_volumen["Segregación"].str.lower()
            if df_volumen["Volumen"].dtype == "object":
                df_volumen["Volumen"] = (df_volumen["Volumen"]
                                         .astype(str)
                                         .str.replace(",", "", regex=False))
            df_volumen["Volumen"] = pd.to_numeric(df_volumen["Volumen"], errors="coerce")
            invalid_vol = df_volumen[df_volumen["Volumen"].isnull()]
            if not invalid_vol.empty:
                print(f"   ! Advertencia: {len(invalid_vol)} filas de volumen inválido serán ignoradas.")
                df_volumen.dropna(subset=["Volumen"], inplace=True)
            df_volumen["Volumen"] = df_volumen["Volumen"].astype(float)
            print(f"   ✓ Hoja '{SHEET_VOLUMEN}' procesada.")
        
            # Bahías por bloques (nueva lógica Cbs)
            SHEET_BAHIAS = "Bahías por bloques"
            df_bahias = pd.read_excel(file_resultado, sheet_name=SHEET_BAHIAS)
            print(f"   ✓ Hoja '{SHEET_BAHIAS}' leída.")
            df_bahias["S_low"] = df_bahias["Segregación"].str.lower()
            df_bahias["B_raw"] = df_bahias["Bloque"]
            df_bahias["B"] = df_bahias["Bloque"].map(map_block).fillna(df_bahias["Bloque"])
        
        except FileNotFoundError:
            print(f"Error Crítico: No se encontró '{file_resultado.name}'. Abortando.")
            sys.exit(1)
        except ValueError as ve:
            print(f"Error procesando '{file_resultado.name}': {ve}. Abortando.")
            sys.exit(1)
        except Exception as e:
            print(f"Error al leer/resultados '{file_resultado.name}': {e}. Abortando.")
            sys.exit(1)
        
        # Mapear para otras hojas
        for df in (df_cargar, df_entregar, df_recibir):
            if "Bloque" in df.columns:
                df["Bloque"] = df["Bloque"].map(map_block).fillna(df["Bloque"])
            if "Segregación" in df.columns:
                df["S_low"] = df["Segregación"].str.lower()
        
        # Constantes
        BLOQUES   = sorted([f"b{i}" for i in range(1, 10)])
        ALL_S_LOW = sorted(df_S["S_low"].unique())
        
        # Hojas estáticas
        df_static_G    = pd.DataFrame({"G": [f"g{i}" for i in range(1, 13)]})
        df_static_B    = pd.DataFrame({"B": BLOQUES})
        df_static_B_E  = pd.DataFrame({"B_E": BLOQUES})
        df_static_B_I  = pd.DataFrame({"B_I": BLOQUES})
        df_static_T    = pd.DataFrame({"T": list(range(1, 9))})
        df_static_mu   = pd.DataFrame({"mu": [30]})
        df_static_W    = pd.DataFrame({"W": [2]})
        df_static_K    = pd.DataFrame({"K": [2]})
        df_static_Rmax = pd.DataFrame({"Rmax": [12]})
        print("✓ Definiciones de hojas estáticas creadas.")
        print("-" * 40)
        
        # Generar instancias por turno
        print("Iniciando generación de archivos por turno...")
        for turno in range(1, 22):
            h_ini, h_fin = (turno - 1) * 8 + 1, turno * 8
            print(f"   Procesando Turno {turno:02d} (Horas {h_ini}-{h_fin})...")
        
            # Gs (nueva lógica: usar DR de D_params_168h en lugar de df_recibir)
            slice_dr = dpar.query("@h_ini <= T <= @h_fin and S_low in @df_S_E.S_low")
            Gs_calc = (
                slice_dr
                .groupby("S_low")["DR"]
                .sum()
                .reset_index()
                .rename(columns={"S_low": "S_E", "DR": "Gs"})
            )
            Gs = (
                pd.DataFrame({"S_E": df_S_E["S_low"].unique()})
                .merge(Gs_calc, on="S_E", how="left")
                .fillna({"Gs": 0})
                .astype({"Gs": int})
            )
        
            # AEbs
            aebs = (df_cargar.query("Periodo == @turno")
                    .groupby(["Bloque", "S_low"])["Cargar"].sum().reset_index())
            grid_bs = pd.MultiIndex.from_product([BLOQUES, ALL_S_LOW],
                                                 names=["Bloque", "S_low"]).to_frame(index=False)
            AEbs = (grid_bs.merge(aebs, on=["Bloque", "S_low"], how="left")
                         .fillna({"Cargar": 0})
                         .astype({"Cargar": int})
                         .rename(columns={"Bloque": "B_E", "S_low": "S_E", "Cargar": "AEbs"})
                         .sort_values(["B_E", "S_E"]))
        
            # AIbs
            aibs = (df_entregar.query("Periodo == @turno")
                    .groupby(["Bloque", "S_low"])["Entregar"].sum().reset_index())
            AIbs = (grid_bs.merge(aibs, on=["Bloque", "S_low"], how="left")
                         .fillna({"Entregar": 0})
                         .astype({"Entregar": int})
                         .rename(columns={"Bloque": "B_I", "S_low": "S_I", "Entregar": "AIbs"})
                         .sort_values(["B_I", "S_I"]))
        
            # DMEst
            exp = dpar.query("@h_ini <= T <= @h_fin and S_low in @df_S_E.S_low").copy()
            if not exp.empty:
                exp["T_rel"] = exp["T"] - h_ini + 1
                DMEst_calc = exp[["S_low", "T_rel", "DC"]].rename(
                    columns={"S_low": "S_E", "T_rel": "T", "DC": "DMEst"})
            else:
                DMEst_calc = pd.DataFrame(columns=["S_E", "T", "DMEst"])
            DMEst = (pd.MultiIndex.from_product([df_S_E.S_low.unique(), range(1, 9)],
                                                names=["S_E", "T"]).to_frame(index=False)
                     .merge(DMEst_calc, on=["S_E", "T"], how="left")
                     .fillna({"DMEst": 0})
                     .astype({"DMEst": int}))
        
            # DMIst
            imp = dpar.query("@h_ini <= T <= @h_fin and S_low in @df_S_I.S_low").copy()
            if not imp.empty:
                imp["T_rel"] = imp["T"] - h_ini + 1
                DMIst_calc = imp[["S_low", "T_rel", "DD"]].rename(
                    columns={"S_low": "S_I", "T_rel": "T", "DD": "DMIst"})
            else:
                DMIst_calc = pd.DataFrame(columns=["S_I", "T", "DMIst"])
            DMIst = (pd.MultiIndex.from_product([df_S_I.S_low.unique(), range(1, 9)],
                                                names=["S_I", "T"]).to_frame(index=False)
                     .merge(DMIst_calc, on=["S_I", "T"], how="left")
                     .fillna({"DMIst": 0})
                     .astype({"DMIst": int}))
        
            # Cbs (nueva lógica usando bahías por bloques)
            bayas_actual = df_bahias[df_bahias["Periodo"] == turno].copy()
            bayas_prev   = df_bahias[df_bahias["Periodo"] == (turno - 1)].copy()
            if bayas_prev.empty:
                bayas_prev = bayas_actual.copy()
            bayas_actual.rename(columns={"Bahías ocupadas": "v"}, inplace=True)
            bayas_prev.rename(columns={"Bahías ocupadas": "v_prev"}, inplace=True)
        
            bayas = (pd.merge(
                        bayas_actual[["S_low", "B", "v"]],
                        bayas_prev[["S_low", "B", "v_prev"]],
                        on=["S_low", "B"], how="outer"
                     )
                     .fillna(0))
            bayas["max_v"] = bayas[["v", "v_prev"]].max(axis=1)
            bayas["cap_teus"] = bayas["max_v"] * 35
            bayas["Cbs_calculado"] = bayas.apply(
                lambda r: r["cap_teus"] / 2 if size_map.get(r["S_low"]) == 40 else r["cap_teus"],
                axis=1
            )
            calculated_cbs_data = (
                bayas.groupby(["B", "S_low"])["Cbs_calculado"]
                     .sum()
                     .reset_index()
            )
            full_grid_cbs = pd.MultiIndex.from_product([BLOQUES, ALL_S_LOW],
                                                       names=["B", "S_low"]).to_frame(index=False)
            Cbs = (full_grid_cbs
                   .merge(calculated_cbs_data, on=["B", "S_low"], how="left")
                   .fillna({"Cbs_calculado": 0}))
            Cbs["Cbs"] = Cbs["Cbs_calculado"].round().astype(int)
            Cbs = (Cbs[["B", "S_low", "Cbs"]]
                   .rename(columns={"S_low": "S"})
                   .sort_values(["B", "S"]))
        
            # Escribir Excel
            out_file = out_dir / f"Instancia_{semana}_{participacion}_T{turno:02d}.xlsx"
            try:
                with pd.ExcelWriter(out_file, engine="openpyxl") as wr:
                    df_S[["S_low", "Segregacion"]].rename(columns={"S_low": "S"})\
                        .to_excel(wr, sheet_name="S", index=False)
                    df_S_E[["S_low", "Segregacion"]].rename(columns={"S_low": "S_E"})\
                        .to_excel(wr, sheet_name="S_E", index=False)
                    df_S_I[["S_low", "Segregacion"]].rename(columns={"S_low": "S_I"})\
                        .to_excel(wr, sheet_name="S_I", index=False)
        
                    AEbs.to_excel(wr, sheet_name="AEbs", index=False)
                    AIbs.to_excel(wr, sheet_name="AIbs", index=False)
                    DMEst.to_excel(wr, sheet_name="DMEst", index=False)
                    DMIst.to_excel(wr, sheet_name="DMIst", index=False)
                    Cbs.to_excel(wr, sheet_name="Cbs", index=False)
                    Gs.to_excel(wr, sheet_name="Gs", index=False)
        
                    df_static_G.to_excel(wr, sheet_name="G", index=False)
                    df_static_B.to_excel(wr, sheet_name="B", index=False)
                    df_static_B_I.to_excel(wr, sheet_name="B_I", index=False)
                    df_static_B_E.to_excel(wr, sheet_name="B_E", index=False)
                    df_static_T.to_excel(wr, sheet_name="T", index=False)
                    df_static_mu.to_excel(wr, sheet_name="mu", index=False)
                    df_static_W.to_excel(wr, sheet_name="W", index=False)
                    df_static_K.to_excel(wr, sheet_name="K", index=False)
                    df_static_Rmax.to_excel(wr, sheet_name="Rmax", index=False)
        
                print(f"      ✓ Instancia turno {turno:02d} guardada: {out_file.name}")
            except Exception as e:
                print(f"      ✗ Error al escribir turno {turno:02d}: {e}")


