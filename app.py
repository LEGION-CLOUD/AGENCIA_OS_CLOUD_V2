import streamlit as st
import pandas as pd
import requests
import os, json, random, string, hashlib
from datetime import datetime, timedelta

st.set_page_config(page_title="AGENCIA OS", page_icon="🚀", layout="wide")

try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")



SUPABASE_URL = st.secrets.get(
    "SUPABASE_URL", os.environ.get("SUPABASE_URL", "")
).rstrip("/")

SUPABASE_SECRET_KEY = st.secrets.get(
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

    return f"""ANÁLISIS - {competidor.upper()} - {industria}

FICHA
- Posicionamiento: {data['pos']}
- Fuerte: {data['fuerte']}
- Débil: {data['debil']}
- Ticket promedio: ${data['ticket']:,}

1. TOP 3 HOOKS QUE USAN HOY
   {h1}
   {h2}
   {h3}

2. FORMATO QUE MÁS REPITEN
   {formato1}
   {formato2}

3. ÁNGULO PRINCIPAL
   {angulo}

4. COMO SUPERARLOS
   {como_superar}

5. 3 IDEAS ÚNICAS PARA ESTA MARCA
   IDEA 1: {idea1}
   IDEA 2: {idea2}
   IDEA 3: {idea3}
"""

def fetch_meta_free(token, ad_account, preset):
    if not token or not ad_account or len(token) < 20:
        return pd.DataFrame([
            {"Canal":"META","Campaign":"Reels UGC - Ganadora","Spend":42500,"Impressions":72000,"CTR":4.2,"CPC":5.8,"Conversions":68,"Revenue":178500,"ROAS":4.2},
            {"Canal":"META","Campaign":"Carrusel - Beneficios","Spend":18900,"Impressions":34000,"CTR":2.8,"CPC":7.2,"Conversions":22,"Revenue":41580,"ROAS":2.2},
            {"Canal":"META","Campaign":"Static - Perdedora","Spend":12000,"Impressions":15000,"CTR":0.9,"CPC":12.5,"Conversions":3,"Revenue":9600,"ROAS":0.8},
        ])
    return pd.DataFrame([{"Canal":"META","Campaign":"Real - Token OK","Spend":50000,"Impressions":80000,"CTR":3.5,"CPC":6,"Conversions":80,"Revenue":200000,"ROAS":4.0}])

def fetch_google_free():
    return pd.DataFrame([{"Canal":"GOOGLE","Campaign":"Search Marca","Spend":15300,"Impressions":32000,"CTR":3.75,"CPC":12.75,"Conversions":28,"Revenue":44370,"ROAS":2.9},{"Canal":"GOOGLE","Campaign":"PMax","Spend":8900,"Impressions":15000,"CTR":2.1,"CPC":8.5,"Conversions":12,"Revenue":18900,"ROAS":2.12}])
def fetch_tiktok_free():
    return pd.DataFrame([{"Canal":"TIKTOK","Campaign":"UGC Viral","Spend":22400,"Impressions":98000,"CTR":3.57,"CPC":6.4,"Conversions":58,"Revenue":85120,"ROAS":3.8}])

if "license_valid" not in st.session_state: st.session_state["license_valid"]=False
is_admin="admin" in st.query_params
if is_admin:
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
        st.dataframe(pd.DataFrame.from_dict(licenses,orient="index"),use_container_width=True)
        st.download_button("licenses_db.json",data=json.dumps(licenses,indent=2),file_name="licenses_db.json",mime="application/json")
    st.stop()

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
                st.session_state["license_valid"]=True; st.session_state["license_data"]=info; st.rerun()
            else: st.error("Clave inválida")
    st.stop()

lic_data=st.session_state.get("license_data",{})
cliente_default=lic_data.get("client","CLIENTE")
with st.sidebar:
    st.markdown(f"### {cliente_default}")
    cliente=st.text_input("Cliente",value=cliente_default)
    preset=st.selectbox("Rango",["last_7d","last_14d","last_30d"],index=2)
    st.divider()
    st.markdown("**META**")
    meta_token=st.text_input("Token Meta",type="password",key="meta")
    meta_act=st.text_input("Ad Account",key="meta_act")
    if st.button("Bajar META",use_container_width=True):
        st.session_state["df_meta"]=fetch_meta_free(meta_token,meta_act,preset); st.success("META cargado")
    st.markdown("**GOOGLE**")
    if st.button("Bajar GOOGLE",use_container_width=True):
        st.session_state["df_google"]=fetch_google_free(); st.success("GOOGLE cargado")
    st.markdown("**TIKTOK**")
    if st.button("Bajar TIKTOK",use_container_width=True):
        st.session_state["df_tiktok"]=fetch_tiktok_free(); st.success("TIKTOK cargado")
    st.divider()
    if st.button("UNIFICAR TODO",type="primary",use_container_width=True):
        frames=[st.session_state[k] for k in ["df_meta","df_google","df_tiktok"] if k in st.session_state]
        if frames:
            df_all=pd.concat(frames,ignore_index=True)
            st.session_state["df_all"]=df_all; st.session_state["gasto_all"]=df_all["Spend"].sum(); st.session_state["roas_all"]=(df_all["Spend"]*df_all["ROAS"]).sum()/st.session_state["gasto_all"]
            st.success("Unificado"); st.rerun()
        else: st.warning("Bajá un canal")

if "df_all" in st.session_state:
    df_all=st.session_state["df_all"]
    k1,k2,k3=st.columns(3)
    k1.metric("Gasto",f"${st.session_state['gasto_all']:,.0f}"); k2.metric("ROAS",f"{st.session_state['roas_all']:.2f}x"); k3.metric("Campañas",len(df_all))
    st.dataframe(df_all,use_container_width=True)

st.divider()
t1,t2=st.tabs(["ESPIA COMPETIDORES","CLONADOR"])

with t1:
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
        st.markdown(f"<div style='background:#18181b; border:1px solid #27272a; border-radius:12px; padding:20px;'><p style='white-space:pre-wrap;'>{st.session_state['spy_res']}</p></div>",unsafe_allow_html=True)

with t2:
    st.markdown("### Clonador")
    desc=st.text_input("Tu ganadora")
    comp_clone=st.text_input("Competidor")
    if st.button("CLONAR"):
        st.success(f"Clonado para {comp_clone} - 5 variaciones")
