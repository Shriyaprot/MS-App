import os
import tempfile
import streamlit as st
import pandas as pd

from auc import (
    process_file,
    plot_data_with_ranges,
    create_multi_file_summary,
    extract_original_spectrum_name
)

MAX_RANGES = 10

st.set_page_config(
    page_title="Mass Spectrometry AUC Analysis",
    layout="wide"
)

st.title("Mass Spectrometry Analysis")
st.header("Area Under the Curve (AUC) Calculator")

st.write(
    "Upload one or more mass spectrometry data files (.csv or .txt format) "
    "to analyze and visualize the area under the curve for different m/z ranges."
)


def uploaded_file_to_bytes(uploaded_file):
    return uploaded_file.getvalue()


def process_uploaded_file(uploaded_file, custom_ranges=None):

    file_content = uploaded_file.getvalue()

    df, results_df, total_areas = process_file(
        file_content=file_content,
        file_path=uploaded_file.name,
        custom_ranges=custom_ranges
    )

    original_name = extract_original_spectrum_name(
        file_content,
        fallback_name=uploaded_file.name
    )

    return (
        df,
        results_df,
        total_areas,
        original_name
    )

def get_mz_bounds(uploaded_files):
    mins = []
    maxes = []

    for uploaded_file in uploaded_files:
        df, _, _, _ = process_uploaded_file(
            uploaded_file,
            custom_ranges=[]
        )

        if df is None or len(df) == 0:
            raise ValueError(
                f"Could not extract m/z data from {uploaded_file.name}"
            )

        mins.append(float(df["x"].min()))
        maxes.append(float(df["x"].max()))

    return min(mins), max(maxes)


# -------------------------------------------------------
# Upload section
# -------------------------------------------------------

left, right = st.columns([2, 1])

with left:
    uploaded_files = st.file_uploader(
    "Upload Mass Spectrometry Spectrum Exports",
    type=None,
    accept_multiple_files=True,
    help=(
        "Supports plain two-column spectra and "
        "Qual Browser exported Mass/Intensity spectra."
    )
)

with right:
    validate_file = st.button(
        "Validate File",
        use_container_width=True
    )

    file_status_box = st.empty()


# -------------------------------------------------------
# File validation
# -------------------------------------------------------

if validate_file:

    if not uploaded_files:
        file_status_box.error("No files selected")

    else:
        try:
            mz_min, mz_max = get_mz_bounds(uploaded_files)

            names = ", ".join(
                uploaded_file.name
                for uploaded_file in uploaded_files
            )

            file_status_box.success(
                f"{len(uploaded_files)} file(s) valid\n\n"
                f"Combined m/z range: {mz_min:.2f} - {mz_max:.2f}\n\n"
                f"Files: {names}"
            )

            st.session_state["mz_bounds"] = (
                mz_min,
                mz_max
            )

        except Exception as exc:
            file_status_box.error(str(exc))


if "mz_bounds" in st.session_state:
    mz_min, mz_max = st.session_state["mz_bounds"]

    st.markdown(
        f"""
### Combined Spectrum Bounds
- **m/z min:** {mz_min:.2f}
- **m/z max:** {mz_max:.2f}
- **Range:** {mz_max - mz_min:.2f}
"""
    )

else:
    st.markdown("### No file loaded yet")


st.divider()

# -------------------------------------------------------
# Range definition
# -------------------------------------------------------

st.subheader("Define m/z Ranges")

range_count = st.selectbox(
    "Number of Ranges",
    options=list(range(1, MAX_RANGES + 1)),
    index=0
)

custom_ranges = []

colors = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f"
]

for i in range(range_count):

    st.markdown(f"#### Range {i + 1}")

    c1, c2, c3 = st.columns(3)

    with c1:
        x1 = st.number_input(
            "x1 (start m/z)",
            value=None,
            placeholder="e.g., 3548.6",
            key=f"x1_{i}"
        )

    with c2:
        x2 = st.number_input(
            "x2 (end m/z)",
            value=None,
            placeholder="e.g., 3552.1",
            key=f"x2_{i}"
        )

    with c3:
        name = st.text_input(
            "Range Name",
            placeholder="e.g., Protein-A1",
            key=f"name_{i}"
        )

    if (
        x1 is not None
        and x2 is not None
        and name.strip()
    ):
        custom_ranges.append(
            {
                "name": name.strip(),
                "range": (
                    float(x1),
                    float(x2)
                ),
                "color": colors[
                    len(custom_ranges)
                    % len(colors)
                ]
            }
        )


st.divider()

# -------------------------------------------------------
# Spectrum close-up
# -------------------------------------------------------

st.subheader("Spectrum Picture Close-Up")

z1, z2 = st.columns(2)

with z1:
    zoom_start = st.number_input(
        "Close-up start m/z",
        value=None,
        placeholder="Optional"
    )

with z2:
    zoom_end = st.number_input(
        "Close-up end m/z",
        value=None,
        placeholder="Optional"
    )


st.divider()

# -------------------------------------------------------
# Validation
# -------------------------------------------------------

validate_ranges_btn, analyze_btn = st.columns(2)

with validate_ranges_btn:
    do_validate_ranges = st.button(
        "Validate Ranges",
        use_container_width=True
    )

with analyze_btn:
    do_analyze = st.button(
        "Analyze Spectrum",
        type="primary",
        use_container_width=True
    )


validation_box = st.empty()


def validate_ranges():
    if not uploaded_files:
        return False, "No files uploaded"

    if not custom_ranges:
        return False, (
            "Please fill in at least one complete range "
            "(x1, x2, name)"
        )

    try:
        mz_min, mz_max = get_mz_bounds(
            uploaded_files
        )

    except Exception as exc:
        return False, str(exc)

    for item in custom_ranges:
        name = item["name"]
        x1, x2 = item["range"]

        if x1 >= x2:
            return (
                False,
                f"Range '{name}': x1 ({x1}) "
                f"must be less than x2 ({x2})"
            )

        if x1 < mz_min or x1 > mz_max:
            return (
                False,
                f"Range '{name}': x1 ({x1}) "
                f"is outside spectrum bounds "
                f"({mz_min:.2f} - {mz_max:.2f})"
            )

        if x2 < mz_min or x2 > mz_max:
            return (
                False,
                f"Range '{name}': x2 ({x2}) "
                f"is outside spectrum bounds "
                f"({mz_min:.2f} - {mz_max:.2f})"
            )

    return (
        True,
        f"All {len(custom_ranges)} ranges validated "
        f"successfully for {len(uploaded_files)} file(s)"
    )


if do_validate_ranges:
    ok, message = validate_ranges()

    if ok:
        validation_box.success(message)
    else:
        validation_box.error(message)


# -------------------------------------------------------
# Analysis
# -------------------------------------------------------

if do_analyze:

    ok, message = validate_ranges()

    if not ok:
        validation_box.error(message)

    else:
        try:

                        if zoom_start is None and zoom_end is None:
                zoom_range = None

            elif zoom_start is None or zoom_end is None:
                raise ValueError(
                    "Please fill both zoom start and zoom end, "
                    "or leave both empty."
                )

            else:
                if zoom_start >= zoom_end:
                    raise ValueError(
                        "Spectrum close-up start must be smaller than end."
                    )

                zoom_range = (
                    float(zoom_start),
                    float(zoom_end)
                )

            file_results = []
            processed_data = {}

            for uploaded_file in uploaded_files:

                df, results_df, total_areas, original_name = (
                    process_uploaded_file(
                        uploaded_file,
                        custom_ranges=custom_ranges
                    )
                )

                file_results.append(
                    {
                        "file_name": original_name,
                        "results_df": results_df,
                        "total_areas": total_areas
                    }
                )

                processed_data[original_name] = (
                    df,
                    results_df
                )

            summary_table = (
                create_multi_file_summary(
                    file_results
                )
            )

            st.session_state[
                "analysis_results"
            ] = {
                "file_results":
                    file_results,
                "processed_data":
                    processed_data,
                "summary_table":
                    summary_table,
                "custom_ranges":
                    custom_ranges,
                "zoom_range":
                    zoom_range
            }

            validation_box.success(
                f"Successfully analyzed "
                f"{len(uploaded_files)} file(s)\n\n"
                f"Calculated "
                f"{len(custom_ranges)} m/z ranges "
                f"for each file"
            )

        except Exception as exc:
            validation_box.error(
                f"Error processing file: {exc}"
            )


# -------------------------------------------------------
# Results
# -------------------------------------------------------

if do_analyze:

    ok, message = validate_ranges()

    if not ok:
        validation_box.error(message)

    else:
        try:

            if zoom_start is None and zoom_end is None:
                zoom_range = None

            elif zoom_start is None or zoom_end is None:
                raise ValueError(
                    "Please fill both zoom start and zoom end, "
                    "or leave both empty."
                )

            else:
                if zoom_start >= zoom_end:
                    raise ValueError(
                        "Spectrum close-up start must be smaller than end."
                    )

                zoom_range = (
                    float(zoom_start),
                    float(zoom_end)
                )

            file_results = []
            processed_data = {}

            for uploaded_file in uploaded_files:

                df, results_df, total_areas, original_name = (
                    process_uploaded_file(
                        uploaded_file,
                        custom_ranges=custom_ranges
                    )
                )

                file_results.append(
                    {
                        "file_name": original_name,
                        "results_df": results_df,
                        "total_areas": total_areas
                    }
                )

                processed_data[original_name] = (
                    df,
                    results_df
                )

            summary_table = create_multi_file_summary(
                file_results
            )

            st.session_state["analysis_results"] = {
                "file_results": file_results,
                "processed_data": processed_data,
                "summary_table": summary_table,
                "custom_ranges": custom_ranges,
                "zoom_range": zoom_range
            }

            validation_box.success(
                f"Successfully analyzed "
                f"{len(uploaded_files)} file(s)\n\n"
                f"Calculated "
                f"{len(custom_ranges)} m/z ranges "
                f"for each file"
            )

        except Exception as exc:
            validation_box.error(
                f"Error processing file: {exc}"
            )


st.divider()

st.subheader("Instructions")

st.markdown(
    """
1. **Upload Files**: Select one or more mass spectrometry files (.csv or .txt)
2. **Validate Files**: Check that the files are valid and view combined m/z bounds
3. **Define Ranges**: Choose how many ranges to add, then enter x1, x2 and a name
4. **Spectrum Picture Close-Up**: Optionally enter the m/z start and end for the plot zoom
5. **Validate Ranges**: Check that all ranges are valid
6. **Analyze Spectrum**: Generate the plot and calculations
7. **Choose Spectrum to Show**: Select which uploaded file should be displayed
8. **Download**: Export results as CSV
"""
)
