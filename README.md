---
title: Mass Spec AUC Analysis
emoji: 🧪
colorFrom: blue
colorTo: green
sdk: gradio
app_file: main.py
pinned: false
---# Mass Spec AUC Analyzer
# Mass Spectrometry Area Under Curve (AUC) Analysis

A web-based application for analyzing exported mass spectrometry
spectra and calculating area under the curve (AUC) for selected
m/z ranges.

Streamlit application for calculating area under the curve
for selected m/z ranges in mass spectrometry spectra.

## Calculation

AUC is calculated using:

scipy.integrate.trapezoid(intensity, mass)

for all measured points satisfying:

start_mz <= mass <= end_mz

No baseline correction, smoothing, interpolation, or
normalization is applied.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
