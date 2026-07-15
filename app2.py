# SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Commercial
# Copyright (c) 2025 <Ian Duncan Njuguna>
# app.py — Property Card DB (Streamlit) with section "Clear" buttons, white basemap, geocoding, edit/delete, docs/notes, import/export
# Storage: properties.json (same folder)
# Deps (install in your app venv):
#   pip install streamlit==1.36.0 pandas==2.2.2 openpyxl==3.1.5 geopy==2.4.1

import json, os, re
from datetime import date, datetime
from typing import Any, Dict, List
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from io import BytesIO
import os
import pandas as pd
import streamlit as st
import pydeck as pdk  # white/light basemap maps
import numpy as np
import folium
import pydeck as pdk
from typing import Optional

# MUST be the first Streamlit command on this page
def _configure_page_once():
    if not st.session_state.get("_page_configured", False):
        st.set_page_config(
            page_title="Property Card Database for Shared Equity Homeownership",
            page_icon="🏠",
            layout="wide",
            initial_sidebar_state="expanded",
        )
        st.session_state["_page_configured"] = True

_configure_page_once()

st.title("🏠 Property Card Database for Shared Equity Homeownership")

# Optional geocoding (install geopy)
try:
    from geopy.geocoders import Nominatim
except Exception:
    Nominatim = None

DATA_FILE   = "properties.json"
EXPORT_FILE = "seh_export_all.xlsx"
ATTACH_DIR  = "attachments"  # uploaded files stored per-property here

# -------------------- Helpers --------------------
def load_data() -> Dict[str, Any]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_data(properties, filename="properties.json"):
    def convert(obj):
        if isinstance(obj, (datetime, date, pd.Timestamp)):
            return obj.isoformat()
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return obj

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(properties, f, indent=2, ensure_ascii=False, default=convert)        

def to_index_or_default(options: List[str], value: str, default: int = 0) -> int:
    try:
        return options.index(value)
    except Exception:
        return default

def none_if_nan(v):
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    return v

def to_iso(d: Any) -> Any:
    if isinstance(d, date):
        return d.isoformat()
    return d

def safe_addr_folder(addr: str) -> str:
    s = re.sub(r"\s+", "_", addr.strip())
    s = re.sub(r"[^A-Za-z0-9_.-]", "-", s)
    return s[:120] if s else "unknown"

def ensure_lists(rec: Dict[str, Any]) -> None:
    rec.setdefault("details", {})
    rec.setdefault("transactions", [])
    rec.setdefault("acquisition_strategy", {})
    rec.setdefault("documents", [])
    rec.setdefault("notes", [])
    rec["details"].setdefault("latitude", None)
    rec["details"].setdefault("longitude", None)

def geocode_address(address: str):
    """Return (lat, lon) or None if not available."""
    if not address or not address.strip() or Nominatim is None:
        return None
    try:
        geolocator = Nominatim(user_agent="seh-property-card (contact: idnjuguna@asu.edu)")
        loc = geolocator.geocode(address, timeout=10)
        if loc:
            return float(loc.latitude), float(loc.longitude)
    except Exception:
        return None
    return None

def has_coords(a, b) -> bool:
    try:
        return a is not None and b is not None and float(a) != 0.0 and float(b) != 0.0
    except Exception:
        return False

#Define the map rendering function with toggle support
def render_property_map(df: pd.DataFrame, mode: str = "Markers") -> Optional[pdk.Deck]:
    if df.empty:
        view = pdk.ViewState(latitude=0, longitude=0, zoom=1)
    else:
        first = df.iloc[0]
        view = pdk.ViewState(
            latitude=float(first["lat"]),
            longitude=float(first["lon"]),
            zoom=17 if len(df) == 1 else 11,
            pitch=0,
            bearing=0,
        )

    if mode == "Markers":
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position='[lon, lat]',
            get_fill_color="[255, 0, 0]",
            get_radius=10,
            radiusScale=10,
            radiusMinPixels=5,
            radiusMaxPixels=30,
            pickable=True,
        )
    elif mode == "Heatmap":
        layer = pdk.Layer(
            "HeatmapLayer",
            data=df,
            get_position='[lon, lat]',
            get_weight=1,
            radiusPixels=60,
            aggregation='"SUM"',
        )
    else:
        return None

    return pdk.Deck(
        map_provider="carto",
        map_style="light",
        initial_view_state=view,
        layers=[layer],
        tooltip={"text": "{parcel_address}"} if mode == "Markers" else None,
    )

def deck_scatter(df: pd.DataFrame) -> Optional[pdk.Deck]:
    """PyDeck map with light basemap + scatter points; df must have lat/lon and parcel_address."""
    if df.empty or "lat" not in df.columns or "lon" not in df.columns:
        return None  # avoids crashing

    first = df.iloc[0]
    view = pdk.ViewState(
        latitude=float(first["lat"]),
        longitude=float(first["lon"]),
        zoom=15 if len(df) == 1 else 11,
    )

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position='[lon, lat]',  # NOTE: [lon, lat]
        get_fill_color="[255, 0, 0]",  # <-- RED (R, G, B)
        get_radius=18,
        pickable=True,
    )

    return pdk.Deck(
        map_provider="carto",
        map_style="light",
        initial_view_state=view,
        layers=[layer],
        tooltip={"text": "{parcel_address}"},
    )

def _parse_date(val):
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val:
        try:
            return datetime.fromisoformat(val).date()
        except Exception:
            return None
    return None

import re

def extract_int(val, default=0):
    match = re.search(r'\d+', str(val))
    return int(match.group()) if match else default

#def extract_float(val, default=0.0):
    #match = re.search(r'\d+(\.\d+)?', str(val))
    #return float(match.group()) if match else default

def extract_float(val, default=0.0, allow_sign=False):
    try:
        return float(val)
    except Exception:
        if val is None:
            return default
        s = str(val).strip()
        pattern = r'-?\d+(?:\.\d+)?' if allow_sign else r'\d+(?:\.\d+)?'
        m = re.search(pattern, s)
        return float(m.group()) if m else default
    
#handler for unit details page export
def generate_unit_pdf(record, address, logo_path="logo.png"):
    """
    Create a multi-section PDF report for one property.

    record: dict with keys "details", "transactions", "acquisition_strategy", "notes".
    address: parcel address (string).
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    header_height = 90
    bottom_margin = 50
    line_height = 14

    # ---------- Header / footer helpers ----------
    def draw_header():
        # Logo (optional)
        if logo_path and os.path.exists(logo_path):
            try:
                c.drawImage(
                    logo_path,
                    50,
                    height - 70,
                    width=50,
                    height=50,
                    preserveAspectRatio=True,
                    mask="auto",
                )
            except Exception:
                pass

        # Title + address
        c.setFont("Helvetica-Bold", 18)
        c.drawString(120, height - 45, "Property Card Database")
        c.setFont("Helvetica", 11)
        c.drawString(120, height - 60, f"Shared Equity Homeownership – {address}")

    def draw_footer():
        c.setFont("Helvetica-Oblique", 9)
        page_num = c.getPageNumber()
        c.drawRightString(width - 50, bottom_margin - 20, f"Page {page_num}")

    def start_page():
        draw_header()
        return height - header_height

    def ensure_space(y, lines=1):
        needed = lines * line_height + 10
        if y - needed < bottom_margin:
            draw_footer()
            c.showPage()
            return start_page()
        return y

    def section_title(text, y):
        y = ensure_space(y, 2)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, y, text)
        y -= line_height
        c.setLineWidth(0.5)
        c.line(50, y, width - 50, y)
        y -= line_height
        c.setFont("Helvetica", 10)
        return y

    # ---------- Unpack record ----------
    details = record.get("details", {}) or {}
    tx_list = record.get("transactions", []) or []
    acq = record.get("acquisition_strategy", {}) or {}
    notes = record.get("notes", []) or {}

    y = start_page()

    # ---------- Part 1: Property details ----------
    y = section_title("Part 1 – Property details", y)

    detail_fields = [
        ("unit_number", "Unit / Apt / Condo Number"),
        ("neighborhood", "Neighborhood"),
        ("city", "City"),
        ("county", "County"),
        ("state", "State"),
        ("zip_code", "Zip code"),
        ("organization", "Organization"),
        ("msa", "MSA"),
        ("unit_type", "Unit type"),
        ("square_footage", "Square footage"),
        ("bedrooms", "Bedrooms"),
        ("bathrooms", "Bathrooms"),
        ("new_construction", "New construction"),
        ("rehabilitation", "Rehabilitation"),
        ("year_built", "Year built"),
        ("latitude", "Latitude"),
        ("longitude", "Longitude"),
        ("other_features", "Other features"),
    ]

    for key, label in detail_fields:
        value = details.get(key, "")
        if value in (None, "", 0):
            continue
        y = ensure_space(y)
        c.drawString(60, y, f"{label}: {value}")
        y -= line_height

    # ---------- Part 2: Transaction details ----------
    if tx_list:
        y = section_title("Part 2 – Transaction details (repeatable)", y)

        tx_fields = [
            ("year_acquired", "Year acquired by CLT"),
            ("year_sold", "Year sold"),
            ("initial_acquisition_cost", "Initial acquisition cost"),
            ("subsidy_amount", "Subsidy amount"),
            ("subsidy_source", "Subsidy source"),
            ("subsidy_purpose", "Subsidy purpose"),
            ("list_price", "List price"),
            ("time_on_market_months", "Time on market (months)"),
            ("fee_simple_appraisal_value", "Fee simple appraisal value"),
            ("leasehold_appraised", "Leasehold appraised"),
            ("appraised_market_value", "Appraised market value"),
            ("purchase_price", "Purchase price"),
            ("write_down", "Write down"),
            ("base_price", "Base price"),
            ("seller_equity_amount", "Seller equity amount"),
            ("loan_amount", "Loan amount"),
            ("interest_rate", "Interest rate (%)"),
            ("loan_type", "Loan type"),
            ("lender_name", "Lender name"),
            ("loan_term_years", "Loan term (years)"),
            ("monthly_payments", "Monthly payments"),
            ("monthly_taxes_and_insurance", "Monthly taxes & insurance"),
            ("land_fee", "Land fee"),
            ("resale_formula", "Resale formula"),
            ("additional_repair_amount", "Additional repair amount"),
            ("additional_repair_purpose", "Additional repair purpose"),
            ("additional_repair_source", "Additional repair source"),
            ("household_size", "Household size"),
            ("household_income_to_AMI_percent", "Household income to AMI (%)"),
            ("household_income_at_move_in", "Household income at move in"),
            ("household_income_at_move_out", "Household income at move out"),
            ("loan_remaining_seller", "Loan remaining from seller"),
            ("length_of_tenure", "Length of tenure (years)"),
            ("affordability_relative_to_market", "Affordability relative to market (%)"),
        ]

        for idx, tx in enumerate(tx_list, start=1):
            y = ensure_space(y, 3)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(55, y, f"Transaction #{idx}")
            y -= line_height
            c.setFont("Helvetica", 10)

            for key, label in tx_fields:
                val = tx.get(key, "")
                if val in (None, "", 0):
                    continue
                y = ensure_space(y)
                c.drawString(70, y, f"{label}: {val}")
                y -= line_height

            y -= line_height  # extra space after each transaction

    # ---------- Part 3: Acquisition strategy ----------
    if acq:
        y = section_title("Part 3 – Acquisition strategy", y)
        long_fields = [
            ("acquisition_criteria_type", "Acquisition criteria type"),
            ("acquisition_strategy_description", "Acquisition strategy description"),
            ("exclusion_criteria", "Exclusion criteria"),
        ]
        for key, label in long_fields:
            val = acq.get(key, "")
            if not val:
                continue
            text = f"{label}: {val}"
            # simple wrapping at ~90 characters
            while text:
                y = ensure_space(y)
                line = text[:90]
                text = text[90:]
                c.drawString(60, y, line)
                y -= line_height
        y -= line_height

    # ---------- Notes ----------
    if notes:
        y = section_title("Notes", y)

        try:
            notes_sorted = sorted(
                notes,
                key=lambda n: n.get("timestamp") or "",
                reverse=True,
            )
        except Exception:
            notes_sorted = notes

        for n in notes_sorted:
            ts = n.get("timestamp", "")
            txt = n.get("text", "")

            header = f"- {ts}:"
            y = ensure_space(y)
            c.drawString(60, y, header)
            y -= line_height

            remaining = txt
            while remaining:
                y = ensure_space(y)
                line = remaining[:100]
                remaining = remaining[100:]
                c.drawString(70, y, line)
                y -= line_height

            y -= line_height / 2

    # Finish
    draw_footer()
    c.save()
    buffer.seek(0)
    return buffer

# ------------- Section state: init/reset/load helpers -------------
UNIT_TYPE_OPTIONS = [
    "Single family (detached)",
    "Single family (attached; e.g., townhome)",
    "Multi-family: Duplex, 4-plex",
    "Multi-family (mid-scale): 5-25 unit",
    "Multi-family (mid-scale): 26 + unit"
]

def reset_details_form():
    st.session_state["k_neighborhood"] = ""
    st.session_state["k_zip"] = 0
    st.session_state["k_city"] = ""
    st.session_state["k_county"] = ""
    st.session_state["k_state"] = ""
    st.session_state["k_organization"] = ""
    st.session_state["k_msa"] = ""
    st.session_state["k_new_construction"] = "Yes"
    st.session_state["k_rehabilitation"] = "Yes"
    st.session_state["k_year_built"] = 0
    st.session_state["k_unit_type"] = UNIT_TYPE_OPTIONS[0]
    st.session_state["k_sqft"] = 0
    st.session_state["k_bedrooms"] = 0
    st.session_state["k_bathrooms"] = 0.0
    st.session_state["k_other_features"] = ""
    st.session_state["k_unit_number"] = ""
    st.session_state["lat_input"] = 0.0
    st.session_state["lon_input"] = 0.0


def load_details_form_for(addr: str, props: Dict[str, Any]):
    rec = props.get(addr, {"details": {}})
    det = rec.get("details", {})

    st.session_state["k_unit_number"] = det.get("unit_number", "")
    st.session_state["k_neighborhood"] = det.get("neighborhood", "")
    st.session_state["k_zip"] = extract_int(det.get("zip_code", 0))
    st.session_state["k_city"] = det.get("city", "")
    st.session_state["k_county"] = det.get("county", "")
    st.session_state["k_state"] = det.get("state", "")
    st.session_state["k_organization"] = det.get("organization", "")
    st.session_state["k_msa"] = det.get("msa", "")
    st.session_state["k_new_construction"] = det.get("new_construction", "Yes") or "Yes"
    st.session_state["k_rehabilitation"] = det.get("rehabilitation", "Yes") or "Yes"
    st.session_state["k_year_built"] = extract_int(det.get("year_built", 0))
    st.session_state["k_unit_type"] = det.get("unit_type", UNIT_TYPE_OPTIONS[0]) or UNIT_TYPE_OPTIONS[0]
    st.session_state["k_sqft"] = extract_int(det.get("square_footage", 0))
    st.session_state["k_bedrooms"] = extract_float(det.get("bedrooms", 0))
    st.session_state["k_bathrooms"] = extract_float(det.get("bathrooms", 0))
    st.session_state["k_other_features"] = det.get("other_features", "")
    #st.session_state["lat_input"] = extract_float(det.get("latitude", 0.0))
    #st.session_state["lon_input"] = extract_float(det.get("longitude", 0.0))
    st.session_state["lat_input"] = extract_float(det.get("latitude", 0.0), 0.0, allow_sign=True)
    st.session_state["lon_input"] = extract_float(det.get("longitude", 0.0), 0.0, allow_sign=True)


from datetime import date

# Transaction Add form keys
TX_KEYS_DEFAULTS = {
    #column1
    "tx_year_acquired": date.today(),
    "tx_year_sold": date.today(),
    "tx_initial_acquisition_cost": 0.0,
    "tx_subsidy_amount": 0.0,
    "tx_subsidy_source": "",
    "tx_subsidy_purpose": "",
    "tx_list_price": 0.0,
    "tx_time_on_market_months": 0.0,
    "tx_fee_simple_appraisal_value": 0.0,
    "tx_leasehold_appraised": 0.0,
    "tx_appraised_market_value": 0.0,
    #column2
    "tx_purchase_price": 0.0,
    "tx_write_down": 0.0,
    "tx_base_price": 0.0,
    "tx_seller_equity_amount": 0.0,
    "tx_loan_amount": 0.0,
    "tx_interest_rate": 0.000,
    "tx_loan_type": "",
    "tx_lender_name": "",
    "tx_loan_term_years": 0,
    "tx_monthly_payments": 0.0,
    "tx_monthly_taxes_and_insurance": 0.0,
    "tx_land_fee": 0.0,
    #column3
    "tx_resale_formula": "",
    "tx_additional_repair_amount": 0.0,
    "tx_additional_repair_purpose": "",
    "tx_additional_repair_source": "",
    "tx_household_size": 0,
    "tx_household_income_to_AMI_percent": 0.0,
    "tx_household_income_at_move_in": 0.0,
    "tx_household_income_at_move_out": 0.0,
    "tx_loan_remaining_seller": 0.0,
    "tx_length_of_tenure": 0.0,
    "tx_affordability_relative_to_market": 0.0,
}

def reset_tx_add_form(rerun: bool = False):
    # clear only tx_* keys; avoid post-widget mutations during render
    for k in TX_KEYS_DEFAULTS.keys():
        st.session_state.pop(k, None)
    if rerun:
        st.rerun()

def ensure_tx_add_defaults():
    for k, v in TX_KEYS_DEFAULTS.items():
        st.session_state.setdefault(k, v)

# Acquisition Strategy keys
def reset_acq_form():
    for k in ["acq_type", "acq_desc", "acq_excl"]:
        st.session_state[k] = ""

def load_acq_form_for(addr: str, props: Dict[str, Any]):
    rec = props.get(addr, {})
    acq = rec.get("acquisition_strategy", {})
    st.session_state["acq_type"] = acq.get("acquisition_criteria_type", "")
    st.session_state["acq_desc"] = acq.get("acquisition_strategy_description", "")
    st.session_state["acq_excl"] = acq.get("exclusion_criteria", "")


properties: Dict[str, Any] = load_data()
if "selected_address" not in st.session_state:
    st.session_state.selected_address = ""

if "upload_version" not in st.session_state:
    st.session_state["upload_version"] = 0  # lets us "clear" file_uploader

# ---------- Search & Select ----------
st.subheader("Find a property")
q = st.text_input("Search by parcel address", "", placeholder="e.g., 123 Main")
matches = [a for a in properties.keys() if q.lower() in a.lower()] if q else sorted(properties.keys())
sel = st.selectbox("Select a saved property", [""] + matches, index=0)
if sel != st.session_state.selected_address and sel != "":
    st.session_state.selected_address = sel

# ---- PDF download for selected property ----
current_addr = st.session_state.selected_address

if current_addr:
    unit_data = properties.get(current_addr)
    if unit_data:
        pdf_buffer = generate_unit_pdf(
            unit_data,
            current_addr,
            logo_path="logo.png",  # make sure this file exists next to app.py
        )

        st.download_button(
            label="📄 Download PDF for this property",
            data=pdf_buffer,
            file_name=f"{current_addr}_report.pdf",
            mime="application/pdf",
        )

# New property button (full reset)
col_new, col_reset_all = st.columns([1, 1])
with col_new:
    if st.button("➕ New property"):
        st.session_state.selected_address = ""
        st.session_state["_addr_loaded_for"] = ""
        reset_details_form()
        reset_tx_add_form(rerun=False)   # only clear, no rerun here)
        reset_acq_form()
        st.experimental_rerun()

st.markdown("---")


# ---------- PART 1: Property details ----------
st.header("Part 1: Property details")

# Address field
parcel_address = st.text_input("Parcel address", value=st.session_state.selected_address or "")

# If user typed/switched address, load section forms from that record (or defaults)
if st.session_state.get("_addr_loaded_for", None) != parcel_address:
    if parcel_address.strip():
        # switching to a non-empty address:
        load_details_form_for(parcel_address, properties)
        load_acq_form_for(parcel_address, properties)
        reset_tx_add_form(rerun=False)  # clear tx keys, NO rerun here
    else:
        # empty address: reset other sections only
        reset_details_form()
        reset_acq_form()
        # DO NOT call reset_tx_add_form() here (would loop on first load)

    st.session_state["_addr_loaded_for"] = parcel_address


def _do_geocode():
    if Nominatim is None:
        st.session_state["__geo_msg"] = "need_geopy"
        return

    # Try to use stored coordinates if they exist
    rec = st.session_state.get("props", {}).get(parcel_address, {})
    det = rec.get("details", {})
    
    lat = det.get("latitude")
    lon = det.get("longitude")

    try:
        if lat and lon:
            st.session_state["lat_input"] = float(lat)
            st.session_state["lon_input"] = float(lon)
            st.session_state["__geo_msg"] = f"from_data:{float(lat):.6f},{float(lon):.6f}"
            return
    except ValueError:
        pass  # Will fall through to geocoding below if parsing fails

    # If no lat/lon, fallback to geocoding
    full_address = f"{parcel_address}, {st.session_state.get('k_city', '')}, {st.session_state.get('k_state', '')} {st.session_state.get('k_zip', '')}"
    coords = geocode_address(full_address)

    if coords:
        st.session_state["lat_input"] = coords[0]
        st.session_state["lon_input"] = coords[1]
        st.session_state["__geo_msg"] = f"geocoded:{coords[0]:.6f},{coords[1]:.6f}"
    else:
        st.session_state["__geo_msg"] = f"noresult for: {full_address}"

# Add new field row for: City, County, State
city_col, county_col, state_col = st.columns(3)
with city_col:
    st.text_input("City", key="k_city")
with county_col:
    st.text_input("County", key="k_county")
with state_col:
    st.text_input("State", key="k_state")

# Second row for ZIP, Organization, MSA
zip_col, org_col, msa_col = st.columns(3)
with zip_col:
    st.number_input("Zip code", key="k_zip", step=1)
with org_col:
    st.text_input("Organization", key="k_organization")
with msa_col:
    st.text_input("MSA", key="k_msa")

col1, col2 = st.columns(2)
with col1:
    st.text_input("Unit / Apt / Condo Number", key="k_unit_number")
    neighborhood = st.text_input("Neighborhood", key="k_neighborhood")
    new_construction = st.selectbox(
        "New construction",
        ["Yes", "No"],
        index=0 if st.session_state.get("k_new_construction", "Yes") == "Yes" else 1,
        key="k_new_construction",
    )

    rehabilitation = st.selectbox(
        "Rehabilitation",
        ["Yes", "No"],
        index=0 if st.session_state.get("k_rehabilitation", "Yes") == "Yes" else 1,
        key="k_rehabilitation",
    )
    year_built = st.number_input("Year built", key="k_year_built", step=1)

with col2:
    ut_idx = to_index_or_default(UNIT_TYPE_OPTIONS, st.session_state.get("k_unit_type", UNIT_TYPE_OPTIONS[0]), 0)
    unit_type = st.selectbox("Unit type", UNIT_TYPE_OPTIONS, index=ut_idx, key="k_unit_type")
    square_footage = st.number_input("Square footage", key="k_sqft", step=1)
    bedrooms = st.number_input("Bedrooms", key="k_bedrooms", step=1)
    bathrooms = st.number_input("Bathrooms", key="k_bathrooms", step=0.5, format="%.1f")
    other_features = st.text_area("Other features", key="k_other_features")

st.subheader("Location")
lc1, lc2, lc3 = st.columns([1, 1, 2])
with lc1:
    st.number_input("Latitude", key="lat_input", format="%.6f")
with lc2:
    st.number_input("Longitude", key="lon_input", format="%.6f")
with lc3:
    st.button("📍 Geocode address", on_click=_do_geocode)

_msg = st.session_state.pop("__geo_msg", "")
if _msg.startswith("ok:"):
    st.success("Geocoded: " + _msg[3:])
elif _msg == "noresult":
    st.warning("No result for that address. Try adding city/ZIP or set lat/lon manually.")
elif _msg == "need_geopy":
    st.error("Geocoding requires geopy. Install in this app's venv: .\\.venv\\Scripts\\python.exe -m pip install geopy")


# ---------- Single-property map ----------
if has_coords(st.session_state["lat_input"], st.session_state["lon_input"]):
    _single_df = pd.DataFrame({
        "parcel_address": [parcel_address or "(unsaved address)"],
        "lat": [float(st.session_state["lat_input"])],
        "lon": [float(st.session_state["lon_input"])],
    })
    st.pydeck_chart(deck_scatter(_single_df))
    

    st.markdown(
        f"[Open in Google Maps](https://www.google.com/maps?q={st.session_state['lat_input']},{st.session_state['lon_input']}) &nbsp;|&nbsp; "
        f"[OpenStreetMap](https://www.openstreetmap.org/?mlat={st.session_state['lat_input']}&mlon={st.session_state['lon_input']}#map=18/{st.session_state['lat_input']}/{st.session_state['lon_input']})"
    )

# ---------- Save / Clear buttons (section-only) ----------
sc1, sc2 = st.columns([1, 1])
with sc1:
    if st.button("💾 Save property details"):
        if not parcel_address.strip():
            st.error("Parcel address is required.")
        else:
            properties.setdefault(parcel_address, {
                "details": {},
                "transactions": [],
                "acquisition_strategy": {},
                "documents": [],
                "notes": []
            })
            properties[parcel_address]["details"] = {
                "unit_number": st.session_state["k_unit_number"],
                "neighborhood": st.session_state["k_neighborhood"],
                "zip_code": st.session_state["k_zip"],
                "city": st.session_state["k_city"],
                "county": st.session_state["k_county"],
                "state": st.session_state["k_state"],
                "organization": st.session_state["k_organization"],
                "msa": st.session_state["k_msa"],
                "unit_number": st.session_state["k_unit_number"],
                "new_construction": st.session_state["k_new_construction"],
                "rehabilitation": st.session_state["k_rehabilitation"],
                "year_built": st.session_state["k_year_built"],
                "unit_type": st.session_state["k_unit_type"],
                "square_footage": st.session_state["k_sqft"],
                "bedrooms": st.session_state["k_bedrooms"],
                "bathrooms": st.session_state["k_bathrooms"],
                "other_features": st.session_state["k_other_features"],
                "latitude": st.session_state["lat_input"],
                "longitude": st.session_state["lon_input"],
            }

            # If address changed, move record (preserve other sections)
            if st.session_state.selected_address and parcel_address != st.session_state.selected_address:
                old = st.session_state.selected_address
                for key in ["transactions", "acquisition_strategy", "documents", "notes"]:
                    properties[parcel_address][key] = properties.get(old, {}).get(key, [] if key != "acquisition_strategy" else {})
                if old in properties:
                    del properties[old]
                st.session_state.selected_address = parcel_address

            save_data(properties)
            st.success("Property details saved.")

with sc2:
    if st.button("🧹 Clear property details (this section only)"):
        reset_details_form()
        st.success("Cleared Property Details section.")

# ---------- Danger zone — delete property ----------
current_addr_key_part1 = parcel_address.strip() or st.session_state.selected_address
with st.expander("Danger zone: Delete this property"):
    confirm = st.text_input("Type DELETE to confirm")
    if st.button("🗑️ Permanently delete property") and confirm.strip().upper() == "DELETE":
        if current_addr_key_part1 and current_addr_key_part1 in properties:
            del properties[current_addr_key_part1]
            save_data(properties)
            st.session_state.selected_address = ""
            st.session_state["_addr_loaded_for"] = ""
            reset_details_form()
            reset_tx_add_form(rerun=False)  # only clear, no rerun here
            reset_acq_form()
            st.success("Property deleted.")
            st.experimental_rerun()

st.markdown("---")

# ---------- PART 2: Transaction details (repeatable) ----------
st.header("Part 2: Transaction details (repeatable)")

current_addr_key = parcel_address.strip() or st.session_state.selected_address
existing_tx = properties.get(current_addr_key, {}).get("transactions", [])

# Existing transactions with Edit/Delete
if existing_tx:
    st.markdown("**Existing transactions**")
    for i, t in enumerate(existing_tx):
        with st.expander(f"Transaction #{i+1}"):
            acq = t.get("year_acquired") or ""
            sold = t.get("year_sold") or ""
            price = t.get("purchase_price") or 0
            hh_size = t.get("household_size", "n/a")
            ami_pct = t.get("household_income_to_AMI_percent", "n/a")
            st.caption(f"Acquired: {acq} | Sold: {sold} | Purchase price: {price} | HH size: {hh_size} | AMI%: {ami_pct}")

            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button(f"✏️ Edit #{i+1}", key=f"edit_tx_{i}"):
                    st.session_state["edit_tx_index"] = i
            with c2:
                if st.button(f"🗑️ Delete #{i+1}", key=f"del_tx_{i}"):
                    properties[current_addr_key]["transactions"].pop(i)
                    save_data(properties)
                    st.success(f"Deleted transaction #{i+1}.")
                    st.experimental_rerun()

# Edit form (appears when Edit is clicked)
edit_i = st.session_state.get("edit_tx_index", None)
if edit_i is not None and 0 <= edit_i < len(existing_tx):
    tx = existing_tx[edit_i]
    st.subheader(f"Edit Transaction #{edit_i+1}")

    with st.form("edit_tx_form"):
        ec1, ec2, ec3 = st.columns(3)
        #..............column1.............
        with ec1:
            year_acquired_e = st.date_input("Year acquired by CLT", value=_parse_date(tx.get("year_acquired")))
            year_sold_e = st.date_input("Year sold", value=_parse_date(tx.get("year_sold")))
            initial_acquisition_cost_e = st.number_input("Initial acquisition cost", value=float(tx.get("initial_acquisition_cost") or 0.0), step=1000.0)
            subsidy_amount_e = st.number_input("Subsidy amount", value=float(tx.get("subsidy_amount") or 0.0), step=1000.0)
            subsidy_source_e = st.text_input("Subsidy source", value=str(tx.get("subsidy_source") or ""))
            subsidy_purpose_e = st.text_input("Subsidy purpose", value=str(tx.get("subsidy_purpose") or ""))
            list_price_e = st.number_input("List price", value=float(tx.get("list_price") or 0.0), step=1000.0)
            time_on_market_months_e = st.number_input("Time on the market (months)", value=float(tx.get("time_on_market_months") or 0.0), step=0.5)
            fee_simple_appraisal_value_e = st.number_input("Fee simple appraisal value", value=float(tx.get("fee_simple_appraisal_value") or 0.0), step=1000.0)
            leasehold_appraised_e = st.number_input("Leasehold appraised", value=float(tx.get("leasehold_appraised") or 0.0), step=1000.0)
            appraised_market_value_e = st.number_input("Appraised market value", value=float(tx.get("appraised_market_value") or 0.0), step=1000.0)
        #..............column2.............
        with ec2:
            purchase_price_e = st.number_input("Purchase price", value=float(tx.get("purchase_price") or 0.0), step=1000.0)
            write_down_e = st.number_input("Write down", value=float(tx.get("write_down") or 0.0), step=500.0)
            base_price_e = st.number_input("Base price", value=float(tx.get("base_price") or 0.0), step=1000.0)
            seller_equity_amount_e = st.number_input("Seller equity amount", value=float(tx.get("seller_equity_amount") or 0.0), step=500.0)
            loan_amount_e = st.number_input("Loan amount", value=float(tx.get("loan_amount") or 0.0), step=1000.0)
            interest_rate_e = st.number_input("Interest rate (%)", value=float(tx.get("interest_rate") or 0.0), step=0.001, format="%.3f", min_value=0.0, max_value=100.0)
            loan_type_e = st.text_input("Loan type", value=str(tx.get("loan_type") or ""))
            lender_name_e = st.text_input("Lender name", value=str(tx.get("lender_name") or ""))
            loan_term_years_e = st.number_input("Loan term (years)", value=float(tx.get("loan_term_years") or 0), step=1)
            monthly_payments_e = st.number_input("Monthly payments", value=float(tx.get("monthly_payments") or 0.0), step=50.0)
            monthly_taxes_and_insurance_e = st.number_input("Monthly taxes and insurance", value=float(tx.get("monthly_taxes_and_insurance") or 0.0), step=50.0)
            land_fee_e = st.number_input("Land fee", value=float(tx.get("land_fee") or 0.0), step=50.0)
        #..............column3.............
        with ec3:    
            resale_formula_e = st.text_input("Resale formula", value=str(tx.get("resale_formula") or ""))
            additional_repair_amount_e = st.number_input("Additional repair amount", value=float(tx.get("additional_repair_amount") or 0.0), step=500.0)
            additional_repair_purpose_e = st.text_input("Additional repair purpose", value=str(tx.get("additional_repair_purpose") or ""))
            additional_repair_source_e = st.text_input("Additional repair source", value=str(tx.get("additional_repair_source") or ""))
            household_size_e = st.number_input("Household size", value=int(tx.get("household_size") or 0), step=1, min_value=0)
            household_income_to_AMI_percent_e = st.number_input("Household income to AMI (%)", value=float(tx.get("household_income_to_AMI_percent") or 0.0), step=0.1)
            household_income_at_move_in_e = st.number_input("Household income at move in", value=float(tx.get("household_income_at_move_in") or 0.0), step=1000.0)
            household_income_at_move_out_e = st.number_input("Household income at move out", value=float(tx.get("household_income_at_move_out") or 0.0), step=1000.0)
            loan_remaining_seller_e = st.number_input("Loan remaining from seller", value=float(tx.get("loan_remaining_seller") or 0.0), step=1000.0)
            length_of_tenure_e = st.number_input("Length of tenure (years)", value=float(tx.get("length_of_tenure") or 0.0), step=0.5)
            # Auto-calculate a default, but allow override
            base_price_val = float(tx.get("base_price") or 0.0)
            fee_simple_val = float(tx.get("fee_simple_appraisal_value") or 0.0)
            if fee_simple_val > 0:
                default_affordability = (1 - (base_price_val / fee_simple_val)) * 100
            else:
                default_affordability = float(tx.get("affordability_relative_to_market") or 0.0)

            affordability_relative_to_market_e = st.number_input(
                "Affordability relative to the market (%)",
                value=default_affordability,
                step=0.1,
                format="%.2f"
            )
            #affordability_relative_to_market_e = st.number_input("Affordability relative to the market (%)", value=float(tx.get("affordability_relative_to_market") or 0.0), step=0.1)
        if st.form_submit_button("💾 Save changes"):
            properties[current_addr_key]["transactions"][edit_i] = {
                "year_acquired": year_acquired_e.isoformat() if year_acquired_e else None,
                "year_sold": year_sold_e.isoformat() if year_sold_e else None,
                "initial_acquisition_cost": initial_acquisition_cost_e,
                "subsidy_amount": subsidy_amount_e,
                "subsidy_source": subsidy_source_e,
                "subsidy_purpose": subsidy_purpose_e,
                "list_price": list_price_e,
                "time_on_market_months": time_on_market_months_e,
                "fee_simple_appraisal_value": fee_simple_appraisal_value_e,
                "leasehold_appraised": leasehold_appraised_e,
                "appraised_market_value": appraised_market_value_e,
                "purchase_price": purchase_price_e,
                "write_down": write_down_e,
                "base_price": base_price_e,
                "seller_equity_amount": seller_equity_amount_e,
                "loan_amount": loan_amount_e,
                "interest_rate": interest_rate_e,
                "loan_type": loan_type_e,
                "lender_name": lender_name_e,
                "loan_term_years": loan_term_years_e,
                "monthly_payments": monthly_payments_e,
                "monthly_taxes_and_insurance": monthly_taxes_and_insurance_e,
                "land_fee": land_fee_e,
                "resale_formula": resale_formula_e,
                "additional_repair_amount": additional_repair_amount_e,
                "additional_repair_purpose": additional_repair_purpose_e,
                "additional_repair_source": additional_repair_source_e,
                "household_size": household_size_e,
                "household_income_to_AMI_percent": household_income_to_AMI_percent_e,
                "household_income_at_move_in": household_income_at_move_in_e,
                "household_income_at_move_out": household_income_at_move_out_e,
                "loan_remaining_seller": loan_remaining_seller_e,
                "length_of_tenure": length_of_tenure_e,
                "affordability_relative_to_market": affordability_relative_to_market_e,
            }
            save_data(properties)
            st.session_state["edit_tx_index"] = None
            st.success("Transaction updated.")
            st.experimental_rerun()

    if st.button("Cancel editing"):
        st.session_state["edit_tx_index"] = None
        st.experimental_rerun()

# Seed defaults exactly once before the add form
ensure_tx_add_defaults()

with st.form("tx_form"):
    st.subheader("Add a new transaction")
    c1, c2, c3 = st.columns(3)
    #..............column1.............
    with c1:
        st.date_input("Year acquired by CLT", key="tx_year_acquired")
        st.caption(":red[Change date! ❗]")
        st.date_input("Year sold", key="tx_year_sold")
        st.caption(":red[Change date if different! ❗]")

        st.number_input("Initial acquisition cost", step=1000.0, key="tx_initial_acquisition_cost")
        st.number_input("Subsidy amount", step=1000.0, key="tx_subsidy_amount")
        st.text_input("Subsidy source", key="tx_subsidy_source")
        st.text_input("Subsidy purpose", key="tx_subsidy_purpose")

        st.number_input("List price", step=1000.0, key="tx_list_price")
        st.number_input("Time on the market (months)", step=0.5, key="tx_time_on_market_months")
        st.number_input("Fee simple appraisal value", step=1000.0, key="tx_fee_simple_appraisal_value")
        st.number_input("Leasehold appraised", step=1000.0, key="tx_leasehold_appraised")
        st.number_input("Appraised market value", step=1000.0, key="tx_appraised_market_value")
    #..............column2.............
    with c2:
        st.number_input("Purchase price", step=1000.0, key="tx_purchase_price")
        st.number_input("Write down", step=500.0, key="tx_write_down")
        st.number_input("Base price", step=1000.0, key="tx_base_price")
        st.number_input("Seller equity amount", step=500.0, key="tx_seller_equity_amount")
        st.number_input("Loan amount", step=1000.0, key="tx_loan_amount")
        st.number_input("Interest rate (%)", step=0.001, format="%.3f", min_value=0.0, max_value=100.0, key="tx_interest_rate")
        st.text_input("Loan type", key="tx_loan_type")   # e.g. Conventional, FHA, CLT-specific
        st.text_input("Lender name", key="tx_lender_name")
        st.number_input("Loan term (years)", step=1, min_value=0, key="tx_loan_term_years")
        st.number_input("Monthly payments", step=50.0, key="tx_monthly_payments")
        st.number_input("Monthly taxes and insurance", step=50.0, key="tx_monthly_taxes_and_insurance")
        st.number_input("Land fee", step=50.0, key="tx_land_fee")
    #..............column3.............
    with c3:
        st.text_input("Resale formula", key="tx_resale_formula")
        st.number_input("Additional repair amount", step=500.0, key="tx_additional_repair_amount")
        st.text_input("Additional repair purpose", key="tx_additional_repair_purpose")
        st.text_input("Additional repair source", key="tx_additional_repair_source")
        st.number_input("Household size", step=1, min_value=0, key="tx_household_size")
        st.number_input("Household income to AMI (%)", step=0.1, key="tx_household_income_to_AMI_percent")
        st.number_input("Household income at move in", step=1000.0, key="tx_household_income_at_move_in")
        st.number_input("Household income at move out", step=1000.0, key="tx_household_income_at_move_out")
        st.number_input("Loan remaining from seller", step=1000.0, key="tx_loan_remaining_seller")
        st.number_input("Length of tenure (years)", step=0.5, key="tx_length_of_tenure")
                # Auto-calculate a default, but allow override
        base_price_val = st.session_state.get("tx_base_price", 0.0)
        fee_simple_val = st.session_state.get("tx_fee_simple_appraisal_value", 0.0)
        if fee_simple_val > 0:
            default_affordability = (1 - (base_price_val / fee_simple_val)) * 100
        else:
            default_affordability = st.session_state.get("tx_affordability_relative_to_market", 0.0)

        st.number_input(
            "Affordability relative to the market (%)",
            value=default_affordability,
            step=0.1,
            format="%.2f",
            key="tx_affordability_relative_to_market"
        )
        #st.number_input("Affordability relative to the market (%)", step=0.1, key="tx_affordability_relative_to_market")
    cc1, cc2 = st.columns([1, 1])
    add_clicked = cc1.form_submit_button("➕ Add transaction")
    clear_tx_clicked = cc2.form_submit_button("🧹 Clear transaction form")

    if add_clicked:
        if not current_addr_key:
            st.error("Enter and save a parcel address first.")
        else:
            properties.setdefault(current_addr_key, {"details": {}, "transactions": [], "acquisition_strategy": {}, "documents": [], "notes": []})
            properties[current_addr_key]["transactions"].append({
                "year_acquired": to_iso(st.session_state["tx_year_acquired"]),
                "year_sold": to_iso(st.session_state["tx_year_sold"]),
                "initial_acquisition_cost": st.session_state["tx_initial_acquisition_cost"],
                "subsidy_amount": st.session_state["tx_subsidy_amount"],
                "subsidy_source": st.session_state["tx_subsidy_source"],
                "subsidy_purpose": st.session_state["tx_subsidy_purpose"],
                "list_price": st.session_state["tx_list_price"],
                "time_on_market_months": st.session_state["tx_time_on_market_months"],
                "fee_simple_appraisal_value": st.session_state["tx_fee_simple_appraisal_value"],
                "leasehold_appraised": st.session_state["tx_leasehold_appraised"],
                "appraised_market_value": st.session_state["tx_appraised_market_value"],
                "purchase_price": st.session_state["tx_purchase_price"],
                "write_down": st.session_state["tx_write_down"],
                "base_price": st.session_state["tx_base_price"],
                "seller_equity_amount": st.session_state["tx_seller_equity_amount"],
                "loan_amount": st.session_state["tx_loan_amount"],
                "interest_rate": st.session_state["tx_interest_rate"],
                "monthly_payments": st.session_state["tx_monthly_payments"],
                "monthly_taxes_and_insurance": st.session_state["tx_monthly_taxes_and_insurance"],
                "land_fee": st.session_state["tx_land_fee"],
                "resale_formula": st.session_state["tx_resale_formula"],
                "additional_repair_amount": st.session_state["tx_additional_repair_amount"],
                "additional_repair_purpose": st.session_state["tx_additional_repair_purpose"],
                "additional_repair_source": st.session_state["tx_additional_repair_source"],
                "household_size": st.session_state["tx_household_size"],
                "household_income_to_AMI_percent": st.session_state["tx_household_income_to_AMI_percent"],
                "household_income_at_move_in": st.session_state["tx_household_income_at_move_in"],
                "household_income_at_move_out": st.session_state["tx_household_income_at_move_out"],
                "loan_remaining_seller": st.session_state["tx_loan_remaining_seller"],
                "length_of_tenure": st.session_state["tx_length_of_tenure"],
                "affordability_relative_to_market": st.session_state["tx_affordability_relative_to_market"],
            })
            save_data(properties)
            st.success("Transaction saved.")
            reset_tx_add_form(rerun=True)   # clear + rerun after user action

    if clear_tx_clicked:
        reset_tx_add_form(rerun=True)       # clear + rerun after user action

st.markdown("---")


# ---------- PART 3: Acquisition strategy ----------
st.header("Part 3: Acquisition strategy")

acq_type = st.text_input("Acquisition criteria type", key="acq_type")
acq_desc = st.text_area("Acquisition strategy description", key="acq_desc")
acq_excl = st.text_area("Exclusion criteria", key="acq_excl")

ac1, ac2 = st.columns([1, 1])
with ac1:
    if st.button("💾 Save acquisition strategy"):
        if not current_addr_key:
            st.error("Enter and save a parcel address first.")
        else:
            properties.setdefault(current_addr_key, {"details": {}, "transactions": [], "acquisition_strategy": {}, "documents": [], "notes": []})
            properties[current_addr_key]["acquisition_strategy"] = {
                "acquisition_criteria_type": st.session_state["acq_type"],
                "acquisition_strategy_description": st.session_state["acq_desc"],
                "exclusion_criteria": st.session_state["acq_excl"],
            }
            save_data(properties)
            st.success("Acquisition strategy saved.")
with ac2:
    if st.button("🧹 Clear acquisition strategy (this section only)"):
        reset_acq_form()
        st.success("Cleared Acquisition Strategy section.")

st.markdown("---")

# ---------- Documents & Notes ----------
st.header("Documents & Notes")
os.makedirs(ATTACH_DIR, exist_ok=True)

docs = properties.get(current_addr_key, {}).get("documents", [])
notes = properties.get(current_addr_key, {}).get("notes", [])

if docs:
    st.subheader("Existing documents")
    for i, d in enumerate(docs, start=1):
        colA, colB, colC = st.columns([3, 2, 2])
        with colA:
            st.write(f"**{i}. {d.get('filename','(no name)')}**")
            st.caption(d.get("description", ""))
            st.caption(f"Uploaded: {d.get('uploaded_on','')}")
        full_path = d.get("relpath")
        if full_path and os.path.exists(full_path):
            with open(full_path, "rb") as f:
                data = f.read()
            with colB:
                st.download_button("Download", data=data, file_name=os.path.basename(full_path), key=f"dl_{i}")
        else:
            with colB:
                st.button("Download", disabled=True, key=f"dl_{i}_disabled")
        with colC:
            st.caption(full_path or "")

st.subheader("Upload new documents")
u_key = f"uploader_{st.session_state['upload_version']}"
up_files = st.file_uploader(
    "Select files",
    type=["pdf","doc","docx","xls","xlsx","png","jpg","jpeg","gif","txt","csv"],
    accept_multiple_files=True,
    key=u_key,
)
doc_desc = st.text_input("Optional description for these files", key="doc_desc")

ud1, ud2 = st.columns([1,1])
with ud1:
    if st.button("📎 Save uploaded files"):
        if not current_addr_key:
            st.error("Enter and save a parcel address first.")
        elif not up_files:
            st.warning("Pick one or more files first.")
        else:
            addr_folder = os.path.join(ATTACH_DIR, safe_addr_folder(current_addr_key))
            os.makedirs(addr_folder, exist_ok=True)
            properties.setdefault(current_addr_key, {"details": {}, "transactions": [], "acquisition_strategy": {}, "documents": [], "notes": []})
            for uf in up_files:
                safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", uf.name)
                out_path = os.path.join(addr_folder, safe_name)
                with open(out_path, "wb") as f:
                    f.write(uf.getbuffer())
                properties[current_addr_key]["documents"].append({
                    "filename": safe_name,
                    "relpath": out_path,
                    "uploaded_on": datetime.now().isoformat(timespec="seconds"),
                    "description": st.session_state.get("doc_desc",""),
                })
            save_data(properties)
            st.success(f"Saved {len(up_files)} document(s).")
            # clear uploader
            st.session_state["upload_version"] += 1
            st.session_state["doc_desc"] = ""
            st.experimental_rerun()
with ud2:
    if st.button("🧹 Clear selected files (don’t upload)"):
        st.session_state["upload_version"] += 1
        st.session_state["doc_desc"] = ""
        st.success("Cleared selected files.")
        st.experimental_rerun()

st.subheader("Notes")
if notes:
    st.dataframe(pd.DataFrame(notes), use_container_width=True, height=180)

new_note = st.text_area("Add a note", key="note_text")
nn1, nn2 = st.columns([1,1])
with nn1:
    if st.button("📝 Save note"):
        if not current_addr_key:
            st.error("Enter and save a parcel address first.")
        elif not st.session_state["note_text"].strip():
            st.warning("Type a note first.")
        else:
            properties.setdefault(current_addr_key, {"details": {}, "transactions": [], "acquisition_strategy": {}, "documents": [], "notes": []})
            properties[current_addr_key]["notes"].append({
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "text": st.session_state["note_text"].strip()
            })
            save_data(properties)
            st.success("Note saved.")
            st.session_state["note_text"] = ""
            st.experimental_rerun()
with nn2:
    if st.button("🧹 Clear note text"):
        st.session_state["note_text"] = ""
        st.success("Cleared note text.")

st.markdown("---")

# ---------- Export ONE Excel (5 sheets) ----------
if st.button("📤 Export all to Excel (one file)"):
    props_rows = []
    for addr, rec in properties.items():
        det = rec.get("details", {})
        props_rows.append({
            "parcel_address": addr,
            "neighborhood": det.get("neighborhood"),
            "zip_code": det.get("zip_code"),
            "city": det.get("city"),
            "county": det.get("county"),
            "state": det.get("state"),
            "organization": det.get("organization"),
            "msa": det.get("msa"),
            "unit_number": det.get("unit_number"),
            "new_construction": det.get("new_construction"),
            "rehabilitation": det.get("rehabilitation"),
            "year_built": det.get("year_built"),
            "unit_type": det.get("unit_type"),
            "square_footage": det.get("square_footage"),
            "bedrooms": det.get("bedrooms"),
            "bathrooms": det.get("bathrooms"),
            "other_features": det.get("other_features"),
            "latitude": det.get("latitude"),
            "longitude": det.get("longitude"),
        })

    tx_rows, strat_rows, doc_rows, note_rows = [], [], [], []
    for addr, rec in properties.items():
        for t in rec.get("transactions", []):
            row = {"parcel_address": addr}
            row.update(t)  # includes the three new fields automatically
            tx_rows.append(row)
        s = rec.get("acquisition_strategy", {})
        if s:
            row = {"parcel_address": addr}
            row.update(s)
            strat_rows.append(row)
        for d in rec.get("documents", []):
            doc_rows.append({
                "parcel_address": addr,
                "filename": d.get("filename"),
                "relpath": d.get("relpath"),
                "uploaded_on": d.get("uploaded_on"),
                "description": d.get("description")
            })
        for n in rec.get("notes", []):
            note_rows.append({
                "parcel_address": addr,
                "timestamp": n.get("timestamp"),
                "text": n.get("text")
            })

    try:
        with pd.ExcelWriter(EXPORT_FILE, engine="openpyxl") as xw:
            pd.DataFrame(props_rows).to_excel(xw, sheet_name="Properties", index=False)
            pd.DataFrame(tx_rows).to_excel(xw, sheet_name="Transactions", index=False)
            pd.DataFrame(strat_rows).to_excel(xw, sheet_name="AcquisitionStrategy", index=False)
            pd.DataFrame(doc_rows).to_excel(xw, sheet_name="Documents", index=False)
            pd.DataFrame(note_rows).to_excel(xw, sheet_name="Notes", index=False)
        st.success(f"Exported: {EXPORT_FILE} (5 sheets).")
    except ModuleNotFoundError:
        st.error("Missing Excel engine. Install once: pip install openpyxl")

# ---------- Import from the same Excel (5 sheets) ----------

st.markdown("### 📥 Import from Excel (one file, 5 sheets)")
upload = st.file_uploader("Pick an Excel file exported by this app", type=["xlsx"], key="import_xlsx")

if upload and st.button("Import now"):
    xls = pd.ExcelFile(upload, engine="openpyxl")

    props_df = pd.read_excel(xls, "Properties") if "Properties" in xls.sheet_names else pd.DataFrame()
    tx_df    = pd.read_excel(xls, "Transactions") if "Transactions" in xls.sheet_names else pd.DataFrame()
    strat_df = pd.read_excel(xls, "AcquisitionStrategy") if "AcquisitionStrategy" in xls.sheet_names else pd.DataFrame()
    docs_df  = pd.read_excel(xls, "Documents") if "Documents" in xls.sheet_names else pd.DataFrame()
    notes_df = pd.read_excel(xls, "Notes") if "Notes" in xls.sheet_names else pd.DataFrame()

    new_props: Dict[str, Any] = {}

    # ---- Properties sheet ----
    if not props_df.empty:
        for _, r in props_df.fillna("").iterrows():
            addr = str(r.get("parcel_address", "")).strip()
            if not addr:
                continue

            details = {}
            for k in [
                "neighborhood", "zip_code", "city", "county", "state",
                "organization", "msa","unit_number", "new_construction", "rehabilitation",
                "year_built", "unit_type", "square_footage",
                "bedrooms", "bathrooms", "other_features",
                "latitude", "longitude",
            ]:
                if k in props_df.columns:
                    v = r.get(k)
                    if k in ("latitude", "longitude"):
                        try:
                            v = float(v) if str(v).strip() != "" else None
                        except Exception:
                            v = None
                    details[k] = none_if_nan(v)

            new_props[addr] = {
                "details": details,
                "transactions": [],
                "acquisition_strategy": {},
                "documents": [],
                "notes": [],
            }

    # ---- Transactions sheet ----
    if not tx_df.empty:
        for _, r in tx_df.iterrows():
            addr = str(r.get("parcel_address", "")).strip()
            if not addr:
                continue
            new_props.setdefault(addr, {
                "details": {},
                "transactions": [],
                "acquisition_strategy": {},
                "documents": [],
                "notes": [],
            })
            t = {}
            for k in [
                "year_acquired", "year_sold", "initial_acquisition_cost",
                "subsidy_amount", "subsidy_source", "subsidy_purpose",
                "list_price", "fee_simple_appraisal_value",
                "leasehold_appraised", "appraised_market_value",
                "purchase_price", "write_down", "base_price", "loan_amount",
                "loan_type", "lender_name", "loan_term_years",
                "monthly_payments", "monthly_taxes_and_insurance",
                "land_fee", "interest_rate", "seller_equity_amount",
                "additional_repair_amount", "additional_repair_purpose",
                "additional_repair_source",
                "household_income_at_move_in", "household_income_at_move_out",
                "resale_formula", "length_of_tenure",
                "time_on_market_months", "affordability_relative_to_market",
                "loan_remaining_seller",
                "household_size", "household_income_to_AMI_percent",
            ]:
                if k in tx_df.columns:
                    t[k] = none_if_nan(r.get(k))
            new_props[addr]["transactions"].append(t)

    # ---- AcquisitionStrategy sheet ----
    if not strat_df.empty:
        for _, r in strat_df.iterrows():
            addr = str(r.get("parcel_address", "")).strip()
            if not addr:
                continue
            new_props.setdefault(addr, {
                "details": {},
                "transactions": [],
                "acquisition_strategy": {},
                "documents": [],
                "notes": [],
            })
            s = {}
            for k in [
                "acquisition_criteria_type",
                "acquisition_strategy_description",
                "exclusion_criteria",
            ]:
                if k in strat_df.columns:
                    s[k] = none_if_nan(r.get(k))
            new_props[addr]["acquisition_strategy"] = s

    # ---- Documents sheet ----
    if not docs_df.empty:
        for _, r in docs_df.iterrows():
            addr = str(r.get("parcel_address", "")).strip()
            if not addr:
                continue
            new_props.setdefault(addr, {
                "details": {},
                "transactions": [],
                "acquisition_strategy": {},
                "documents": [],
                "notes": [],
            })
            d = {}
            for k in ["filename", "relpath", "uploaded_on", "description"]:
                if k in docs_df.columns:
                    d[k] = none_if_nan(r.get(k))
            new_props[addr]["documents"].append(d)

    # ---- Notes sheet ----
    if not notes_df.empty:
        for _, r in notes_df.iterrows():
            addr = str(r.get("parcel_address", "")).strip()
            if not addr:
                continue
            new_props.setdefault(addr, {
                "details": {},
                "transactions": [],
                "acquisition_strategy": {},
                "documents": [],
                "notes": [],
            })
            n = {}
            for k in ["timestamp", "text"]:
                if k in notes_df.columns:
                    n[k] = none_if_nan(r.get(k))
            new_props[addr]["notes"].append(n)

    # ---- Merge into existing properties ----
    for addr, rec in new_props.items():
        if addr in properties:
            existing = properties[addr]

            if "details" in rec:
                existing_details = existing.get("details", {})
                new_details = rec.get("details", {})
                existing["details"] = {
                    **existing_details,
                    **{k: v for k, v in new_details.items() if v is not None},
                }

            if rec.get("transactions"):
                existing_tx = existing.get("transactions", [])
                existing["transactions"] = existing_tx + rec["transactions"]

            if rec.get("acquisition_strategy"):
                existing["acquisition_strategy"] = {
                    **existing.get("acquisition_strategy", {}),
                    **rec["acquisition_strategy"],
                }

            if rec.get("documents"):
                existing_docs = existing.get("documents", [])
                existing["documents"] = existing_docs + rec["documents"]

            if rec.get("notes"):
                existing_notes = existing.get("notes", [])
                existing["notes"] = existing_notes + rec["notes"]

            properties[addr] = existing
        else:
            properties[addr] = rec

    save_data(properties)
    st.success(f"Imported/merged {len(new_props)} properties from Excel (existing ones kept).")

st.markdown("---")


# ---------- All Properties Map (white basemap) ----------
st.header("🗺️ All Properties Map")

# Extract rows with coordinates
rows = []
for addr, rec in properties.items():
    det = rec.get("details", {})
    la, lo = det.get("latitude"), det.get("longitude")
    if has_coords(la, lo):
        rows.append({
            "parcel_address": addr,
            "neighborhood": det.get("neighborhood"),
            "zip_code": det.get("zip_code"),
            "city": det.get("city"),
            "county": det.get("county"),
            "state": det.get("state"),
            "organization": det.get("organization"),
            "msa": det.get("msa"),
            "lat": float(la),
            "lon": float(lo),
        })

# Build master DataFrame
all_df = pd.DataFrame(rows)

# --- Filters ---
st.subheader("Search/Filter Properties")

fc1, fc2 = st.columns(2)
fc3, fc4 = st.columns(2)
fc5, fc6 = st.columns(2)

with fc1:
    f_city = st.text_input("City", "")
with fc2:
    f_zip = st.text_input("ZIP Code", "")
with fc3:
    f_county = st.text_input("County", "")
with fc4:
    f_state = st.text_input("State", "")
with fc5:
    f_organization = st.text_input("Organization", "")
with fc6:
    f_msa = st.text_input("MSA", "")

# Apply filters
filtered = all_df.copy()
if f_city.strip():
    filtered = filtered[filtered["city"].fillna("").str.contains(f_city, case=False, na=False)]
if f_zip.strip():
    filtered = filtered[filtered["zip_code"].astype(str).str.contains(f_zip, case=False, na=False)]
if f_county.strip():
    filtered = filtered[filtered["county"].fillna("").str.contains(f_county, case=False, na=False)]
if f_state.strip():
    filtered = filtered[filtered["state"].fillna("").str.contains(f_state, case=False, na=False)]
if f_organization.strip():
    filtered = filtered[filtered["organization"].fillna("").str.contains(f_organization, case=False, na=False)]
if f_msa.strip():
    filtered = filtered[filtered["msa"].fillna("").str.contains(f_msa, case=False, na=False)]

# --- Map Display Options ---
st.subheader("🗺️ Map Display Options")
map_mode = st.radio("Select map mode", options=["Markers", "Heatmap"], horizontal=True)

# --- Output ---
st.caption(f"{len(filtered)} pinned propertie(s)")

if not filtered.empty:
    st.pydeck_chart(render_property_map(filtered, map_mode))
    st.dataframe(
        filtered[[
            "parcel_address", "neighborhood", "city", "county", "state",
            "organization", "msa", "zip_code", "lat", "lon"
        ]],
        use_container_width=True,
        height=280
    )
else:
    st.info("No properties with coordinates yet. Use Geocode buttons above or enter lat/lon manually and save.")
    
    #....... The End ..............................
    # Last edited 12/3/2025