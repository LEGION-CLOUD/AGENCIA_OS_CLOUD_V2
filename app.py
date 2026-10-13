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
    return {"LEGION-LULA-2026-LULA": {"client":"Lula","created":datetime.now().isoformat(),"expires":(datetime.now()+timedelta(days=30)).isoformat(),"max_accounts":3,"active":True}}

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

def get_logo():
    for p in ["assets/logo.png","logo.png"]:
        if os.path.exists(p): return p
    return None

def llamar_groq_multi(cliente, gasto_total, roas_total, df_all_string, notas):
    if not GROQ_API_KEY:
        return f"REPORTE MULTI-CANAL AUTO - {cliente}\nGasto: ${gasto_total:,.0f} | ROAS: {roas_total:.2f}x\n\n{df_all_string}\n\nGANADORAS: ROAS>3.5x escalar\nPERDEDORAS: ROAS<1.2x pausar"
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        prompt = f"Sos CMO elite. Cliente {cliente}. Gasto ${gasto_total:.0f}, ROAS {roas_total:.2f}x. Data:\n{df_all_string}\nDame ranking canales, ganadoras, perdedoras, reasignacion, 3 acciones."
        payload = {"model": "llama-3.1-8b-instant", "messages": [{"role":"user","content":prompt}], "temperature":0.6, "max_tokens":1500}
        r = requests.post(url, headers=headers, json=payload, timeout=45)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error Groq: {e}"

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

def fetch_google_mock(token, customer_id, preset):
    if not token: raise Exception("Falta Google token")
    return pd.DataFrame([{"Canal":"GOOGLE","Campaign":"Search - Marca","Spend":15300,"Impressions":32000,"CTR":3.75,"CPC":12.75,"Conversions":28,"Revenue":44370,"ROAS":2.9},{"Canal":"GOOGLE","Campaign":"PMax - Ecom","Spend":31200,"Impressions":165000,"CTR":1.75,"CPC":10.76,"Conversions":19,"Revenue":34320,"ROAS":1.1}])

def fetch_tiktok_mock(token, advertiser_id, preset):
    if not token: raise Exception("Falta TikTok token")
    return pd.DataFrame([{"Canal":"TIKTOK","Campaign":"UGC Viral","Spend":22400,"Impressions":98000,"CTR":3.57,"CPC":6.4,"Conversions":58,"Revenue":85120,"ROAS":3.8}])

def crear_pdf_multi(cliente, gasto, roas, insight, df_all):
    try:
        buffer=io.BytesIO()
        c=canvas.Canvas(buffer,pagesize=letter)
        width,height=letter
        logo=get_logo()
        c.setFillColor(colors.HexColor("#7c3aed"))
        c.rect(0,height-85,width,85,fill=1,stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold",18)
        c.drawString(50,height-38,"AGENCIA OS • MULTI-CANAL")
        c.setFont("Helvetica",9)
        c.drawString(50,height-58,f"Cliente: {cliente} • {datetime.now().strftime('%d/%m/%Y')}")
        if logo:
            try: c.drawImage(logo,width-90,height-75,width=55,height=55,preserveAspectRatio=True,mask='auto')
            except: pass
        y=height-120
        c.setFillColor(colors.HexColor("#111113"))
        c.roundRect(40,y-40,width-80,50,12,fill=1,stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold",10)
        c.drawString(60,y-10,f"Gasto Total: ${gasto:,.0f} | ROAS: {roas:.2f}x")
        y-=70
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold",12)
        c.drawString(50,y,"Reporte IA Multi-Canal")
        c.setFont("Helvetica",8.5)
        y-=18
        lines=[]
        for para in insight.split("\n"):
            while len(para)>108:
                cut=para[:108].rfind(" ")
                if cut==-1: cut=108
                lines.append(para[:cut]); para=para[cut:].lstrip()
            lines.append(para)
        for line in lines:
            if y<80:
                c.showPage(); y=height-50; c.setFont("Helvetica",8.5)
            c.drawString(50,y,line[:115]); y-=11
        c.showPage()
        c.setFillColor(colors.HexColor("#7c3aed"))
        c.rect(0,height-50,width,50,fill=1,stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold",13)
        c.drawString(50,height-30,f"Performance - {cliente}")
        cols_reales=["Canal","Campaign","Spend","ROAS","CTR","CPC","Conversions"]
        cols_reales=[c for c in cols_reales if c in df_all.columns]
        if len(cols_reales)<3: cols_reales=df_all.columns.tolist()[:6]
        df_t=df_all[cols_reales].head(18).astype(str)
        for col in df_t.columns: df_t[col]=df_t[col].apply(lambda x: x[:24])
        table_data=[df_t.columns.tolist()]+df_t.values.tolist()
        col_w=(width-80)/len(cols_reales)
        t=Table(table_data,colWidths=[col_w]*len(cols_reales),repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor("#7c3aed")),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTSIZE',(0,0),(-1,0),8),('FONTSIZE',(0,1),(-1,-1),7),('GRID',(0,0),(-1,-1),0.5,colors.HexColor("#e4e4e7")),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor("#f4f4f5")])]))
        t.wrapOn(c,width,height); t.drawOn(c,40,height-340)
        c.save(); buffer.seek(0); return buffer.getvalue()
    except Exception as e:
        st.error(f"Error PDF: {e}"); return None

if "license_valid" not in st.session_state: st.session_state["license_valid"]=False
query_params = st.query_params
is_admin = query_params.get("admin","")=="1"

if is_admin:
    st.title("🔐 ADMIN - Generador")
    pwd = st.text_input("Contraseña Admin", type="password")
    if pwd == ADMIN_PASSWORD:
        licenses = load_licenses()
        st.success("Admin OK")
        col1,col2,col3 = st.columns(3)
        with col1: cname = st.text_input("Cliente", "Lula")
        with col2: days = st.number_input("Días", value=30)
        with col3: max_acc = st.number_input("Max cuentas", value=3)
        if st.button("🚀 GENERAR", type="primary"):
            new_key = generate_key(cname)
            exp = datetime.now() + timedelta(days=days)
            licenses[new_key] = {"client":cname,"created":datetime.now().isoformat(),"expires":exp.isoformat(),"max_accounts":max_acc,"active":True}
            save_licenses(licenses)
            st.code(new_key)
            st.success(f"Creada para {cname}")
        st.divider()
        if licenses:
            st.dataframe(pd.DataFrame.from_dict(licenses, orient="index"), use_container_width=True)
    else:
        if pwd: st.error("Mal")
    st.stop()

if not st.session_state["license_valid"]:
    st.markdown("<h1 style='text-align:center; margin-top:80px; font-weight:800; letter-spacing:-1px;'>AGENCIA OS</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#71717a; margin-top:-10px;'>Acceso privado</p>", unsafe_allow_html=True)
    colA, colB, colC = st.columns([1,2,1])
    with colB:
        lic_input = st.text_input("Clave de acceso", placeholder="Ingresá tu clave", type="password", label_visibility="collapsed")
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
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

# APP REAL - LIMPIO SIN DATOS DE LICENCIA
lic_data = st.session_state.get("license_data", {})
cliente_default = lic_data.get("client", "CLIENTE")

with st.sidebar:
    cliente = st.text_input("Cliente", value=cliente_default)
    preset = st.selectbox("Rango", ["last_7d","last_14d","last_30d","this_month","last_90d"], index=2)
    st.divider()
    st.markdown("**🔵 META ADS**")
    meta_token = st.text_input("Token", type="password", key="meta", label_visibility="collapsed", placeholder="Token Meta")
    meta_act = st.text_input("Ad Account", placeholder="act_...", key="meta_act")
    if st.button("⬇️ Bajar Meta", use_container_width=True):
        try:
            df_meta=fetch_meta(meta_token, meta_act, preset)
            st.session_state["df_meta"]=df_meta
            st.success(f"{len(df_meta)} campañas")
        except Exception as e: st.error(f"{e}")
    st.markdown("**🔴 GOOGLE ADS**")
    google_token = st.text_input("Google Token", type="password", key="google", label_visibility="collapsed", placeholder="Token Google")
    google_cid = st.text_input("Customer ID", key="gcid", placeholder="123-456-7890")
    if st.button("⬇️ Bajar Google", use_container_width=True):
        try:
            df_google=fetch_google_mock(google_token, google_cid, preset)
            st.session_state["df_google"]=df_google
            st.success(f"{len(df_google)} campañas")
        except Exception as e: st.error(f"{e}")
    st.markdown("**⚫ TIKTOK ADS**")
    tiktok_token = st.text_input("TikTok Token", type="password", key="tiktok", label_visibility="collapsed", placeholder="Token TikTok")
    tiktok_adv = st.text_input("Advertiser ID", key="tidad", placeholder="123456")
    if st.button("⬇️ Bajar TikTok", use_container_width=True):
        try:
            df_tiktok=fetch_tiktok_mock(tiktok_token, tiktok_adv, preset)
            st.session_state["df_tiktok"]=df_tiktok
            st.success(f"{len(df_tiktok)} campañas")
        except Exception as e: st.error(f"{e}")
    st.divider()
    if st.button("🔥 Unificar todo", type="primary", use_container_width=True):
        frames=[]
        for k in ["df_meta","df_google","df_tiktok"]:
            if k in st.session_state: frames.append(st.session_state[k])
        if frames:
            df_all=pd.concat(frames, ignore_index=True)
            gasto=df_all["Spend"].sum()
            roas=(df_all["Spend"]*df_all["ROAS"]).sum()/gasto if gasto>0 else 0
            st.session_state["df_all"]=df_all
            st.session_state["gasto_all"]=gasto
            st.session_state["roas_all"]=roas
            st.rerun()
        else: st.warning("Bajá un canal")

c1,c2=st.columns([3,1])
with c1:
    st.markdown(f"<h1 style='font-weight:800; letter-spacing:-1.5px;'>AGENCIA OS <span style='color:#7c3aed;'>CLOUD</span></h1><p style='color:#71717a; margin-top:-12px;'>{cliente} • Multi-canal • {datetime.now().strftime('%d/%m %H:%M')}</p>", unsafe_allow_html=True)
with c2:
    st.markdown("<div style='text-align:right; padding-top:18px;'><span style='background:#18181b; border:1px solid #27272a; padding:7px 14px; border-radius:20px; font-size:12px; color:#a1a1aa;'>● LIVE</span></div>", unsafe_allow_html=True)

if "df_all" in st.session_state:
    df_all=st.session_state["df_all"]; gasto=st.session_state["gasto_all"]; roas=st.session_state["roas_all"]
    k1,k2,k3=st.columns(3)
    k1.metric("Gasto Total", f"${gasto:,.0f}", f"{len(df_all)} campañas")
    k2.metric("ROAS Global", f"{roas:.2f}x")
    k3.metric("Canales", f"{df_all['Canal'].nunique()}", ", ".join(df_all['Canal'].unique()))
    st.divider()
    t1,t2,t3=st.tabs(["Data","Reporte IA","PDF"])
    with t1:
        st.dataframe(df_all, use_container_width=True, height=450)
        st.bar_chart(df_all.groupby("Canal")["Spend"].sum())
    with t2:
        if st.button("Generar reporte IA", type="primary", use_container_width=True):
            with st.spinner("Generando..."):
                insight=llamar_groq_multi(cliente, gasto, roas, df_all.to_string(index=False), "")
                st.session_state["insight_multi"]=insight
        if "insight_multi" in st.session_state:
            st.markdown(f"<div style='background:#111113; border:1px solid #27272a; border-radius:16px; padding:24px;'><p style='white-space:pre-wrap; color:#e4e4e7;'>{st.session_state['insight_multi']}</p></div>", unsafe_allow_html=True)
    with t3:
        if "insight_multi" in st.session_state:
            pdf=crear_pdf_multi(cliente, gasto, roas, st.session_state["insight_multi"], df_all)
            if pdf: st.download_button("Descargar PDF", data=pdf, file_name=f"Reporte_{cliente}_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", type="primary", use_container_width=True)
        else: st.info("Generá el reporte primero")
else:
    st.markdown("### Conectá un canal para empezar")
    df_demo=pd.DataFrame([{"Canal":"META","Campaign":"Reels UGC","Spend":42500,"ROAS":4.2},{"Canal":"GOOGLE","Campaign":"Search Marca","Spend":15300,"ROAS":2.9},{"Canal":"TIKTOK","Campaign":"UGC Viral","Spend":22400,"ROAS":3.8}])
    st.dataframe(df_demo, use_container_width=True)
