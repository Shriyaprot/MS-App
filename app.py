import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from io import BytesIO
from auc_engine import calculate_area


st.set_page_config(
    page_title="Mass Spec AUC Analyzer",
    layout="wide"
)

st.title("Mass Spectrometry AUC Analyzer")

st.write(
    "Upload Qual Browser exported mass spectra, define one or more m/z ranges, "
    "calculate area under the curve, and export the results."
)


def read_qual_browser_file(uploaded_file):
    text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    lines = text.splitlines()

    original_raw_name = uploaded_file.name
    data_start = None

    # Try to recover original RAW filename from the header
    for line in lines[:20]:
        if ".RAW" in line.upper():
            original_raw_name = line.strip()
            break

    # Find Mass / Intensity table
    for i, line in enumerate(lines):
        if "Mass" in line and "Intensity" in line:
            data_start = i + 1
            break

    if data_start is None:
        raise ValueError(
            "Could not find a 'Mass Intensity' table in this file."
        )

    rows = []

    for line in lines[data_start:]:
        parts = line.split()

        if len(parts) < 2:
            continue

        try:
            mass = float(parts[0])
            intensity = float(parts[1])
            rows.append([mass, intensity])
        except ValueError:
            continue

    if not rows:
        raise ValueError("No numeric mass/intensity data were found.")

    df = pd.DataFrame(rows, columns=["x", "y"])
    df = df.dropna().sort_values("x")

    return df, original_raw_name


def short_name(original_name):
    """
    Create a readable display name such as:
    Liver_TG7_HCD160
    """

    lower = original_name.lower()

    organ = "Sample"

    for possible in [
        "liver",
        "lung",
        "kidney",
        "heart",
        "brain"
    ]:
        if possible in lower:
            organ = possible.capitalize()
            break

    trapgas = None
    hcd = None

    import re

    tg_match = re.search(r"trapgas(\d+)", lower)
    hcd_match = re.search(r"hcd(\d+)", lower)

    if tg_match:
        trapgas = tg_match.group(1)

    if hcd_match:
        hcd = hcd_match.group(1)

    pieces = [organ]

    if trapgas:
        pieces.append(f"TG{trapgas}")

    if hcd:
        pieces.append(f"HCD{hcd}")

    return "_".join(pieces)


uploaded_files = st.file_uploader(
    "Upload exported spectra",
    type=["txt", "csv"],
    accept_multiple_files=True
)

st.divider()

st.subheader("Define m/z ranges")

if "ranges" not in st.session_state:
    st.session_state.ranges = [
        {
            "name": "Peak 1",
            "start": 0.0,
            "end": 0.0
        }
    ]


for i, peak_range in enumerate(st.session_state.ranges):

    col1, col2, col3 = st.columns(3)

    with col1:
        peak_range["name"] = st.text_input(
            "Peak name",
            value=peak_range["name"],
            key=f"name_{i}"
        )

    with col2:
        peak_range["start"] = st.number_input(
            "Start m/z",
            value=float(peak_range["start"]),
            format="%.4f",
            key=f"start_{i}"
        )

    with col3:
        peak_range["end"] = st.number_input(
            "End m/z",
            value=float(peak_range["end"]),
            format="%.4f",
            key=f"end_{i}"
        )


col_add, col_remove = st.columns(2)

with col_add:
    if st.button("Add range"):
        st.session_state.ranges.append(
            {
                "name": f"Peak {len(st.session_state.ranges) + 1}",
                "start": 0.0,
                "end": 0.0
            }
        )
        st.rerun()

with col_remove:
    if (
        st.button("Remove last range")
        and len(st.session_state.ranges) > 1
    ):
        st.session_state.ranges.pop()
        st.rerun()


st.divider()


if uploaded_files:

    st.subheader("Detected spectra")

    preview_rows = []

    for uploaded_file in uploaded_files:
        try:
            df, original_name = read_qual_browser_file(uploaded_file)

            preview_rows.append({
                "Uploaded file": uploaded_file.name,
                "Original RAW file": original_name,
                "Display name": short_name(original_name),
                "Data points": len(df)
            })

        except Exception as exc:
            preview_rows.append({
                "Uploaded file": uploaded_file.name,
                "Original RAW file": "",
                "Display name": "",
                "Data points": f"ERROR: {exc}"
            })

    st.dataframe(
        pd.DataFrame(preview_rows),
        use_container_width=True
    )


if uploaded_files and st.button(
    "Calculate AUC",
    type="primary"
):

    all_results = []

    for uploaded_file in uploaded_files:

        try:
            df, original_name = read_qual_browser_file(
                uploaded_file
            )

        except Exception as exc:
            st.error(
                f"Could not read {uploaded_file.name}: {exc}"
            )
            continue

        display_name = short_name(original_name)

        st.subheader(display_name)
        st.caption(original_name)

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["x"],
                y=df["y"],
                mode="lines",
                name="Spectrum",
                line=dict(color="black")
            )
        )

        for peak_range in st.session_state.ranges:

            x_start = peak_range["start"]
            x_end = peak_range["end"]
            peak_name = peak_range["name"]

            area = calculate_area(
                df,
                x_start,
                x_end
            )

            df_range = df[
                (df["x"] >= x_start)
                & (df["x"] <= x_end)
            ]

            fig.add_trace(
                go.Scatter(
                    x=df_range["x"],
                    y=df_range["y"],
                    mode="lines",
                    fill="tozeroy",
                    name=peak_name
                )
            )

            all_results.append({
                "Display Name": display_name,
                "Original RAW File": original_name,
                "Peak": peak_name,
                "Start m/z": x_start,
                "End m/z": x_end,
                "AUC": area
            })

        fig.update_layout(
            xaxis_title="m/z",
            yaxis_title="Intensity",
            hovermode="x unified",
            height=550
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    if all_results:

        results_df = pd.DataFrame(all_results)

        st.divider()
        st.subheader("AUC Results")

        st.dataframe(
            results_df,
            use_container_width=True
        )

        wide_df = results_df.pivot_table(
            index=[
                "Display Name",
                "Original RAW File"
            ],
            columns="Peak",
            values="AUC",
            aggfunc="first"
        ).reset_index()

        output = BytesIO()

        with pd.ExcelWriter(
            output,
            engine="openpyxl"
        ) as writer:

            results_df.to_excel(
                writer,
                sheet_name="AUC Results",
                index=False
            )

            wide_df.to_excel(
                writer,
                sheet_name="Summary",
                index=False
            )

        st.download_button(
            "Download Excel Results",
            data=output.getvalue(),
            file_name="mass_spec_auc_results.xlsx",
            mime=(
                "application/"
                "vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )
