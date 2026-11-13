import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt
import heapq
import pandas as pd
from shapely.ops import polygonize, unary_union

# 1) Descargar la red
ciudad = "Santiago de Querétaro, Querétaro, Mexico"
G = ox.graph_from_place(ciudad, network_type="drive")

# 2) Proyectar a metrico
G = ox.project_graph(G)

#Puntos Generadores en grados (Sucursales)

seed_points_latlon = [
    (	20.65185389	,	-100.4332575	)	,	#	urban center
    (	20.62502622	,	-100.4399523	)	,	#	plaza revolución
    (	20.60992354	,	-100.4186663	)	,	#	cinco de febrero
    (	20.55676451	,	-100.4201212	)	,	#	pueblito
    (	20.58607147	,	-100.3921382	)	,	#	constituyentes
    (	20.58775044	,	-100.3791939	)	,	#	cons. Auditorio
    (	20.59982721	,	-100.3931387	)	,	#	centro
    (	20.59585588	,	-100.3694748	)	,	#	bernardo
    (	20.61631254	,	-100.3981287	)	,	#	walmart bernardo
    (	20.63031123	,	-100.3991128	)	,	#	zip and go
]

# Crear puntos (lon, lat)
points_geom = [Point(lon, lat) for lat, lon in seed_points_latlon]

# Crear GeoDataFrame con CRS WGS84
seeds_gdf = gpd.GeoDataFrame(geometry=points_geom, crs="EPSG:4326")

# Reproyectar a EPSG:32614
seeds_gdf_32614 = seeds_gdf.to_crs("EPSG:32614")

# Ver resultados
print(seeds_gdf_32614)

# 3) Semillas: lista de (lon, lat) o (lat, lon) -> convertir a puntos proyectados
seed_points_ll = [
(350688.805, 2284276.885),
(349964.944, 2281313.378),
(352168.595, 2279622.114),
(351965.678, 2273739.096),
(354910.784, 2276957.996),
(356261.616, 2277132.368),
(354819.521, 2278481.542),
(357282.223, 2278021.025),
(354315.106, 2280310.805),
(354225.877, 2281861.242)
]

# lon,lat
seeds_gdf = gpd.GeoDataFrame(geometry=[Point(xy) for xy in seed_points_ll], crs="EPSG:32614")
seeds_gdf = seeds_gdf.to_crs(ox.graph_to_gdfs(G, nodes=False, edges=True).crs)  # proyectar al mismo CRS

#Verificar que ambos son el mismo crs
print(seeds_gdf.crs)
print(ox.graph_to_gdfs(G, nodes=False, edges=True).crs)

fig, ax = ox.plot_graph(G, bgcolor='black', node_size=0.8, edge_color='white', show=False, close=False)

seeds_gdf.plot(ax=ax, color='blue', markersize=50, alpha=0.8)

plt.show()

# 4) Snap seeds to closest graph node
nodes, edges = ox.graph_to_gdfs(G)
# encontrar nodo más cercano para cada semilla
seed_node_ids = []
for geom in seeds_gdf.geometry:
    # nearest_nodes espera x,y en coordenadas proyectadas
    nearest = ox.distance.nearest_nodes(G, X=geom.x, Y=geom.y)
    seed_node_ids.append(nearest)

# 5) Multi-source Dijkstra: asigna a cada nodo la semilla más cercana por distancia (edge length)
# Preparar distancia por arista (si no existe, usar 'length' que osmnx crea)
for u, v, k, data in G.edges(keys=True, data=True):
    if 'length' not in data:
        data['length'] = ox.utils_graph.get_edge_attribute(G, 'length', default=1)

# Crear una dict de distancia y label: inicializar con semillas

INF = 10**12
dist = {n: INF for n in G.nodes}
label = {n: None for n in G.nodes}
pq = []
for i, s in enumerate(seed_node_ids):
    dist[s] = 0
    label[s] = i  # etiqueta 0..N-1
    heapq.heappush(pq, (0, s))

# Dijkstra multi-origen
while pq:
    d, u = heapq.heappop(pq)
    if d > dist[u]:
        continue
    for v, attr in G[u].items():
        # attr is dict of keys->edge dicts because MultiDiGraph; iterate keys
        for key, ed in attr.items():
            w = ed.get('length', 1.0)
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                label[v] = label[u]
                heapq.heappush(pq, (nd, v))

# 6) Añadir etiquetas a nodos geodataframe para visualizar
nodes['label'] = nodes.index.map(label)
nodes = nodes.dropna(subset=['label'])
nodes['label'] = nodes['label'].astype(int)

# 7) Visualizar (cada color = semilla)
fig, ax = plt.subplots(figsize=(10,10))
edges.plot(ax=ax, linewidth=0.8, alpha=0.5, color='black')
nodes.plot(column='label', ax=ax, markersize=15, cmap='tab10', legend=True)
for i, geom in enumerate(seeds_gdf.geometry):
  ax.scatter(geom.x, geom.y, s=50, marker='x', color='k')
plt.title("Asignación por red: cada nodo coloreado por\n semilla más cercana (distancia por calles)")
plt.show()

## guardar información 
# Script para guardar coordenadas y secciones en archivo

# Función para obtener información de cada nodo
def save_voronoi_results(G, label, seed_node_ids, seeds_gdf, filename="voronoi_assignments.csv"):
    """
    Guarda las asignaciones de Voronoi en un archivo CSV
    """
    results = []
    
    # Información de las semillas
    seed_info = {}
    for i, seed_node in enumerate(seed_node_ids):
        if seed_node in G.nodes:
            node_data = G.nodes[seed_node]
            seed_info[i] = {
                'seed_lat': seeds_gdf.iloc[i].geometry.y if i < len(seeds_gdf) else None,
                'seed_lon': seeds_gdf.iloc[i].geometry.x if i < len(seeds_gdf) else None,
                'seed_node_id': seed_node
            }
    
    # Recolectar datos de todos los nodos
    for node_id, section in label.items():
        if section is not None and node_id in G.nodes:
            node_data = G.nodes[node_id]
            
            # Convertir coordenadas proyectadas a lat/lon si es necesario
            if 'x' in node_data and 'y' in node_data:
                # Asumiendo que las coordenadas están en EPSG:32614, convertirlas a WGS84
                point_proj = Point(node_data['x'], node_data['y'])
                gdf_proj = gpd.GeoDataFrame([point_proj], columns=['geometry'], crs=G.graph['crs'])
                gdf_wgs84 = gdf_proj.to_crs("EPSG:4326")
                lat = gdf_wgs84.geometry.iloc[0].y
                lon = gdf_wgs84.geometry.iloc[0].x
            else:
                lat = lon = None
            
            results.append({
                'node_id': node_id,
                'latitude': lat,
                'longitude': lon,
                'section': int(section),
                'seed_lat': seed_info.get(section, {}).get('seed_lat'),
                'seed_lon': seed_info.get(section, {}).get('seed_lon'),
                'seed_node_id': seed_info.get(section, {}).get('seed_node_id')
            })
    
    # Crear DataFrame y guardar
    df = pd.DataFrame(results)
    df.to_csv(filename, index=False, encoding='utf-8')
    print(f"Archivo guardado: {filename}")
    print(f"Total de nodos asignados: {len(df)}")
    print(f"Número de secciones: {df['section'].nunique()}")
    
    return df

# Ejecutar la función para guardar resultados
df_results = save_voronoi_results(G, label, seed_node_ids, seeds_gdf_32614, "queretaro_voronoi_sections.csv")

# Mostrar preview de los datos
print("\nPrimeras 10 filas del archivo:")
print(df_results.head(10))

# Estadísticas básicas
print("\nEstadísticas por sección:")
section_counts = df_results['section'].value_counts().sort_index()
print(section_counts)



## Mostrar solo los contornos de las regiones
fig, ax = plt.subplots(figsize=(12,12))

# Crear polígonos de Voronoi aproximados
voronoi_polygons = []
for section_id in range(len(seed_node_ids)):
    # Nodos de esta sección
    section_nodes = nodes[nodes['label'] == section_id]
    if len(section_nodes) > 0:
        # Crear convex hull o polígono aproximado
        points = section_nodes.geometry.unary_union
        hull = points.convex_hull
        voronoi_polygons.append(hull)

# Plotear contornos
voronoi_gdf = gpd.GeoDataFrame(geometry=voronoi_polygons, crs=nodes.crs)
voronoi_gdf.boundary.plot(ax=ax, linewidth=2, alpha=0.7)

# Calles de fondo
edges.plot(ax=ax, linewidth=0.3, alpha=0.3, color='gray')

# Tus sucursales
for i, geom in enumerate(seeds_gdf.geometry):
    ax.scatter(geom.x, geom.y, s=80, color='red', edgecolor='black', linewidth=1.5)

plt.title("Contornos de Regiones de Voronoi")
plt.show()



## Visualizar UNA MUESTRA de nodos 
fig, ax = plt.subplots(figsize=(12,12))

# Plotear todas las calles
edges.plot(ax=ax, linewidth=0.8, alpha=0.5, color='black')

# FILTRAR: Mostrar solo cada 10mo nodo para reducir densidad
nodes_filtered = nodes.iloc[::10]  # Toma cada 10mo nodo

# Plotear nodos filtrados
nodes_filtered.plot(column='label', ax=ax, markersize=8, cmap='tab10', legend=True)

# Resaltar las semillas (tus sucursales importantes)
for i, geom in enumerate(seeds_gdf.geometry):
    ax.scatter(geom.x, geom.y, s=100, marker='*', color='red', edgecolor='black', linewidth=1.5)

plt.title("Regiones de Voronoi - Puntos filtrados para mejor visualización")
plt.show()