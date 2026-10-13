import streamlit as st
import pandas as pd
import requests
import io
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

st.set_page_config(page_title="AGENCIA OS MULTI", page_icon="🚀", layout="wide")

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "") if "GROQ_API_KEY" in st.secrets else ""
META_TOKEN = st.secrets.get("META_TOKEN", "") if "META_TOKEN" in st.secrets else ""
GOOGLE_TOKEN = st.secrets.get("GOOGLE_TOKEN", "") if "GOOGLE_TOKEN" in st.secrets else ""
TIKTOK_TOKEN = st.secrets.get("TIKTOK_TOKEN", "") if "TIKTOK_TOKEN" in st.secrets else ""

def get_logo():
    for p in ["assets/logo.png","logo.png"]:
        if os.path.exists(p): return p
    return None

def llamar_groq_multi(cliente, gasto_total, roas_total, df_all_string, notas):
    if not GROQ_API_KEY:
        return f"REPORTE MULTI-CANAL AUTO - {cliente}\nGasto Total: ${gasto_total:,.0f} | ROAS: {roas_total:.2f}x\n\nData unificada:\n{df_all_string}\n\nGANADORAS: Escalar ROAS >3.5x\nPERDEDORAS: Pausar ROAS <1.2x\nMIX: Mover presupuesto a canal con mejor ROAS\n(Conecta GROQ_API_KEY para insight elite)"
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        prompt = f"""Sos CMO elite multi-canal. Cliente {cliente}. Gasto total ${gasto_total:.0f}, ROAS {roas_total:.2f}x. Notas: {notas}.
Data unificada de 3 canales (Meta, Google, TikTok) bajada AUTO:
{df_all_string}

Dame:
1. RANKING CANALES: cual rinde mejor por ROAS
2. GANADORAS (escalar) con canal
3. PERDEDORAS (pausar) con canal
4. REASIGNACION PRESUPUESTO: de donde sacar y a donde mover
5. 3 ACCIONES ESTA SEMANA multi-canal

Corto, con numeros, argentino."""
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

def fetch_google_mock(token, customer_id, preset): # Placeholder real API necesita google-ads lib
    # Para demo, si pegan token, simulamos estructura real. Reemplazar con google-ads library en prod.
    if not token: raise Exception("Falta Google token")
    # Aca iria la llamada real a Google Ads API
    # Por ahora devolvemos demo para que no frene la app
    demo = [
        {"Canal":"GOOGLE","Campaign":"Search - Marca Exacta","Spend":15300,"Impressions":32000,"CTR":3.75,"CPC":12.75,"Conversions":28,"Revenue":44370,"ROAS":2.9},
        {"Canal":"GOOGLE","Campaign":"PMax - Ecommerce","Spend":31200,"Impressions":165000,"CTR":1.75,"CPC":10.76,"Conversions":19,"Revenue":34320,"ROAS":1.1},
    ]
    return pd.DataFrame(demo)

def fetch_tiktok_mock(token, advertiser_id, preset):
    if not token: raise Exception("Falta TikTok token")
    demo = [
        {"Canal":"TIKTOK","Campaign":"TikTok - UGC Test Viral","Spend":22400,"Impressions":98000,"CTR":3.57,"CPC":6.4,"Conversions":58,"Revenue":85120,"ROAS":3.8},
    ]
    return pd.DataFrame(demo)

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
        c.drawString(50,height-38,"AGENCIA OS • MULTI-CANAL AUTO")
        c.setFont("Helvetica",9)
        c.drawString(50,height-58,f"Cliente: {cliente} • META+GOOGLE+TIKTOK AUTO • {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        if logo:
            try: c.drawImage(logo,width-90,height-75,width=55,height=55,preserveAspectRatio=True,mask='auto')
            except: pass
        y=height-120
        c.setFillColor(colors.HexColor("#111113"))
        c.roundRect(40,y-40,width-80,50,12,fill=1,stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold",10)
        c.drawString(60,y-10,f"Gasto Total Multi: ${gasto:,.0f} | ROAS Global: {roas:.2f}x | Canales: {df_all['Canal'].nunique() if 'Canal' in df_all.columns else 1}")
        y-=70
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold",12)
        c.drawString(50,y,"Reporte IA Multi-Canal - Unificado")
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
        c.drawString(50,height-30,f"Performance Multi - {cliente}")
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
        c.setFont("Helvetica",7); c.setFillColor(colors.grey)
        c.drawString(40,30,f"LEGION CLOUD MULTI • {datetime.now()} • Data directa APIs • Meta+Google+TikTok")
        c.save(); buffer.seek(0); return buffer.getvalue()
    except Exception as e:
        st.error(f"Error PDF: {e}"); return None

# SIDEBAR
with st.sidebar:
    st.markdown("## 🚀 LEGION CLOUD"); st.markdown("### AGENCIA OS MULTI V5")
    cliente=st.text_input("Cliente","E-COMMERCE DEMO")
    st.divider()
    st.markdown("#### 🔌 CONECTORES AUTO")
    preset=st.selectbox("Rango", ["last_7d","last_14d","last_30d","this_month","last_90d"], index=2)

    st.markdown("**🔵 META ADS**")
    meta_token=st.text_input("Meta Token", value=META_TOKEN, type="password", key="meta")
    meta_act=st.text_input("Ad Account ID", placeholder="act_123...", key="meta_act")
    if st.button("⬇️ BAJAR META", use_container_width=True):
        try:
            df_meta=fetch_meta(meta_token, meta_act, preset)
            st.session_state["df_meta"]=df_meta
            st.success(f"Meta: {len(df_meta)} campañas")
        except Exception as e: st.error(f"Meta: {e}")

    st.markdown("**🔴 GOOGLE ADS**")
    google_token=st.text_input("Google Token / Dev", value=GOOGLE_TOKEN, type="password", key="google")
    google_cid=st.text_input("Customer ID", placeholder="123-456-7890", key="gcid")
    if st.button("⬇️ BAJAR GOOGLE", use_container_width=True):
        try:
            df_google=fetch_google_mock(google_token, google_cid, preset)
            st.session_state["df_google"]=df_google
            st.success(f"Google: {len(df_google)} campañas (demo - conectar API real)")
        except Exception as e: st.error(f"Google: {e}")

    st.markdown("**⚫ TIKTOK ADS**")
    tiktok_token=st.text_input("TikTok Token", value=TIKTOK_TOKEN, type="password", key="tiktok")
    tiktok_adv=st.text_input("Advertiser ID", placeholder="123456789", key="tidad")
    if st.button("⬇️ BAJAR TIKTOK", use_container_width=True):
        try:
            df_tiktok=fetch_tiktok_mock(tiktok_token, tiktok_adv, preset)
            st.session_state["df_tiktok"]=df_tiktok
            st.success(f"TikTok: {len(df_tiktok)} campañas")
        except Exception as e: st.error(f"TikTok: {e}")

    if st.button("🔥 UNIFICAR TODO MULTI", type="primary", use_container_width=True):
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
            st.success(f"Unificado: ${gasto:,.0f} - {len(df_all)} campañas")
            st.rerun()
        else: st.warning("Primero bajá al menos 1 canal")

    st.divider()
    st.caption("V5 MULTI AUTO • Sin CSV")

# HEADER
c1,c2=st.columns([3,1])
with c1:
    st.markdown("<h1 style='font-weight:800; letter-spacing:-1.5px;'>AGENCIA OS <span style='color:#7c3aed;'>MULTI AUTO</span></h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#888;'>Cliente: <b>{cliente}</b> • META + GOOGLE + TIKTOK • Unificado AUTO • {datetime.now().strftime('%d/%m %H:%M')}</p>", unsafe_allow_html=True)
with c2:
    st.markdown("<div style='text-align:right; padding-top:14px;'><span style='background:#10b981; padding:7px 14px; border-radius:20px; font-size:12px; color:white; font-weight:700;'>● MULTI LIVE</span></div>", unsafe_allow_html=True)

if "df_all" in st.session_state:
    df_all=st.session_state["df_all"]; gasto=st.session_state["gasto_all"]; roas=st.session_state["roas_all"]
    k1,k2,k3,k4=st.columns(4)
    k1.metric("💸 Gasto Multi", f"${gasto:,.0f}", f"{len(df_all)} campañas")
    k2.metric("📈 ROAS Global", f"{roas:.2f}x")
    k3.metric("🔌 Canales", f"{df_all['Canal'].nunique()} conectados", ", ".join(df_all['Canal'].unique()))
    k4.metric("🤖 IA", "Groq Multi", "Llama 3.1")
    st.divider()
    t1,t2,t3=st.tabs(["📊 Data Unificada","🤖 Reporte IA Multi","📄 PDF Multi"])
    with t1:
        st.dataframe(df_all, use_container_width=True, height=450)
        st.bar_chart(df_all.groupby("Canal")["Spend"].sum())
    with t2:
        if st.button("🚀 GENERAR REPORTE MULTI-CANAL CON GROQ", type="primary", use_container_width=True):
            with st.spinner("IA unificando Meta+Google+TikTok..."):
                insight=llamar_groq_multi(cliente, gasto, roas, df_all.to_string(index=False), "")
                st.session_state["insight_multi"]=insight
        if "insight_multi" in st.session_state:
            st.markdown(f"<div style='background:#111113; border:1px solid #2a2a30; border-radius:16px; padding:24px;'><h4 style='color:#a78bfa;'>📋 Reporte Multi - {cliente}</h4><p style='white-space:pre-wrap; color:#e4e4e7;'>{st.session_state['insight_multi']}</p></div>", unsafe_allow_html=True)
    with t3:
        if "insight_multi" in st.session_state:
            pdf=crear_pdf_multi(cliente, gasto, roas, st.session_state["insight_multi"], df_all)
            if pdf: st.download_button("📄 Descargar PDF MULTI-CANAL", data=pdf, file_name=f"Reporte_MULTI_{cliente}_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", type="primary", use_container_width=True)
        else: st.info("Generá el reporte multi primero")
else:
    st.markdown("### 👇 Conectá al menos 1 canal en la sidebar y dale UNIFICAR")
    st.info("Flujo: 1) Bajar Meta 2) Bajar Google 3) Bajar TikTok 4) UNIFICAR TODO -> Reporte IA Multi")
    # Demo para que Lula vea sin token
    df_demo=pd.DataFrame([
        {"Canal":"META","Campaign":"Reels UGC","Spend":42500,"ROAS":4.2,"CTR":2.27,"CPC":10.12,"Conversions":89},
        {"Canal":"GOOGLE","Campaign":"Search Marca","Spend":15300,"ROAS":2.9,"CTR":3.75,"CPC":12.75,"Conversions":28},
        {"Canal":"TIKTOK","Campaign":"UGC Viral","Spend":22400,"ROAS":3.8,"CTR":3.57,"CPC":6.4,"Conversions":58},
    ])
    st.dataframe(df_demo, use_container_width=True)
