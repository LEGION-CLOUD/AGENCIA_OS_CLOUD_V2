import streamlit as st
import pandas as pd
import requests
import os, json, random, string, hashlib
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

st.set_page_config(page_title="AGENCIA OS", page_icon="🚀", layout="wide")
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

def analisis_real_diferenciado(competidor):
    comp_lower = competidor.lower().strip()
    data = None
    for k,v in BRAND_DB.items():
        if k in comp_lower:
            data = v
            break
    if not data:
        if any(x in comp_lower for x in ["coto","dia","carrefour","vea","disco","jumbo","walmart","super","mercado"]):
            data = {"industria":"SUPERMERCADO","pos":"Ahorro y cercanía","fuerte":"Precio","debil":"Digital flojo","ticket":30000}
        elif any(x in comp_lower for x in ["jean","zara","levis","ropa","moda","47","complot","mango","h&m"]):
            data = {"industria":"MODA","pos":"Tendencia y horma","fuerte":"Diseño","debil":"Precio/calidad","ticket":50000}
        elif any(x in comp_lower for x in ["fravega","garbarino","musimundo","electro","tech"]):
            data = {"industria":"TECH","pos":"Cuotas y variedad","fuerte":"Financiación","debil":"Servicio","ticket":120000}
        else:
            data = {"industria":"GENERAL","pos":"Beneficio principal","fuerte":"Marca conocida","debil":"Poco diferencial","ticket":25000}

    industria = data["industria"]
    
    hooks_super = [
        f"\"Llevá 2x1 solo HOY en {competidor} - Ahorrá $15.000\"",
        f"\"Asado $6.999/kg en {competidor} - Hasta agotar stock\"",
        f"\"Con {competidor} Comunidad +30% OFF + 12 cuotas\"",
        f"\"Precios que no se ven: {competidor} $2.999 el kilo de pan\"",
        f"\"{competidor} te devuelve $10.000 si gastás $30.000\"",
        f"\"Canasta familiar $45.000 en {competidor} vs $68.000 afuera\"",
        f"\"{competidor} 3x2 en lácteos - Solo esta semana\"",
        f"\"Ofertas locas {competidor}: Shampoo $1.499\"",
    ]
    hooks_moda = [
        f"\"El jean {competidor} que no se transparenta ni se baja\"",
        f"\"Probé 5 jeans y solo {competidor} me levantó la cola\"",
        f"\"{competidor} 501 original - Dura 10 años\"",
        f"\"Antes $89.999 ahora $44.999 {competidor} - Últimas 20\"",
        f"\"{competidor} talle real argentino, no importado que aprieta\"",
        f"\"{competidor} no se deforma después de 20 lavados - Test\"",
        f"\"Por qué todas dejan Zara por {competidor}\"",
        f"\"{competidor} levanta 3cm sin tacos - Truco horma\"",
    ]
    hooks_tech = [
        f"\"{competidor} 50% OFF + 18 cuotas sin interés - Hoy\"",
        f"\"Llevá 2 electro en {competidor} pagá 1 - Liquidación\"",
        f"\"{competidor} precio más bajo del país o te devolvemos x2\"",
        f"\"{competidor} retira en 2hs gratis + garantía 2 años\"",
    ]

    if industria == "SUPERMERCADO":
        pool = hooks_super
        h1 = hash_pick(competidor+"1", pool)
        h2 = hash_pick(competidor+"2", pool)
        while h2==h1: h2 = hash_pick(competidor+"2x", pool)
        h3 = hash_pick(competidor+"3", pool)
        while h3==h1 or h3==h2: h3 = hash_pick(competidor+"3x", pool)
        formato1 = hash_pick(competidor+"f1", ["60% Carrusel precio gigante rojo","70% Reels changuito lleno vs ticket","50% Video oferta con reloj urgencia","80% Static precio + %OFF"])
        formato2 = hash_pick(competidor+"f2", ["30% Reels vertical","25% Carrusel comparativa","40% UGC cliente mostrando ticket","15% Influencer comprando"])
        angulo = f"{data['pos']}. Fuerte en {data['fuerte']}, débil en {data['debil']}. Ticket promedio ${data['ticket']:,}"
        como_superar = hash_pick(competidor+"sup", [
            f"Comparativa ticket real: Fui a {competidor} y acá con $20k - mirá donde rinde más",
            f"Garantía precio: Si encontrás más barato en {competidor}, te devolvemos diferencia x2 + envío gratis",
            f"Video reacción a su oferta con calculadora mostrando letra chica",
            f"Atacar debilidad: {competidor} es {data['debil']} - nosotros somos lo opuesto",
        ])
        ideas = [f"Canasta $20k en {competidor} vs nuestra - Desafío real", f"5 productos que {competidor} cobra caro", f"Qué compras con $10k en {competidor} vs acá", f"Letra chica de {competidor}", f"{competidor} {data['debil']} - nosotros lo resolvimos"]
        idea1 = hash_pick(competidor+"i1", ideas)
        idea2 = hash_pick(competidor+"i2", ideas)
        while idea2==idea1: idea2 = hash_pick(competidor+"i2b", ideas)
        idea3 = hash_pick(competidor+"i3", ideas)
        while idea3==idea1 or idea3==idea2: idea3 = hash_pick(competidor+"i3b", ideas)

    elif industria == "MODA":
        pool = hooks_moda
        h1 = hash_pick(competidor+"1", pool)
        h2 = hash_pick(competidor+"2", pool)
        while h2==h1: h2 = hash_pick(competidor+"2x", pool)
        h3 = hash_pick(competidor+"3", pool)
        while h3==h1 or h3==h2: h3 = hash_pick(competidor+"3x", pool)
        formato1 = hash_pick(competidor+"f1", ["70% UGC Reels chica probándose 12-18seg","60% Video probador espejo","80% Try-on haul"])
        formato2 = hash_pick(competidor+"f2", ["20% Carrusel detalles tela","30% Antes/después","15% Test transparencia"])
        angulo = f"{data['pos']}. Fuerte en {data['fuerte']}, débil en {data['debil']}. Ticket ${data['ticket']:,}"
        como_superar = f"Atacar {data['debil']}: {competidor} falla en {data['debil']} - mostrar que lo resolvimos"
        idea1 = hash_pick(competidor+"i1", [f"Test sentadilla {competidor} vs nosotros", f"Por qué dejé {competidor}", f"{competidor} talle único vs nuestro talle real"])
        idea2 = hash_pick(competidor+"i2", [f"{competidor} se transparenta? Test luz", f"Lo que {competidor} no te dice", f"{competidor} $89k vs nuestro $45k"])
        idea3 = hash_pick(competidor+"i3", [f"Reacción a ad de {competidor}", f"Probé {competidor} 30 días", f"Micro-influencer talle 44 probando {competidor}"])
    else:
        h1 = hash_pick(competidor+"1", hooks_tech+hooks_moda)
        h2 = hash_pick(competidor+"2", hooks_tech+hooks_moda)
        h3 = hash_pick(competidor+"3", hooks_tech+hooks_moda)
        formato1 = "60% Video oferta + precio"
        formato2 = "30% Carrusel beneficios"
        angulo = f"{data['pos']} - Ticket ${data['ticket']:,}"
        como_superar = f"Comparativa directa vs {competidor} atacando {data['debil']}"
        idea1, idea2, idea3 = f"Vs {competidor} test", f"Errores de {competidor}", f"Reacción a {competidor}"

    return f"""ANÁLISIS ORIENTATIVO - {competidor.upper()} - {industria}

FICHA ORIENTATIVA (NO VERIFICADA)
- Posicionamiento: {data['pos']}
- Fuerte: {data['fuerte']}
- Débil: {data['debil']}
- Ticket orientativo: ${data['ticket']:,}

1. HIPÓTESIS DE HOOKS (NO VERIFICADAS EN ANUNCIOS ACTUALES)
   {h1}
   {h2}
   {h3}

2. FORMATOS SUGERIDOS (NO OBSERVADOS)
   {formato1}
   {formato2}

3. ÁNGULO SUGERIDO
   {angulo}

4. COMO SUPERARLOS
   {como_superar}

5. 3 IDEAS ÚNICAS PARA ESTA MARCA
   IDEA 1: {idea1}
   IDEA 2: {idea2}
   IDEA 3: {idea3}
"""

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


def fetch_tiktok_free():
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
    st.markdown("<h1 style='text-align:center; margin-top:80px; font-weight:800;'>AGENCIA OS</h1>",unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#71717a;'>Acceso privado</p>",unsafe_allow_html=True)
    _,mid,_=st.columns([1,2,1])
    with mid:
        lic_input=st.text_input("Clave",placeholder="Ingresá tu clave",type="password",label_visibility="collapsed")
        if st.button("Ingresar",type="primary",use_container_width=True):
            licenses=load_licenses()
            ok,info=validate_license(lic_input,licenses)
            if ok:
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
cliente_default=lic_data.get("client","CLIENTE")
meta_download_requested = False
google_download_requested = False
with st.sidebar:
    st.markdown(f"### {cliente_default}")
    cliente=st.text_input("Cliente",value=cliente_default)
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
    st.markdown("**META**")
    meta_token=st.text_input("Token Meta",type="password",key="meta")
    meta_act=st.text_input("Ad Account",key="meta_act")
    st.caption("La conexión actual requiere un token manual; no usa OAuth.")
    if st.button("Bajar META",use_container_width=True):
        meta_download_requested = True
    st.markdown("**GOOGLE**")
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
    st.markdown("**TIKTOK**")
    if st.button("Bajar TIKTOK",use_container_width=True):
        st.session_state.pop("df_tiktok",None)
        st.warning("La integración de TikTok Ads no está configurada; no se descargaron datos.")
    st.divider()
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

if "df_all" in st.session_state:
    df_all=st.session_state["df_all"]
    k1,k2,k3=st.columns(3)
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
    k1.metric("Gasto",gasto_display); k2.metric("ROAS",roas_display); k3.metric("Campañas",len(df_all))
    st.dataframe(df_all,use_container_width=True)

st.divider()
t1,t2=st.tabs(["ESPIA COMPETIDORES","CLONADOR"])

with t1:
    st.caption("Demostrativo: genera hipótesis locales; no consulta ni verifica anuncios actuales.")
    comp=st.text_input("Marca",placeholder="coto, dia, carrefour, levis, zara, fravega...")
    c1,c2=st.columns(2)
    with c1:
        if st.button("ESPIAR AHORA",type="primary",use_container_width=True):
            if not comp: st.warning("Poné marca")
            else: st.session_state["spy_res"]=analisis_real_diferenciado(comp)
    with c2:
        if st.button("COMPARAR 2 MARCAS"):
            if not comp: st.warning("Poné marca primero")
            else:
                otra = "dia" if "coto" in comp.lower() else "coto"
                st.session_state["spy_res"]=analisis_real_diferenciado(comp)+"\n\n--- VS ---\n\n"+analisis_real_diferenciado(otra)
    if "spy_res" in st.session_state:
        st.text(st.session_state["spy_res"])

with t2:
    st.markdown("### Clonador")
    desc=st.text_input("Tu ganadora")
    comp_clone=st.text_input("Competidor")
    if st.button("CLONAR"):
        st.warning("El clonador todavía no genera variaciones; no se realizó una clonación.")
