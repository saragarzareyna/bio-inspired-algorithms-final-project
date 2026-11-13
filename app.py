# librerías 
from shiny import App, render, ui, reactive
import pathlib
import numpy as np
import random
import os
import time
import math
import osmnx as ox
import pandas as pd
import networkx as nx
import matplotlib.cm as cm
import matplotlib.pyplot as plt
from routingpy import ORS
from routingpy.exceptions import RouterApiError


# config de la API
ORS_API_KEY = os.environ.get("ORS_API_KEY", "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImYxM2QwMjAyM2E4YTQzMDU4ZDJiYWQ0Y2RiMzY4NmFmIiwiaCI6Im11cm11cjY0In0=")
PROFILE = "driving-car"
BLOCK = 50        # ORS: 50x50 por petición
PAUSE = 0.5

## funciones funcionales ACO

# Indica si es posible agregar un nodo a la ruta actual
def es_factible(ruta, nodos, siguiente_nodo, carga_actual, tiempo_actual, matriz_tiempo, capacidad_camion):
    demanda, inicio_tiempo, limite_tiempo, tiempo_servicio = nodos[siguiente_nodo]
    tiempo_viaje = matriz_tiempo[ruta[-1]][siguiente_nodo]

    # Verificar capacidad
    if carga_actual + demanda > capacidad_camion:
        return False

    # Verificar ventana de tiempo
    tiempo_llegada = tiempo_actual + tiempo_viaje
    comienzo_servicio = max(tiempo_llegada, inicio_tiempo)
    if comienzo_servicio > limite_tiempo:
        return False

    return True

# Realiza el costo de la ruta
def costo_ruta(ruta, matriz_tiempo):
    costo = 0
    for i in range(len(ruta) - 1):
        costo += matriz_tiempo[ruta[i]][ruta[i + 1]]
    return costo

# Construir soluciones
def construir_solucion(matriz_tiempo, num_nodos, nodos, almacen, capacidad_camion, feromona, alpha, beta, visibilidad):
    no_visitado = set(range(1, num_nodos))
    rutas = []
    distancia_total = 0

    while no_visitado:
        ruta = [almacen]
        carga_actual = 0
        tiempo_actual = 0

        while True:
            posibles_nodos = [
                j for j in no_visitado
                if es_factible(ruta, nodos, j, carga_actual, tiempo_actual, matriz_tiempo, capacidad_camion)
            ]

            if not posibles_nodos:
                ruta.append(almacen)
                distancia_total += costo_ruta(ruta, matriz_tiempo)
                rutas.append(ruta)
                break

            i = ruta[-1]
            probs = []
            for j in posibles_nodos:
                tau = feromona[i][j] ** alpha
                eta = visibilidad[i][j] ** beta
                probs.append(tau * eta)
            probs = np.array(probs)
            probs /= probs.sum()


            siguiente_nodo = random.choices(posibles_nodos, weights=probs, k=1)[0]
            no_visitado.remove(siguiente_nodo)

            demanda, inicio_tiempo, limite_tiempo, tiempo_servicio = nodos[siguiente_nodo]
            tiempo_viaje = matriz_tiempo[i][siguiente_nodo]
            llegada = tiempo_actual + tiempo_viaje
            comienzo_servicio = max(llegada, inicio_tiempo)
            tiempo_actual = comienzo_servicio + tiempo_servicio
            carga_actual += demanda

            ruta.append(siguiente_nodo)

    return rutas, distancia_total

# ACTUALIZAR FEROMONAS
def actualizar_feromona(mejores_rutas, mejor_costo, feromona, rho, Q):
    feromona *= (1 - rho)
    for ruta in mejores_rutas:
        for i in range(len(ruta) - 1):
            a, b = ruta[i], ruta[i + 1]
            feromona[a][b] += Q / mejor_costo

# time matrix
# coordenadas
def obtener_coords(num_seccion, INPUT_CSV_BASE=f"secciones\seccion_"):
    """
    Obtiene coordenadas de una sección específica

    Args:
        num_seccion (int): Número de la sección (0-9)
        INPUT_CSV_BASE (str): Base del nombre de los archivos (por defecto "seccion_")

    Returns:
        pandas.DataFrame: DataFrame con todas las coordenadas
    """
    # Construir el nombre del archivo
    input_csv = f"{INPUT_CSV_BASE}{num_seccion}.csv"

    try:
        # Leer el archivo CSV
        df = pd.read_csv(input_csv)

        # Verificar que existen las columnas necesarias
        cols = ["id","latitude", "longitude"]
        if not set(cols).issubset(df.columns):
            raise ValueError(f"Faltan columnas {cols} en {input_csv}. Columnas: {list(df.columns)}")

        # Filtrar y procesar los datos
        df = df[cols].copy()

        # esto estaba en la función og pero me recomendó quitarlo pero me da cosita
        # bad = (~df["latitude"].between(-90,90)) | (~df["longitude"].between(-180,180))

        # Convertir a float y retornar TODOS los datos
        coords = df[["id","latitude","longitude"]].astype(float).reset_index(drop=True)

        return coords

    except FileNotFoundError:
        raise FileNotFoundError(f"No se encontró el archivo {input_csv}")
    except Exception as e:
        raise Exception(f"Error procesando la sección {num_seccion}: {str(e)}")

coords_seccion_1 = obtener_coords(1)  # Todos los datos de seccion_1
coords_seccion_2 = obtener_coords(2)  # Todos los datos de seccion_2
coords_seccion_3 = obtener_coords(3)  # Todos los datos de seccion_3
coords_seccion_4 = obtener_coords(4)  # Todos los datos de seccion_4
coords_seccion_5 = obtener_coords(5)  # Todos los datos de seccion_5
coords_seccion_6 = obtener_coords(6)  # Todos los datos de seccion_6
coords_seccion_7 = obtener_coords(7)  # Todos los datos de seccion_7
coords_seccion_8 = obtener_coords(8)  # Todos los datos de seccion_8
coords_seccion_9 = obtener_coords(9)  # Todos los datos de seccion_9


# pairs
# coordenadas de sucursales
latlon = [
    (0, 20.62502622, -100.4399523),    # 1 - plaza revolución
    (0, 20.60992354, -100.4186663),    # 2 - cinco de febrero
    (0, 20.65185389, -100.4332575),    # 3 - urban center
    (0, 20.58607147, -100.3921382),    # 4 - constituyentes
    (0, 20.58775044, -100.3791939),    # 5 - cons. Auditorio
    (0, 20.59982721, -100.3931387),    # 6- centro
    (0, 20.59585588, -100.3694748),    # 7- bernardo
    (0, 20.61631254, -100.3981287),    # 8- walmart bernardo
    (0, 20.63031123, -100.3991128)     # 9- zip and go
]

# time matrix -- esta es funcional y nunca se llama
def build_time_matrix(coords_latlon, profile=PROFILE, block=BLOCK, pause=PAUSE, api_key=ORS_API_KEY):
    """
    coords_latlon: lista [(lat, lon), ...] en WGS84
    Devuelve matriz NxN en minutos (np.ndarray).
    """
    coords = list(coords_latlon)
    n = len(coords)
    client = ORS(api_key=api_key)
    M = np.zeros((n, n), dtype=float)

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

# time matrix (como df) (se llama a esta!)
def time_matrix_function(seccion, N_SAMPLE):
    coords_df = globals()[f"coords_seccion_{seccion}"]

    coords = coords_df[["id","latitude","longitude"]].astype(float).sample(N_SAMPLE, random_state=42).reset_index(drop=True)
    sucursal = latlon[seccion-1]  # Coordenada de la sucursal de ESTA sección
    sucursal_df = pd.DataFrame([sucursal], columns=["id", "latitude", "longitude"])

    coords = pd.concat([sucursal_df, coords], ignore_index=True)
    print(coords)
    pairs = coords[["latitude","longitude"]].to_numpy().tolist()
    print(pairs)

    T = build_time_matrix(pairs)
    out = pd.DataFrame(T)
    return(out, coords)

#cargar el Mapa de queretaro
G = ox.load_graphml("queretaro.graphml")

# aco core!!!
def mejor_ruta(n_sample_input, seccion_input, n_hormigas=3, iteraciones=50, alpha=1, beta=3, rho=0.3, Q=100, capacidad_camion=2000):
    # matriz de tiempo
    matriz_tiempo, coordenadas_id = time_matrix_function(seccion_input, n_sample_input)
    matriz_tiempo = np.array(matriz_tiempo, dtype=float)
    print("matriz de tiempo")
    print(matriz_tiempo)

    # MATRIZ DE VISIBILIDAD (HEURÍSTICA)
    visibilidad = np.zeros_like(matriz_tiempo, dtype=float)
    mask = matriz_tiempo != 0
    visibilidad[mask] = 1.0 / matriz_tiempo[mask]
    np.fill_diagonal(visibilidad, 0)

    # nodos (DEMANDAS Y TIEMPOS)
    # (demanda, tiempo incial, tiempo limite de entrega, tiempo que se dura en entregar el paquete)
    n = len(matriz_tiempo)  # número total de nodos (incluyendo el depósito)
    nodos = []  # depósito fijo

    # valores del depósito/almacén/sucursal
    nodos.append((0, 0, 720, 0))

    # generar el resto de nodos
    for _ in range(n - 1):
        x1 = random.randint(100, 1800)   # volumen del paquete
        x2 = random.randint(0, 50)      # tiempo válido de entrega
        x3 = random.randint(650, 720)   # tiempo límite de entrega
        x4 = random.randint(10, 30)     # tiempo realizando la entrega
        nodos.append((x1, x2, x3, x4))

    num_nodos = len(nodos)
    almacen = 0  # índice del depósito

    mejor_costo_global = float('inf')
    mejor_ruta_global = None
    historia_costos = []
    feromona = np.ones((num_nodos, num_nodos))


    for it in range(iteraciones):
        mejor_costo_iteracion = float('inf')
        mejor_ruta_iteracion = None

        for _ in range(n_hormigas):
            rutas, costo = construir_solucion(matriz_tiempo, num_nodos, nodos, almacen, capacidad_camion, feromona, alpha, beta, visibilidad)
            if costo < mejor_costo_iteracion:
                mejor_costo_iteracion = costo
                mejor_ruta_iteracion = rutas

        actualizar_feromona(mejor_ruta_iteracion, mejor_costo_iteracion, feromona, rho, Q)

        if mejor_costo_iteracion < mejor_costo_global:
            mejor_costo_global = mejor_costo_iteracion
            mejor_ruta_global = mejor_ruta_iteracion

        historia_costos.append(mejor_costo_global)

    return {
        "matriz_costos": matriz_tiempo,
        "iteracion": f"{it+1}/{iteraciones}",
        "costo": mejor_costo_global,
        "ruta": mejor_ruta_global,
        "historia": historia_costos,
        "Matriz_con_id": coordenadas_id
    }


# verificar que funcionan las funciones
# mejor_ruta(20,1)


# aquí empieza el shiny

# user interface
app_ui = ui.page_fluid(
    # CSS for styling
    ui.tags.head(
        ui.tags.style("""
            /* Global styles */
            body {
                font-family: "Helvetica", "Helvetica", sans-serif;
                background-color: #000000;
                color: #ffffff;
                margin: 0;
                padding: 0;
            }

            .accordion {
                border: 2px solid #333333 !important;  /* Cambia el grosor aquí */
                border-radius: 8px !important;
            }

            .accordion-button {
                font-size: 0.6em !important;
                font-weight: bold !important;
                color: #000000 !important;
                background-color: #ffffff !important;
            }
            
            .card-header {
                font-size: 1.2em !important;  /* Cambiado de 0.6em a 1.5em */
                font-weight: bold !important;
                color: #000000 !important;
                background-color: #ffffff !important;
            }
            .accordion-button:not(.collapsed) {
                background-color: #ffffff !important;
                color: #000000 !important;
            }

            .accordion-container {
                max-width: 1000px;           /* Ancho máximo más angosto */
                margin: 0 auto;             /* Centrado */
                padding: 0 20px;            /* Espacio a los lados */
            }

            /* Asegurar que los acordeones usen el contenedor */
            .accordion {
                width: 100% !important;
            }
            
            /* Video background styling */
            .video-container {
                position: relative;
                width: 100%;
                height: 80vh;
                overflow: hidden;
                background-color: #000000;
            }
            
            .background-video {
                position: absolute;
                top: 50%;
                left: 50%;
                min-width: 100%;
                min-height: 100%;
                width: auto;
                height: auto;
                transform: translate(-50%, -50%);
                z-index: 0;
                object-fit: cover;
            }
            
            .centered-text {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                color: #ffffff;
                text-align: center;
                z-index: 2;
                text-shadow: 2px 2px 8px rgba(0,0,0,0.8);
                font-family: "Helvetica", "Arial", sans-serif;
                width: 80%;
            }
            
            .centered-text h1 {
                font-size: 3.5em;
                margin-bottom: 20px;
                font-weight: bold;
                color: #ffffff;
            }
            
            .centered-text p {
                font-size: 1.5em;
                color: #ffffff;
                opacity: 0.9;
            }
            
            /* Video overlay for better text readability */
            .video-overlay {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.3);
                z-index: 1;
            }
            
            /* Tab styling */
            .nav-tabs {
                background-color: #000000;
                border-bottom: 1px solid #333333;
                font-family: "Helvetica", "Arial", sans-serif;
                padding: 0 20px;
            }
            
            .nav-link {
                color: #ffffff !important;
                font-family: "Helvetica", "Arial", sans-serif;
                font-weight: 500;
            }
            
            .nav-link.active {
                background-color: #333333 !important;
                border-color: #333333 !important;
                color: #ffffff !important;
            }
            
            .nav-link:hover {
                background-color: #222222 !important;
                color: #ffffff !important;
            }
            
            /* Tab content styling */
            .tab-content {
                background-color: #000000;
                color: #ffffff;
                padding: 30px;
                min-height: 400px;
                font-family: "Helvetica", "Arial", sans-serif;
            }
            
            .tab-content h2 {
                color: #ffffff;
                font-family: "Helvetica", "Arial", sans-serif;
                font-weight: bold;
                margin-bottom: 20px;
            }
            
            .tab-content p {
                color: #ffffff;
                font-family: "Helvetica", "Arial", sans-serif;
                font-size: 1.1em;
                line-height: 1.6;
            }
            
            /* Content boxes */
            .content-box {
                margin-top: 20px;
                padding: 25px;
                background-color: #1a1a1a;
                border-radius: 8px;
                border: 1px solid #333333;
                color: #ffffff;
                font-family: "Helvetica", "Arial", sans-serif;
            }
            /* Target the specific layout columns by parent class */
            .tab-content .layout-columns {
                max-height: 1500px;
                min-height: 300px;
                height: auto !important;
            }

            /* Si la imagen excede el alto de la ventana, el panel hace scroll */
            .accordion .accordion-body { overflow: auto; }

            /* Imagen responsiva, limitada al alto de la ventana */
            #imagen_seccion, #imagen_seccion img {
                display: block;
                width: 100%;
                height: auto;
                max-width: 100%;
                max-height: 80vh;   /* ajusta 70–90vh a tu gusto */
                object-fit: contain; /* sin recorte; usa 'cover' si quieres llenar recortando */
                margin: 0 auto;
            }
        """)
    ),
    
    # pestañas
    ui.navset_tab(
        # inicio
        ui.nav_panel(
                    "Inicio",
                    ui.div(
                        ui.div(
                            # Video container with multiple source options for better compatibility
                            ui.tags.video(
                                {
                                    "autoplay": True,
                                    "muted": True,
                                    "loop": True,
                                    "playsinline": True,
                                    "class": "background-video"
                                },
                                # Primary video source
                                ui.tags.source(
                                    {
                                        "src": "video-fondo.mp4", 
                                        "type": "video/mp4"
                                    }
                                ),
                                "Your browser does not support the video tag."
                            ),
                            # Overlay for better text readability
                            ui.div(class_="video-overlay"),
                            # Centered text content
                            ui.div(
                                ui.h1("Tu paquete: optimizado"),
                                ui.p(ui.HTML("<strong>con algoritmos matemáticos bioinspirados</strong>")),
                                ui.p("Sara Garza Reyna & Juan Sebastian Chitiva Guerrero"),
                                class_="centered-text"
                            ),
                            class_="video-container"
                        ),
                        style="padding: 0; margin: 0;"
                    )
                ),

        # contexto
        ui.nav_panel(
            "Contexto",
            ui.h2("Contexto del Proyecto"),
            ui.div(
                ui.p("La explosión del e-commerce a nivel global ha transformado la cadena de suministro, trasladando el principal cuello de botella logístico desde el transporte de larga distancia hacia los entornos urbanos. Hoy en día, el mayor reto que enfrentan gigantes como Amazon y paqueterías tradicionales como DHL es la Logística de la Última Milla, un tramo que, si bien es el más corto, representa más de la mitad del costo total de envío. Esta situación se agrava por la creciente congestión en las ciudades, la escasez de estacionamiento y las estrictas demandas de los consumidores por entregas rápidas y puntuales."),
                ui.p("En esencia, este proyecto aborda la modelización y optimización de un problema de ruteo de vehículos (VRP). Partiendo del fundamento teórico del Problema del Viajante de Comercio (TSP) y su evolución al VRP, exploraremos cómo las metaheurísticas bioinspiradas ofrecen soluciones eficientes para contrarrestar la ineficiencia inherente a las entregas individualizadas, la variabilidad del tráfico y la necesidad de integrar la sostenibilidad en las operaciones de reparto."),
                class_="content-box"
            ),
            ui.br(),
            # contenedores: 
            ui.div(
                # Primera cajita colapsable
                ui.accordion(
                    ui.accordion_panel(
                        "Problemática",
                        ui.p("Los Problemas de Ruteo (o Routing Problems) son una clase fundamental de problemas de optimización en la logística y el transporte. El objetivo principal es encontrar la mejor secuencia de rutas para que una flota de vehículos (o agentes, personas, etc.) visite un conjunto de ubicaciones (clientes) desde uno o varios depósitos, minimizando un coste total (como la distancia total recorrida, el tiempo total, el coste de combustible, o una combinación de estos) y respetando diversas restricciones.", style="color: black;"),
                        ui.p("El ejemplo más famoso es el Problema del Viajante de Comercio (TSP), donde un vendedor debe visitar una lista de ciudades una sola vez y regresar al punto de partida, minimizando la distancia total.", style="color: black;"),
                        ui.img(
                            src="problema.png", 
                            style="max-width: 50%; height: auto; display: block; margin: 0 auto;"
                        )
                    ),
                    open = False,
                    id="accordion1"
                ),
                ui.br(),
                # Segunda cajita colapsable
                ui.accordion(
                    ui.accordion_panel(
                        "Antecedentes",
                        ui.p("El antecedente fundamental de los problemas de ruteo y logística moderna se remonta al Problema del Viajante de Comercio (TSP). Sus primeras menciones datan del Siglo XIX (1800s), cuando matemáticos como William Rowan Hamilton lo propusieron como un juego que buscaba el recorrido más corto para visitar una lista de ciudades una sola vez. El problema fue formalizado matemáticamente en la década de 1930s por figuras como Karl Menger, quienes reconocieron su enorme dificultad computacional. El verdadero punto de partida de la logística moderna ocurrió entre los 1950s y 1960s con el Origen del VRP (Problema de Ruteo de Vehículos); en 1959, George Dantzig y John Ramser publicaron el primer artículo sobre el VRP, una extensión del TSP que incorpora múltiples vehículos partiendo de un depósito central. Desde los 1970s hasta la Actualidad, la naturaleza NP-hard de estos problemas impulsó el Desarrollo de Metaheurísticas (como los Algoritmos Genéticos y la Optimización por Colonia de Hormigas) para encontrar soluciones de alta calidad en tiempos eficientes, dada la inviabilidad de calcular la solución óptima exacta en casos de gran escala.", style="color: black;"),
                        ui.img(
                            src="tipos.png", alt="Tipos de problemas de ruteo", 
                            style="max-width: 50%; height: auto; display: block; margin: 0 auto;"
                        )
                    ),
                    open = False,
                    id="accordion2"
                ),
                ui.br(),
                # Tercera cajita colapsable
                ui.accordion(
                    ui.accordion_panel(
                        "Servicios como Amazon y paqueterías como DHL",
                        ui.p("En lugar de enfrentar el simple Problema de Ruteo de Vehículos (VRP), empresas como Amazon y DHL resuelven versiones avanzadas conocidas como Problemas de Ruteo de la Última Milla. Estos incluyen el VRP con Ventanas de Tiempo (VRPTW), que es fundamental ya que asegura que el vehículo llegue en un intervalo pactado, minimizando las costosas entregas fallidas. Además, abordan el VRP de Flota Heterogénea, decidiendo estratégicamente qué tipo de vehículo (furgoneta, vehículo eléctrico, o eBike) es más adecuado para cada cliente y ruta, optimizando así los costos operativos y las capacidades.", style="color: black;"),
                        ui.p("El nivel de complejidad aumenta con el VRP con Recogida y Entrega Simultánea (VRPPD), crucial para maximizar la eficiencia en cada parada, pues los conductores realizan tanto la entrega de paquetes como la recolección de devoluciones o envíos de vendedores. Finalmente, el VRP Dinámico o en Tiempo Real es vital en entornos urbanos congestionados, permitiendo a las compañías ajustar las rutas sobre la marcha para manejar nuevos pedidos urgentes, cancelaciones o, de forma crítica, adaptarse a los cambios imprevistos en las condiciones del tráfico y congestión, lo que es esencial para servicios rápidos como Amazon Prime Now.", style="color: black;"),
                        ui.img(
                            src="routing-problem-ilustrated.png", 
                            style="max-width: 50%; height: auto; display: block; margin: 0 auto;"
                        )
                    ),
                    open = False,
                    id="accordion3"
                ),
                ui.br(),
                # Cuarta cajita colapsable
                ui.accordion(
                    ui.accordion_panel(
                        "La última milla",
                        ui.p("La logística de la última milla es la fase final y más costosa de la cadena de suministro, implicando el movimiento de mercancías desde el centro de distribución hasta la puerta del cliente. Este tramo se vuelve desproporcionadamente caro y complejo, llegando a representar hasta el 53% del costo total de envío, debido a la transición de la eficiencia del transporte a granel a la ineficiencia de las entregas individualizadas. Las rutas de la última milla, concentradas en áreas urbanas, se caracterizan por una alta densidad de paradas, lo que obliga a lidiar constantemente con la congestión, la búsqueda de estacionamiento (el desafío que describe tu situación problema), y las restricciones de circulación, haciendo que el tiempo de viaje sea altamente variable e impredecible.", style="color: black;"),
                        ui.p("A esta complejidad se añaden las rigurosas restricciones del cliente, como las Ventanas de Tiempo (VRPTW), que imponen límites estrictos a la flexibilidad del ruteo. Uno de los mayores costos operativos proviene de las entregas fallidas cuando el cliente no está presente, lo que requiere reintentos costosos; por ello, empresas como Amazon y DHL implementan estrategias mitigadoras como el uso de casilleros o la entrega dentro del hogar (smart lock). Finalmente, el panorama se complica con la sostenibilidad y la regulación urbana, ya que muchas ciudades prohíben vehículos contaminantes, forzando a las compañías a migrar a flotas heterogéneas (eléctricos, eBikes) y a la optimización multi-objetivo para incluir la reducción de la huella de carbono como un factor de rendimiento esencial.", style="color: black;"),
                        ui.img(src="last-mile.png", 
                        style="max-width: 50%; height: auto; display: block; margin: 0 auto;"
                        )
                    ),
                    open = False,
                    id="accordion4"
                ),
                ui.br(),
                class_="accordion-container"
            )
        ),

        # bioinspi-qué??
        ui.nav_panel(
            "¿Bioinspirados?",
            ui.h2("¿Bioinspirados?"),
            ui.div(
                ui.p("Un algoritmo matemático bioinspirado es un método de computación que imita o se basa en procesos y comportamientos que ocurren en la naturaleza para resolver problemas complejos de optimización."),
                ui.p("La presente sección aborda la optimización del Problema de Ruteo de Vehículos (VRP) a través de estos algoritmos. Incluye una descripción de los requisitos del problema, una comparativa exhaustiva de las metaheurísticas más utilizadas a nivel mundial, y una introducción fundamental a los principios del Algoritmo Genético (AG), la Optimización por Enjambre de Partículas (PSO) y la Optimización por Colonia de Hormigas (ACO)."),
                class_="content-box"
            ),
            ui.br(),
            # contenedores: 
            ui.div(
                # comparativa
                ui.accordion(
                    ui.accordion_panel(
                        "Comparativa",
                        ui.p("Los tres algoritmos se pueden comparar por el uso que tienen:", style="color: black;"),
                        ui.img(
                            src="tabla-comp.png", alt="Tipos de problemas de ruteo", 
                            style="max-width: 50%; height: auto; display: block; margin: 0 auto;"
                        )
                    ),
                    open = False,
                    id="ac2"
                ),
                ui.br(),
                # Tercera cajita colapsable AG 
                ui.accordion(
                    ui.accordion_panel(
                        "Algoritmo Genético",
                        ui.p("Un algoritmo genético es una técnica de optimización que imita la selección natural y la evolución para encontrar la mejor solución a un problema", style="color: black;"),
                        ui.img(
                            src="code-ag.png", 
                            style="max-width: 50%; height: auto; display: block; margin: 0 auto;"
                        ),
                        ui.p("Se puede visualizar de la siguiente manera: ", style="color: black;"),
                        ui.img(
                            src="ag-gif.gif", 
                            style="max-width: 50%; height: auto; display: block; margin: 0 auto;"
                        ),
                    ),
                    open = False,
                    id="acAG"
                ),
                ui.br(),
                # PSO
                ui.accordion(
                    ui.accordion_panel(
                        "PSO",
                        ui.p("La Optimización por Enjambre de Partículas (PSO) es un algoritmo bioinspirado que resuelve problemas optimizando una solución candidata a través de la colaboración de un colectivo de agentes, imitando el comportamiento social de bandadas de aves o bancos de peces.", style="color: black;"),
                        ui.img(
                            src="code-pso.png", 
                            style="max-width: 35%; height: auto; display: block; margin: 0 auto;"
                        ),
                        ui.p("Se puede visualizar de la siguiente manera: ", style="color: black;"),
                        ui.img(
                            src="pso-gif.gif", 
                            style="max-width: 50%; height: auto; display: block; margin: 0 auto;"
                        ),
                    ),
                    open = False,
                    id="acPSO"
                ),
                ui.br(),
                # ACO
                ui.accordion(
                    ui.accordion_panel(
                        "ACO",
                        ui.p("El algoritmo de optimización por colonia de hormigas (ACO) es una técnica probabilística bioinspirada que utiliza el comportamiento colectivo de las hormigas para encontrar la mejor ruta en un problema de optimización.", style="color: black;"),
                        ui.img(
                            src="code-aco.png", 
                            style="max-width: 65%; height: auto; display: block; margin: 0 auto;"
                        ),
                        ui.p("Se puede visualizar de la siguiente manera: ", style="color: black;"),
                        ui.img(
                            src="aco-gif.gif", 
                            style="max-width: 50%; height: auto; display: block; margin: 0 auto;"
                        ),
                    ),
                    open = False,
                    id="acACO"
                ),
                ui.br(),
                # reqs
                ui.accordion(
                    ui.accordion_panel(
                        "Requisitos para resolver el problema",
                        ui.tags.ul(
                            ui.tags.li("Función objetivo: Minimizar el tiempo de ruta"),
                            ui.tags.li("Restricciones: Limite de tiempo, capacidad de camión, tiempo de entrega por paquete "), 
                            ui.tags.li("Coordenadas de clientes/puntos de entrega"),
                            ui.tags.li("Coordenadas de depósito")
                        ),
                        ui.img(
                            src="caja.png", 
                            style="max-width: 50%; height: auto; display: block; margin: 0 auto;"
                        )
                    ),
                    open = False,
                    id="ac1"
                ),
                ui.br(),
                                # Cuarta cajita colapsable
                ui.accordion(
                    ui.accordion_panel(
                        "Librerías",
                        ui.p("Para la implementación de esta solución, destacan por su funcionalidad ciertas librerías: ", style="color: black;"),
                        ui.img(src="paqueterias.png", 
                        style="max-width: 65%; height: auto; display: block; margin: 0 auto;"
                        )
                    ),
                    open = False,
                    id="accordionLibs"
                ),
                class_="accordion-container"
            )
        ),

        # pestaña requisitos
        ui.nav_panel(
            "Requisitos",
            ui.div(
                # Título
                ui.h2("Requisitos"),
                
                # Texto descriptivo
                ui.p(ui.tags.b("Puntos de Partida y Operación Logística")),
                ui.p("Se han seleccionado las sucursales de DHL en Querétaro como los puntos de partida (depósitos) para el sistema. La ubicación de estos puntos es ajustable según los recursos de cada empresa y la ciudad operativa. Estas sucursales sirven como la base para la división de la ciudad en nueve secciones geográficas. Cada sucursal funciona como un centro de almacenamiento donde los paquetes son recibidos y custodiados hasta que los repartidores inician la distribución final a su destino, un proceso conocido como la última milla."),
                
                # Cuadro con referencia a página web pública (MyMaps)
                ui.div(
                        ui.tags.iframe(
                            src="https://www.google.com/maps/d/embed?mid=15cpce7xN8srqz0miVIUlwO7HF_-N6ZE&ehbc=2E312F&noprof=1",
                            width="100%",
                            height="480",
                            style="border: 0px solid #007bff; border-radius: 0px;",
                            frameborder="0",
                            allowfullscreen=""
                        ),
                        style="padding: 0px; background-color: #f8f9fa; border-radius: 10px; margin: 0px;"
                    ),
                ui.br(),
                # Dos columnas
                ui.layout_columns(
                    # Columna 1 - Foto local
                    ui.div(
                        ui.accordion(
                            ui.accordion_panel(
                                "Secciones de la Ciudad",
                                ui.img(
                                    src="voronoi.png", alt="Tipos de problemas de ruteo", 
                                    style="max-width: 100%; height: auto; display: block; margin: 0 auto;"
                                ),
                            ),
                            open = False,
                        )
                    ),
                    
                    # Columna 2 - Acordeones
                    ui.div(
                        ui.accordion(
                            ui.accordion_panel(
                                "Matriz de tiempo",
                                ui.p("Usando la API gratuita de open route service se obtiene la matriz de tiempos ingresando los pares de coordenadas (latitud y longitud) de los puntos a analizar, junto con el tipo de vehículo en el que se mide el tiempo de llegar de punto i a punto j. Esta API únicamente soporta a 50 puntos a la vez, adaptandose a las necesidades académicas de este proyecto. Si se quisieran analizar más puntos, se puede usar la API de Google, que tiene un costo adicional y esta fuera del alcance de este proyecto.", style="color: black;"),
                                ui.div(
                                    ui.a(
                                        "Conocer más", 
                                        href="https://openrouteservice.org/", 
                                        target="_blank",
                                        style="background-color: #8B0000; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 10px;"
                                    ),
                                    style="text-align: center;"
                                ),
                            ),
                            open = False,
                            id="matrizdecostosapi"
                        ),
                        ui.br(),
                        # Tercera cajita colapsable AG 
                    ),
                    col_widths=[6, 6]  # Dos columnas de igual ancho
                ),
                class_="container-fluid mt-4"
            )
        ),

        # parámetros
        ui.nav_panel(
            "Parámetros",
            ui.div(
                ui.h2("Simulador de parámetros en ACO aplicado a Querétaro"),
                ui.p("En este simulador se puede visualizar el efecto que tienen los parámetros del ACO en la calidad de la solución al problema."),
                ui.p("Con esta pestaña se busca simular distintas soluciones para facilitar la comparación de las mismas y admirar la versatilidad del algoritmo"),
                # Layout con dos columnas
                ui.layout_columns(
                    (
                        # Columna izquierda - Controles
                        ui.accordion(
                                ui.accordion_panel(
                                    "Parámetros de la simulación",
                                    ui.p("Se está modelando sobre la sección 1.", style="color: black;"),
                                    ui.p("Los parámetros son:", style="color: black;"),
                                    ui.tags.ul(
                                        ui.tags.li("No. de paquetes a entregar = 25"),
                                        ui.tags.li("Capacidad del camión (en litros) = 20,000")
                                    ),
                                    ui.input_slider(
                                        "n_hormigas", 
                                        "Hormigas:", 
                                        min=1, 
                                        max=10, 
                                        value=3
                                    ),
                                    ui.input_slider(
                                        "iteraciones", 
                                        "Iteraciones:", 
                                        min=5, 
                                        max=250, 
                                        value=10
                                    ),
                                    ui.input_slider(
                                        "alpha", 
                                        "alpha:", 
                                        min=0.01, 
                                        max=4, 
                                        value=1,
                                        step = 0.01
                                    ),
                                    ui.input_slider(
                                        "beta", 
                                        "beta:", 
                                        min=0.01, 
                                        max=4, 
                                        value=3,
                                        step = 0.01
                                    ),
                                    ## alpha=1, beta=3, rho=0.3, Q=100,
                                    ui.input_slider(
                                        "rho", 
                                        "Taza de evaporación (rho):", 
                                        min=0.01, 
                                        max=1, 
                                        value=0.3,
                                        step = 0.01
                                    ),
                                    ui.input_slider(
                                        "Q", 
                                        "Cantidad de feromona (Q):", 
                                        min=1, 
                                        max=250, 
                                        value=100,
                                        step = 1
                                    ),
                                ),
                            open = True,
                        ),
                        ui.br(),
                        ui.accordion(
                                ui.accordion_panel(
                                    "Resultados",
                                    ui.p("La ruta óptima se encontro en la iteración: ", style="color: black;"),
                                    ui.output_text("iteracion_p"),
                                    # ui.p("La matriz de costos es:", style="color: black;"),
                                    # ui.output_text("matriz_p"),
                                    ui.p("Tiene un costo de: ", style="color: black;"),
                                    ui.output_text("costo_calc_p"),
                                    ui.p("La ruta es: ", style="color: black;"),
                                    ui.output_text("ruta_p"),
                                ),
                            open = True,
                        ),
                        ui.br(),
                    ),
                    
                    # Columna derecha - Imagen
                    (
                        ui.accordion(
                            ui.accordion_panel(
                                "Sección no.1",
                                ui.img(
                                    src="seccion_1.png", alt="Tipos de problemas de ruteo", 
                                    style="max-width: 80%; height: auto; display: block; margin: 0 auto;"
                                ),
                                ),
                            open=True,
                        ),
                        ui.accordion(
                            ui.accordion_panel(
                                "Costo en cada iteración",
                                ui.output_plot("costo_plot_p"), 
                                height="600px"
                                ),
                            open = False,
                        ),
                        ui.accordion(
                            ui.accordion_panel(
                                "Ruta óptima",
                            ui.output_plot("ruta_optima_grafico_p"), 
                            height="600px"
                            ),
                            open = False,
                        ),
                    ui.br()
                    ),
                    col_widths=[4,8],
                    height = 500
                ),
                class_="tab-content"
            )
        ),
    
        # simulador
        ui.nav_panel(
            "Simulador",
            ui.div(
                ui.h2("Simulador de puntos de entrega en Querétaro"),
                ui.p("En este simulador se puede visualizar el proceso con más o menos puntos de entrega, con camiones con más o menos volumen dentro de una sección especifica del municipio"),
                ui.p("Con esta pestaña se busca visualizar distintos escenarios para facilitar el entendimiento del programa y la versatilidad de la solución"),
                # Layout con dos columnas
                ui.layout_columns(
                    (
                    # Columna izquierda - Controles
                        ui.accordion(
                            ui.accordion_panel(
                                "Parámetros de la simulación",
                                ## n_hormigas=3, iteraciones=50, alpha=1, beta=3, rho=0.3, Q=100,
                                ui.p("Los parámetros son:", style="color: black;"),
                                ui.tags.ul(
                                    ui.tags.li("No. de hormigas = 3"),
                                    ui.tags.li("iteraciones = 50"), 
                                    ui.tags.li("alpha = 1"),
                                    ui.tags.li("beta = 3"),
                                    ui.tags.li("Q = 100"),
                                    ui.tags.li("rho = 0.3")
                                ),
                                ui.input_slider(
                                    "n_sample", 
                                    "Paquetes a entregar:", 
                                    min=2, 
                                    max=50, 
                                    value=4
                                ),
                                ui.input_slider(
                                    "camion", 
                                    "Capacidad del camión (en litros):", 
                                    min=5000, 
                                    max=90000, 
                                    value=20000,
                                    step = 5000
                                ),
                                ui.input_numeric(
                                    "seccion", 
                                    "Sección (1-9):", 
                                    min=1, 
                                    max=9, 
                                    value=3
                                ),
                            ),
                        open = True,
                        ),
                        ui.br(),
                        ui.accordion(
                                ui.accordion_panel(
                                    "Resultados",
                                    ui.p("La ruta óptima se encontro en la iteración: ", style="color: black;"),
                                    ui.output_text("iteracion_s"),
                                    #ui.p("La matriz de costos es:", style="color: black;"),
                                    #ui.output_text("matriz_s"),
                                    ui.p("Tiene un costo de: ", style="color: black;"),
                                    ui.output_text("costo_calc_s"),
                                    ui.p("La ruta es: ", style="color: black;"),
                                    ui.output_text("ruta_s"),
                                ),
                            open = True,
                        ),
                        ui.br(),
                    ),
                    # Columna derecha - Imagen
                    (
                        ui.accordion(
                            ui.accordion_panel(
                                "Sección seleccionada",
                                ui.output_image("imagen_seccion"), 
                                ),
                            open=True,
                        ),
                        ui.accordion(
                            ui.accordion_panel(
                                "Costo en cada iteración",
                                ui.output_plot("costo_plot_s"), 
                                height="600px"
                                ),
                            open = False,
                        ),
                        ui.accordion(
                            ui.accordion_panel(
                                "Ruta óptima",
                            ui.output_plot("ruta_optima_grafico_s"), 
                            height="600px"
                            ),
                            open = False,
                        ),
                    ui.br()
                    ),
                    col_widths=[4,8],
                    height = 500
                ),
                class_="tab-content"
            )
        ),

        # Más más más cada día sumamos más!! ahora somos diez millones de linduraaas!!
        ui.nav_panel(
            "Otros",
            ui.div(
                ui.h2("Resultados, trabajo futuro, escalabilidad, conclusiones y referencias..."),
                ui.div(
                    ui.p(ui.tags.b("Resultados")),
                    ui.p("El algoritmo de Colonia de Hormigas funcionó adecuadamente para el desarrollo de este problema. Encontró de manera óptima una ruta basado en las restricciones dadas y se adapta a múltiples soluciones. Por ejemplo, en caso de que se tengan vehículos con poco volumen, se realizan varias rutas que soporten su capacidad."),
                    class_="content-box"
                ),
                ui.br(),
                ui.div(
                    ui.p(ui.tags.b("Trabajo futuro")),
                    ui.p("En primer lugar, se propone la implementación de una solución que contemple la variedad en las restricciones de volumen de los vehículos, permitiendo modelar simultáneamente desde motocicletas hasta unidades de gran capacidad (tráilers). Esto representa un avance significativo respecto al enfoque actual, que opera bajo el supuesto de una flota homogénea."),

                    # 2. Multi-Objetivo (Tiempo y Costo)
                    ui.p("En segundo término, si bien se centró exclusivamente en la minimización del tiempo de ruteo, el costo como un objetivo crítico de optimización es crucial. Este análisis debe abarcar elementos económicos, como el consumo de combustible, los costos asociados al conductor y del impacto económico derivado del incumplimiento en los plazos de entrega al cliente."),

                    # 3. Herramienta de Validación y Simulación
                    ui.p("Asimismo, se identifica la utilidad de desarrollar un simulador para que el usuario pueda evaluar los costos de rutas alternativas al ingresar secuencias de entrega definidas y así verificar la efectividad del algoritmo bajo distintos escenarios y facilitar la experimentación controlada."),

                    # 4. Reconocimiento de Alternativas Algorítmicas
                    ui.p("Finalmente, si bien la implementación del algoritmo de Optimización por Colonia de Hormigas (ACO) fue ideal para la problemática abordada, se reconoce el valor de otros algoritmos matemáticos bioinspirados, tales como AG y PSO, al igual que otras metodologías de ruteo referenciadas en la pestaña de contexto."),
                    class_="content-box"
                ), 
                ui.br(),
                ui.div(
                    ui.p(ui.tags.b("Escalabilidad y aplicación")),
                    ui.p("Idealmente, se exploraría el uso de APIs que soporten más pares de coordenadas; sin embargo, modelar distintos tipos de vehiculos en una instancia, distintas ventanas de entrega de acuerdo a las preferencias de los clientes o inclusive un algoritmo en tiempo real que ajuste sobre la marcha, entre otros, serían conceptos que nos gustaría explorar en el futuro tomando esto como base."),
                    ui.p("Sin embargo, las posibilidades son muchas con los recursos actuales y se podrían explorar soluciones a otros problemas, por ejemplo: la recolección de basura, la distribución de víveres en caso de un desastre natural y por supuesto: problemas de última milla en otros sectores como el de alimentos y otros perecederos a domicilio."),
                    ui.p("Las posibilidades son muchas y el código crowdscourced y opensource como el openrouteservice lo hacen más fácil ahora que nunca."),
                    class_="content-box"
                ),   
                ui.br(),
                ui.div(
                    ui.p(ui.tags.b("Conclusiones")),
                    ui.p("En conclusión, los algoritmos matemáticos bio-inspirados nos invitan a buscar soluciones a los problemas más complejos en los lugares menos esperados. Nos invitan a pensar más allá del parámetro o el código y a enamorarnos del problema. Nos invitan a ser curiosos."),
                    class_="content-box"
                ),  
                ui.br(),
                ui.div(
                    ui.p(ui.tags.b("Referencias")),
                    ui.tags.ul(
                        ui.tags.li("Navata artículo: Navata. (s. f.). The Last Mile Delivery Problem: Why It Matters And How To Solve It. Recuperado de https://navata.com/cms/last-mile-delivery-problem/"),
                        ui.tags.li("BBC artículo: Sherman, N. (2018, 4 de enero). Crowded streets: Cities face a surge in online deliveries. BBC News – Business. Recuperado de https://www.bbc.com/news/business-42245367"), 
                        ui.tags.li("Gupta, A., & Saini, S. (2017, diciembre). An enhanced ant colony optimization algorithm for vehicle routing problem with time windows [Ponencia de conferencia]. 2017 Ninth International Conference on Advanced Computing (ICoAC). IEEE. https://doi.org/10.1109/ICoAC.2017.8441175")
                    ),
                    class_="content-box"
                ),  
                class_="tab-content"
            )
        ),
        id="main_tabs"
    )
)

# Server function
def server(input, output, session):

# PARA PARAMETROS --- VARIABLES CON P
    # resultado_actual como reactive calc en lugar de reactive.Value
    @reactive.Calc
    def resultado_actual_p():
        n_sample = 24
        seccion = 1
        n_hormigas = input.n_hormigas()
        iteraciones = input.iteraciones()
        alpha = input.alpha()
        beta = input.beta()
        rho = input.rho()
        Q = input.Q()
        capacidad_camion = 20000
        resultado = mejor_ruta(n_sample, seccion, n_hormigas, iteraciones, alpha, beta, rho, Q, capacidad_camion)
        return resultado

    @output
    @render.text
    def matriz_p():
        resultado = resultado_actual_p()
        if resultado is not None:
            return resultado["matriz_costos"]
        return ""

    @output
    @render.text
    def iteracion_p():
        resultado = resultado_actual_p()
        if resultado is not None:
            return resultado["iteracion"]
        return ""

    @output
    @render.text
    def costo_calc_p():
        resultado = resultado_actual_p()
        if resultado is not None:
            return resultado["costo"]
        return ""

    @output
    @render.text
    def ruta_p():
        resultado = resultado_actual_p()
        if resultado is not None:
            return resultado["ruta"]
        return ""

    @output
    @render.plot
    def costo_plot_p():
        resultado = resultado_actual_p()  # Esto hace que sea reactivo
        if resultado is not None and "historia" in resultado:
            historia_costos = resultado["historia"]
            
            # Crear la figura y ejes
            fig, ax = plt.subplots(figsize=(8, 4))
            
            # Graficar
            ax.plot(historia_costos, 'b-', linewidth=2)
            ax.set_xlabel("Iteración")
            ax.set_ylabel("Mejor costo")
            ax.grid(True)
            
            return fig
        else:
            # Retornar una figura vacía si no hay datos
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.text(0.5, 0.5, "No hay datos disponibles", 
                   ha='center', va='center', transform=ax.transAxes)
            return fig

    @output
    @render.plot
    def ruta_optima_grafico_p():
        resultado = resultado_actual_p()  # Esto hace que sea reactivo
        
        if resultado is not None and "Matriz_con_id" in resultado:
            coordenadas_id = resultado["Matriz_con_id"]
        
        if resultado is not None and "ruta" in resultado: 
            mejor_ruta_global = resultado["ruta"]

        # --- Crear figura ---
        fig, ax = plt.subplots(figsize=(10,10))

        # --- Dibujar toda la red como fondo ---
        nodes, edges = ox.graph_to_gdfs(G)
        edges.plot(ax=ax, linewidth=0.5, edgecolor='lightgray')

        # --- Colores distintos para cada ruta ---
        n_rutas = len(mejor_ruta_global)
        colores = cm.get_cmap('tab10', n_rutas)  # colormap de matplotlib

        # --- Guardar todos los puntos para límites ---
        all_x, all_y = [], []

        # --- Dibujar rutas ---
        for ruta_idx, camino in enumerate(mejor_ruta_global):
            color_ruta = colores(ruta_idx)

            for i in range(len(camino) - 1):
                nodo_origen = ox.distance.nearest_nodes(
                    G,
                    X=coordenadas_id['longitude'][camino[i]],
                    Y=coordenadas_id['latitude'][camino[i]]
                )
                nodo_destino = ox.distance.nearest_nodes(
                    G,
                    X=coordenadas_id['longitude'][camino[i+1]],
                    Y=coordenadas_id['latitude'][camino[i+1]]
                )

                # --- Intentar obtener ruta en la red ---
                try:
                    ruta_nodos = nx.shortest_path(G, nodo_origen, nodo_destino, weight='length')
                except nx.NetworkXNoPath:
                    print(f"No hay ruta entre {nodo_origen} y {nodo_destino}, se dibuja línea directa.")
                    ruta_nodos = [nodo_origen, nodo_destino]  # fallback: línea recta

                # --- Guardar coordenadas de la ruta ---
                all_x.extend([G.nodes[n]['x'] for n in ruta_nodos])
                all_y.extend([G.nodes[n]['y'] for n in ruta_nodos])

                # --- Graficar la ruta ---
                ruta_edges = edges.loc[
                    edges.index.get_level_values(0).isin(ruta_nodos) &
                    edges.index.get_level_values(1).isin(ruta_nodos)
                ]
                if not ruta_edges.empty:
                    ruta_edges.plot(ax=ax, linewidth=2, edgecolor=color_ruta)
                else:
                    # Si no hay edges, dibujar línea recta
                    x_coords = [G.nodes[n]['x'] for n in ruta_nodos]
                    y_coords = [G.nodes[n]['y'] for n in ruta_nodos]
                    ax.plot(x_coords, y_coords, linewidth=2, color=color_ruta)

            # --- Nodos inicio y fin ---
            nodo_inicio = ox.distance.nearest_nodes(
                G,
                X=coordenadas_id['longitude'][camino[0]],
                Y=coordenadas_id['latitude'][camino[0]]
            )
            nodo_fin = ox.distance.nearest_nodes(
                G,
                X=coordenadas_id['longitude'][camino[-1]],
                Y=coordenadas_id['latitude'][camino[-1]]
            )
            all_x.extend([G.nodes[nodo_inicio]['x'], G.nodes[nodo_fin]['x']])
            all_y.extend([G.nodes[nodo_inicio]['y'], G.nodes[nodo_fin]['y']])

            # --- Depósito (solo en la primera ruta) ---
            if ruta_idx == 0:
                ax.scatter(
                    G.nodes[nodo_inicio]['x'],
                    G.nodes[nodo_inicio]['y'],
                    c='k', marker='x', s=80, label='Depósito', zorder=5
                )
        # --- Ajustar límites automáticamente según todos los puntos ---
        margin = 0.001
        ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
        ax.set_ylim(min(all_y) - margin, max(all_y) + margin)
        
        # --- Agregar texto a todos los puntos ---
        # --- Clientes y depósito ---
        for idx, row in coordenadas_id.iterrows():
        # Graficar el punto
            if idx!=0:
                ax.scatter(
                    row['longitude'],
                    row['latitude'],
                    c='red' if row['id'] != 0 else 'k',  # depósito negro, clientes rojo
                    s=60 if row['id'] != 0 else 80,
                    marker='o' if row['id'] != 0 else 'x',
                    zorder=5
                )
                # Agregar texto
                ax.text(
                    row['longitude'] + 0.00005,  # pequeño desplazamiento para que no tapen el punto
                    row['latitude'] + 0.00005,
                    str(idx),
                    fontsize=8,
                    color='black',
                    zorder=6
                )

# PARA SIMULADO --- VARIABLES CON S
    # resultado_actual como reactive calc en lugar de reactive.Value
    @reactive.Calc
    def resultado_actual():
        n_sample = input.n_sample()
        seccion = input.seccion()
        camion = input.camion()
        resultado = mejor_ruta(n_sample, seccion, capacidad_camion=camion)
        return resultado

    @output
    @render.text
    def matriz_s():
        resultado = resultado_actual()
        if resultado is not None:
            return resultado["matriz_costos"]
        return ""

    @output
    @render.text
    def iteracion_s():
        resultado = resultado_actual()
        if resultado is not None:
            return resultado["iteracion"]
        return ""

    @output
    @render.text
    def costo_calc_s():
        resultado = resultado_actual()
        if resultado is not None:
            return resultado["costo"]
        return ""

    @output
    @render.text
    def ruta_s():
        resultado = resultado_actual()
        if resultado is not None:
            return resultado["ruta"]
        return ""

    @output
    @render.plot
    def costo_plot_s():
        resultado = resultado_actual()  # Esto hace que sea reactivo
        if resultado is not None and "historia" in resultado:
            historia_costos = resultado["historia"]
            
            # Crear la figura y ejes
            fig, ax = plt.subplots(figsize=(8, 4))
            
            # Graficar
            ax.plot(historia_costos, 'b-', linewidth=2)
            ax.set_xlabel("Iteración")
            ax.set_ylabel("Mejor costo")
            ax.grid(True)
            
            return fig
        else:
            # Retornar una figura vacía si no hay datos
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.text(0.5, 0.5, "No hay datos disponibles", 
                   ha='center', va='center', transform=ax.transAxes)
            return fig

    @render.image
    def imagen_seccion():
        seccion = input.seccion()
        ruta_imagen = f"seccion_{seccion}.png"  # Si están en el mismo directorio
        return {"src": ruta_imagen, "alt": f"Sección {seccion}", "style": "max-width: 100%; height: auto; display: block; margin: 0 auto;object-fit:contain; max-height:80vh;"}

    @output
    @render.plot
    def ruta_optima_grafico_s():
        resultado = resultado_actual()  # Esto hace que sea reactivo
        if resultado is not None and "Matriz_con_id" in resultado:
            coordenadas_id = resultado["Matriz_con_id"]
        
        if resultado is not None and "ruta" in resultado: 
            mejor_ruta_global = resultado["ruta"]

        # --- Crear figura ---
        fig, ax = plt.subplots(figsize=(10,10))

        # --- Dibujar toda la red como fondo ---
        nodes, edges = ox.graph_to_gdfs(G)
        edges.plot(ax=ax, linewidth=0.5, edgecolor='lightgray')

        # --- Colores distintos para cada ruta ---
        n_rutas = len(mejor_ruta_global)
        colores = cm.get_cmap('tab10', n_rutas)  # colormap de matplotlib

        # --- Guardar todos los puntos para límites ---
        all_x, all_y = [], []

        # --- Dibujar rutas ---
        for ruta_idx, camino in enumerate(mejor_ruta_global):
            color_ruta = colores(ruta_idx)

            for i in range(len(camino) - 1):
                nodo_origen = ox.distance.nearest_nodes(
                    G,
                    X=coordenadas_id['longitude'][camino[i]],
                    Y=coordenadas_id['latitude'][camino[i]]
                )
                nodo_destino = ox.distance.nearest_nodes(
                    G,
                    X=coordenadas_id['longitude'][camino[i+1]],
                    Y=coordenadas_id['latitude'][camino[i+1]]
                )

                # --- Intentar obtener ruta en la red ---
                try:
                    ruta_nodos = nx.shortest_path(G, nodo_origen, nodo_destino, weight='length')
                except nx.NetworkXNoPath:
                    print(f"No hay ruta entre {nodo_origen} y {nodo_destino}, se dibuja línea directa.")
                    ruta_nodos = [nodo_origen, nodo_destino]  # fallback: línea recta

                # --- Guardar coordenadas de la ruta ---
                all_x.extend([G.nodes[n]['x'] for n in ruta_nodos])
                all_y.extend([G.nodes[n]['y'] for n in ruta_nodos])

                # --- Graficar la ruta ---
                ruta_edges = edges.loc[
                    edges.index.get_level_values(0).isin(ruta_nodos) &
                    edges.index.get_level_values(1).isin(ruta_nodos)
                ]
                if not ruta_edges.empty:
                    ruta_edges.plot(ax=ax, linewidth=2, edgecolor=color_ruta)
                else:
                    # Si no hay edges, dibujar línea recta
                    x_coords = [G.nodes[n]['x'] for n in ruta_nodos]
                    y_coords = [G.nodes[n]['y'] for n in ruta_nodos]
                    ax.plot(x_coords, y_coords, linewidth=2, color=color_ruta)

            # --- Nodos inicio y fin ---
            nodo_inicio = ox.distance.nearest_nodes(
                G,
                X=coordenadas_id['longitude'][camino[0]],
                Y=coordenadas_id['latitude'][camino[0]]
            )
            nodo_fin = ox.distance.nearest_nodes(
                G,
                X=coordenadas_id['longitude'][camino[-1]],
                Y=coordenadas_id['latitude'][camino[-1]]
            )
            all_x.extend([G.nodes[nodo_inicio]['x'], G.nodes[nodo_fin]['x']])
            all_y.extend([G.nodes[nodo_inicio]['y'], G.nodes[nodo_fin]['y']])

            # --- Depósito (solo en la primera ruta) ---
            if ruta_idx == 0:
                ax.scatter(
                    G.nodes[nodo_inicio]['x'],
                    G.nodes[nodo_inicio]['y'],
                    c='k', marker='x', s=80, label='Depósito', zorder=5
                )
            # --- Ajustar límites automáticamente según todos los puntos ---
            margin = 0.001
            ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
            ax.set_ylim(min(all_y) - margin, max(all_y) + margin)

        # --- Agregar texto a todos los puntos ---
        # --- Clientes y depósito ---
        for idx, row in coordenadas_id.iterrows():
        # Graficar el punto
            if idx!=0:
                ax.scatter(
                    row['longitude'],
                    row['latitude'],
                    c='red' if row['id'] != 0 else 'k',  # depósito negro, clientes rojo
                    s=60 if row['id'] != 0 else 80,
                    marker='o' if row['id'] != 0 else 'x',
                    zorder=5
                )
                # Agregar texto
                ax.text(
                    row['longitude'] + 0.00005,  # pequeño desplazamiento para que no tapen el punto
                    row['latitude'] + 0.00005,
                    str(idx),
                    fontsize=8,
                    color='black',
                    zorder=6
                )


# Create the app
www_dir = pathlib.Path(__file__).parent / "www"
app = App(app_ui, server, static_assets=www_dir)


if __name__ == "__main__":
    app.run()