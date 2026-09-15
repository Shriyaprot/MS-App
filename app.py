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

    original_name = uploaded_file.name

    return (
        df,
        results_df,
        total_areas,
        original_name
    )
class PastedSpectrum:
    """
    Makes pasted spectrum text behave like an uploaded file.
    """

    def __init__(self, text):
        self._content = text.encode("utf-8")

        self.name = extract_original_spectrum_name(
            self._content,
            fallback_name="pasted_spectrum.txt"
        )

    def getvalue(self):
        return self._content
def split_pasted_spectra(text):
    """
    Split one large clipboard paste into separate spectra.

    Each spectrum is expected to begin with:
        SPECTRUM - MS
    """

    lines = text.splitlines()

    spectra_blocks = []
    current_block = []

    for line in lines:

        if line.strip().upper() == "SPECTRUM - MS":

            # Save the previous spectrum before starting a new one
            if current_block:
                block_text = "\n".join(current_block).strip()

                if block_text:
                    spectra_blocks.append(block_text)

            current_block = [line]

        else:
            # Only collect lines after the first SPECTRUM - MS marker
            if current_block:
                current_block.append(line)

    # Save final spectrum
    if current_block:
        block_text = "\n".join(current_block).strip()

        if block_text:
            spectra_blocks.append(block_text)

    return spectra_blocks
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
# -------------------------------------------------------
# Paste spectrum section
# -------------------------------------------------------
# -------------------------------------------------------
# Data input section
# -------------------------------------------------------

st.subheader("Spectrum Input")

input_mode = st.radio(
    "Choose input type",
    options=[
        "Thermo RAW files",
        "Converted TXT files"
    ],
    horizontal=True
)

uploaded_files = []
raw_files = []
txt_files = []


# -------------------------------------------------------
# RAW FILE INPUT
# -------------------------------------------------------

if input_mode == "Thermo RAW files":

    st.info(
        "Upload one or more Thermo .RAW files. "
        "The app will eventually extract the spectrum directly "
        "and reproduce the validated TXT-style input internally."
    )

    raw_files = st.file_uploader(
        "Upload Thermo RAW files",
        type=["raw", "RAW"],
        accept_multiple_files=True,
        key="raw_file_uploader"
    )

    if raw_files:

        st.success(
            f"Detected {len(raw_files)} RAW file(s)."
        )

        raw_table = []

        for i, raw_file in enumerate(
            raw_files,
            start=1
        ):

            raw_table.append(
                {
                    "No.": i,
                    "Spectrum": raw_file.name,
                    "Size (MB)": round(
                        raw_file.size / (1024 * 1024),
                        2
                    ),
                    "Status": "RAW extraction pending"
                }
            )

        st.dataframe(
            pd.DataFrame(raw_table),
            use_container_width=True,
            hide_index=True
        )


# -------------------------------------------------------
# TXT FILE INPUT
# -------------------------------------------------------

else:

    st.info(
        "Upload one or more previously converted two-column "
        "m/z / intensity TXT files."
    )

    txt_files = st.file_uploader(
        "Upload converted TXT files",
        type=["txt"],
        accept_multiple_files=True,
        key="txt_file_uploader"
    )

    if txt_files:

        uploaded_files = txt_files

        st.success(
            f"Detected {len(txt_files)} TXT file(s)."
        )

        txt_table = []

        for i, txt_file in enumerate(
            txt_files,
            start=1
        ):

            txt_table.append(
                {
                    "No.": i,
                    "Spectrum": txt_file.name,
                    "Size (KB)": round(
                        txt_file.size / 1024,
                        1
                    )
                }
            )

        st.dataframe(
            pd.DataFrame(txt_table),
            use_container_width=True,
            hide_index=True
        )
# -------------------------------------------------------
# Input validation
# -------------------------------------------------------

validate_file = st.button(
    "Validate Spectra",
    use_container_width=True
)

file_status_box = st.empty()


if validate_file:

    # ---------------------------------------------------
    # RAW validation
    # ---------------------------------------------------

    if input_mode == "Thermo RAW files":

        if not raw_files:

            file_status_box.error(
                "Please upload at least one Thermo RAW file."
            )

        else:

            raw_validation_rows = []

            for raw_file in raw_files:

                raw_validation_rows.append(
                    {
                        "Spectrum": raw_file.name,
                        "Size (MB)": round(
                            raw_file.size / (1024 * 1024),
                            2
                        ),
                        "RAW file": "Detected",
                        "Spectrum extraction": "Pending"
                    }
                )

            st.session_state[
                "validated_raw_files"
            ] = raw_validation_rows

            file_status_box.success(
                f"{len(raw_files)} RAW file(s) detected successfully."
            )


    # ---------------------------------------------------
    # TXT validation
    # ---------------------------------------------------

    else:

        if not txt_files:

            file_status_box.error(
                "Please upload at least one TXT file."
            )

        else:

            try:

                validation_rows = []

                all_mins = []
                all_maxes = []

                for spectrum_file in txt_files:

                    (
                        df,
                        _,
                        _,
                        original_name
                    ) = process_uploaded_file(
                        spectrum_file,
                        custom_ranges=[]
                    )

                    mz_min_file = float(
                        df["x"].min()
                    )

                    mz_max_file = float(
                        df["x"].max()
                    )

                    all_mins.append(
                        mz_min_file
                    )

                    all_maxes.append(
                        mz_max_file
                    )

                    validation_rows.append(
                        {
                            "Spectrum": original_name,
                            "Data points": len(df),
                            "Min m/z": mz_min_file,
                            "Max m/z": mz_max_file
                        }
                    )

                st.session_state["mz_bounds"] = (
                    min(all_mins),
                    max(all_maxes)
                )

                st.session_state[
                    "validated_spectra"
                ] = validation_rows

                file_status_box.success(
                    f"{len(txt_files)} TXT spectrum file(s) "
                    f"validated successfully."
                )

            except Exception as exc:

                file_status_box.error(
                    f"Could not validate spectra: {exc}"
                )

if (
    input_mode == "Converted TXT files"
    and "validated_spectra" in st.session_state
):

    st.subheader("Validated Spectra")

    validated_df = pd.DataFrame(
        st.session_state["validated_spectra"]
    )

    st.dataframe(
        validated_df,
        use_container_width=True,
        hide_index=True
    )


if (
    input_mode == "Thermo RAW files"
    and "validated_raw_files" in st.session_state
):

    st.subheader("Detected RAW Spectra")

    raw_validated_df = pd.DataFrame(
        st.session_state["validated_raw_files"]
    )

    st.dataframe(
        raw_validated_df,
        use_container_width=True,
        hide_index=True
    )
# -------------------------------------------------------
# Results
# -------------------------------------------------------

if "analysis_results" in st.session_state:

    result_state = st.session_state["analysis_results"]

    st.subheader("Results")

    processed_data = result_state["processed_data"]

    selected_file = st.selectbox(
        "Spectrum to Show",
        options=list(processed_data.keys())
    )

    df, results_df = processed_data[selected_file]

    fig = plot_data_with_ranges(
        df,
        results_df,
        result_state["custom_ranges"],
        zoom_range=result_state["zoom_range"]
    )

    st.pyplot(fig)

    st.dataframe(
        result_state["summary_table"],
        use_container_width=True
    )

    csv_data = (
        result_state["summary_table"]
        .to_csv(index=False)
        .encode("utf-8")
    )

    st.download_button(
        "Download Results (CSV)",
        data=csv_data,
        file_name="results.csv",
        mime="text/csv"
    )
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

    # RAW MODE
    if input_mode == "Thermo RAW files":

        if not raw_files:
            return False, "No RAW files uploaded"

        if not custom_ranges:
            return False, (
                "Please fill in at least one complete range "
                "(x1, x2, name)"
            )

        return (
            True,
            f"{len(raw_files)} RAW file(s) detected and "
            f"{len(custom_ranges)} range(s) defined successfully."
        )

    # TXT MODE
    if not uploaded_files:
        return False, "No TXT files uploaded"

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


# -------------------------------------------------------
# Analysis
# -------------------------------------------------------

# -------------------------------------------------------
# Results
# -------------------------------------------------------

if do_analyze:

    ok, message = validate_ranges()

    if not ok:
        validation_box.error(message)

    elif input_mode == "Thermo RAW files":

        validation_box.warning(
            "RAW files and ranges are valid. "
            "Direct Thermo RAW spectrum extraction is the next step "
            "and is not implemented yet."
        )

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
