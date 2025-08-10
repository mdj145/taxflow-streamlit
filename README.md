# TaxFlow AI – Streamlit MVP

## Files
- `app.py` – Streamlit app
- `requirements.txt` – Python dependencies
- `runtime.txt` – Pin Python 3.11 on Streamlit Cloud
- `tax_rules_il_2025.yaml` – Editable Israeli tax rules (demo)

## How to deploy
1) Upload these files to a **public** GitHub repo.  
2) On https://share.streamlit.io → Create app → pick your repo, Branch: `main`, Main file path: `app.py`.  
3) If build hangs, ensure `runtime.txt` is present and restart.
