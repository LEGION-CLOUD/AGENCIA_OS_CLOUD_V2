import streamlit as st
import pandas as pd
import requests, io, os, json, random, string
from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

st.set_page_config(page_title="AGENCIA OS", page_icon="🚀", layout="wide")

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
    if datetime.now() > exp: return False, f"Vencida {exp.strftime('%d/%m/%Y')}"
    if not lic.get("active", True): return False, "Desactivada"
    return True, lic

# ... (resto funciones meta/pdf igual) ...
def llamar_groq_multi(cliente, gasto_total, roas_total, df_all_string, notas):
    if not GROQ_API_KEY: return f"REPORTE - {cliente}\nGasto: ${gasto_total:,.0f} | ROAS: {roas_total:.2f}x"
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        prompt = f"Sos CMO elite. Cliente {cliente}. Gasto ${gasto_total:.0f}, ROAS {roas_total:.2f}x. Data:\n{df_all_string}"
        payload = {"model": "llama-3.1-8b-instant", "messages": [{"role":"user","content":prompt}], "temperature":0.6, "max_tokens":1500}
        r = requests.post(url, headers=headers, json=payload, timeout=45)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e: return f"Error: {e}"

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
        rows.append({"Canal":"META","Campaign":item.get("campaign_name","-"),"Spend":spend,"Impressions":int(item.get("impressions",0) or 0),"CTR":float(item.get("ctr",0) or 0),"CPC":float(item.get("cpc",0) or 0),"Conversions":conv,"Revenue":revenue,"ROAS":round(roas,2)})
    return pd.DataFrame(rows)

def crear_pdf_multi(cliente, gasto, roas, insight, df_all):
    try:
        buffer=io.BytesIO()
        c=canvas.Canvas(buffer,pagesize=letter)
        width,height=letter
        c.setFillColor(colors.HexColor("#7c3aed"))
        c.rect(0,height-85,width,85,fill=1,stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold",18)
        c.drawString(50,height-38,"AGENCIA OS")
        c.save(); buffer.seek(0); return buffer.getvalue()
    except: return None

# --- ADMIN CON EDICION ---
if "license_valid" not in st.session_state: st.session_state["license_valid"]=False
is_admin = "admin" in st.query_params

if is_admin:
    st.title("🔐 ADMIN - Gestión de Licencias")
    pwd = st.text_input("Contraseña Admin", type="password")
    if pwd == ADMIN_PASSWORD:
        licenses = load_licenses()
        st.success("Admin OK")

        tab1, tab2 = st.tabs(["➕ Crear", "✏️ Editar / Borrar"])
        
        with tab1:
            col1,col2,col3 = st.columns(3)
            with col1: cname = st.text_input("Nombre Cliente", "NuevoCliente")
            with col2: days = st.number_input("Días validez", value=90, min_value=1)
            with col3: max_acc = st.number_input("Max cuentas", value=5)
            if st.button("🚀 GENERAR NUEVA LICENCIA", type="primary", use_container_width=True):
                new_key = generate_key(cname)
                exp = datetime.now() + timedelta(days=days)
                licenses[new_key] = {"client":cname,"created":datetime.now().isoformat(),"expires":exp.isoformat(),"max_accounts":max_acc,"active":True}
                save_licenses(licenses)
                st.code(new_key)
                st.success(f"Creada para {cname} hasta {exp.strftime('%d/%m/%Y')}")
                st.balloons()

        with tab2:
            if not licenses:
                st.info("No hay licencias")
            else:
                st.markdown("Seleccioná una licencia para editar")
                lic_keys = list(licenses.keys())
                selected = st.selectbox("Licencia", lic_keys, format_func=lambda k: f"{k} - {licenses[k]['client']} - {'✅' if licenses[k]['active'] else '❌'} - vence {licenses[k]['expires'][:10]}")
                
                if selected:
                    lic = licenses[selected]
                    colA, colB = st.columns(2)
                    with colA:
                        new_client = st.text_input("Cambiar nombre cliente", value=lic["client"])
                        new_days = st.number_input("Extender días desde hoy", value=30, min_value=1)
                        active = st.checkbox("Activa", value=lic.get("active", True))
                    with colB:
                        st.markdown(f"**Actual:** {selected}")
                        st.markdown(f"**Cliente:** {lic['client']}")
                        st.markdown(f"**Creada:** {lic['created'][:10]}")
                        st.markdown(f"**Vence:** {lic['expires'][:10]}")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("💾 Guardar cambios", use_container_width=True):
                            licenses[selected]["client"] = new_client
                            licenses[selected]["active"] = active
                            save_licenses(licenses)
                            st.success("Guardado")
                            st.rerun()
                    with c2:
                        if st.button("⏰ Extender + días", use_container_width=True):
                            new_exp = datetime.now() + timedelta(days=new_days)
                            licenses[selected]["expires"] = new_exp.isoformat()
                            licenses[selected]["client"] = new_client
                            licenses[selected]["active"] = active
                            save_licenses(licenses)
                            st.success(f"Extendida hasta {new_exp.strftime('%d/%m/%Y')}")
                            st.rerun()
                    with c3:
                        if st.button("🗑️ BORRAR licencia", type="primary", use_container_width=True):
                            del licenses[selected]
                            save_licenses(licenses)
                            st.warning(f"Borrada {selected}")
                            st.rerun()

        st.divider()
        st.markdown("### 📋 Todas las licencias")
        if licenses:
            df_lic = pd.DataFrame.from_dict(licenses, orient="index")
            st.dataframe(df_lic, use_container_width=True)
            st.download_button("⬇️ Descargar licenses_db.json (subilo a GitHub para persistir)", data=json.dumps(licenses, indent=2), file_name="licenses_db.json", mime="application/json", use_container_width=True)
            st.caption("IMPORTANTE: Después de editar, descargá el json y súbilo a tu repo en GitHub (Upload > Commit) para que no se borre al reiniciar.")
    else:
        if pwd: st.error("Contraseña incorrecta")
    st.stop()

# --- LOGIN CLIENTE LIMPIO ---
if not st.session_state["license_valid"]:
    st.markdown("<h1 style='text-align:center; margin-top:80px; font-weight:800;'>AGENCIA OS</h1>", unsafe_allow_html=True)
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

# APP NORMAL
lic_data = st.session_state.get("license_data", {})
cliente_default = lic_data.get("client", "CLIENTE")
with st.sidebar:
    cliente = st.text_input("Cliente", value=cliente_default)
    preset = st.selectbox("Rango", ["last_7d","last_14d","last_30d","this_month","last_90d"], index=2)
    meta_token = st.text_input("Token Meta", type="password", key="meta")
    meta_act = st.text_input("Ad Account", placeholder="act_...", key="meta_act")
    if st.button("⬇️ Bajar Meta", use_container_width=True):
        try:
            df_meta=fetch_meta(meta_token, meta_act, preset)
            st.session_state["df_all"]=df_meta
            st.session_state["gasto_all"]=df_meta["Spend"].sum()
            st.session_state["roas_all"]=(df_meta["Spend"]*df_meta["ROAS"]).sum()/st.session_state["gasto_all"] if st.session_state["gasto_all"]>0 else 0
            st.rerun()
        except Exception as e: st.error(f"{e}")

st.markdown(f"<h1>AGENCIA OS <span style='color:#7c3aed;'>CLOUD</span></h1>", unsafe_allow_html=True)
if "df_all" in st.session_state:
    df_all=st.session_state["df_all"]; gasto=st.session_state["gasto_all"]; roas=st.session_state["roas_all"]
    st.metric("Gasto", f"${gasto:,.0f}")
    st.dataframe(df_all, use_container_width=True)
