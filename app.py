import streamlit as st
import pandas as pd
from io import BytesIO

from auc import (
    process_file,
    plot_data_with_ranges,
    create_multi_file_summary,
    extract_original_spectrum_name
)


# =======================================================
# APP SETTINGS
# =======================================================

MAX_RANGES = 10

st.set_page_config(
    page_title="Mass Spectrometry AUC Analysis",
    layout="wide"
)

st.title("Mass Spectrometry Analysis")
st.header("Area Under the Curve (AUC) Calculator")

st.write(
    "Paste one or more Qual Browser spectra, or upload converted TXT files. "
    "The app calculates AUC values, normalized fractions, plots spectra, "
    "and exports the results to Excel."
)


# =======================================================
# FILE-LIKE OBJECT FOR PASTED SPECTRA
# =======================================================

class PastedSpectrum:

    def __init__(self, text):

        self._content = text.encode(
            "utf-8"
        )

        self.name = extract_original_spectrum_name(
            self._content,
            fallback_name="pasted_spectrum.txt"
        )

    def getvalue(self):

        return self._content


# =======================================================
# SPLIT CONCATENATED QUAL BROWSER SPECTRA
# =======================================================

def split_pasted_spectra(text):
    """
    Split a large pasted block into individual spectra.

    Every spectrum must start with:

        SPECTRUM - MS
    """

    lines = text.splitlines()

    spectra_blocks = []
    current_block = []

    for line in lines:

        if line.strip().upper() == "SPECTRUM - MS":

            # Save previous spectrum
            if current_block:

                block_text = "\n".join(
                    current_block
                ).strip()

                if block_text:

                    spectra_blocks.append(
                        block_text
                    )

            # Start new spectrum
            current_block = [line]

        else:

            if current_block:

                current_block.append(
                    line
                )

    # Save final spectrum
    if current_block:

        block_text = "\n".join(
            current_block
        ).strip()

        if block_text:

            spectra_blocks.append(
                block_text
            )

    return spectra_blocks


# =======================================================
# PROCESS ONE TXT / PASTED SPECTRUM
# =======================================================

def process_uploaded_file(
    uploaded_file,
    custom_ranges=None
):

    file_content = uploaded_file.getvalue()

    (
        df,
        results_df,
        total_areas
    ) = process_file(
        file_content=file_content,
        file_path=uploaded_file.name,
        custom_ranges=custom_ranges
    )

    # For pasted Qual Browser spectra,
    # recover the original RAW filename.
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


# =======================================================
# GET COMBINED MASS RANGE
# =======================================================

def get_mz_bounds(uploaded_files):

    mins = []
    maxes = []

    for uploaded_file in uploaded_files:

        (
            df,
            _,
            _,
            _
        ) = process_uploaded_file(
            uploaded_file,
            custom_ranges=[]
        )

        if df is None or len(df) == 0:

            raise ValueError(
                f"Could not extract m/z data from "
                f"{uploaded_file.name}"
            )

        mins.append(
            float(df["x"].min())
        )

        maxes.append(
            float(df["x"].max())
        )

    return (
        min(mins),
        max(maxes)
    )


# =======================================================
# INPUT
# =======================================================

st.divider()

st.subheader("Spectrum Input")

input_mode = st.radio(
    "Choose input type",
    options=[
        "Paste Qual Browser spectra",
        "Converted TXT files"
    ],
    horizontal=True
)


uploaded_files = []


# =======================================================
# OPTION 1 — PASTE QUAL BROWSER DATA
# =======================================================

if input_mode == "Paste Qual Browser spectra":

    st.info(
        "Copy spectra from Qual Browser and paste them below. "
        "You can paste many spectra one after another. "
        "Each spectrum must begin with 'SPECTRUM - MS'."
    )

    pasted_spectrum = st.text_area(
        "Paste concatenated spectra here",
        height=420,
        placeholder=(
            "SPECTRUM - MS\n"
            "sample_1.RAW\n"
            "FTMS...\n"
            "Scan #: 1\n"
            "RT: 0.05\n"
            "Data points: ...\n"
            "Mass    Intensity\n"
            "11983.746568    28.266903\n"
            "11986.235786    91.601959\n"
            "...\n\n"
            "SPECTRUM - MS\n"
            "sample_2.RAW\n"
            "..."
        )
    )

    if pasted_spectrum.strip():

        spectrum_blocks = split_pasted_spectra(
            pasted_spectrum
        )

        for block in spectrum_blocks:

            spectrum_file = PastedSpectrum(
                block
            )

            uploaded_files.append(
                spectrum_file
            )

        if uploaded_files:

            st.success(
                f"Detected "
                f"{len(uploaded_files)} "
                f"spectrum file(s)."
            )

            detected_rows = []

            for i, spectrum_file in enumerate(
                uploaded_files,
                start=1
            ):

                detected_rows.append(
                    {
                        "No.": i,
                        "Spectrum": spectrum_file.name
                    }
                )

            st.dataframe(
                pd.DataFrame(
                    detected_rows
                ),
                use_container_width=True,
                hide_index=True
            )


# =======================================================
# OPTION 2 — CONVERTED TXT FILES
# =======================================================

else:

    st.info(
        "Upload one or more converted two-column "
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
            f"Detected "
            f"{len(txt_files)} "
            f"TXT file(s)."
        )

        txt_rows = []

        for i, txt_file in enumerate(
            txt_files,
            start=1
        ):

            txt_rows.append(
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
            pd.DataFrame(
                txt_rows
            ),
            use_container_width=True,
            hide_index=True
        )


# =======================================================
# VALIDATE SPECTRA
# =======================================================

st.divider()

validate_file = st.button(
    "Validate Spectra",
    use_container_width=True
)

file_status_box = st.empty()


if validate_file:

    if not uploaded_files:

        file_status_box.error(
            "No spectra loaded."
        )

    else:

        try:

            validation_rows = []

            all_mins = []
            all_maxes = []

            for spectrum_file in uploaded_files:

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
                        "Spectrum":
                            original_name,

                        "Data points":
                            len(df),

                        "Min m/z":
                            mz_min_file,

                        "Max m/z":
                            mz_max_file
                    }
                )

            st.session_state[
                "mz_bounds"
            ] = (
                min(all_mins),
                max(all_maxes)
            )

            st.session_state[
                "validated_spectra"
            ] = validation_rows

            file_status_box.success(
                f"{len(uploaded_files)} "
                f"spectrum file(s) "
                f"validated successfully."
            )

        except Exception as exc:

            file_status_box.error(
                f"Could not validate spectra: "
                f"{exc}"
            )


# =======================================================
# DISPLAY VALIDATED FILES
# =======================================================

if "validated_spectra" in st.session_state:

    st.subheader(
        "Validated Spectra"
    )

    validated_df = pd.DataFrame(
        st.session_state[
            "validated_spectra"
        ]
    )

    st.dataframe(
        validated_df,
        use_container_width=True,
        hide_index=True
    )


# =======================================================
# DEFINE AUC RANGES
# =======================================================

st.divider()

st.subheader(
    "Define m/z Ranges"
)

range_count = st.selectbox(
    "Number of Ranges",
    options=list(
        range(
            1,
            MAX_RANGES + 1
        )
    ),
    index=2
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


# =======================================================
# RANGE INPUTS
# =======================================================

for i in range(
    range_count
):

    st.markdown(
        f"#### Range {i + 1}"
    )

    c1, c2, c3 = st.columns(
        3
    )


    # -----------------------------------------------
    # Helpful defaults for your current experiment
    # -----------------------------------------------

    default_starts = [
        11000.0,
        14000.0,
        22000.0
    ]

    default_ends = [
        13000.0,
        22000.0,
        35000.0
    ]

    default_names = [
        "20S",
        "20S minus 1",
        "20S minus 2"
    ]


    with c1:

        default_x1 = (
            default_starts[i]
            if i < 3
            else None
        )

        x1 = st.number_input(
            "x1 (start m/z)",
            value=default_x1,
            placeholder="Start m/z",
            key=f"x1_{i}"
        )


    with c2:

        default_x2 = (
            default_ends[i]
            if i < 3
            else None
        )

        x2 = st.number_input(
            "x2 (end m/z)",
            value=default_x2,
            placeholder="End m/z",
            key=f"x2_{i}"
        )


    with c3:

        default_name = (
            default_names[i]
            if i < 3
            else ""
        )

        name = st.text_input(
            "Range Name",
            value=default_name,
            placeholder="Range name",
            key=f"name_{i}"
        )


    if (
        x1 is not None
        and x2 is not None
        and name.strip()
    ):

        custom_ranges.append(
            {
                "name":
                    name.strip(),

                "range":
                    (
                        float(x1),
                        float(x2)
                    ),

                "color":
                    colors[
                        len(custom_ranges)
                        % len(colors)
                    ]
            }
        )


# =======================================================
# PLOT CLOSE-UP
# =======================================================

st.divider()

st.subheader(
    "Spectrum Picture Close-Up"
)

z1, z2 = st.columns(
    2
)


with z1:

    zoom_start = st.number_input(
        "Close-up start m/z",
        value=5000.0,
        placeholder="Optional"
    )


with z2:

    zoom_end = st.number_input(
        "Close-up end m/z",
        value=35000.0,
        placeholder="Optional"
    )


# =======================================================
# RANGE VALIDATION
# =======================================================

st.divider()

validate_ranges_col, analyze_col = st.columns(
    2
)


with validate_ranges_col:

    do_validate_ranges = st.button(
        "Validate Ranges",
        use_container_width=True
    )


with analyze_col:

    do_analyze = st.button(
        "Analyze Spectra",
        type="primary",
        use_container_width=True
    )


validation_box = st.empty()


def validate_ranges():

    if not uploaded_files:

        return (
            False,
            "No spectra loaded."
        )

    if not custom_ranges:

        return (
            False,
            "Please define at least "
            "one complete range."
        )

    try:

        mz_min, mz_max = (
            get_mz_bounds(
                uploaded_files
            )
        )

    except Exception as exc:

        return (
            False,
            str(exc)
        )

    for item in custom_ranges:

        name = item["name"]

        x1, x2 = item[
            "range"
        ]

        if x1 >= x2:

            return (
                False,
                f"Range '{name}': "
                f"x1 must be smaller "
                f"than x2."
            )

        if x1 < mz_min:

            return (
                False,
                f"Range '{name}' starts "
                f"below the spectrum "
                f"minimum "
                f"({mz_min:.2f})."
            )

        if x2 > mz_max:

            return (
                False,
                f"Range '{name}' ends "
                f"above the spectrum "
                f"maximum "
                f"({mz_max:.2f})."
            )

    return (
        True,
        f"All {len(custom_ranges)} "
        f"ranges validated for "
        f"{len(uploaded_files)} "
        f"spectrum file(s)."
    )


if do_validate_ranges:

    ok, message = (
        validate_ranges()
    )

    if ok:

        validation_box.success(
            message
        )

    else:

        validation_box.error(
            message
        )


# =======================================================
# ANALYSIS
# =======================================================

if do_analyze:

    ok, message = (
        validate_ranges()
    )

    if not ok:

        validation_box.error(
            message
        )

    else:

        try:

            # -------------------------------------------
            # Plot zoom
            # -------------------------------------------

            if (
                zoom_start is None
                and zoom_end is None
            ):

                zoom_range = None

            elif (
                zoom_start is None
                or zoom_end is None
            ):

                raise ValueError(
                    "Please fill both "
                    "zoom start and zoom end, "
                    "or leave both empty."
                )

            else:

                if (
                    zoom_start
                    >= zoom_end
                ):

                    raise ValueError(
                        "Close-up start "
                        "must be smaller "
                        "than close-up end."
                    )

                zoom_range = (
                    float(
                        zoom_start
                    ),
                    float(
                        zoom_end
                    )
                )


            # -------------------------------------------
            # Process all spectra
            # -------------------------------------------

            file_results = []

            processed_data = {}


            for uploaded_file in uploaded_files:

                (
                    df,
                    results_df,
                    total_areas,
                    original_name
                ) = process_uploaded_file(
                    uploaded_file,
                    custom_ranges=
                        custom_ranges
                )


                file_results.append(
                    {
                        "file_name":
                            original_name,

                        "results_df":
                            results_df,

                        "total_areas":
                            total_areas
                    }
                )


                processed_data[
                    original_name
                ] = (
                    df,
                    results_df
                )


            # -------------------------------------------
            # Existing AUC summary
            # -------------------------------------------

            summary_table = (
                create_multi_file_summary(
                    file_results
                )
            )


            # -------------------------------------------
            # Identify the AUC columns
            # -------------------------------------------

            range_columns = [
                column
                for column
                in summary_table.columns
                if column.startswith(
                    "Range "
                )
            ]


            # -------------------------------------------
            # Total AUC
            # -------------------------------------------

            summary_table[
                "Total"
            ] = (
                summary_table[
                    range_columns
                ]
                .sum(
                    axis=1
                )
            )


            # -------------------------------------------
            # Normalized fractions
            #
            # Fraction values are percentages:
            #
            # 0.64
            # 59.14
            # 40.21
            #
            # matching your existing Excel convention.
            # -------------------------------------------

            if len(
                range_columns
            ) >= 1:

                summary_table[
                    "20S fraction"
                ] = (
                    summary_table[
                        range_columns[0]
                    ]
                    /
                    summary_table[
                        "Total"
                    ]
                    * 100
                )


            if len(
                range_columns
            ) >= 2:

                summary_table[
                    "minus 1 fraction"
                ] = (
                    summary_table[
                        range_columns[1]
                    ]
                    /
                    summary_table[
                        "Total"
                    ]
                    * 100
                )


            if len(
                range_columns
            ) >= 3:

                summary_table[
                    "minus 2 fraction"
                ] = (
                    summary_table[
                        range_columns[2]
                    ]
                    /
                    summary_table[
                        "Total"
                    ]
                    * 100
                )


            # -------------------------------------------
            # Store results
            # -------------------------------------------

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
                f"{len(uploaded_files)} "
                f"spectrum file(s)."
            )


        except Exception as exc:

            validation_box.error(
                f"Error processing "
                f"spectra: {exc}"
            )


# =======================================================
# RESULTS
# =======================================================

if (
    "analysis_results"
    in st.session_state
):

    st.divider()

    st.subheader(
        "Results"
    )

    result_state = (
        st.session_state[
            "analysis_results"
        ]
    )

    processed_data = (
        result_state[
            "processed_data"
        ]
    )


    # ===================================================
    # SELECT SPECTRUM
    # ===================================================

    selected_file = st.selectbox(
        "Spectrum to Show",
        options=list(
            processed_data.keys()
        )
    )


    df, results_df = (
        processed_data[
            selected_file
        ]
    )


    # ===================================================
    # PLOT
    # ===================================================

    fig = plot_data_with_ranges(
        df,
        results_df,
        result_state[
            "custom_ranges"
        ],
        zoom_range=
            result_state[
                "zoom_range"
            ]
    )

    st.pyplot(
        fig
    )


    # ===================================================
    # SUMMARY TABLE
    # ===================================================

    st.subheader(
        "AUC and Population Fractions"
    )

    summary_table = (
        result_state[
            "summary_table"
        ]
    )

    st.dataframe(
        summary_table,
        use_container_width=True,
        hide_index=True
    )


    # ===================================================
    # CSV DOWNLOAD
    # ===================================================

    csv_data = (
        summary_table
        .to_csv(
            index=False
        )
        .encode(
            "utf-8"
        )
    )

    st.download_button(
        "Download Results (CSV)",
        data=csv_data,
        file_name=
            "mass_spec_results.csv",
        mime="text/csv"
    )


    # ===================================================
    # EXCEL DOWNLOAD
    # ===================================================

    excel_buffer = BytesIO()


    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl"
    ) as writer:

        # -----------------------------------------------
        # SHEET 1 — SUMMARY
        # -----------------------------------------------

        summary_table.to_excel(
            writer,
            sheet_name="Summary",
            index=False
        )


        summary_sheet = (
            writer.book[
                "Summary"
            ]
        )


        summary_sheet.freeze_panes = (
            "A2"
        )


        # Bold header
        for cell in summary_sheet[1]:

            cell.font = (
                cell.font.copy(
                    bold=True
                )
            )


        # -----------------------------------------------
        # Number formatting
        # -----------------------------------------------

        header_map = {
            cell.value:
                cell.column
            for cell
            in summary_sheet[1]
        }


        # AUC columns
        for header_name in header_map:

            if (
                str(
                    header_name
                ).startswith(
                    "Range "
                )
                or
                header_name
                == "Total"
            ):

                column_number = (
                    header_map[
                        header_name
                    ]
                )

                for row in range(
                    2,
                    summary_sheet.max_row
                    + 1
                ):

                    summary_sheet.cell(
                        row=row,
                        column=
                            column_number
                    ).number_format = (
                        "0.0000"
                    )


        # Fractions
        fraction_headers = [
            "20S fraction",
            "minus 1 fraction",
            "minus 2 fraction"
        ]


        for header_name in (
            fraction_headers
        ):

            if (
                header_name
                in header_map
            ):

                column_number = (
                    header_map[
                        header_name
                    ]
                )

                for row in range(
                    2,
                    summary_sheet.max_row
                    + 1
                ):

                    summary_sheet.cell(
                        row=row,
                        column=
                            column_number
                    ).number_format = (
                        "0.000000"
                    )


        # -----------------------------------------------
        # Auto-width
        # -----------------------------------------------

        for column_cells in (
            summary_sheet.columns
        ):

            max_length = 0

            column_letter = (
                column_cells[
                    0
                ].column_letter
            )

            for cell in (
                column_cells
            ):

                if (
                    cell.value
                    is not None
                ):

                    max_length = max(
                        max_length,
                        len(
                            str(
                                cell.value
                            )
                        )
                    )

            summary_sheet.column_dimensions[
                column_letter
            ].width = min(
                max_length + 2,
                60
            )


        # ===============================================
        # SHEET 2 — RANGE DEFINITIONS
        # ===============================================

        range_rows = []

        for i, item in enumerate(
            result_state[
                "custom_ranges"
            ],
            start=1
        ):

            x1, x2 = (
                item["range"]
            )

            range_rows.append(
                {
                    "Range":
                        i,

                    "Name":
                        item["name"],

                    "Start m/z":
                        x1,

                    "End m/z":
                        x2
                }
            )


        pd.DataFrame(
            range_rows
        ).to_excel(
            writer,
            sheet_name=
                "Range Definitions",
            index=False
        )


        # ===============================================
        # INDIVIDUAL SPECTRUM DATA SHEETS
        # ===============================================

        for i, (
            spectrum_name,
            spectrum_data
        ) in enumerate(
            processed_data.items(),
            start=1
        ):

            spectrum_df, _ = (
                spectrum_data
            )

            # Excel sheet names must be <=31 characters
            sheet_name = (
                f"Spectrum_{i}"
            )

            export_df = (
                spectrum_df.copy()
            )

            export_df.columns = [
                "m/z",
                "Intensity"
            ]

            export_df.to_excel(
                writer,
                sheet_name=
                    sheet_name,
                index=False
            )


    st.download_button(
        "Download Results (Excel)",
        data=
            excel_buffer.getvalue(),
        file_name=
            "mass_spec_auc_results.xlsx",
        mime=(
            "application/"
            "vnd.openxmlformats-"
            "officedocument."
            "spreadsheetml.sheet"
        )
    )


# =======================================================
# INSTRUCTIONS
# =======================================================

st.divider()

st.subheader(
    "Instructions"
)

st.markdown(
    """
1. **Choose input type** — paste Qual Browser spectra or upload converted TXT files.
2. **Paste/upload spectra** — multiple spectra can be analyzed together.
3. **Validate Spectra** — confirm that the app detects the files and m/z data.
4. **Define ranges** — default values are provided for 20S, 20S minus 1 and 20S minus 2.
5. **Set plot close-up** if desired.
6. **Validate Ranges**.
7. **Analyze Spectra**.
8. Use **Spectrum to Show** to inspect individual spectra.
9. Download the complete results as **Excel** or **CSV**.
"""
)
