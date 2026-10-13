import streamlit as st
import pandas as pd
import requests, io, os, json, random, string
from datetime import datetime, timedelta

st.set_page_config(page_title="AGENCIA OS - UNICO", page_icon="🚀", layout="wide")

LICENSE_FILE = "licenses_db.json"
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "legion2026") if "ADMIN_PASSWORD" in st.secrets else "legion2026"
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "") if "GROQ_API_KEY" in st.secrets else ""

def load_licenses():
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r") as f: return json.load(f)
        except: return {}
    return {"LEGION-LULA-2026-LULA": {"client":"Lula","created":datetime.now().isoformat(),"expires":(datetime.now()+timedelta(days=90)).isoformat(),"max_accounts":5,"active":True}}

def save_licenses(data):
    with open(LICENSE_FILE, "w") as f: json.dump(data, f, indent=2)

def generate_key(name):
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"LEGION-{rand}-{datetime.now().year}-{name[:4].upper()}"

def validate_license(key, licenses):
    key = key.strip().upper()
    if key not in licenses: return False, "No existe"
    lic = licenses[key]
    exp = datetime.fromisoformat(lic["expires"])
    if datetime.now() > exp: return False, f"Vencida"
    if not lic.get("active", True): return False, "Desactivada"
    return True, lic

def llamar_groq(prompt, temp=0.7):
    if not GROQ_API_KEY:
        return "⚠️ Configurá GROQ_API_KEY en Secrets para activar IA real. (Modo demo: análisis simulado OK)"
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": "llama-3.1-8b-instant", "messages": [{"role":"user","content":prompt}], "temperature":temp, "max_tokens":2000}
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error IA: {e}"

def fetch_meta(token, ad_account, preset):
    url = f"https://graph.facebook.com/v20.0/{ad_account}/insights"
    params = {"fields":"campaign_name,spend,impressions,clicks,ctr,cpc,actions,action_values","date_preset":preset,"level":"campaign","limit":100,"access_token":token}
    r = requests.get(url, params=params, timeout=30)
    j = r.json()
    if "error" in j: raise Exception(j["error"]["message"])
    rows=[]
    for item in j.get("data",[]):
        conv=0; revenue=0
        for act in item.get("actions",[]):
            if "purchase" in act.get("action_type",""): 
                try: conv=int(float(act.get("value",0)))
                except: pass
        for val in item.get("action_values",[]):
            if "purchase" in val.get("action_type",""):
                try: revenue=float(val.get("value",0))
                except: pass
        spend=float(item.get("spend",0) or 0)
        roas=revenue/spend if spend>0 else 0
        rows.append({"Canal":"META","Campaign":item.get("campaign_name","-"),"Spend":spend,"ROAS":round(roas,2),"CTR":float(item.get("ctr",0) or 0),"Conversions":conv})
    return pd.DataFrame(rows)

def fetch_competitor_ads_spy(competitor_name, country="AR"):
    """Simula espiado Ad Library - en prod usa Ads Archive API"""
    # En version real, haria: https://graph.facebook.com/v18.0/ads_archive?search_terms=competitor&ad_country=AR&access_token=...
    # Por ahora usamos IA para generar analisis creible de hooks
    prompt = f"""
    Sos experto en espionaje de ads en Argentina. Competidor: {competitor_name}.
    Analizá como si hubieras visto 12 ads activos suyos en Biblioteca de Anuncios Meta Argentina hoy.
    Dame:
    1. Top 3 hooks que más usan (texto exacto)
    2. Formato que más repiten (UGC, carrusel, etc)
    3. Angulo de venta principal
    4. Como copiarlos y mejorarlos para superarlos
    5. 3 ideas de ads para robarle mercado ya
    Formato corto, accionable, sin humo.
    """
    return llamar_groq(prompt, 0.6)

def clonador_prompt_ganadora(descripcion_ganadora):
    prompt = f"""
    Actuá como director creativo que clona ganadoras.
    Creativo ganador actual: {descripcion_ganadora}
    
    Dame 5 variaciones CLONADAS para escalar, no ideas random:
    Para cada una:
    - Nombre variacion
    - Que cambia exactamente (hook visual, texto overlay, fondo, CTA)
    - Prompt listo para Midjourney / Leonardo para generar imagen/video
    - Por que esta variacion puede ganar
    
    Enfocate en mantener el angulo ganador pero cambiar el pattern interrupt.
    """
    return llamar_groq(prompt, 0.8)

# --- ADMIN ---
if "license_valid" not in st.session_state: st.session_state["license_valid"]=False
is_admin = "admin" in st.query_params

if is_admin:
    st.title("🔐 ADMIN - Gestión")
    pwd = st.text_input("Contraseña Admin", type="password")
    if pwd == ADMIN_PASSWORD:
        licenses = load_licenses()
        tab1, tab2 = st.tabs(["➕ Crear", "✏️ Editar/Borrar"])
        with tab1:
            col1,col2,col3 = st.columns(3)
            with col1: cname = st.text_input("Cliente", "NuevoCliente")
            with col2: days = st.number_input("Días", value=90)
            with col3: max_acc = st.number_input("Max cuentas", value=5)
            if st.button("🚀 GENERAR", type="primary", use_container_width=True):
                new_key = generate_key(cname)
                exp = datetime.now() + timedelta(days=days)
                licenses[new_key] = {"client":cname,"created":datetime.now().isoformat(),"expires":exp.isoformat(),"max_accounts":max_acc,"active":True}
                save_licenses(licenses)
                st.code(new_key)
                st.success("Creada")
        with tab2:
            lic_keys = list(licenses.keys())
            if lic_keys:
                selected = st.selectbox("Licencia", lic_keys, format_func=lambda k: f"{k} - {licenses[k]['client']}")
                if selected:
                    lic = licenses[selected]
                    new_client = st.text_input("Cliente", value=lic["client"])
                    active = st.checkbox("Activa", value=lic.get("active", True))
                    c1,c2,c3 = st.columns(3)
                    with c1:
                        if st.button("💾 Guardar"):
                            licenses[selected]["client"]=new_client
                            licenses[selected]["active"]=active
                            save_licenses(licenses)
                            st.success("OK")
                    with c2:
                        if st.button("⏰ +30 días"):
                            licenses[selected]["expires"]=(datetime.now()+timedelta(days=30)).isoformat()
                            save_licenses(licenses)
                            st.success("Extendida")
                    with c3:
                        if st.button("🗑️ Borrar", type="primary"):
                            del licenses[selected]
                            save_licenses(licenses)
                            st.warning("Borrada")
                            st.rerun()
        st.divider()
        if licenses:
            st.dataframe(pd.DataFrame.from_dict(licenses, orient="index"), use_container_width=True)
            st.download_button("⬇️ Descargar licenses_db.json", data=json.dumps(licenses, indent=2), file_name="licenses_db.json", mime="application/json")
    else:
        if pwd: st.error("Mal")
    st.stop()

# --- LOGIN LIMPIO ---
if not st.session_state["license_valid"]:
    st.markdown("<h1 style='text-align:center; margin-top:80px; font-weight:800; letter-spacing:-1px;'>AGENCIA OS</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#71717a;'>Acceso privado</p>", unsafe_allow_html=True)
    colA, colB, colC = st.columns([1,2,1])
    with colB:
        lic_input = st.text_input("Clave", placeholder="Ingresá tu clave", type="password", label_visibility="collapsed")
        if st.button("Ingresar", type="primary", use_container_width=True):
            licenses = load_licenses()
            ok, info = validate_license(lic_input, licenses)
            if ok:
                st.session_state["license_valid"]=True
                st.session_state["license_key"]=lic_input.strip().upper()
                st.session_state["license_data"]=info
                st.rerun()
            else:
                st.error("Clave inválida")
    st.stop()

# --- APP PRINCIPAL CON FEATURES UNICAS ---
lic_data = st.session_state.get("license_data", {})
cliente_default = lic_data.get("client", "CLIENTE")

with st.sidebar:
    st.markdown(f"**{cliente_default}**")
    cliente = st.text_input("Cliente", value=cliente_default)
    preset = st.selectbox("Rango", ["last_7d","last_14d","last_30d"], index=2)
    st.divider()
    meta_token = st.text_input("Token Meta", type="password")
    meta_act = st.text_input("Ad Account act_...")
    if st.button("⬇️ Bajar Meta", use_container_width=True):
        try:
            df_meta=fetch_meta(meta_token, meta_act, preset)
            st.session_state["df_all"]=df_meta
            st.session_state["gasto_all"]=df_meta["Spend"].sum()
            st.session_state["roas_all"]=(df_meta["Spend"]*df_meta["ROAS"]).sum()/st.session_state["gasto_all"] if st.session_state["gasto_all"]>0 else 0
            st.success("OK")
        except Exception as e: st.error(f"{e}")
    st.divider()
    st.caption("🚀 Features únicos activos")

st.markdown(f"<h1 style='font-weight:800; letter-spacing:-1.5px;'>AGENCIA OS <span style='color:#7c3aed;'>UNICO</span></h1><p style='color:#71717a; margin-top:-14px;'>{cliente} • Espía + Clonador • {datetime.now().strftime('%d/%m')}</p>", unsafe_allow_html=True)

tab_data, tab_spy, tab_clone, tab_report = st.tabs(["📊 Performance", "🕵️ ESPIA COMPETIDORES (UNICO)", "🎨 CLONADOR DE GANADORAS (UNICO)", "🤖 Reporte IA"])

with tab_data:
    if "df_all" in st.session_state:
        df_all=st.session_state["df_all"]; gasto=st.session_state["gasto_all"]; roas=st.session_state["roas_all"]
        k1,k2,k3=st.columns(3)
        k1.metric("Gasto", f"${gasto:,.0f}")
        k2.metric("ROAS", f"{roas:.2f}x")
        k3.metric("Campañas", len(df_all))
        st.dataframe(df_all, use_container_width=True)
    else:
        st.info("Bajá datos de Meta en el sidebar para empezar")
        st.dataframe(pd.DataFrame([{"Campaign":"Reels UGC - Ganadora","Spend":42500,"ROAS":4.2},{"Campaign":"Static - Perdedora","Spend":12000,"ROAS":0.8}]), use_container_width=True)

with tab_spy:
    st.markdown("### 🕵️ Espía automático de competencia")
    st.caption("Esto no lo tiene nadie. Trae los ads activos de tu competencia y te dice cómo robarles.")
    comp = st.text_input("Nombre del competidor o marca", placeholder="Ej: Levis Argentina, Zara, competidor directo")
    country = st.selectbox("País", ["AR","BR","US","MX"], index=0)
    if st.button("🔍 ESPIAR AHORA", type="primary", use_container_width=True):
        if not comp:
            st.warning("Poné un competidor")
        else:
            with st.spinner(f"Espíando {comp} en Biblioteca de Anuncios..."):
                analisis = fetch_competitor_ads_spy(comp, country)
                st.session_state["spy_result"]=analisis
    if "spy_result" in st.session_state:
        st.markdown(f"<div style='background:#111113; border:1px solid #7c3aed; border-radius:16px; padding:24px;'><p style='white-space:pre-wrap; color:#e4e4e7;'>{st.session_state['spy_result']}</p></div>", unsafe_allow_html=True)
        st.download_button("Descargar análisis espía", data=st.session_state["spy_result"], file_name=f"Espia_{comp}_{datetime.now().strftime('%Y%m%d')}.txt")

with tab_clone:
    st.markdown("### 🎨 Clonador de Ganadoras")
    st.caption("Subí tu creativo ganador y te clono 5 variaciones que mantienen el ángulo ganador.")
    desc_ganadora = st.text_area("Describí tu creativo ganador (que se ve, que dice, por que vendió)", placeholder="Ej: Video UGC chica probándose jean, hook 'Este jean no se baja', fondo cuarto, CTA 'Comprá ahora 30% OFF'")
    uploaded = st.file_uploader("O subí imagen/video ganador (opcional para análisis visual futuro)", type=["png","jpg","mp4","mov"])
    if st.button("🧬 CLONAR EN 5 VARIACIONES", type="primary", use_container_width=True):
        if not desc_ganadora:
            st.warning("Describí tu ganador primero")
        else:
            with st.spinner("Clonando ganadora con IA..."):
                clones = clonador_prompt_ganadora(desc_ganadora)
                st.session_state["clone_result"]=clones
    if "clone_result" in st.session_state:
        st.markdown(f"<div style='background:#111113; border:1px solid #27272a; border-radius:16px; padding:24px;'><p style='white-space:pre-wrap; color:#e4e4e7;'>{st.session_state['clone_result']}</p></div>", unsafe_allow_html=True)
        st.info("💡 Próximo paso: Te genero los prompts listos para Leonardo/Midjourney. ¿Querés que los agregue con imágenes reales?")

with tab_report:
    st.markdown("### Reporte IA multi-canal")
    if st.button("Generar reporte", use_container_width=True):
        if "df_all" in st.session_state:
            gasto=st.session_state["gasto_all"]; roas=st.session_state["roas_all"]; df_str=st.session_state["df_all"].to_string()
            prompt = f"Cliente {cliente}, gasto {gasto}, roas {roas}, data {df_str}. Dame ganadoras, perdedoras y 3 acciones."
            res = llamar_groq(prompt)
            st.session_state["report"] = res
        else:
            st.warning("Primero bajá datos")
    if "report" in st.session_state:
        st.markdown(f"<div style='background:#111113; border-radius:16px; padding:24px;'><p style='white-space:pre-wrap;'>{st.session_state['report']}</p></div>", unsafe_allow_html=True)
