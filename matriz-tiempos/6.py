# 6.py
# pip install routingpy pandas numpy

import os
import time
import math
import numpy as np
import pandas as pd
from routingpy import ORS
from routingpy.exceptions import RouterApiError


INPUT_CSV  = r"C:\Users\saraa\Documents\semestre 5\proyecto-rutas\paso5y6\filtrado_6.csv"
OUTPUT_CSV = r"C:\Users\saraa\Documents\semestre 5\proyecto-rutas\paso5y6\matriz_tiempos.csv"


ORS_API_KEY = os.environ.get("ORS_API_KEY", "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImYxM2QwMjAyM2E4YTQzMDU4ZDJiYWQ0Y2RiMzY4NmFmIiwiaCI6Im11cm11cjY0In0=")
PROFILE = "driving-car"
BLOCK = 50        # ORS: 50x50 por petición
PAUSE = 0.5
N_SAMPLE = 3


def build_time_matrix(coords_latlon, profile=PROFILE, block=BLOCK, pause=PAUSE, api_key=ORS_API_KEY):
    """
    coords_latlon: lista [(lat, lon), ...] en WGS84
    Devuelve matriz NxN en minutos (np.ndarray).
    """
    coords = list(coords_latlon)
    n = len(coords)
    client = ORS(api_key=api_key)
    M = np.zeros((n, n), dtype=float)
    print(coords,n,client,M)

    nb = math.ceil(n / block)
    for bi in range(nb):
        src_idx = range(bi*block, min((bi+1)*block, n))
        sources = [(coords[k][1], coords[k][0]) for k in src_idx]  # (lon, lat)

        for bj in range(nb):
            dst_idx = range(bj*block, min((bj+1)*block, n))
            destinations = [(coords[k][1], coords[k][0]) for k in dst_idx]

            locations = sources + destinations
            src_ids = list(range(len(sources)))
            dst_ids = list(range(len(sources), len(sources)+len(destinations)))

            # Reintentos básicos
            last_err = None
            for intento in range(3):
                try:
                    res = client.matrix(
                        locations=locations,
                        profile=profile,
                        sources=src_ids,
                        destinations=dst_ids,
                        metrics=["duration"]
                    )
                    break
                except RouterApiError as e:
                    last_err = e
                    # Mensaje específico si 403
                    if "disallowed" in str(e).lower() or "403" in str(e):
                        raise RuntimeError(
                            "ORS 403: tu API key no tiene acceso al endpoint Matrix "
                            "o está bloqueada / cuota agotada. Revisa tu key/plan o usa OSRM local."
                        ) from e
                    time.sleep(1.5 * (intento+1))
                except Exception as e:
                    last_err = e
                    time.sleep(1.5 * (intento+1))
            else:
                # si los 3 intentos fallan
                raise last_err

            # ✅ acceso correcto a atributos y manejo de None → np.nan
            durations = res.durations  # segundos (lista de listas)
            block_mat = np.array(
                [[(v if v is not None else np.nan) for v in row] for row in durations],
                dtype=float
            )

            # Pega al global en minutos
            for ii, i_global in enumerate(src_idx):
                for jj, j_global in enumerate(dst_idx):
                    M[i_global, j_global] = block_mat[ii, jj] / 60.0

            time.sleep(pause)
    return M

def main():
    # 1) Lee y filtra
    df = pd.read_csv(INPUT_CSV)
    cols = ["latitude", "longitude", "section"]
    if not set(cols).issubset(df.columns):
        raise ValueError(f"Faltan columnas {cols} en {INPUT_CSV}. Columnas: {list(df.columns)}")

    print(f"Selected 3 columns: {cols}")
    df = df[cols].copy()
    df = df[df["section"] == 6].reset_index(drop=True)
    print(f"Filtered by section = 6\nRemaining rows: {len(df)}")

    # 2) sanity check de rango
    bad = (~df["latitude"].between(-90,90)) | (~df["longitude"].between(-180,180))
    print(f"Fuera de rango: {bad.sum()} filas")

    # 3) sample + sucursal
    coords = df[["latitude","longitude"]].astype(float).sample(N_SAMPLE, random_state=42).reset_index(drop=True)
    sucursal = {"latitude": 20.59982721, "longitude": -100.3931387}
    coords.loc[len(coords)] = sucursal
    coords = coords.reset_index(drop=True)
    print(coords)

    # 4) lista (lat, lon)
    pairs = coords[["latitude","longitude"]].to_numpy().tolist()
    print("pairs",pairs)
    print("long", len(pairs))

    # 5) matriz
    T = build_time_matrix(pairs)
    out = pd.DataFrame(T)
    print(out)

if __name__ == "__main__":
    main()
