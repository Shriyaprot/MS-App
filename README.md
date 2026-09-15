# Mass Spec AUC Analyzer

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
