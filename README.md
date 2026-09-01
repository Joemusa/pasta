# Pasta and Noodles review

Smollan Unilever template deck built from `03. Monthly Trended Export_2026-08-18.xlsx`.

## Generate the PDF

```bash
python3 -m pip install -r analysis/requirements.txt
python3 analysis/build_smollan_deck.py
```

Outputs:

- `output/Unilever_Pasta_Noodles_Jun2026.pptx`
- `output/Unilever_Pasta_Noodles_Jun2026.pdf`

PDF export uses LibreOffice Impress (`soffice --headless --convert-to pdf`).
