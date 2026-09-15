import pandas as pd
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.integrate import trapezoid
from io import StringIO

# Define default color palette for ranges
DEFAULT_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']

# Default x ranges (can be overridden by user input)
X_RANGES = [
    {'name': 'WT-WT1', 'range': (3268.0, 3279.0), 'color': '#1f77b4'},
    {'name': 'WT-H43R1', 'range': (3114.0, 3123.0), 'color': '#ff7f0e'},
    {'name': 'H43R-H43R1', 'range': (2959.5, 2967.0), 'color': '#2ca02c'},
]

def calculate_area(df, x_start, x_end):
    """Calculate area under the curve for a given x range using trapezoidal rule."""
    df_range = df[(df['x'] >= x_start) & (df['x'] <= x_end)]
    if len(df_range) == 0:
        return 0
    area = trapezoid(df_range['y'], df_range['x'])
    return area if not np.isnan(area) else 0

def read_data_file(file_content):
    """Read mass spectrometry data from file content."""
    if isinstance(file_content, bytes):
        file_content = file_content.decode('utf-8')
    df = pd.read_csv(StringIO(file_content), delimiter=r'\s+', header=None, names=['x', 'y'])
    df["x"] = pd.to_numeric(df["x"], errors="coerce")
    df["y"] = pd.to_numeric(df["y"], errors="coerce")
    df = df.dropna().sort_values("x")
    return df

def read_csv_file(file_content):
    """Read exported mass spectrometry CSV file."""
    if isinstance(file_content, bytes):
        file_content = file_content.decode('utf-8')

    for skiprows in (8, 0):
        for header in (None, 0):
            try:
                df = pd.read_csv(StringIO(file_content), sep=",", skiprows=skiprows, header=header)
                if df.shape[1] < 2:
                    continue

                df = df.iloc[:, :2].copy()
                df.columns = ["x", "y"]
                df["x"] = pd.to_numeric(df["x"], errors="coerce")
                df["y"] = pd.to_numeric(df["y"], errors="coerce")
                df = df.dropna().sort_values("x")
                if len(df) > 0:
                    return df
            except Exception:
                continue

    raise ValueError("Could not read CSV file. Please use two columns: m/z and intensity.")

def process_file(file_content=None, file_path=None, custom_ranges=None):
    """
    Process a single file and calculate all areas.
    
    Args:
        file_content: File bytes for .txt and .csv files
        file_path: Path to the file, used to detect file type
        custom_ranges: List of dicts with 'name', 'range' tuple (start, end)
    """
    if file_path and file_path.lower().endswith('.csv'):
        df = read_csv_file(file_content)
    else:
        df = read_data_file(file_content)
    
    # Use custom ranges if provided, otherwise use defaults
    ranges_to_use = custom_ranges if custom_ranges else X_RANGES
    
    results = []
    for idx, item in enumerate(ranges_to_use):
        name = item['name']
        x_start, x_end = item['range']
        area = calculate_area(df, x_start, x_end)
        color = item.get('color', DEFAULT_COLORS[idx % len(DEFAULT_COLORS)])
        results.append({
            'name': name,
            'x_start': x_start,
            'x_end': x_end,
            'area': area,
            'color': color
        })
    
    results_df = pd.DataFrame(results)
    
    # Calculate group totals based on name prefixes
    total_areas = {}
    
    # Find unique prefixes (assuming format "PREFIX-SUB")
    prefixes = set()
    for name in results_df['name']:
        if '-' in name:
            prefix = '-'.join(name.split('-')[:-1])
            prefixes.add(prefix)
    
    for prefix in sorted(prefixes):
        sub_ranges = results_df[results_df['name'].str.startswith(prefix)]
        total_key = f"{prefix}_total"
        total_areas[total_key] = sub_ranges['area'].sum()
    
    return df, results_df, total_areas

def plot_data_with_ranges(df, results_df=None, custom_ranges=None, zoom_range=None):
    """Plot the data with highlighted regions for each x range."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot the main data
    ax.plot(df['x'], df['y'], 'k-', linewidth=1.5, label='Data')
    
    # Use custom ranges if provided, otherwise use defaults
    ranges_to_use = custom_ranges if custom_ranges else X_RANGES
    
    # Get colors from results_df if available
    color_map = {}
    if results_df is not None:
        for _, row in results_df.iterrows():
            color_map[row['name']] = row.get('color', '#1f77b4')
    
    # Highlight the ranges
    for idx, item in enumerate(ranges_to_use):
        x_start, x_end = item['range']
        name = item['name']
        color = color_map.get(name, item.get('color', DEFAULT_COLORS[idx % len(DEFAULT_COLORS)]))
        
        df_range = df[(df['x'] >= x_start) & (df['x'] <= x_end)]
        if len(df_range) > 0:
            ax.fill_between(df_range['x'], df_range['y'], alpha=0.3, color=color, label=name)
            ax.plot(df_range['x'], df_range['y'], color=color, linewidth=2)
    
    ax.set_xlabel('m/z', fontsize=12)
    ax.set_ylabel('Intensity', fontsize=12)
    ax.set_title('Mass Spectrometry Data - Area Under Curve Analysis', fontsize=14)
    if zoom_range:
        zoom_start, zoom_end = zoom_range
        ax.set_xlim(zoom_start, zoom_end)
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig

def create_summary_table(results_df, total_areas):
    """Create a formatted summary table."""
    summary_data = []
    
    # Add individual ranges
    for _, row in results_df.iterrows():
        summary_data.append({
            'Range': row['name'],
            'Start': f"{row['x_start']:.1f}",
            'End': f"{row['x_end']:.1f}",
            'Area': f"{row['area']:.4f}"
        })
    
    # Add a separator and totals
    if len(total_areas) > 0:
        summary_data.append({'Range': '---', 'Start': '---', 'End': '---', 'Area': '---'})
        
        for key, value in sorted(total_areas.items()):
            # Convert key format (e.g., 'WT-WT_total' -> 'WT-WT Total')
            total_name = key.replace('_total', ' Total').replace('_', ' ')
            summary_data.append({
                'Range': total_name,
                'Start': '-',
                'End': '-',
                'Area': f"{value:.4f}"
            })
    
    return pd.DataFrame(summary_data)

def create_multi_file_summary(file_results):
    """Create one summary row per file with one area column per range."""
    rows = []

    for file_result in file_results:
        row = {"File": file_result["file_name"]}
        # Use enumerate to get a 1-based index (i + 1) for every range
        for i, (_, result_row) in enumerate(file_result["results_df"].iterrows()):
            
            # Create a completely unique column name showing the number, name, and m/z start/end
            col_name = f"Range {i + 1}: {result_row['name']} ({result_row['x_start']:.1f}-{result_row['x_end']:.1f})"
            
            row[col_name] = result_row["area"]

        rows.append(row)

    return pd.DataFrame(rows)
