# este code es para guardar los archivos de lat y lon de cada sección 

import pandas as pd
from pyproj import Transformer

def process_data(file_path, selected_columns=None, section_filter=None):
    # Read the CSV file
    try:
        df = pd.read_csv(file_path)
        print(f"Successfully loaded data with {len(df)} rows and {len(df.columns)} columns")
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None
    
    # Select specific columns if provided
    if selected_columns is not None:
        # Check if all selected columns exist
        missing_cols = [col for col in selected_columns if col not in df.columns]
        if missing_cols:
            print(f"Warning: The following columns were not found: {missing_cols}")
            # Keep only the columns that exist
            selected_columns = [col for col in selected_columns if col in df.columns]
        
        if selected_columns:
            df = df[selected_columns]
            print(f"Selected {len(selected_columns)} columns: {selected_columns}")
    
    # Filter by section if provided
    if section_filter is not None:
        # First, check if there's a section column
        section_cols = [col for col in df.columns if 'section' in col.lower()]
        
        if section_cols:
            section_col = section_cols[0]  # Use the first section column found
            if isinstance(section_filter, list):
                df = df[df[section_col].isin(section_filter)]
            else:
                df = df[df[section_col] == section_filter]
            print(f"Filtered by {section_col} = {section_filter}")
            print(f"Remaining rows: {len(df)}")
        else:
            print("No section column found. Available columns:")
            for col in df.columns:
                print(f"  - {col}")
    
    return df

# Seleccionar una sección 
section_value = 0
    
result_df = process_data(
    file_path=r"C:\Users\saraa\Desktop\proyecto-rutas\sucursales-entregas\queretaro_voronoi_sections.csv",
    selected_columns=['latitude', 'longitude', 'section'],
    section_filter=section_value
)
    
df = result_df
df = df.rename(columns={'latitude': 'northing', 'longitude': 'easting'}) # UTM, no grados
tr = Transformer.from_crs("EPSG:32614", "EPSG:4326", always_xy=True)
lon, lat = tr.transform(df['easting'].values, df['northing'].values)

df['longitude'] = lon
df['latitude']  = lat

bad = ~df['latitude'].between(-90, 90) | ~df['longitude'].between(-180, 180)
print(f"Fuera de rango: {bad.sum()} filas")

coords_list = df[['latitude', 'longitude']].to_numpy().tolist()

if coords_list is not None:
    output_path = r"C:\Users\saraa\Desktop\proyecto-rutas\paso5y6\filtrado_0.csv"
    result_df.to_csv(output_path, index=False)
