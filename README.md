# CreatorRights

A content rights register and clearance checker. It answers one question before a campaign goes live: **are we allowed to use this asset, on this platform, in this region, on this date?**

**Live demo:** https://YOUR-USERNAME.github.io/creatorrights/  (replace after enabling GitHub Pages)

## What it does
- **Dashboard:** clearance outcomes, reasons checks fail, results by campaign and platform, expiring licences.
- **Clearance check:** returns Cleared, Review, Blocked, or Unverified with reasons. Edited versions inherit their parent asset's restrictions.
- **Contract reader:** proposes licence terms from pasted contract text and quotes the clause used; a person confirms before anything is verified.
- **Asset register and audit log.**

## Repository contents
| Path | What it is |
|---|---|
| `index.html` | The client demo web app (single file, no install; hosted by GitHub Pages) |
| `data/` | Synthetic datasets: 60 assets and 220 clearance checks (CSV) |
| `excel/CreatorRights_Dashboard.xlsx` | Excel dashboard built on the same data |
| `streamlit_app/` | Python (Streamlit + SQLite) version of the prototype |

## Run the Python version locally
```
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py
```
Set `ANTHROPIC_API_KEY` to enable the AI contract reader; without it a rule-based fallback is used.

## Data note
All data is synthetic and for demonstration only. No real contracts or personal data.
