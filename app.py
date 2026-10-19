import streamlit as st
import pandas as pd
import requests
import os, json, random, string, hashlib
import uuid
from urllib.parse import quote_plus
import unicodedata
import re
from datetime import date, datetime, timedelta
from meta_ads import (
    CAMPAIGN_COLUMNS,
    MetaAdsError,
    fetch_meta_insights,
    meta_date_range,
    normalize_ad_account,
)
from google_ads import (
    GoogleAdsError,
    OAUTH_CALLBACK_QUERY_KEYS,
    build_authorization_url,
    capture_oauth_callback,
    complete_oauth_callback,
    create_oauth_state,
    fetch_google_campaigns,
    fingerprint_license,
    get_valid_access_token,
    load_oauth_config,
    normalize_customer_id,
)
from tiktok_ads import (
    TikTokAdsError,
    export_report_csv,
    export_report_excel,
    fetch_campaign_report,
    normalize_advertiser_id,
)
from competitor_store import (
    CompetitorStoreError,
    create_observation,
    export_observations_json,
    load_observations_for_tenants,
    save_observations,
    tenant_id_candidates_for_license,
    tenant_id_for_license,
)
from ad_copy import generate_ad_proposals

st.set_page_config(page_title="AGENCIA OS", page_icon="🚀", layout="wide")
st.markdown(
    """
    <style>
    /* AGENCIA_OS_THEME_V1 */

    .stApp {
        background:
            radial-gradient(ellipse at 15% 0%, rgba(124, 58, 237, 0.13), transparent 38%),
            #0b0b12;
        color: #f4f4f5;
    }

    .stApp [data-testid="stHeader"] {
        background: rgba(11, 11, 18, 0.75);
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #11101b 0%, #0c0c13 100%);
        border-right: 1px solid rgba(167, 139, 250, 0.18);
    }

    /* AGENCIA_OS_SIDEBAR_BRAND_V1 */
    .agency-sidebar-brand {
        padding: 8px 4px 22px 4px;
        margin-bottom: 20px;
        border-bottom: 1px solid rgba(167, 139, 250, 0.20);
    }
    .agency-sidebar-mark {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 42px;
        height: 42px;
        margin-bottom: 13px;
        border: 1px solid rgba(196, 181, 253, 0.45);
        border-radius: 13px;
        background: linear-gradient(135deg, #8b5cf6, #5b21b6);
        color: #ffffff;
        font-size: 24px;
        font-weight: 800;
        box-shadow: 0 7px 22px rgba(124, 58, 237, 0.25);
    }
    .agency-sidebar-name {
        color: #ffffff;
        font-size: 1.12rem;
        font-weight: 800;
        letter-spacing: 0.04em;
    }
    .agency-sidebar-caption {
        margin-top: 4px;
        color: #a78bfa;
        font-size: 0.62rem;
        font-weight: 700;
        letter-spacing: 0.12em;
    }
    .agency-sidebar-section {
        margin: 0 0 8px 0;
        color: #a78bfa;
        font-size: 0.68rem;
        font-weight: 750;
        letter-spacing: 0.12em;
    }

    .stApp h1, .stApp h2, .stApp h3 {
        color: #fafafa;
        letter-spacing: -0.025em;
    }

    .stApp [data-testid="stCaptionContainer"] {
        color: #a1a1aa;
    }

    div.stButton > button,
    div[data-testid="stDownloadButton"] button {
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.18s ease;
        border-color: rgba(167, 139, 250, 0.35);
    }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #7c3aed, #6d28d9);
        color: #ffffff;
        border: 1px solid #8b5cf6;
    }

    div.stButton > button:hover,
    div[data-testid="stDownloadButton"] button:hover {
        border-color: #a78bfa;
        color: #ffffff;
    }

    button[data-baseweb="tab"] {
        font-weight: 600;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: #c4b5fd;
    }

    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    div[data-testid="stTextArea"] textarea {
        border-radius: 10px;
        border-color: #343044;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: rgba(167, 139, 250, 0.20);
        border-radius: 16px;
    }

    div[data-testid="stMetric"] {
        background: rgba(24, 22, 36, 0.72);
        border: 1px solid rgba(167, 139, 250, 0.18);
        border-radius: 14px;
        padding: 14px 16px;
    }

    /* AGENCIA_OS_METRICS_V1 */
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
        color: #c4b5fd;
        font-weight: 650;
    }

    div[data-testid="stMetric"] [data-testid="stMetricLabel"] p {
        color: #c4b5fd;
        font-size: 0.9rem;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #ffffff;
        font-size: clamp(1.5rem, 2vw, 2rem);
        font-weight: 750;
        letter-spacing: -0.03em;
    }

    div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
        font-weight: 600;
    }


    hr {
        border-color: rgba(167, 139, 250, 0.18);
    }
    .agency-hero {
        padding: 28px 30px;
        margin: 4px 0 26px 0;
        border: 1px solid rgba(167, 139, 250, 0.28);
        border-radius: 20px;
        background: linear-gradient(115deg, rgba(124, 58, 237, 0.20), rgba(20, 18, 32, 0.96) 65%);
        box-shadow: 0 12px 35px rgba(0, 0, 0, 0.18);
    }
    .agency-hero .eyebrow {
        color: #c4b5fd;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.16em;
        margin-bottom: 8px;
    }
    .agency-hero h1 {
        color: #ffffff;
        font-size: clamp(2rem, 4vw, 3rem);
        font-weight: 800;
        letter-spacing: -0.045em;
        margin: 0;
    }
    .agency-hero p {
        color: #c4c4d0;
        font-size: 1rem;
        margin: 8px 0 0 0;
    }

    :root {
        --agency-canvas: #090c13;
        --agency-surface: #10151f;
        --agency-surface-raised: #151b27;
        --agency-border: rgba(159, 151, 190, 0.18);
        --agency-text: #f4f5f8;
        --agency-muted: #9da5b4;
        --agency-violet: #9b7bff;
        --agency-violet-soft: rgba(139, 112, 246, 0.12);
        --agency-green: #4fd1a1;
        --agency-amber: #f0bd68;
        --agency-red: #f17e8b;
    }

    .stApp {
        background:
            radial-gradient(ellipse at 8% 0%, rgba(118, 91, 209, 0.13), transparent 32%),
            linear-gradient(180deg, #0b0e16 0%, var(--agency-canvas) 58%);
        color: var(--agency-text);
        font-family: "Aptos", "Segoe UI Variable", system-ui, sans-serif;
    }

    .stApp header[data-testid="stHeader"] {
        background: rgba(9, 12, 19, 0.82);
    }

    .block-container {
        max-width: 1540px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111622 0%, #0c1018 100%);
        border-right: 1px solid var(--agency-border);
    }

    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.75rem;
    }

    .agency-sidebar-brand {
        border-color: var(--agency-border);
        padding-bottom: 18px;
    }

    .agency-sidebar-mark {
        border-radius: 10px;
        background: linear-gradient(145deg, #a18aff, #6e52d8);
        box-shadow: 0 8px 22px rgba(91, 70, 177, 0.24);
    }

    .agency-sidebar-caption,
    .agency-sidebar-section {
        color: #b6a5ff;
    }

    .agency-sidebar-section {
        margin-top: 10px;
        font-size: 0.66rem;
        letter-spacing: 0.14em;
    }

    .agency-sidebar-nav {
        display: grid;
        gap: 4px;
        margin: 8px 0 12px;
    }

    .agency-sidebar-nav a {
        display: block;
        padding: 9px 10px;
        border: 1px solid transparent;
        border-radius: 7px;
        color: #c5cad4;
        font-size: 0.86rem;
        font-weight: 580;
        text-decoration: none;
        transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
    }

    .agency-sidebar-nav a:hover {
        border-color: var(--agency-border);
        background: rgba(155, 123, 255, 0.1);
        color: #ffffff;
    }

    .agency-hero {
        margin-bottom: 22px;
        padding: 24px 28px;
        border-color: var(--agency-border);
        border-radius: 14px;
        background: linear-gradient(112deg, rgba(105, 82, 177, 0.19), rgba(16, 21, 31, 0.96) 68%);
        box-shadow: 0 14px 35px rgba(0, 0, 0, 0.22);
    }

    .agency-hero h1 {
        font-size: 2.45rem;
        letter-spacing: 0;
    }

    .agency-hero .eyebrow {
        color: #c7baff;
        letter-spacing: 0.12em;
    }

    .agency-section-heading {
        margin: 22px 0 14px;
    }

    .agency-section-heading .agency-kicker {
        color: #b6a5ff;
        font-size: 0.68rem;
        font-weight: 750;
        letter-spacing: 0.13em;
    }

    .agency-section-heading h2 {
        margin: 4px 0 0;
        color: var(--agency-text);
        font-size: 1.45rem;
        font-weight: 720;
        letter-spacing: 0;
    }

    .agency-section-heading p {
        margin: 5px 0 0;
        color: var(--agency-muted);
        font-size: 0.9rem;
    }

    .agency-platform-strip {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin: 0 0 24px;
    }

    .agency-platform-card {
        min-width: 0;
        padding: 15px 16px;
        border: 1px solid var(--agency-border);
        border-radius: 10px;
        background: linear-gradient(145deg, rgba(21, 27, 39, 0.94), rgba(14, 18, 27, 0.98));
    }

    .agency-platform-name {
        color: var(--agency-muted);
        font-size: 0.68rem;
        font-weight: 750;
        letter-spacing: 0.1em;
    }

    .agency-platform-state {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 9px;
        color: var(--agency-text);
        font-size: 0.9rem;
        font-weight: 650;
        line-height: 1.35;
        overflow-wrap: anywhere;
    }

    .agency-platform-state::before {
        width: 7px;
        height: 7px;
        flex: 0 0 7px;
        border-radius: 50%;
        background: var(--agency-muted);
        content: "";
    }

    .agency-platform-state.is-ready::before,
    .agency-platform-state.is-connected::before {
        background: var(--agency-green);
        box-shadow: 0 0 10px rgba(79, 209, 161, 0.36);
    }

    .agency-platform-state.is-empty::before,
    .agency-platform-state.is-pending::before,
    .agency-platform-state.is-unavailable::before {
        background: var(--agency-amber);
    }

    .agency-platform-state.is-error::before {
        background: var(--agency-red);
    }

    div[data-testid="stMetric"] {
        min-height: 116px;
        padding: 18px 20px;
        border-color: var(--agency-border);
        border-radius: 11px;
        background: linear-gradient(145deg, rgba(22, 28, 41, 0.96), rgba(14, 18, 27, 0.98));
        box-shadow: 0 9px 24px rgba(0, 0, 0, 0.14);
    }

    div[data-testid="stMetric"] [data-testid="stMetricLabel"],
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] p {
        color: #b7a9fa;
        font-size: 0.82rem;
        font-weight: 650;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: var(--agency-text);
        font-size: 1.8rem;
        font-weight: 740;
        letter-spacing: 0;
    }

    div[data-testid="stDataFrame"] {
        overflow: hidden;
        border: 1px solid var(--agency-border);
        border-radius: 10px;
        background: var(--agency-surface);
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--agency-border);
        border-radius: 11px;
        background: rgba(16, 21, 31, 0.58);
    }

    div.stButton > button,
    div[data-testid="stDownloadButton"] button,
    div[data-testid="stLinkButton"] a {
        min-height: 42px;
        border: 1px solid rgba(155, 123, 255, 0.32);
        border-radius: 8px;
        background: #171927;
        color: #f4f2ff;
        font-weight: 650;
        transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease;
    }

    div.stButton > button[kind="primary"] {
        border-color: #8f72ec;
        background: linear-gradient(135deg, #7d61d8, #6248b8);
        color: #ffffff;
    }

    div.stButton > button:hover,
    div[data-testid="stDownloadButton"] button:hover,
    div[data-testid="stLinkButton"] a:hover {
        border-color: #b6a5ff;
        background: #211e32;
        color: #ffffff;
        transform: translateY(-1px);
    }

    button[data-baseweb="tab"] {
        color: #a8afbc;
        font-weight: 650;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: #c8bbff;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid var(--agency-border);
    }

    .stTabs [data-baseweb="tab"] {
        min-height: 44px;
        padding: 0 15px;
        border-radius: 8px 8px 0 0;
    }

    .stTabs [data-baseweb="tab-panel"] {
        padding-top: 1.2rem;
    }

    div[data-testid="stAlert"] {
        border-radius: 9px;
    }

    div[data-testid="stCodeBlock"] {
        border: 1px solid var(--agency-border);
        border-radius: 9px;
        background: #0d121b;
    }

    div[data-testid="stTextArea"] textarea,
    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div {
        border-color: #353b4a;
        border-radius: 8px;
        background: #111722;
    }

    @media (max-width: 900px) {
        .agency-platform-strip {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .block-container {
            padding-top: 1.4rem;
        }
    }

    @media (max-width: 600px) {
        .agency-platform-strip {
            grid-template-columns: minmax(0, 1fr);
        }
        .agency-hero {
            padding: 20px;
        }
        .agency-hero h1 {
            font-size: 2rem;
        }
        div[data-testid="stMetric"] {
            min-height: 100px;
            padding: 14px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.session_state.pop("google_oauth_state", None)

if capture_oauth_callback(st.query_params, st.session_state):
    for key in OAUTH_CALLBACK_QUERY_KEYS:
        if key in st.query_params:
            del st.query_params[key]
    st.rerun()

try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")


try:
    _secrets = dict(st.secrets)
except Exception:
    _secrets = {}

SUPABASE_URL = _secrets.get(
    "SUPABASE_URL", os.environ.get("SUPABASE_URL", "")
).rstrip("/")

SUPABASE_SECRET_KEY = _secrets.get(
    "SUPABASE_SECRET_KEY",
    os.environ.get("SUPABASE_SECRET_KEY", "")
)

SUPABASE_LICENSES_URL = f"{SUPABASE_URL}/rest/v1/agencia_os_licenses"



def supabase_headers():
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise RuntimeError(
            "Faltan SUPABASE_URL o SUPABASE_SECRET_KEY en Secrets."
        )

    return {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept-Profile": "public",
        "Content-Profile": "public",
    }


def load_licenses():
    try:
        response = requests.get(
            SUPABASE_LICENSES_URL,
            headers=supabase_headers(),
            params={
                "select": "license_key,client,created,expires,max_accounts,active"
            },
            timeout=20,
        )
        response.raise_for_status()

        records = response.json()
        return {
            row["license_key"]: {
                "client": row["client"],
                "created": row["created"],
                "expires": row["expires"],
                "max_accounts": row["max_accounts"],
                "active": row["active"],
            }
            for row in records
        }

    except Exception as exc:
        detalle = str(exc)
        if "response" in locals():
            detalle += f" | HTTP: {response.status_code}"
            detalle += f" | Respuesta: {response.text[:1000]}"
        st.error(
            "No se pudieron cargar las licencias desde Supabase. "
            f"Detalle técnico: {detalle}"
        )
        st.stop()


def save_licenses(licenses):
    try:
        headers = supabase_headers()
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"

        records = [
            {
                "license_key": key,
                "client": lic["client"],
                "created": lic["created"],
                "expires": lic["expires"],
                "max_accounts": int(lic["max_accounts"]),
                "active": lic.get("active", True),
            }
            for key, lic in licenses.items()
        ]

        if not records:
            return

        response = requests.post(
            SUPABASE_LICENSES_URL,
            headers=headers,
            params={"on_conflict": "license_key"},
            json=records,
            timeout=20,
        )
        response.raise_for_status()
    except Exception as exc:
        st.error(
            "No se pudieron guardar las licencias en Supabase. "
            "Revisá la conexión y los permisos. "
            f"Detalle: {exc}"
        )
        st.stop()

def delete_license(license_key):
    try:
        headers = supabase_headers()
        headers["Prefer"] = "return=minimal"

        response = requests.delete(
            SUPABASE_LICENSES_URL,
            headers=headers,
            params={"license_key": f"eq.{license_key}"},
            timeout=20,
        )
        response.raise_for_status()
    except Exception as exc:
        st.error(
            "No se pudo eliminar la licencia en Supabase. "
            f"Detalle: {exc}"
        )
        st.stop()


def generate_key(name):
    rand=''.join(random.choices(string.ascii_uppercase+string.digits,k=4))
    return f"LEGION-{rand}-{datetime.now().year}-{name[:4].upper()}"
def validate_license(key, licenses):
    key=key.strip().upper()
    if key not in licenses: return False,"No existe"
    lic=licenses[key]
    if datetime.now() > datetime.fromisoformat(lic["expires"]): return False,"Vencida"
    if not lic.get("active",True): return False,"Desactivada"
    return True,lic


LICENSE_SCOPED_SESSION_KEYS = (
    "meta",
    "meta_act",
    "df_meta",
    "meta_period",
    "meta_query",
    "meta_result_status",
    "google_oauth_credentials",
    "google_oauth_license_fingerprint",
    "google_oauth_pending_callback",
    "google_oauth_notice",
    "google_license_fingerprint",
    "google_customer_id",
    "google_login_customer_id",
    "google_license_revalidation",
    "df_google",
    "google_report",
    "tiktok_access_token",
    "tiktok_advertiser_id",
    "df_tiktok",
    "tiktok_report",
    "df_all",
    "gasto_all",
    "roas_all",
    "competitor_tenant_id",
    "competitor_tenant_candidates_v1",
    "competitor_observations_v1",
    "competitor_observations_loaded_tenant_v1",
    "competitor_observations_load_error_v1",
    "competitor_observations_unsaved_v1",
    "spy_saved_observations_filter",
    "spy_compare_first",
    "spy_compare_second",
)


def clear_license_scoped_session(session_state):
    for key in LICENSE_SCOPED_SESSION_KEYS:
        session_state.pop(key, None)


def start_license_session(session_state):
    clear_license_scoped_session(session_state)
    session_state["_license_scope"] = uuid.uuid4().hex


def invalidate_license_session(session_state):
    clear_license_scoped_session(session_state)
    session_state["license_valid"] = False
    session_state.pop("license_data", None)
    session_state.pop("_license_scope", None)


def hash_pick(text, options):
    h=int(hashlib.md5(text.lower().encode()).hexdigest(),16)
    return options[h % len(options)]

BRAND_DB = {
    "coto": {"industria":"SUPERMERCADO","pos":"Precio más bajo + Comunidad Coto 30% + carne barata","fuerte":"Carne, Comunidad, 2x1","debil":"No tiene envíos rápidos, marca vieja","ticket":45000},
    "dia": {"industria":"SUPERMERCADO","pos":"Marca propia Dia + ahorro extremo + cercanía barrio","fuerte":"Marca propia barata, locales chicos","debil":"Poca variedad premium, no carnes premium","ticket":18000},
    "carrefour": {"industria":"SUPERMERCADO","pos":"Hiper con todo + Mi Carrefour + Precios Corajudos","fuerte":"Variedad enorme, electro, marca propia","debil":"Precios inestables, experiencia caótica","ticket":38000},
    "vea": {"industria":"SUPERMERCADO","pos":"Super argentino familiar + VEA Ahorro","fuerte":"Presencia interior país, promos bancarias","debil":"Poco digital, sin comunidad fuerte","ticket":25000},
    "disco": {"industria":"SUPERMERCADO","pos":"Premium + calidad + Disco Plus","fuerte":"Productos premium, atención, vinos","debil":"Caro, no compite por precio","ticket":52000},
    "jumbo": {"industria":"SUPERMERCADO","pos":"Jumbo premium + Jumbo Más + importados","fuerte":"Importados, gourmet, calidad","debil":"Muy caro, para ABC1","ticket":65000},
    "levis": {"industria":"MODA","pos":"Original 501 + durabilidad 100 años + heritage USA","fuerte":"Calidad denim, marca aspiracional, 501 icónico","debil":"Caro, poca moda rápida, talles limitados","ticket":89000},
    "zara": {"industria":"MODA","pos":"Fast fashion + tendencia pasarela en 2 semanas","fuerte":"Tendencia ultra rápida, variedad infinita","debil":"Calidad media, se rompe rápido, poco sustentable","ticket":45000},
    "47 street": {"industria":"MODA","pos":"Teen argentina + jean que levanta cola + UGC real","fuerte":"Horma argentina, UGC, precio medio","debil":"Solo teen, no +30","ticket":38000},
    "complot": {"industria":"MODA","pos":"Diseño autor argentino + exclusivo","fuerte":"Diseño, no masivo, calidad","debil":"Caro, pocos locales","ticket":72000},
    "fravega": {"industria":"TECH","pos":"Electro barato + cuotas sin interés + retiro rápido","fuerte":"Cuotas, variedad electro, Frávega 100 años","debil":"Post-venta malo, letra chica","ticket":150000},
    "musimundo": {"industria":"TECH","pos":"Tech joven + gaming + Musimundo a todo","fuerte":"Gaming, audio, joven","debil":"Stock inconsistente","ticket":90000},
}

def coincide_termino(texto, termino):
    """Busca términos completos para evitar coincidencias dentro de otras palabras."""
    return re.search(r"(?<!\w)" + re.escape(termino) + r"(?!\w)", texto) is not None


def analisis_real_diferenciado(competidor):
    nombre = competidor.strip()
    if not nombre:
        return "Escribi una marca para generar propuestas."

    comp_lower = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", nombre.casefold())
        if not unicodedata.combining(caracter)
    )

    sectores = {
        "SUPERMERCADO": [
            "coto", "dia", "carrefour", "vea", "disco", "jumbo",
            "walmart", "supermercado", "supermercados", "mercado"
        ],
        "MODA": [
            "levis", "levi's", "zara", "ropa", "moda", "jean",
            "complot", "mango", "h&m", "47 street"
        ],
        "TECH": [
            "fravega", "frávega", "garbarino", "musimundo",
            "samsung", "galaxy", "lg", "motorola", "xiaomi", "nvidia",
            "redmi", "huawei", "honor", "sony", "playstation",
            "xbox", "nintendo", "lenovo", "asus", "acer",
            "hp", "dell", "intel", "amd", "apple", "iphone",
            "ipad", "macbook", "electro", "tecnologia",
            "tecnología", "gaming"
        ],
    }

    industria = "GENERAL"
    for sector, palabras in sectores.items():
        if any(coincide_termino(comp_lower, palabra) for palabra in palabras):
            industria = sector
            break

    hooks_por_sector = {
        "SUPERMERCADO": [
            "Arma tu lista de compras y prioriza lo que realmente necesitas.",
            "Ideas para organizar las compras de la semana sin complicarte.",
            "Compara el precio por unidad antes de elegir.",
            "Tu proxima compra empieza con una lista inteligente.",
            "Descubri opciones para planificar mejor las compras del hogar.",
        ],
        "MODA": [
            "Tres formas de combinar una prenda para distintos momentos.",
            "Enfocate en el calce, los detalles y como se siente la prenda.",
            "Arma un look versatil con prendas que ya tenes.",
            "Mira los detalles de la prenda antes de elegir tu proximo look.",
            "Encuentra un estilo que se adapte a vos.",
        ],
        "TECH": [
            "Que conviene revisar antes de elegir tu proximo dispositivo.",
            "Compara funciones y elegi segun lo que realmente necesitas.",
            "Mira el producto en uso y conoce sus funciones principales.",
            "Una guia simple para comparar opciones de tecnologia.",
            "Antes de comprar, revisa compatibilidad, garantia y prestaciones.",
        ],
        "GENERAL": [
            "Conoce la propuesta y como puede ayudarte.",
            "Tres preguntas que conviene resolver antes de elegir.",
            "Mira como funciona y descubre si se adapta a tus necesidades.",
            "Conoce los detalles importantes antes de tomar una decision.",
            "Una forma simple de descubrir una nueva alternativa.",
        ],
    }

    hooks = hooks_por_sector[industria]
    h1 = hash_pick(nombre + "|hook1", hooks)
    h2 = hash_pick(nombre + "|hook2", hooks)
    h3 = hash_pick(nombre + "|hook3", hooks)
    seleccion_hooks = []
    for hook in (h1, h2, h3):
        if hook not in seleccion_hooks:
            seleccion_hooks.append(hook)
    for hook in hooks:
        if len(seleccion_hooks) >= 3:
            break
        if hook not in seleccion_hooks:
            seleccion_hooks.append(hook)

    formatos_por_sector = {
        "SUPERMERCADO": [
            "Video vertical mostrando como planificar una compra semanal.",
            "Carrusel con una lista de compras organizada por categorias.",
            "Pieza estatica con un consejo practico para comparar productos.",
        ],
        "MODA": [
            "Video vertical mostrando tres combinaciones de una prenda.",
            "Carrusel con detalles, calce y distintas formas de uso.",
            "Pieza estatica destacando materiales y caracteristicas visibles.",
        ],
        "TECH": [
            "Video vertical demostrando funciones reales de un dispositivo.",
            "Carrusel explicando compatibilidad, prestaciones y garantia.",
            "Pieza estatica con especificaciones comprobables del producto.",
        ],
        "GENERAL": [
            "Video vertical mostrando el producto o servicio en uso.",
            "Carrusel con beneficios comprobables y preguntas frecuentes.",
            "Pieza estatica con una propuesta clara y llamada a la accion.",
        ],
    }
    formatos = formatos_por_sector[industria]

    angulos = {
        "SUPERMERCADO": "Planificacion, utilidad y claridad al comprar.",
        "MODA": "Estilo, combinaciones y detalles visibles del producto.",
        "TECH": "Funciones, comparacion de prestaciones y uso real.",
        "GENERAL": "Beneficio principal, demostracion y respuesta a dudas.",
    }

    ideas_por_sector = {
        "SUPERMERCADO": [
            "Guia para organizar una lista de compras segun las necesidades del hogar.",
            "Demostracion de como comparar precio por unidad entre productos.",
            "Planificacion de comidas semanales con una lista de ingredientes.",
            "Preguntas frecuentes sobre conservacion y uso de productos.",
            "Comparativa de productos basada en etiquetas y precios verificados.",
        ],
        "MODA": [
            "Guia para combinar una prenda en distintas ocasiones.",
            "Demostracion de detalles, calce y terminaciones visibles.",
            "Consejos para elegir talles consultando las medidas publicadas.",
            "Preguntas frecuentes sobre materiales y cuidados de las prendas.",
            "Comparativa de prendas basada en caracteristicas verificables.",
        ],
        "TECH": [
            "Guia para comprobar compatibilidad antes de comprar un dispositivo.",
            "Demostracion de funciones disponibles en el producto.",
            "Explicacion de garantia y especificaciones publicadas.",
            "Preguntas frecuentes sobre configuracion y uso.",
            "Comparativa basada en especificaciones verificadas de los equipos.",
        ],
        "GENERAL": [
            f"Guia practica relacionada con la categoria de {nombre}.",
            f"Demostracion paso a paso de una solucion para el publico de {nombre}.",
            "Preguntas frecuentes que un cliente deberia resolver antes de comprar.",
            "Comparativa basada en datos comprobables, si hay fuentes disponibles.",
            "Testimonio real de un cliente, solo si se cuenta con su autorizacion.",
        ],
    }
    ideas = ideas_por_sector[industria]

    ideas_seleccionadas = []
    for i in range(5):
        idea = hash_pick(nombre + "|idea|" + str(i), ideas)
        if idea not in ideas_seleccionadas:
            ideas_seleccionadas.append(idea)
    for idea in ideas:
        if len(ideas_seleccionadas) >= 3:
            break
        if idea not in ideas_seleccionadas:
            ideas_seleccionadas.append(idea)

    return (
        f"ANALISIS ORIENTATIVO: {nombre}\n"
        f"Rubro estimado: {industria}\n\n"
        "ALCANCE Y LIMITACIONES\n"
        "- No se consultaron ni verificaron anuncios actuales de esta marca.\n"
        "- No hay precios, descuentos, tickets, inversiones ni resultados verificados.\n"
        "- El rubro es una estimacion basada en palabras del nombre ingresado.\n"
        "- Las siguientes ideas son propuestas creativas, no anuncios observados.\n\n"
        "1. TRES PROPUESTAS DE HOOK\n"
        + "\n".join(f"- {hook}" for hook in seleccion_hooks[:3])
        + "\n\n2. FORMATOS CREATIVOS SUGERIDOS\n"
        + "\n".join(f"- {formato}" for formato in formatos)
        + f"\n\n3. ANGULO CREATIVO SUGERIDO\n{angulos[industria]}\n"
        "\n4. COMO DIFERENCIAR TU OFERTA\n"
        "- Destaca beneficios propios que puedas demostrar.\n"
        "- Compara precios o prestaciones solo con datos actuales verificables.\n"
        "- No atribuyas debilidades, promociones ni afirmaciones no comprobadas al competidor.\n"
        "\n5. TRES IDEAS DE CONTENIDO ORIGINAL\n"
        + "\n".join(
            f"IDEA {i + 1}: {idea}"
            for i, idea in enumerate(ideas_seleccionadas[:3])
        )
    )


def fetch_meta_free(
    token,
    ad_account,
    preset,
    custom_start=None,
    custom_end=None,
    selected_period=None,
):
    if not token or not token.strip() or not ad_account or not ad_account.strip():
        st.error("Ingresá el token de Meta y el ID de la cuenta publicitaria.")
        return None

    try:
        period = selected_period or meta_date_range(
            preset,
            custom_start=custom_start,
            custom_end=custom_end,
        )
        return fetch_meta_insights(token, ad_account, period)
    except (ValueError, MetaAdsError) as exc:
        st.error(str(exc))

    return None


def fetch_google_free():
    return pd.DataFrame(columns=CAMPAIGN_COLUMNS)


if "license_valid" not in st.session_state: st.session_state["license_valid"]=False
is_admin="admin" in st.query_params
if is_admin:
    if not isinstance(ADMIN_PASSWORD, str) or not ADMIN_PASSWORD.strip():
        st.error("El acceso administrativo no está configurado.")
        st.stop()
    st.title("ADMIN")
    pwd=st.text_input("Contraseña",type="password")
    if pwd==ADMIN_PASSWORD:
        licenses=load_licenses()
        c1,c2,c3=st.columns(3)
        with c1: cname=st.text_input("Cliente","Nuevo")
        with c2: days=st.number_input("Días",value=90)
        with c3: max_acc=st.number_input("Max",value=5)
        if st.button("GENERAR",type="primary",use_container_width=True):
            new_key=generate_key(cname)
            exp=datetime.now()+timedelta(days=days)
            licenses[new_key]={"client":cname,"created":datetime.now().isoformat(),"expires":exp.isoformat(),"max_accounts":max_acc,"active":True}
            save_licenses(licenses)
            st.code(new_key)

        st.dataframe(
            pd.DataFrame.from_dict(licenses, orient="index"),
            use_container_width=True,
        )

        st.markdown("### Gestionar licencias")

        if licenses:
            selected_key = st.selectbox(
                "Seleccioná una licencia",
                options=list(licenses.keys()),
                format_func=lambda key: (
                    f"{key} — {licenses[key]['client']}"
                ),
            )

            selected_license = licenses[selected_key]
            is_active = selected_license.get("active", True)

            st.write(
                f"**Estado:** {'Activa' if is_active else 'Desactivada'}"
            )

            col_estado, col_eliminar = st.columns(2)

            with col_estado:
                if is_active:
                    if st.button(
                        "Desactivar licencia",
                        use_container_width=True,
                    ):
                        licenses[selected_key]["active"] = False
                        save_licenses(licenses)
                        st.success("Licencia desactivada.")
                        st.rerun()
                else:
                    if st.button(
                        "Reactivar licencia",
                        use_container_width=True,
                    ):
                        licenses[selected_key]["active"] = True
                        save_licenses(licenses)
                        st.success("Licencia reactivada.")
                        st.rerun()

            with col_eliminar:
                confirmar = st.checkbox(
                    "Confirmo que quiero eliminarla",
                    key=f"confirmar_borrado_{selected_key}",
                )

                if st.button(
                    "Eliminar definitivamente",
                    disabled=not confirmar,
                    use_container_width=True,
                ):
                    delete_license(selected_key)
                    st.success("Licencia eliminada.")
                    st.rerun()

        st.download_button("licenses_db.json",data=json.dumps(licenses,indent=2),file_name="licenses_db.json",mime="application/json")
    st.stop()

google_config = None
google_config_error = None
try:
    google_config = load_oauth_config(_secrets)
except GoogleAdsError as exc:
    google_config_error = str(exc)

if not st.session_state["license_valid"]:
    invalidate_license_session(st.session_state)
    st.markdown("<h1 style='text-align:center; margin-top:80px; font-weight:800;'>AGENCIA OS</h1>",unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#71717a;'>Acceso privado</p>",unsafe_allow_html=True)
    _,mid,_=st.columns([1,2,1])
    with mid:
        lic_input=st.text_input("Clave",placeholder="Ingresá tu clave",type="password",label_visibility="collapsed")
        if st.button("Ingresar",type="primary",use_container_width=True):
            licenses=load_licenses()
            ok,info=validate_license(lic_input,licenses)
            if ok:
                start_license_session(st.session_state)
                tenant_candidates = tenant_id_candidates_for_license(info, lic_input)
                st.session_state["competitor_tenant_candidates_v1"] = tenant_candidates
                st.session_state["competitor_tenant_id"] = tenant_candidates[0]
                if google_config is not None:
                    current_license_fingerprint = fingerprint_license(
                        lic_input,
                        google_config,
                    )
                    if (
                        st.session_state.get("google_oauth_license_fingerprint")
                        != current_license_fingerprint
                    ):
                        st.session_state.pop("google_oauth_credentials", None)
                        st.session_state.pop("df_google", None)
                        st.session_state.pop("google_report", None)
                    st.session_state["google_license_fingerprint"] = (
                        current_license_fingerprint
                    )
                st.session_state["license_valid"]=True; st.session_state["license_data"]=info; st.rerun()
            else: st.error("Clave inválida")
    st.stop()

google_license_fingerprint = st.session_state.get("google_license_fingerprint")
google_oauth_notice = st.session_state.pop("google_oauth_notice", None)
pending_oauth_callback = st.session_state.get("google_oauth_pending_callback")
if pending_oauth_callback is not None and google_license_fingerprint:
    st.session_state.pop("google_oauth_pending_callback", None)
    if google_config is None:
        google_oauth_notice = (
            "No se pudo validar la autorización porque falta configurar Google OAuth."
        )
    else:
        try:
            google_credentials = complete_oauth_callback(
                pending_oauth_callback.get("code"),
                pending_oauth_callback.get("state"),
                google_config,
                google_license_fingerprint,
                oauth_error=pending_oauth_callback.get("error"),
            )
        except GoogleAdsError as exc:
            google_oauth_notice = str(exc)
        else:
            previous_credentials = st.session_state.get(
                "google_oauth_credentials", {}
            )
            if (
                not google_credentials["refresh_token"]
                and st.session_state.get("google_oauth_license_fingerprint")
                == google_license_fingerprint
                and previous_credentials.get("refresh_token")
            ):
                google_credentials["refresh_token"] = previous_credentials[
                    "refresh_token"
                ]
            st.session_state["google_oauth_credentials"] = google_credentials
            st.session_state["google_oauth_license_fingerprint"] = (
                google_license_fingerprint
            )
            google_oauth_notice = "Google Ads quedó conectado para esta sesión."

lic_data=st.session_state.get("license_data",{})
if "_license_scope" not in st.session_state:
    start_license_session(st.session_state)
if st.session_state.get("license_valid") and lic_data:
    st.session_state.setdefault(
        "competitor_tenant_id", tenant_id_for_license(lic_data)
    )
    st.session_state.setdefault(
        "competitor_tenant_candidates_v1",
        tenant_id_candidates_for_license(lic_data),
    )
cliente_default=lic_data.get("client","CLIENTE")
meta_download_requested = False
google_download_requested = False
tiktok_download_requested = False
with st.sidebar:
    st.markdown(
        """
        <div class="agency-sidebar-brand">
            <div class="agency-sidebar-mark">A</div>
            <div class="agency-sidebar-name">AGENCIA OS</div>
            <div class="agency-sidebar-caption">ADVERTISING INTELLIGENCE</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <nav class="agency-sidebar-nav" aria-label="Navegación principal">
            <a href="#dashboard">Dashboard</a>
            <a href="#platforms">Plataformas</a>
            <a href="#tools">Herramientas</a>
        </nav>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="agency-sidebar-section">CUENTA ACTIVA</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"### {cliente_default}")
    if st.button("Cambiar licencia", use_container_width=True):
        invalidate_license_session(st.session_state)
        st.rerun()
    cliente=st.text_input("Cliente",value=cliente_default)
    st.markdown('<div class="agency-sidebar-section">PERÍODO DEL INFORME</div>', unsafe_allow_html=True)
    preset=st.selectbox(
        "Rango",
        ["last_7d","last_14d","last_30d","custom"],
        index=2,
        format_func=lambda value: {
            "last_7d": "Últimos 7 días",
            "last_14d": "Últimos 14 días",
            "last_30d": "Últimos 30 días",
            "custom": "Fechas personalizadas",
        }[value],
    )
    custom_start = None
    custom_end = None
    if preset == "custom":
        custom_start = st.date_input(
            "Desde",
            value=date.today() - timedelta(days=30),
            key="meta_custom_start",
        )
        custom_end = st.date_input(
            "Hasta",
            value=date.today() - timedelta(days=1),
            key="meta_custom_end",
        )
        if custom_start <= custom_end:
            st.caption(
                f"Período seleccionado: {custom_start.isoformat()} a "
                f"{custom_end.isoformat()} (histórico)."
            )
        else:
            st.warning("La fecha de inicio no puede ser posterior a la fecha de fin.")
    else:
        selected_period = meta_date_range(preset)
        st.caption(
            f"Período seleccionado: {selected_period[0]} a "
            f"{selected_period[1]} (histórico)."
        )
    st.divider()
    st.markdown('<div class="agency-sidebar-section">PLATAFORMAS PUBLICITARIAS</div>', unsafe_allow_html=True)
    st.markdown("**META ADS**")
    meta_token=st.text_input("Token Meta",type="password",key="meta")
    meta_act=st.text_input("Ad Account",key="meta_act")
    st.caption("La conexión actual requiere un token manual; no usa OAuth.")
    if st.button("Bajar META",use_container_width=True):
        meta_download_requested = True
    st.markdown("**GOOGLE ADS**")
    if google_oauth_notice:
        st.info(google_oauth_notice)
    if google_config_error:
        st.warning(google_config_error)
    elif google_config:
        if not google_license_fingerprint:
            st.warning(
                "Revalidá la licencia para vincular la autorización de Google Ads."
            )
            google_license_input = st.text_input(
                "Licencia para Google Ads",
                type="password",
                key="google_license_revalidation",
            )
            if st.button("Validar licencia para Google Ads", use_container_width=True):
                licenses = load_licenses()
                license_is_valid, _ = validate_license(
                    google_license_input,
                    licenses,
                )
                if license_is_valid:
                    current_license_fingerprint = fingerprint_license(
                        google_license_input,
                        google_config,
                    )
                    if (
                        st.session_state.get("google_oauth_license_fingerprint")
                        != current_license_fingerprint
                    ):
                        st.session_state.pop("google_oauth_credentials", None)
                        st.session_state.pop("df_google", None)
                        st.session_state.pop("google_report", None)
                    st.session_state["google_license_fingerprint"] = (
                        current_license_fingerprint
                    )
                    st.rerun()
                else:
                    st.error("La licencia no es válida.")
        else:
            google_credentials = st.session_state.get("google_oauth_credentials")
            if (
                google_credentials
                and st.session_state.get("google_oauth_license_fingerprint")
                != google_license_fingerprint
            ):
                st.session_state.pop("google_oauth_credentials", None)
                st.session_state.pop("df_google", None)
                st.session_state.pop("google_report", None)
                google_credentials = None
            if not google_credentials:
                google_state = create_oauth_state(
                    google_config,
                    google_license_fingerprint,
                )
                st.link_button(
                    "Conectar Google Ads",
                    build_authorization_url(google_config, google_state),
                    use_container_width=True,
                )
            else:
                st.success("Google Ads conectado en esta sesión.")
                google_customer_id = st.text_input(
                    "ID de cliente Google Ads",
                    key="google_customer_id",
                    help="Ingresá el ID de 10 dígitos, con o sin guiones.",
                )
                google_login_customer_id = st.text_input(
                    "ID de cuenta administradora (opcional)",
                    key="google_login_customer_id",
                    help="Completalo solo si accedés al cliente mediante una cuenta administradora.",
                )
                if st.button("Bajar GOOGLE",use_container_width=True):
                    google_download_requested = True
                if st.button("Desconectar Google Ads",use_container_width=True):
                    st.session_state.pop("google_oauth_credentials", None)
                    st.session_state.pop("google_oauth_license_fingerprint", None)
                    st.session_state.pop("df_google", None)
                    st.session_state.pop("google_report", None)
                    st.rerun()
    st.markdown("**TIKTOK ADS**")
    tiktok_access_token = st.text_input(
        "Token de acceso TikTok",
        type="password",
        key="tiktok_access_token",
    )
    tiktok_advertiser_input = st.text_input(
        "ID de anunciante TikTok",
        key="tiktok_advertiser_id",
    )
    if st.button("Bajar TIKTOK",use_container_width=True):
        tiktok_download_requested = True
    st.divider()
    st.markdown('<div class="agency-sidebar-section">ACCIONES</div>', unsafe_allow_html=True)
    if st.button("UNIFICAR TODO",type="primary",use_container_width=True):
        frames=[
            st.session_state[key]
            for key in ["df_meta","df_google","df_tiktok"]
            if key in st.session_state and not st.session_state[key].empty
        ]
        if frames:
            df_all=pd.concat(frames,ignore_index=True)
            gasto_all = (
                df_all["Spend"].sum()
                if df_all["Spend"].notna().all()
                else None
            )
            revenue_all = (
                df_all["Revenue"].sum()
                if df_all["Revenue"].notna().all()
                else None
            )
            roas_all = (
                revenue_all / gasto_all
                if revenue_all is not None and gasto_all is not None and gasto_all > 0
                else None
            )
            st.session_state["df_all"]=df_all
            st.session_state["gasto_all"]=gasto_all
            st.session_state["roas_all"]=roas_all
            st.success("Unificado"); st.rerun()
        else: st.warning("Bajá un canal que haya devuelto datos reales.")

st.markdown(
    """
    <section class="agency-hero">
        <div class="eyebrow">PLATAFORMAS | ANALITICA | ESTRATEGIA</div>
        <h1>AGENCIA OS</h1>
        <p>Tu centro de control publicitario</p>
    </section>
    """,
    unsafe_allow_html=True,
)
if tiktok_download_requested:
    for key in (
        "df_all",
        "gasto_all",
        "roas_all",
        "df_tiktok",
        "tiktok_report",
    ):
        st.session_state.pop(key, None)
    selected_tiktok_period = None
    normalized_tiktok_advertiser = None
    try:
        selected_tiktok_period = meta_date_range(
            preset,
            custom_start=custom_start,
            custom_end=custom_end,
        )
        normalized_tiktok_advertiser = normalize_advertiser_id(
            tiktok_advertiser_input
        )
        with st.spinner("Consultando TikTok Ads..."):
            df_tiktok = fetch_campaign_report(
                tiktok_access_token,
                normalized_tiktok_advertiser,
                selected_tiktok_period,
            )
    except (TikTokAdsError, ValueError) as exc:
        st.session_state["tiktok_report"] = {
            "advertiser_id": normalized_tiktok_advertiser,
            "period": selected_tiktok_period,
            "status": "error",
            "message": str(exc),
        }
    else:
        st.session_state["df_tiktok"] = df_tiktok
        st.session_state["tiktok_report"] = {
            "advertiser_id": normalized_tiktok_advertiser,
            "period": selected_tiktok_period,
            "status": "empty" if df_tiktok.empty else "data",
        }

if "tiktok_report" in st.session_state:
    tiktok_report = st.session_state["tiktok_report"]
    st.markdown("### TIKTOK ADS — resultados históricos")
    if tiktok_report["period"]:
        since, until = tiktok_report["period"]
        account_context = (
            f"Anunciante consultado: {tiktok_report['advertiser_id']} · "
            if tiktok_report["advertiser_id"]
            else ""
        )
        st.caption(
            f"{account_context}Período: {since} a {until}. "
            "No son datos en tiempo real."
        )
    if tiktok_report["status"] == "error":
        st.warning(
            "No se completó la consulta de TikTok Ads: "
            f"{tiktok_report['message']}"
        )
    elif tiktok_report["status"] == "empty":
        st.info("TikTok Ads respondió correctamente sin campañas en el período consultado.")
        df_tiktok = st.session_state["df_tiktok"]
        st.download_button(
            "Descargar informe TIKTOK ADS (CSV)",
            data=export_report_csv(df_tiktok),
            file_name=f"tiktok_ads_campanas_{since}_{until}.csv",
            mime="text/csv",
            key="download_tiktok_csv",
            use_container_width=True,
        )
        st.download_button(
            "Descargar informe TIKTOK ADS (Excel)",
            data=export_report_excel(df_tiktok),
            file_name=f"tiktok_ads_campanas_{since}_{until}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_tiktok_excel",
            use_container_width=True,
        )
    elif tiktok_report["status"] == "data":
        df_tiktok = st.session_state["df_tiktok"]
        st.success(f"TikTok Ads devolvió {len(df_tiktok)} filas de métricas.")
        st.dataframe(df_tiktok, use_container_width=True)
        st.download_button(
            "Descargar informe TIKTOK ADS (CSV)",
            data=export_report_csv(df_tiktok),
            file_name=f"tiktok_ads_campanas_{since}_{until}.csv",
            mime="text/csv",
            key="download_tiktok_csv",
            use_container_width=True,
        )
        st.download_button(
            "Descargar informe TIKTOK ADS (Excel)",
            data=export_report_excel(df_tiktok),
            file_name=f"tiktok_ads_campanas_{since}_{until}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_tiktok_excel",
            use_container_width=True,
        )

if google_download_requested:
    for key in ("df_all", "gasto_all", "roas_all", "df_google", "google_report"):
        st.session_state.pop(key, None)
    google_selected_period = None
    google_display_customer_id = None
    try:
        google_selected_period = meta_date_range(
            preset,
            custom_start=custom_start,
            custom_end=custom_end,
        )
        normalized_customer_id = normalize_customer_id(google_customer_id)
        google_display_customer_id = normalized_customer_id
        credentials = st.session_state["google_oauth_credentials"]
        with st.spinner("Consultando Google Ads..."):
            access_token = get_valid_access_token(credentials, google_config)
            df_google = fetch_google_campaigns(
                access_token,
                normalized_customer_id,
                google_selected_period,
                login_customer_id=google_login_customer_id or None,
            )
    except (GoogleAdsError, ValueError) as exc:
        st.session_state["google_report"] = {
            "customer_id": google_display_customer_id,
            "period": google_selected_period,
            "status": "error",
            "message": str(exc),
        }
    else:
        st.session_state["df_google"] = df_google
        st.session_state["google_report"] = {
            "customer_id": normalized_customer_id,
            "period": google_selected_period,
            "status": "empty" if df_google.empty else "data",
        }

if "google_report" in st.session_state:
    google_report = st.session_state["google_report"]
    st.markdown("### GOOGLE ADS — resultados históricos")
    if google_report["period"]:
        since, until = google_report["period"]
        account_context = (
            f"Cuenta consultada: {google_report['customer_id']} · "
            if google_report["customer_id"]
            else ""
        )
        st.caption(f"{account_context}Período: {since} a {until}. No son datos en tiempo real.")
    if google_report["status"] == "error":
        st.warning(
            "No se completó la consulta de Google Ads: "
            f"{google_report['message']}"
        )
    elif google_report["status"] == "empty":
        st.info("Google Ads respondió correctamente sin campañas en el período consultado.")
    elif google_report["status"] == "data":
        df_google = st.session_state["df_google"]
        st.success(f"Google Ads devolvió {len(df_google)} filas de métricas.")
        st.caption(
            "Revenue refleja el valor de conversión configurado en Google Ads; "
            "no necesariamente equivale a ventas monetarias."
        )
        st.dataframe(df_google, use_container_width=True)
        st.download_button(
            "Descargar informe GOOGLE ADS (CSV)",
            data=df_google.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"google_ads_campanas_{since}_{until}.csv",
            mime="text/csv",
            key="download_google_csv",
            use_container_width=True,
        )

if meta_download_requested:
    for key in (
        "df_all",
        "gasto_all",
        "roas_all",
        "df_meta",
        "meta_period",
        "meta_query",
        "meta_result_status",
    ):
        st.session_state.pop(key, None)
    try:
        selected_period = meta_date_range(
            preset,
            custom_start=custom_start,
            custom_end=custom_end,
        )
        normalized_account = normalize_ad_account(meta_act)
    except ValueError as exc:
        st.error(str(exc))
        st.session_state["meta_result_status"] = "error"
    else:
        st.session_state["meta_period"] = selected_period
        st.session_state["meta_query"] = {
            "account": normalized_account,
            "period": selected_period,
        }
        with st.spinner("Consultando Meta Ads..."):
            df_meta = fetch_meta_free(
                meta_token,
                meta_act,
                preset,
                custom_start=custom_start,
                custom_end=custom_end,
                selected_period=selected_period,
            )
        if df_meta is None:
            st.session_state["meta_result_status"] = "error"
        else:
            st.session_state["df_meta"] = df_meta
            st.session_state["meta_result_status"] = (
                "empty" if df_meta.empty else "data"
            )

if "meta_query" in st.session_state:
    meta_query = st.session_state["meta_query"]
    since, until = meta_query["period"]
    st.markdown("### META — resultados históricos")
    st.caption(
        f"Cuenta consultada: {meta_query['account']} · "
        f"Período: {since} a {until}. No son datos en tiempo real."
    )
    if st.session_state.get("meta_result_status") == "error":
        st.warning("La consulta no se completó; no se muestran métricas de esta solicitud.")
    elif st.session_state.get("meta_result_status") == "empty":
        st.info("Meta respondió correctamente sin campañas para el período consultado.")
    elif st.session_state.get("meta_result_status") == "data":
        df_meta = st.session_state["df_meta"]
        metric_columns = ["Spend", "Impressions", "CTR", "CPC", "Conversions", "Revenue"]
        if df_meta[metric_columns].notna().any().any():
            st.success(f"Meta devolvió {len(df_meta)} campañas con resultados.")
        else:
            st.warning("Meta devolvió campañas, pero no valores para las métricas solicitadas.")
        st.dataframe(df_meta, use_container_width=True)
        st.download_button(
            "Descargar informe META (CSV)",
            data=df_meta.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"meta_campanas_{since}_{until}.csv",
            mime="text/csv",
            key="download_meta_csv",
            use_container_width=True,
        )

meta_report_status = st.session_state.get("meta_result_status", "pending")
meta_status_labels = {
    "data": ("Informe disponible", "is-ready"),
    "empty": ("Sin datos para el período", "is-empty"),
    "error": ("Error en el último intento", "is-error"),
}
meta_status = meta_status_labels.get(meta_report_status, ("Pendiente", "is-pending"))

google_report_status = st.session_state.get("google_report", {}).get("status")
google_is_connected = (
    bool(st.session_state.get("google_oauth_credentials"))
    and st.session_state.get("google_oauth_license_fingerprint")
    == google_license_fingerprint
)
if google_report_status == "error":
    google_status = ("Error en el último intento", "is-error")
elif google_report_status == "empty":
    google_status = ("Sin datos para el período", "is-empty")
elif google_report_status == "data":
    google_status = ("Informe disponible", "is-ready")
elif google_is_connected:
    google_status = ("Conectado en esta sesión", "is-connected")
elif google_config_error:
    google_status = ("Configuración pendiente", "is-pending")
else:
    google_status = ("Pendiente", "is-pending")

tiktok_report_status = st.session_state.get("tiktok_report", {}).get("status")
tiktok_status = {
    "data": ("Informe disponible", "is-ready"),
    "empty": ("Sin datos para el período", "is-empty"),
    "error": ("Error en el último intento", "is-error"),
}.get(tiktok_report_status, ("Pendiente", "is-pending"))

platform_statuses = (
    ("META ADS", meta_status),
    ("INSTAGRAM", ("Sin integración separada", "is-unavailable")),
    ("GOOGLE ADS", google_status),
    ("TIKTOK ADS", tiktok_status),
)
st.markdown('<div class="agency-section-heading" id="platforms"><div class="agency-kicker">PLATAFORMAS</div><h2>Estado de conexiones</h2><p>Estados basados en la sesión y en los últimos informes disponibles.</p></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="agency-platform-strip">'
    + "".join(
        '<div class="agency-platform-card">'
        f'<div class="agency-platform-name">{name}</div>'
        f'<div class="agency-platform-state {state_class}">{label}</div>'
        "</div>"
        for name, (label, state_class) in platform_statuses
    )
    + "</div>",
    unsafe_allow_html=True,
)

st.markdown('<div class="agency-section-heading" id="dashboard"><div class="agency-kicker">RESUMEN</div><h2>Dashboard ejecutivo</h2><p>Resultados agregados de los informes cargados para el período seleccionado.</p></div>', unsafe_allow_html=True)
k1, k2, k3 = st.columns(3)

if "df_all" in st.session_state:
    df_all = st.session_state["df_all"]
    gasto_display = (
        f"${st.session_state['gasto_all']:,.0f}"
        if st.session_state["gasto_all"] is not None
        else "No disponible"
    )
    roas_display = (
        f"{st.session_state['roas_all']:.2f}x"
        if st.session_state["roas_all"] is not None
        else "No disponible"
    )
    campanas_display = str(len(df_all))
else:
    df_all = None
    gasto_display = "\u2014"
    roas_display = "\u2014"
    campanas_display = "\u2014"

k1.metric("Gasto", gasto_display, help="Inversi?n de los informes consolidados")
k2.metric("ROAS", roas_display, help="Retorno publicitario de los informes consolidados")
k3.metric("Campa\u00f1as", campanas_display, help="Registros incluidos en el informe consolidado")

if df_all is not None:
    spend_by_platform = (
        df_all.loc[df_all["Spend"].notna()]
        .groupby("Canal")["Spend"]
        .sum()
        .sort_values(ascending=False)
    )
    if len(spend_by_platform) > 1:
        st.markdown("#### Inversi?n por plataforma")
        st.bar_chart(spend_by_platform, height=240)
    st.markdown("#### Rendimiento consolidado")
    st.dataframe(df_all, width="stretch", hide_index=True)
else:
    st.info("Todav\u00eda no hay informes consolidados. Cuando cargues datos y elijas UNIFICAR TODO, las m\u00e9tricas mostrar\u00e1n los resultados reales.")

st.divider()
st.markdown('<div class="agency-section-heading" id="tools"><div class="agency-kicker">CREATIVIDAD</div><h2>Herramientas de campaña</h2><p>Investigación orientativa y generación de propuestas originales.</p></div>', unsafe_allow_html=True)
t1, t2 = st.tabs(["ESPÍA DE COMPETIDORES", "CLONADOR CREATIVO"])

with t1:
    tenant_id = st.session_state.get("competitor_tenant_id")
    loaded_tenant_id = st.session_state.get(
        "competitor_observations_loaded_tenant_v1"
    )
    if tenant_id and loaded_tenant_id != tenant_id:
        try:
            resolved_tenant_id, cloud_observations = load_observations_for_tenants(
                SUPABASE_URL,
                SUPABASE_SECRET_KEY,
                st.session_state.get(
                    "competitor_tenant_candidates_v1", [tenant_id]
                ),
            )
        except CompetitorStoreError as exc:
            st.session_state["competitor_observations_load_error_v1"] = str(exc)
        else:
            tenant_id = resolved_tenant_id
            st.session_state["competitor_tenant_id"] = resolved_tenant_id
            st.session_state["competitor_observations_v1"] = cloud_observations
            st.session_state["competitor_observations_loaded_tenant_v1"] = resolved_tenant_id
            st.session_state["competitor_observations_unsaved_v1"] = False
            st.session_state.pop("competitor_observations_load_error_v1", None)

    observation_load_error = st.session_state.get(
        "competitor_observations_load_error_v1"
    )
    competitor_storage_ready = bool(
        tenant_id
        and st.session_state.get("competitor_observations_loaded_tenant_v1")
        == tenant_id
        and not observation_load_error
    )
    if observation_load_error:
        st.warning(
            "No se pudieron cargar las observaciones guardadas. "
            "El formulario de registro queda deshabilitado hasta resolverlo. "
            f"Detalle: {observation_load_error}"
        )
    elif competitor_storage_ready:
        st.caption("Almacenamiento de observaciones conectado a Supabase para esta licencia.")
    else:
        st.warning("Ingresá con una licencia válida para usar el registro persistente del Espía.")

    st.subheader("Espía de competidores")
    st.caption(
        "Busca anuncios publicos en la Biblioteca de Meta. "
        "Las ideas generadas por Agencia OS son orientativas y no son datos verificados."
    )
    comp = st.text_input(
        "Marca o competidor",
        placeholder="Ej.: Coto, Zara, Fravega...",
        key="spy_competitor",
    )
    comp2 = st.text_input(
        "Segunda marca para comparar (opcional)",
        placeholder="Ej.: Carrefour",
        key="spy_competitor_2",
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("BUSCAR ANUNCIOS PUBLICOS", type="primary", use_container_width=True):
            if not comp.strip():
                st.warning("Escribi una marca para buscar.")
            else:
                meta_url = (
                    "https://www.facebook.com/ads/library/"
                    "?active_status=active&ad_type=all&country=AR"
                    "&is_targeted_country=false&media_type=all"
                    "&search_type=keyword_unordered"
                    "&sort_data[direction]=desc&sort_data[mode]=total_impressions&q="
                    + quote_plus(comp.strip())
                )
                st.session_state["spy_meta_url"] = meta_url
                st.session_state["spy_last_comp"] = comp.strip()

    with c2:
        if st.button("GENERAR HIPOTESIS", use_container_width=True):
            if not comp.strip():
                st.warning("Escribi una marca para generar hipotesis.")
            else:
                st.session_state["spy_res"] = analisis_real_diferenciado(comp.strip())
                st.session_state["spy_res_brand"] = comp.strip()

    if "spy_meta_url" in st.session_state:
        st.link_button(
            "Abrir resultados en la Biblioteca de anuncios de Meta",
            st.session_state["spy_meta_url"],
            use_container_width=True,
        )
        st.caption(
            "La busqueda se abre en Meta. Agencia OS no descarga ni verifica automaticamente "
            "los anuncios mostrados en esa pagina."
        )

    if st.button("COMPARAR HIPOTESIS DE DOS MARCAS", use_container_width=True):
        if not comp.strip() or not comp2.strip():
            st.warning("Completa las dos marcas para compararlas.")
        elif comp.strip().casefold() == comp2.strip().casefold():
            st.warning("Eleg? dos marcas diferentes.")
        else:
            st.session_state["spy_res"] = (
                analisis_real_diferenciado(comp.strip())
                + "\n\n--- COMPARACION ORIENTATIVA ---\n\n"
                + analisis_real_diferenciado(comp2.strip())
            )
            st.session_state["spy_res_brand"] = comp.strip() + " / " + comp2.strip()

    st.markdown("#### Analizar un anuncio real")
    st.caption(
        "Pega el texto que ves en el anuncio. El analisis utiliza el contenido "
        "aportado manualmente; no verifica el enlace, el anunciante ni las metricas."
    )
    spy_ad_url = st.text_input(
        "Enlace del anuncio (opcional, no verificado)",
        placeholder="https://...",
        key="spy_ad_url",
    )
    spy_ad_copy = st.text_area(
        "Texto del anuncio",
        placeholder="Pega aqui el texto del anuncio que encontraste en Meta...",
        height=150,
        key="spy_ad_copy",
    )

    if st.button("ANALIZAR TEXTO APORTADO", use_container_width=True):
        if not spy_ad_copy.strip():
            st.warning("Pega el texto del anuncio antes de analizarlo.")
        else:
            ad_text = spy_ad_copy.strip()
            lines = [line.strip() for line in ad_text.splitlines() if line.strip()]
            words = ad_text.split()
            normalized = "" .join(ch for ch in unicodedata.normalize("NFKD", ad_text.casefold()) if not unicodedata.combining(ch))

            sentences = [
                part.strip(" \t\r\n-?")
                for part in ad_text.replace("!", ".").replace("?", ".").split(".")
                if part.strip(" \t\r\n-?")
            ]
            hook = sentences[0] if sentences else ad_text[:180]

            cta_terms = [
                "descubri", "compra", "comprar", "compralo", "escribinos",
                "contactanos", "reserva", "reservar", "pedilo", "pedi",
                "conoce", "conoce mas", "mas informacion", "visitanos",
                "proba", "proba ahora", "solicita", "consulta", "consultanos",
                "sumate", "registrate", "inscribite", "hace tu pedido",
                "hace clic", "entra ahora"
            ]
            cta_found = [term for term in cta_terms if term in normalized]

            benefit_terms = [
                "beneficio", "ahorro", "ahorra", "gratis", "rapido",
                "facil", "calidad", "nuevo", "nueva", "solucion",
                "resultado", "comodidad", "proteccion", "personalizado",
                "coleccion", "oferta", "descuento", "promocion"
            ]
            benefits_found = [term for term in benefit_terms if term in normalized]

            has_offer_signals = any(
                marker in normalized for marker in ("$", "%", "ars", "usd", "2x1", "descuento", "promocion", "oferta")
            )
            has_question = "?" in ad_text or "?" in ad_text
            has_urgency = any(
                term in normalized for term in (
                    "por tiempo limitado", "ultimos dias", "solo hoy",
                    "hasta agotar", "no te lo pierdas"
                )
            )

            report = [
                "ANALISIS DEL TEXTO APORTADO",
                "",
                "ORIGEN Y LIMITACIONES",
                "- Analisis automatico de texto proporcionado manualmente.",
                "- No se verificaron el anunciante, el enlace ni la autenticidad del anuncio.",
                "- No se consultaron estadisticas, alcance, gasto ni resultados de Meta.",
                "",
                "1. GANCHO PROBABLE",
                f"- {hook[:240]}",
                "",
                "2. BENEFICIO O PROPUESTA",
                (
                    "- Posibles palabras de beneficio: " + ", ".join(benefits_found) + "."
                    if benefits_found
                    else "- No se detecto una promesa de beneficio clara mediante las palabras analizadas."
                ),
                "",
                "3. OFERTA Y URGENCIA",
                (
                    "- Hay referencias que podrian indicar precio, descuento u oferta; su validez no fue verificada."
                    if has_offer_signals
                    else "- No se detectaron referencias habituales a precio o descuento."
                ),
                (
                    "- Se detectaron expresiones de urgencia; no se verifico si tienen fundamento."
                    if has_urgency
                    else "- No se detectaron expresiones comunes de urgencia."
                ),
                "",
                "4. LLAMADA A LA ACCION",
                (
                    "- Posibles CTA detectadas: " + ", ".join(cta_found) + "."
                    if cta_found
                    else "- No se detecto una llamada a la accion habitual. Puede estar expresada de otra manera."
                ),
                "",
                "5. ESTRUCTURA Y FORMATO",
                f"- Extension aproximada: {len(words)} palabras.",
                f"- Lineas con contenido: {len(lines)}.",
                f"- Contiene una pregunta: {'Si' if has_question else 'No'}.",
                "",
                "6. OPORTUNIDADES PARA TU PROPIA PUBLICIDAD",
                "- Conserva la estructura que resulte util, pero redacta un mensaje original.",
                "- Explica el beneficio de tu oferta en la primera frase.",
                "- Agrega una demostracion o prueba real cuando este disponible.",
                "- Usa precios, descuentos, urgencia y promesas solo si puedes verificarlos.",
                "- Termina con una llamada a la accion concreta.",
                "",
                "ENLACE APORTADO (NO VERIFICADO)",
                spy_ad_url.strip() or "No se proporciono un enlace.",
            ]
            st.session_state["spy_ad_analysis"] = "\n".join(report)
            st.session_state["spy_ad_reference_text"] = ad_text
            st.session_state["spy_ad_reference_hook"] = hook
            st.session_state["spy_ad_reference_cta"] = cta_found[0] if cta_found else ""
            st.session_state["spy_ad_reference_offer"] = has_offer_signals
            st.session_state["spy_ad_reference_benefits"] = benefits_found

    if "spy_ad_analysis" in st.session_state:
        st.markdown("#### Resultado del analisis")
        st.text(st.session_state["spy_ad_analysis"])

    if "spy_res" in st.session_state:
        st.markdown("#### Hipotesis orientativas")
        st.caption(
            "Se generan con reglas y datos precargados. No representan una observacion "
            "verificada de anuncios actuales ni de precios reales."
        )
        st.text(st.session_state["spy_res"])


    st.divider()
    st.markdown("#### Registrar y guardar una observación")
    st.caption(
        "Registrá los datos que observaste en una biblioteca pública. "
        "Agencia OS no descarga automáticamente el anuncio ni verifica sus métricas."
    )

    with st.expander("Registrar una observación", expanded=False):
        with st.form("competitor_observation_form", clear_on_submit=True):
            obs_col1, obs_col2 = st.columns(2)
            with obs_col1:
                obs_brand = st.text_input(
                    "Marca competidora",
                    value=st.session_state.get("spy_last_comp", ""),
                    key="spy_observation_brand",
                )
                obs_platform = st.selectbox(
                    "Plataforma",
                    ("Meta", "Google", "TikTok", "Otra"),
                    key="spy_observation_platform",
                )
                obs_url = st.text_input(
                    "URL pública del anuncio o fuente (opcional)",
                    placeholder="https://...",
                    key="spy_observation_url",
                )
                obs_date = st.date_input(
                    "Fecha de observación",
                    value=date.today(),
                    key="spy_observation_date",
                )
                obs_format = st.text_input(
                    "Formato creativo",
                    placeholder="Video, imagen, carrusel...",
                    key="spy_observation_format",
                )
                obs_headline = st.text_input(
                    "Titular",
                    key="spy_observation_headline",
                )
            with obs_col2:
                obs_text = st.text_area(
                    "Texto del anuncio",
                    key="spy_observation_text",
                    height=140,
                )
                obs_proposition = st.text_input(
                    "Propuesta",
                    key="spy_observation_proposition",
                )
                obs_offer = st.text_input(
                    "Oferta (si corresponde)",
                    key="spy_observation_offer",
                )
                obs_cta = st.text_input(
                    "Llamada a la acción",
                    key="spy_observation_cta",
                )
                obs_destination = st.text_input(
                    "Destino público indicado",
                    key="spy_observation_destination",
                )
            obs_notes = st.text_area("Notas", key="spy_observation_notes")
            save_observation = st.form_submit_button(
                "Guardar observación en la nube",
                type="primary",
                use_container_width=True,
                disabled=not competitor_storage_ready,
            )

        if save_observation:
            try:
                new_record = create_observation({
                    "brand": obs_brand,
                    "platform": obs_platform,
                    "source_url": obs_url,
                    "observed_on": obs_date.isoformat(),
                    "creative_format": obs_format,
                    "headline": obs_headline,
                    "text": obs_text,
                    "proposition": obs_proposition,
                    "offer": obs_offer,
                    "call_to_action": obs_cta,
                    "destination": obs_destination,
                    "notes": obs_notes,
                })
            except ValueError as exc:
                st.error(str(exc))
            else:
                current_records = list(
                    st.session_state.get("competitor_observations_v1", [])
                )
                candidate_records = current_records + [new_record]
                st.session_state["competitor_observations_v1"] = candidate_records
                try:
                    save_observations(
                        SUPABASE_URL, SUPABASE_SECRET_KEY,
                        tenant_id, candidate_records
                    )
                except CompetitorStoreError as exc:
                    st.session_state["competitor_observations_unsaved_v1"] = True
                    st.error(f"No se confirmó el guardado en Supabase: {exc}")
                    st.warning(
                        "El registro queda en esta sesión. Descargá un JSON "
                        "antes de cerrar y reintentá el guardado."
                    )
                else:
                    st.session_state["competitor_observations_unsaved_v1"] = False
                    st.success("Observación guardada en la sesión y en la nube.")
                    st.rerun()

    saved_observations = st.session_state.get("competitor_observations_v1", [])
    if st.session_state.get("competitor_observations_unsaved_v1") and competitor_storage_ready:
        if st.button(
            "Reintentar guardado pendiente",
            key="spy_retry_unsaved_observations",
        ):
            try:
                save_observations(
                    SUPABASE_URL, SUPABASE_SECRET_KEY,
                    tenant_id, saved_observations
                )
            except CompetitorStoreError as exc:
                st.error(f"El guardado sigue pendiente: {exc}")
            else:
                st.session_state["competitor_observations_unsaved_v1"] = False
                st.success("Las observaciones pendientes ya están guardadas en Supabase.")
                st.rerun()

    if saved_observations:
        st.markdown("#### Observaciones guardadas")
        st.caption(f"Registros cargados para esta licencia: {len(saved_observations)}.")
        st.download_button(
            "Descargar respaldo JSON",
            data=export_observations_json(saved_observations),
            file_name="observaciones_competidores.json",
            mime="application/json",
            key="spy_export_observations_json",
        )

        filter_query = st.text_input(
            "Buscar texto, marca o fuente",
            key="spy_saved_observations_filter",
        ).strip().casefold()
        filtered_observations = [
            item for item in saved_observations
            if not filter_query or filter_query in " ".join(
                str(item.get(field, "")) for field in (
                    "brand", "platform", "source_url", "headline",
                    "text", "proposition", "offer", "call_to_action",
                    "destination", "notes",
                )
            ).casefold()
        ]

        display_rows = [
            {
                "Marca": item["brand"],
                "Plataforma": item["platform"],
                "Fecha": item["observed_on"],
                "Formato": item["creative_format"],
                "Titular": item["headline"],
                "Oferta": item["offer"],
                "CTA": item["call_to_action"],
                "Fuente": item["source_url"] or "No indicada",
            }
            for item in filtered_observations
        ]
        st.dataframe(pd.DataFrame(display_rows), width="stretch", hide_index=True)

        if len(filtered_observations) >= 2:
            labels = {
                item["id"]: (
                    f'{item["brand"]} · {item["platform"]} · '
                    f'{item["observed_on"]} · {item["headline"] or "Sin titular"}'
                )
                for item in filtered_observations
            }
            with st.expander("Comparar dos observaciones"):
                compare_cols = st.columns(2)
                first_id = compare_cols[0].selectbox(
                    "Primera observación",
                    list(labels),
                    format_func=lambda value: labels[value],
                    key="spy_compare_first",
                )
                second_id = compare_cols[1].selectbox(
                    "Segunda observación",
                    list(labels),
                    index=min(1, len(labels) - 1),
                    format_func=lambda value: labels[value],
                    key="spy_compare_second",
                )
                if first_id == second_id:
                    st.info("Elegí dos observaciones distintas para compararlas.")
                else:
                    first = next(item for item in filtered_observations if item["id"] == first_id)
                    second = next(item for item in filtered_observations if item["id"] == second_id)
                    diff_cols = st.columns(2)
                    compare_fields = (
                        ("Marca", "brand"),
                        ("Titular", "headline"),
                        ("Texto", "text"),
                        ("Propuesta", "proposition"),
                        ("Oferta", "offer"),
                        ("CTA", "call_to_action"),
                        ("Destino", "destination"),
                        ("Fuente", "source_url"),
                    )
                    for col, record, heading in (
                        (diff_cols[0], first, "Primera observación"),
                        (diff_cols[1], second, "Segunda observación"),
                    ):
                        with col:
                            st.markdown(f"**{heading}**")
                            for label, field in compare_fields:
                                st.markdown(f"**{label}:** {record.get(field) or 'No indicado'}")
    elif competitor_storage_ready:
        st.info("Todavía no hay observaciones guardadas para esta licencia.")

with t2:
    st.subheader("Clonador creativo")
    st.caption(
        "Crea propuestas originales para tu oferta. La marca de referencia no se consulta "
        "automaticamente y sus anuncios no se copian."
    )
    desc = st.text_input(
        "Tu producto, servicio u oferta",
        placeholder="Ej.: servicio de instalacion de aire acondicionado",
        key="clone_offer",
    )
    benefits = st.text_input(
        "Beneficios reales (opcional)",
        placeholder="Ej.: atencion personalizada, instalacion incluida",
        key="clone_benefits",
    )
    promo = st.text_input(
        "Promocion y condiciones reales (opcional)",
        placeholder="Ej.: 10% hasta el viernes, sujeto a condiciones",
        key="clone_promo",
    )
    comp_clone = st.text_input(
        "Marca de referencia (opcional)",
        placeholder="Ej.: una marca competidora",
        key="clone_reference",
    )
    objective = st.selectbox(
        "Objetivo de la publicidad",
        ["Ventas", "Generar consultas", "Reconocimiento de marca"],
        key="clone_objective",
    )

    if st.button("GENERAR 3 PROPUESTAS", type="primary", use_container_width=True):
        if not desc.strip():
            st.warning("Describe tu producto, servicio u oferta.")
        else:
            benefits_text = benefits.strip().rstrip(".")
            promo_text = promo.strip().rstrip(".")
            reference_text = st.session_state.get("spy_ad_reference_text", "").strip()
            reference_hook = st.session_state.get("spy_ad_reference_hook", "").strip()
            reference_brand = comp_clone.strip()

            proposals = generate_ad_proposals(
                desc,
                benefits_text,
                promo_text,
                objective,
            )

            st.session_state["clone_res"] = proposals
            if reference_text:
                st.session_state["clone_reference_note"] = (
                    "Texto de referencia aportado manualmente. Gancho detectado: "
                    + (reference_hook or "no disponible") + ". "
                    + "Anunciante, enlace y métricas no verificados. "
                    + "Generación por reglas, no IA generativa."
                )
            elif reference_brand:
                st.session_state["clone_reference_note"] = (
                    f"Marca ingresada: {reference_brand}. No fue consultada ni verificada. "
                    "Generación por reglas, no IA generativa."
                )
            else:
                if benefits_text or promo_text:
                    st.session_state["clone_reference_note"] = (
                        "Generación por reglas, no IA generativa. "
                        "Se incluyeron los beneficios y/o la promoción que ingresaste; "
                        "no se verificaron de forma independiente."
                    )
                else:
                    st.session_state["clone_reference_note"] = (
                        "Generación por reglas, no IA generativa. "
                        "Sin beneficios ni promociones aportados, se usan textos generales."
                    )

    if "clone_res" in st.session_state:
        note = st.session_state.get("clone_reference_note", "")
        if note:
            st.info(note)

        for proposal in st.session_state["clone_res"]:
            with st.container(border=True):
                st.code(proposal, language=None)
