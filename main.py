import gradio as gr
import os
from auc import process_file, plot_data_with_ranges, create_multi_file_summary

MAX_RANGES = 10

def normalize_uploaded_files(uploaded_files):
    """Return uploaded Gradio files as a list."""
    if uploaded_files is None:
        return []
    if isinstance(uploaded_files, list):
        return uploaded_files
    return [uploaded_files]

def get_file_path(uploaded_file):
    return uploaded_file.name if hasattr(uploaded_file, 'name') else str(uploaded_file)

def is_supported_file(file_path):
    return file_path.lower().endswith((".csv", ".txt"))

def get_range_count(range_count):
    """Clamp the selected number of visible ranges."""
    try:
        range_count = int(range_count)
    except (TypeError, ValueError):
        range_count = 1
    return max(1, min(MAX_RANGES, range_count))

def read_uploaded_file(uploaded_file, custom_ranges=None):
    file_path = get_file_path(uploaded_file)
    with open(file_path, 'rb') as f:
        file_content = f.read()
    return process_file(file_content=file_content, file_path=file_path, custom_ranges=custom_ranges)

def get_mz_bounds(uploaded_files):
    """Extract combined m/z bounds from uploaded files."""
    try:
        files = normalize_uploaded_files(uploaded_files)
        if not files:
            return None, None, "No files uploaded"

        mins = []
        maxes = []

        for uploaded_file in files:
            file_path = get_file_path(uploaded_file)
            if not is_supported_file(file_path):
                return None, None, f"Invalid file type: {os.path.basename(file_path)}"

            df, _, _ = read_uploaded_file(uploaded_file, custom_ranges=[])
            if df is None or len(df) == 0:
                return None, None, f"Could not extract m/z data from {os.path.basename(file_path)}"

            mins.append(float(df['x'].min()))
            maxes.append(float(df['x'].max()))

        mz_min = min(mins)
        mz_max = max(maxes)
        return mz_min, mz_max, f"combined m/z range: {mz_min:.2f} - {mz_max:.2f}"
    
    except Exception as e:
        return None, None, f"Error: {str(e)}"

def build_ranges_from_dynamic_inputs(*args, range_count=None):
    """
    Build custom ranges from dynamic inputs.
    Args come in groups of (x1, x2, name) for each visible range.
    """
    custom_ranges = []
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
    active_arg_count = get_range_count(range_count) * 3 if range_count is not None else len(args)
    args = args[:active_arg_count]
    
    # Process in groups of 3
    for i in range(0, len(args), 3):
        if i + 2 < len(args):
            x1, x2, name = args[i], args[i+1], args[i+2]
            
            # Only add if all fields are filled
            if x1 is not None and x2 is not None and name and name.strip():
                try:
                    x1_float = float(x1)
                    x2_float = float(x2)
                    
                    custom_ranges.append({
                        'name': name.strip(),
                        'range': (x1_float, x2_float),
                        'color': colors[len(custom_ranges) % len(colors)]
                    })
                except (ValueError, TypeError):
                    continue
    
    return custom_ranges if custom_ranges else None

def validate_ranges(uploaded_files, range_count, *args):
    """
    Validate ranges before analysis.
    Returns (is_valid, error_message)
    """
    try:
        files = normalize_uploaded_files(uploaded_files)
        if not files:
            return False, "❌ No files uploaded"
        
        # Get m/z bounds
        mz_min, mz_max, _ = get_mz_bounds(files)
        if mz_min is None:
            return False, "❌ Cannot extract m/z range from files"
        
        # Build ranges from inputs
        custom_ranges = build_ranges_from_dynamic_inputs(*args, range_count=range_count)
        
        if not custom_ranges:
            return False, "❌ Please fill in at least one complete range (x1, x2, name)"
        
        # Validate each range
        for range_item in custom_ranges:
            name = range_item['name']
            x1, x2 = range_item['range']
            
            # Check x1 < x2
            if x1 >= x2:
                return False, f"❌ Range '{name}': x1 ({x1}) must be less than x2 ({x2})"
            
            # Check bounds
            if x1 < mz_min or x1 > mz_max:
                return False, f"❌ Range '{name}': x1 ({x1}) is outside spectrum bounds ({mz_min:.2f} - {mz_max:.2f})"
            
            if x2 < mz_min or x2 > mz_max:
                return False, f"❌ Range '{name}': x2 ({x2}) is outside spectrum bounds ({mz_min:.2f} - {mz_max:.2f})"
        
        return True, f"✓ All {len(custom_ranges)} ranges validated successfully for {len(files)} file(s)"
    
    except Exception as e:
        return False, f"❌ Validation error: {str(e)}"

def build_zoom_range(zoom_start, zoom_end):
    """Build a valid optional zoom range for the spectrum plot."""
    if zoom_start is None and zoom_end is None:
        return None
    if zoom_start is None or zoom_end is None:
        raise ValueError("Please fill both zoom start and zoom end, or leave both empty.")

    zoom_start = float(zoom_start)
    zoom_end = float(zoom_end)
    if zoom_start >= zoom_end:
        raise ValueError("Spectrum close-up start must be smaller than end.")
    return (zoom_start, zoom_end)

def update_spectrum_choices(uploaded_files):
    """Fill the spectrum selector from the uploaded file names."""
    files = normalize_uploaded_files(uploaded_files)
    choices = [
        os.path.basename(get_file_path(uploaded_file))
        for uploaded_file in files
        if is_supported_file(get_file_path(uploaded_file))
    ]

    if not choices:
        return gr.Dropdown(choices=[], value=None, interactive=False)

    return gr.Dropdown(choices=choices, value=choices[0], interactive=True)

def update_range_visibility(range_count):
    """Show only the number of range boxes selected by the user."""
    visible_count = get_range_count(range_count)
    return [gr.update(visible=i < visible_count) for i in range(MAX_RANGES)]

def plot_selected_spectrum(selected_file_name, uploaded_files, zoom_start, zoom_end, range_count, *args):
    """Show the selected uploaded spectrum with the current ranges and zoom."""
    if not selected_file_name:
        return None

    files = normalize_uploaded_files(uploaded_files)
    custom_ranges = build_ranges_from_dynamic_inputs(*args, range_count=range_count)
    if not files or not custom_ranges:
        return None

    zoom_range = build_zoom_range(zoom_start, zoom_end)

    for uploaded_file in files:
        file_path = get_file_path(uploaded_file)
        if os.path.basename(file_path) == selected_file_name:
            df, results_df, _ = read_uploaded_file(uploaded_file, custom_ranges=custom_ranges)
            return plot_data_with_ranges(df, results_df, custom_ranges, zoom_range=zoom_range)

    return None

def analyze_spectrum(uploaded_files, selected_file_name, zoom_start, zoom_end, range_count, *args):
    """
    Main function to analyze uploaded mass spectrometry file.
    Args contain x1, x2, name for each of up to 10 ranges.
    Returns plot and summary table.
    """
    try:
        files = normalize_uploaded_files(uploaded_files)
        if not files:
            return None, None, "❌ Please upload at least one file first.", gr.Dropdown(choices=[], value=None, interactive=False)
        
        # Validate ranges
        is_valid, validation_msg = validate_ranges(files, range_count, *args)
        if not is_valid:
            return None, None, validation_msg, update_spectrum_choices(files)
        
        # Build custom ranges from inputs
        custom_ranges = build_ranges_from_dynamic_inputs(*args, range_count=range_count)
        
        if not custom_ranges:
            return None, None, "❌ Please provide at least one valid m/z range (x1, x2, name).", update_spectrum_choices(files)
        
        zoom_range = build_zoom_range(zoom_start, zoom_end)

        file_results = []
        selected_df = None
        selected_results_df = None
        for uploaded_file in files:
            file_path = get_file_path(uploaded_file)
            if not is_supported_file(file_path):
                return None, None, f"❌ Invalid file type: {os.path.basename(file_path)}. Please upload CSV or TXT files.", update_spectrum_choices(files)

            df, results_df, total_areas = read_uploaded_file(uploaded_file, custom_ranges=custom_ranges)
            file_name = os.path.basename(file_path)

            file_results.append({
                "file_name": file_name,
                "results_df": results_df,
                "total_areas": total_areas
            })

            if file_name == selected_file_name:
                selected_df = df
                selected_results_df = results_df
        
        spectrum_choices = [file_result["file_name"] for file_result in file_results]
        if selected_df is None:
            selected_file_name = spectrum_choices[0]
            default_uploaded_file = files[0]
            selected_df, selected_results_df, _ = read_uploaded_file(default_uploaded_file, custom_ranges=custom_ranges)

        fig = plot_data_with_ranges(selected_df, selected_results_df, custom_ranges, zoom_range=zoom_range)
        
        # Create summary table
        summary_table = create_multi_file_summary(file_results)
        
        # Create status message
        status = (
            f"✓ Successfully analyzed {len(files)} file(s)\n"
            f"✓ Calculated {len(custom_ranges)} m/z ranges for each file\n"
            f"✓ Showing spectrum: {selected_file_name}"
        )
        
        return (
            fig,
            summary_table,
            status,
            gr.Dropdown(choices=spectrum_choices, value=selected_file_name, interactive=True)
        )
    
    except Exception as e:
        return None, None, f"❌ Error processing file: {str(e)}", update_spectrum_choices(uploaded_files)

def download_results(uploaded_files, range_count, *args):
    """Generate CSV file with results for download."""
    try:
        files = normalize_uploaded_files(uploaded_files)
        if not files:
            return None
        
        # Build custom ranges from inputs
        custom_ranges = build_ranges_from_dynamic_inputs(*args, range_count=range_count)
        
        if not custom_ranges:
            return None
        
        file_results = []
        for uploaded_file in files:
            file_path = get_file_path(uploaded_file)
            _, results_df, total_areas = read_uploaded_file(uploaded_file, custom_ranges=custom_ranges)
            file_results.append({
                "file_name": os.path.basename(file_path),
                "results_df": results_df,
                "total_areas": total_areas
            })

        results_export_df = create_multi_file_summary(file_results)
        csv_path = "results_multiple_files.csv" if len(files) > 1 else f"results_{os.path.splitext(file_results[0]['file_name'])[0]}.csv"
        results_export_df.to_csv(csv_path, index=False)
        
        return csv_path
    
    except Exception as e:
        print(f"❌ Error generating results: {str(e)}")
        return None

# Create Gradio interface
with gr.Blocks(title="Mass Spectrometry AUC Analysis") as app:
    gr.Markdown("""
    # Mass Spectrometry Analysis
    ## Area Under the Curve (AUC) Calculator
    
    Upload one or more mass spectrometry data files (.csv or .txt format) to analyze and visualize the area under the curve for different m/z ranges.
    """)
    
    # File upload section
    with gr.Row():
        with gr.Column(scale=2):
            uploaded_files = gr.File(
                label="Upload Mass Spectrometry Data (.csv or .txt)",
                file_types=[".csv", ".txt"],
                file_count="multiple",
                type="filepath"
            )
        
        with gr.Column(scale=1):
            validate_file_btn = gr.Button("Validate File", variant="secondary")
            file_status = gr.Textbox(
                label="File Status",
                interactive=False,
                lines=3
            )
    
    # Hidden state to store m/z bounds
    mz_bounds_state = gr.State(value=(None, None))
    
    # m/z bounds display
    with gr.Row():
        bounds_display = gr.Markdown(value="### No file loaded yet")

    gr.Markdown("---")
    gr.Markdown("### Define m/z Ranges")

    with gr.Row():
        range_count_input = gr.Dropdown(
            label="Number of Ranges",
            choices=[str(i) for i in range(1, MAX_RANGES + 1)],
            value="1",
            interactive=True
        )
    
    # Dynamic range inputs - reveal only the number selected by the user.
    range_inputs = []
    range_groups = []
    
    for i in range(MAX_RANGES):
        with gr.Group(visible=(i == 0)) as range_group:
            with gr.Row():
                gr.Markdown(f"#### Range {i+1}")
            
            with gr.Row():
                with gr.Column(scale=1):
                    x1_input = gr.Number(
                        label=f"x1 (start m/z)",
                        placeholder="e.g., 3548.6",
                        value=None
                    )
                with gr.Column(scale=1):
                    x2_input = gr.Number(
                        label=f"x2 (end m/z)",
                        placeholder="e.g., 3552.1",
                        value=None
                    )
                with gr.Column(scale=1):
                    name_input = gr.Textbox(
                        label="Range Name",
                        placeholder="e.g., Protein-A1",
                        value=None
                    )
            
            range_inputs.extend([x1_input, x2_input, name_input])
            range_groups.append(range_group)
    
    gr.Markdown("---")

    gr.Markdown("### Spectrum Picture Close-Up")
    with gr.Row():
        zoom_start_input = gr.Number(
            label="Close-up start m/z",
            placeholder="Optional"
        )
        zoom_end_input = gr.Number(
            label="Close-up end m/z",
            placeholder="Optional"
        )
    
    gr.Markdown("---")
    
    # Validation and analysis buttons
    with gr.Row():
        validate_ranges_btn = gr.Button("Validate Ranges", variant="secondary", size="lg")
        analyze_btn = gr.Button("Analyze Spectrum", variant="primary", size="lg")
    
    # Status and results section
    with gr.Row():
        validation_status = gr.Textbox(
            label="Validation Status",
            interactive=True,
            lines=3
        )
    
    gr.Markdown("### Results")
    
    with gr.Row():
        spectrum_selector = gr.Dropdown(
            label="Spectrum to Show",
            choices=[],
            value=None,
            interactive=False
        )

    with gr.Row():
        plot_output = gr.Plot(label="Mass Spectrometry Spectrum")
    
    with gr.Row():
        table_output = gr.Dataframe(
            label="Area Calculations",
            interactive=False,
            wrap=True
        )
    
    with gr.Row():
        download_btn = gr.Button("Download Results (CSV)", variant="secondary")
        download_output = gr.File(label="Download")
    
    # Instructions
    with gr.Row():
        with gr.Column():
            gr.Markdown("""
            ### Instructions
            
            1. **Upload Files**: Select one or more mass spectrometry files (.csv or .txt)
            2. **Validate Files**: Click to check if the files are valid and view combined m/z bounds
            3. **Define Ranges**: Choose how many ranges to add, then enter x1, x2 (start/end m/z), and a name for each range
               - Fill in only the ranges you need
               - Ensure: x1 < x2 and both within spectrum bounds
            4. **Spectrum Picture Close-Up**: Optionally enter the m/z start and end for the plot zoom
            5. **Validate Ranges**: Check that all ranges are valid
            6. **Analyze**: Generate the plot and calculations
               - The table shows one row per file and one column per range
            7. **Choose Spectrum to Show**: Select which uploaded file should be shown in the spectrum picture
            8. **Download**: Export results as CSV
            
            ### Data Format Requirements
            
            **For TXT files:**
            - Two columns: m/z (x) and intensity (y)
            - Columns separated by spaces or tabs
            
            **For CSV files:**
            - Files exported from the spectrum software are supported
            - If the first 8 lines are metadata, they are skipped automatically
            - Two columns: m/z (x) and intensity (y)
            - Columns separated by commas
            """)
    
    # File validation callback
    def validate_file_and_get_bounds(uploaded_files):
        files = normalize_uploaded_files(uploaded_files)
        if not files:
            return "❌ No files selected", "### No files loaded yet", (None, None)

        invalid_files = [
            os.path.basename(get_file_path(uploaded_file))
            for uploaded_file in files
            if not is_supported_file(get_file_path(uploaded_file))
        ]
        if invalid_files:
            return (
                f"❌ Invalid file type: {', '.join(invalid_files)}. Please upload .csv or .txt files",
                "### Invalid file type",
                (None, None)
            )
        
        # Get m/z bounds
        mz_min, mz_max, bounds_msg = get_mz_bounds(files)
        if mz_min is None:
            return f"❌ {bounds_msg}", "### Could not extract bounds", (None, None)
        
        file_names = ", ".join(os.path.basename(get_file_path(uploaded_file)) for uploaded_file in files)
        bounds_markdown = f"### Combined Spectrum Bounds\n- **m/z min**: {mz_min:.2f}\n- **m/z max**: {mz_max:.2f}\n- **Range**: {mz_max - mz_min:.2f}"
        status_msg = f"✓ {len(files)} file(s) valid\n✓ {bounds_msg}\n✓ Files: {file_names}"
        
        return status_msg, bounds_markdown, (mz_min, mz_max)
    
    # Connect file validation
    validate_file_btn.click(
        fn=validate_file_and_get_bounds,
        inputs=[uploaded_files],
        outputs=[file_status, bounds_display, mz_bounds_state]
    )

    uploaded_files.change(
        fn=update_spectrum_choices,
        inputs=[uploaded_files],
        outputs=[spectrum_selector]
    )

    range_count_input.change(
        fn=update_range_visibility,
        inputs=[range_count_input],
        outputs=range_groups
    )
    
    # Range validation callback
    def validate_ranges_callback(uploaded_files, range_count, *args):
        is_valid, msg = validate_ranges(uploaded_files, range_count, *args)
        return msg
    
    # Connect range validation
    validate_ranges_btn.click(
        fn=validate_ranges_callback,
        inputs=[uploaded_files, range_count_input] + range_inputs,
        outputs=[validation_status]
    )
    
    # Connect analysis
    analyze_btn.click(
        fn=analyze_spectrum,
        inputs=[uploaded_files, spectrum_selector, zoom_start_input, zoom_end_input, range_count_input] + range_inputs,
        outputs=[plot_output, table_output, validation_status, spectrum_selector]
    )

    spectrum_selector.change(
        fn=plot_selected_spectrum,
        inputs=[spectrum_selector, uploaded_files, zoom_start_input, zoom_end_input, range_count_input] + range_inputs,
        outputs=[plot_output]
    )
    
    # Connect download
    download_btn.click(
        fn=download_results,
        inputs=[uploaded_files, range_count_input] + range_inputs,
        outputs=download_output
    )

if __name__ == "__main__":
    app.launch(
        theme=gr.themes.Soft(),
        server_name="0.0.0.0", 
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", 7860)),
        share=False
    )
