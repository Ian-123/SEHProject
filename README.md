
# Unit Property Card (Local App)

Enter **unit-level property details** (Part 1), add **repeatable transaction history** (Part 2), and record **acquisition strategy** (Part 3). Runs locally with SQLite. No ArcGIS needed.

## Install & Run
```bash
pip install -r requirements.txt
streamlit run app.py
```
Your browser will open to http://localhost:8501.

## Data model
- **units** (Part 1): one row per specific unit.
- **transactions** (Part 2): many rows per unit (repeatable events).
- **acquisition_strategy** (Part 3): one row per unit.

Export everything to `seh_units_export.xlsx` from the app.

## Notes
- The app creates a local DB `seh_units.sqlite`.
- The unique `unit_key` is built from parcel address + ZIP + unit identifier.
