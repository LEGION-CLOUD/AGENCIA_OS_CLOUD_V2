import streamlit as st
import pandas as pd
import requests, os, json, random, string, io
from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

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
def save_licenses(d):
    with open(LICENSE_FILE, "w") as f: json.dump(d, f, indent=2)
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

def llamar_groq_robusto(prompt, temp=0.7):
    if not GROQ_API_KEY or GROQ_API_KEY.strip()=="":
        return None
    url="https://api.groq.com/openai/v1/chat/completions"
    headers={"Authorization":f"Bearer {GROQ_API_KEY}","Content-Type":"application/json"}
    modelos=["llama-3.3-70b-versatile","llama-3.1-70b-versatile","llama-3.1-8b-instant","mixtral-8x7b-32768","gemma2-9b-it"]
    for modelo in modelos:
        try:
            payload={"model":modelo,"messages":[{"role":"user","content":prompt}],"temperature":temp,"max_tokens":2000}
            r=requests.post(url,headers=headers,json=payload,timeout=45)
            if r.status_code==200:
                return r.json()["choices"][0]["message"]["content"]
        except:
            continue
    return None

def fetch_meta(token, ad_account, preset):
    if not token or not ad_account: raise Exception("Falta token o act_")
    url=f"https://graph.facebook.com/v20.0/{ad_account}/insights"
    params={"fields":"campaign_name,spend,impressions,clicks,ctr,cpc,actions,action_values","date_preset":preset,"level":"campaign","limit":100,"access_token":token}
    r=requests.get(url,params=params,timeout=30)
    j=r.json()
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

def fetch_google_mock():
    return pd.DataFrame([{"Canal":"GOOGLE","Campaign":"Search - Marca","Spend":15300,"Impressions":32000,"CTR":3.75,"CPC":12.75,"Conversions":28,"Revenue":44370,"ROAS":2.9},{"Canal":"GOOGLE","Campaign":"PMax - Shopping","Spend":8900,"Impressions":15000,"CTR":2.1,"CPC":8.5,"Conversions":12,"Revenue":18900,"ROAS":2.12}])

def fetch_tiktok_mock():
    return pd.DataFrame([{"Canal":"TIKTOK","Campaign":"UGC Viral","Spend":22400,"Impressions":98000,"CTR":3.57,"CPC":6.4,"Conversions":58,"Revenue":85120,"ROAS":3.8}])

def spy_analysis(competitor, country):
    prompt=f"Sos experto espionaje ads Argentina. Competidor {competitor} pais {country}. Analizá como si vieras 12 ads activos en Ad Library. Dame Top 3 hooks exactos, formato que repiten, angulo venta, como copiarlo mejor, 3 ideas para robarle mercado. Corto accionable."
    res=llamar_groq_robusto(prompt,0.6)
    if res is None:
        return f"""🕵️ ANÁLISIS ESPIA - {competitor.upper()} ({country}) - MODO DEMO PRO

1. TOP 3 HOOKS QUE USAN:
   - "El {competitor} que no falla - 50% OFF hoy"
   - "Probé 5 marcas y solo esta no se transparenta"
   - "Antes $XX ahora $YY - Últimas unidades"

2. FORMATO QUE REPITEN:
   - 70% UGC Reels 9:16 chica probándose (12-18seg)
   - 20% Carrusel beneficios
   - Subtitulos amarillos grandes

3. ANGULO PRINCIPAL:
   - Dolor (se baja/se marca) + solución + prueba social + urgencia precio

4. COMO MEJORARLOS:
   - Primer frame: "NO COMPRES {competitor} sin ver esto"
   - Garantía que ellos no tienen: "Si se baja, x2 devolución"
   - UGC micro-influencer más creíble

5. 3 IDEAS PARA ROBARLE MERCADO:
   - IDEA 1: "{competitor} vs nosotros - test real"
   - IDEA 2: "3 errores al comprar [producto] que {competitor} comete"
   - IDEA 3: Dueto reacción a su ad

[Conectá GROQ_API_KEY en Secrets para IA 100% real]"""
    return res

def clone_analysis(desc):
    prompt=f"Director creativo clona ganadora. Ganadora: {desc}. Dame 5 variaciones con nombre, que cambia exactamente, prompt listo Midjourney/Leonardo, por que puede ganar. Mantener angulo ganador."
    res=llamar_groq_robusto(prompt,0.8)
    if res is None:
        return f"""🧬 CLONADOR - 5 VARIACIONES DE: "{desc[:80]}"

1. HOOK INVERSO: Mismo video primer frame "Dejá de comprar..."
   Prompt: UGC girl trying jeans, surprised, bold text, bedroom, 9:16 - Por que: Pattern interrupt negativo +40% retención

2. FONDO PODEROSO: Misma en calle/espejo gimnasio
   Prompt: Street mirror selfie jeans, urban, natural - Por que: Credibilidad contexto real

3. PRUEBA EXTREMA: Sentadilla / corre con jean
   Prompt: Woman squat test jeans no transparency, movement UGC - Por que: Demuestra beneficio

4. ANTES/DESPUES: Pantalla dividida jean viejo vs este
   Prompt: Split screen before after jeans comparison - Por que: Contraste vende

5. TESTIMONIO: Misma con voz cliente real
   Prompt: UGC testimonial close up emotional captions - Por que: Voz cliente > marca
"""
    return res

# --- ADMIN ---
if "license_valid" not in st.session_state: st.session_state["license_valid"]=False
is_admin="admin" in st.query_params
if is_admin:
    st.title("🔐 ADMIN")
    pwd=st.text_input("Contraseña",type="password")
    if pwd==ADMIN_PASSWORD:
        licenses=load_licenses()
        tab1,tab2=st.tabs(["➕ Crear","✏️ Editar/Borrar"])
        with tab1:
            c1,c2,c3=st.columns(3)
            with c1: cname=st.text_input("Cliente","Nuevo")
            with c2: days=st.number_input("Días",value=90)
            with c3: max_acc=st.number_input("Max",value=5)
            if st.button("🚀 GENERAR",type="primary",use_container_width=True):
                new_key=generate_key(cname)
                exp=datetime.now()+timedelta(days=days)
                licenses[new_key]={"client":cname,"created":datetime.now().isoformat(),"expires":exp.isoformat(),"max_accounts":max_acc,"active":True}
                save_licenses(licenses)
                st.code(new_key)
                st.success("Creada")
        with tab2:
            keys=list(licenses.keys())
            if keys:
                sel=st.selectbox("Licencia",keys,format_func=lambda k: f"{k} - {licenses[k]['client']}")
                lic=licenses[sel]
                new_client=st.text_input("Cliente",value=lic["client"])
                active=st.checkbox("Activa",value=lic.get("active",True))
                a,b,c=st.columns(3)
                with a:
                    if st.button("💾 Guardar"):
                        licenses[sel]["client"]=new_client; licenses[sel]["active"]=active; save_licenses(licenses); st.success("OK")
                with b:
                    if st.button("⏰ +30 días"):
                        licenses[sel]["expires"]=(datetime.now()+timedelta(days=30)).isoformat(); save_licenses(licenses); st.success("Extendida")
                with c:
                    if st.button("🗑️ Borrar",type="primary"):
                        del licenses[sel]; save_licenses(licenses); st.warning("Borrada"); st.rerun()
        st.divider()
        st.dataframe(pd.DataFrame.from_dict(licenses,orient="index"),use_container_width=True)
        st.download_button("⬇️ Descargar licenses_db.json",data=json.dumps(licenses,indent=2),file_name="licenses_db.json",mime="application/json")
    else:
        if pwd: st.error("Mal")
    st.stop()

# --- LOGIN ---
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

# --- APP ---
lic_data=st.session_state.get("license_data",{})
cliente_default=lic_data.get("client","CLIENTE")

with st.sidebar:
    st.markdown(f"### {cliente_default}")
    cliente=st.text_input("Cliente",value=cliente_default)
    preset=st.selectbox("Rango",["last_7d","last_14d","last_30d","this_month","last_90d"],index=2)
    st.divider()
    st.markdown("**🔵 META**")
    meta_token=st.text_input("Token Meta",type="password",key="meta")
    meta_act=st.text_input("Ad Account act_...",key="meta_act")
    if st.button("⬇️ Bajar META",use_container_width=True):
        try:
            df=fetch_meta(meta_token,meta_act,preset)
            st.session_state["df_meta"]=df; st.success(f"{len(df)} campañas META")
        except Exception as e: st.error(f"{e}")
    st.markdown("**🟢 GOOGLE**")
    if st.button("⬇️ Bajar GOOGLE (mock)",use_container_width=True):
        st.session_state["df_google"]=fetch_google_mock(); st.success("Google OK")
    st.markdown("**⚫ TIKTOK**")
    if st.button("⬇️ Bajar TIKTOK (mock)",use_container_width=True):
        st.session_state["df_tiktok"]=fetch_tiktok_mock(); st.success("TikTok OK")
    st.divider()
    if st.button("🔥 UNIFICAR TODO",type="primary",use_container_width=True):
        frames=[]
        for k in ["df_meta","df_google","df_tiktok"]:
            if k in st.session_state: frames.append(st.session_state[k])
        if frames:
            df_all=pd.concat(frames,ignore_index=True)
            gasto=df_all["Spend"].sum()
            roas=(df_all["Spend"]*df_all["ROAS"]).sum()/gasto if gasto>0 else 0
            st.session_state["df_all"]=df_all; st.session_state["gasto_all"]=gasto; st.session_state["roas_all"]=roas
            st.success(f"Unificado: ${gasto:,.0f} - {roas:.2f}x")
            st.rerun()
        else: st.warning("Bajá un canal primero")
    st.divider()
    if not GROQ_API_KEY:
        st.caption("⚠️ Sin GROQ_API_KEY = Modo DEMO PRO")
    else:
        st.caption("✅ IA conectada")

st.markdown(f"<h1 style='font-weight:800;'>AGENCIA OS <span style='color:#7c3aed;'>UNICO</span></h1><p style='color:#71717a; margin-top:-12px;'>{cliente} • Multi-canal + Espía + Clonador</p>",unsafe_allow_html=True)

if "df_all" in st.session_state:
    df_all=st.session_state["df_all"]; gasto=st.session_state["gasto_all"]; roas=st.session_state["roas_all"]
    k1,k2,k3,k4=st.columns(4)
    k1.metric("Gasto Total",f"${gasto:,.0f}"); k2.metric("ROAS Global",f"{roas:.2f}x"); k3.metric("Campañas",len(df_all)); k4.metric("Canales",df_all["Canal"].nunique())
    st.dataframe(df_all,use_container_width=True)
else:
    st.info("👈 Bajá META / GOOGLE / TIKTOK en el sidebar y dale a UNIFICAR TODO")

st.divider()
t1,t2,t3=st.tabs(["🕵️ ESPIA COMPETIDORES (UNICO)","🎨 CLONADOR GANADORAS (UNICO)","🤖 REPORTE IA"])

with t1:
    st.markdown("### 🕵️ Espía automático - Trae ads de tu competencia")
    c1,c2=st.columns([3,1])
    with c1: comp=st.text_input("Nombre competidor/marca",placeholder="Ej: levis",key="spy_comp")
    with c2: country=st.selectbox("País",["AR","US","BR","MX"],index=0)
    if st.button("🔍 ESPIAR AHORA",type="primary",use_container_width=True):
        with st.spinner(f"Espíando {comp}..."):
            res=spy_analysis(comp,country)
            st.session_state["spy_res"]=res
    if "spy_res" in st.session_state:
        st.markdown(f"<div style='background:#18181b; border:1px solid #7c3aed; border-radius:12px; padding:20px;'><p style='white-space:pre-wrap;'>{st.session_state['spy_res']}</p></div>",unsafe_allow_html=True)

with t2:
    st.markdown("### 🎨 Clonador de ganadoras")
    desc=st.text_area("Describí tu creativo ganador",placeholder="Video UGC chica jean hook 'no se baja'...",key="clone_desc")
    if st.button("🧬 CLONAR EN 5 VARIACIONES",type="primary",use_container_width=True):
        with st.spinner("Clonando..."):
            res=clone_analysis(desc)
            st.session_state["clone_res"]=res
    if "clone_res" in st.session_state:
        st.markdown(f"<div style='background:#18181b; border-radius:12px; padding:20px;'><p style='white-space:pre-wrap;'>{st.session_state['clone_res']}</p></div>",unsafe_allow_html=True)

with t3:
    if st.button("Generar reporte IA global",use_container_width=True):
        if "df_all" in st.session_state:
            gasto=st.session_state["gasto_all"]; roas=st.session_state["roas_all"]; df_str=st.session_state["df_all"].to_string()
            prompt=f"Cliente {cliente} gasto {gasto} roas {roas} data {df_str}. Dame ganadoras, perdedoras y 3 acciones."
            res=llamar_groq_robusto(prompt) or f"DEMO: Ganadora ROAS 4.2x escalar +30%, Perdedora 0.8x pausar, Reasignar 12k. Gasto ${gasto:,.0f}"
            st.session_state["report_res"]=res
        else:
            st.warning("Unificá datos primero")
    if "report_res" in st.session_state:
        st.markdown(f"<div style='background:#111113; border-radius:12px; padding:20px;'><p style='white-space:pre-wrap;'>{st.session_state['report_res']}</p></div>",unsafe_allow_html=True)
