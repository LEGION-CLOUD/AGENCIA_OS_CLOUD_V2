import streamlit as st
import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

st.set_page_config(page_title="AGENCIA OS AUTO", page_icon="🚀", layout="wide")

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "") if "GROQ_API_KEY" in st.secrets else ""
META_TOKEN = st.secrets.get("META_TOKEN", "") if "META_TOKEN" in st.secrets else ""

LOGO_PATHS = ["assets/logo.png", "logo.png"]

def get_logo():
    for p in LOGO_PATHS:
        if os.path.exists(p): return p
    return None

def llamar_groq(cliente, gasto, roas, df_string, notas):
    if not GROQ_API_KEY:
        return f"""📋 REPORTE AUTO - {cliente}

Gasto: ${gasto:,.0f} | ROAS: {roas:.2f}x
Data auto bajada de Meta API:
{df_string}

GANADORAS: Escalar ROAS >3.5x
PERDEDORAS: Pausar ROAS <1.2x
ACCION: Mover presupuesto de perdedoras a ganadoras.

(Conecta GROQ_API_KEY para insight elite real)
"""
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        prompt = f"Sos media buyer elite. Cliente {cliente}, Gasto ${gasto:.0f}, ROAS {roas:.2f}x. Notas: {notas}. Data AUTO de Meta API:\n{df_string}\n\nDame: GANADORAS, PERDEDORAS, 3 ACCIONES. Corto, argentino, con numeros."
        payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0.6, "max_tokens": 1200}
        r = requests.post(url, headers=headers, json=payload, timeout=40)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error Groq: {e}"

def crear_pdf_auto(cliente, gasto, roas, insight, df):
    try:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        logo = get_logo()

        c.setFillColor(colors.HexColor("#7c3aed"))
        c.rect(0, height-85, width, 85, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, height-38, f"AGENCIA OS • AUTO")
        c.setFont("Helvetica", 10)
        c.drawString(50, height-58, f"Cliente: {cliente} • AUTO-CONNECT META • {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        if logo:
            try: c.drawImage(logo, width-90, height-75, width=55, height=55, preserveAspectRatio=True, mask='auto')
            except: pass

        y = height-120
        c.setFillColor(colors.HexColor("#111113"))
        c.roundRect(40, y-40, width-80, 50, 12, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(60, y-10, f"Gasto: ${gasto:,.0f} | ROAS: {roas:.2f}x | Campañas: {len(df)} | AUTO")
        
        y -= 70
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Reporte IA - Data Auto Meta API")
        c.setFont("Helvetica", 8.5)
        y -= 18
        lines = []
        for para in insight.split("\n"):
            while len(para) > 108:
                cut = para[:108].rfind(" ")
                if cut==-1: cut=108
                lines.append(para[:cut])
                para = para[cut:].lstrip()
            lines.append(para)
        for line in lines:
            if y < 80:
                c.showPage()
                y = height-50
                c.setFont("Helvetica", 8.5)
            c.drawString(50, y, line[:115])
            y -= 11

        c.showPage()
        c.setFillColor(colors.HexColor("#7c3aed"))
        c.rect(0, height-50, width, 50, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, height-30, f"Performance AUTO - {cliente}")

        cols = [col for col in ["Campaign","Spend","CTR","CPC","Conversions","ROAS","Status"] if any(col.lower() in dc.lower() or dc.lower() in col.lower() for dc in df.columns)]
        # mapear a nombres reales
        cols_reales = []
        for want in cols:
            for real in df.columns:
                if want.lower() in real.lower():
                    cols_reales.append(real)
                    break
        if len(cols_reales)<3: cols_reales = df.columns.tolist()[:6]

        df_t = df[cols_reales].head(15).astype(str)
        for col in df_t.columns: df_t[col] = df_t[col].apply(lambda x: x[:26])
        table_data = [df_t.columns.tolist()] + df_t.values.tolist()
        col_w = (width-80)/len(cols_reales)
        t = Table(table_data, colWidths=[col_w]*len(cols_reales), repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#7c3aed")),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('FONTSIZE',(0,0),(-1,0),8),('FONTSIZE',(0,1),(-1,-1),7),
            ('GRID',(0,0),(-1,-1),0.5,colors.HexColor("#e4e4e7")),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor("#f4f4f5")]),
        ]))
        t.wrapOn(c,width,height)
        t.drawOn(c,40,height-320)
        c.setFont("Helvetica",7)
        c.setFillColor(colors.grey)
        c.drawString(40,30,f"LEGION CLOUD AUTO • {datetime.now()} • Data directa Meta Graph API • No manual")
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"Error PDF: {e}")
        return None

def fetch_meta_insights(token, ad_account, preset):
    url = f"https://graph.facebook.com/v20.0/{ad_account}/insights"
    params = {
        "fields": "campaign_name,spend,impressions,clicks,ctr,cpc,actions,action_values",
        "date_preset": preset,
        "level": "campaign",
        "limit": 100,
        "access_token": token
    }
    r = requests.get(url, params=params, timeout=30)
    j = r.json()
    if "error" in j:
        raise Exception(j["error"]["message"])
    rows=[]
    for item in j.get("data",[]):
        conv=0
        for act in item.get("actions",[]):
            if "purchase" in act.get("action_type",""): 
                try: conv=int(float(act.get("value",0)))
                except: pass
        revenue=0
        for val in item.get("action_values",[]):
            if "purchase" in val.get("action_type",""):
                try: revenue=float(val.get("value",0))
                except: pass
        spend=float(item.get("spend",0) or 0)
        roas=revenue/spend if spend>0 else 0
        rows.append({
            "Campaign": item.get("campaign_name","-"),
            "Spend": spend,
            "Impressions": int(item.get("impressions",0) or 0),
            "Clicks": int(item.get("clicks",0) or 0),
            "CTR": float(item.get("ctr",0) or 0),
            "CPC": float(item.get("cpc",0) or 0),
            "Conversions": conv,
            "Revenue": revenue,
            "ROAS": round(roas,2),
            "Status": "Activa"
        })
    return pd.DataFrame(rows)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## 🚀 LEGION CLOUD")
    st.markdown("### AGENCIA OS AUTO V4")
    cliente = st.text_input("Cliente", "E-COMMERCE DEMO")
    st.divider()
    st.markdown("#### 🔌 AUTO-CONNECT META")
    st.caption("Como Claude, conecta y baja solo")
    token_input = st.text_input("Meta Access Token", value=META_TOKEN, type="password", help="Pegalo de developers.facebook.com")
    ad_account_input = st.text_input("Ad Account ID", placeholder="act_123456789", help="Formato act_...")
    date_preset = st.selectbox("Rango", ["last_7d","last_14d","last_30d","this_month","last_90d"], index=2)
    
    if st.button("⬇️ BAJAR DATA AUTO DE META", type="primary", use_container_width=True):
        if not token_input or not ad_account_input:
            st.error("Falta token o act_")
        else:
            with st.spinner("Conectando a Meta..."):
                try:
                    df_auto = fetch_meta_insights(token_input, ad_account_input, date_preset)
                    if df_auto.empty:
                        st.warning("Meta no devolvió campañas en ese rango")
                    else:
                        st.session_state["df"] = df_auto
                        st.session_state["gasto"] = df_auto["Spend"].sum()
                        total_roas = (df_auto["Spend"]*df_auto["ROAS"]).sum()/st.session_state["gasto"] if st.session_state["gasto"]>0 else 0
                        st.session_state["roas"] = total_roas
                        st.success(f"✅ {len(df_auto)} campañas bajadas AUTO")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()
    st.markdown("#### 📁 Fallback manual (si no tenés token)")
    archivo = st.file_uploader("CSV / Excel", type=["csv","xlsx"], label_visibility="collapsed")
    st.markdown("#### 📝 Contexto")
    notas = st.text_area("Notas", "Cliente pide escalar sin subir CPA. Reels funciona.", height=80, label_visibility="collapsed")
    st.divider()
    st.caption("V4 AUTO • Sin CSV necesario")

# --- HEADER ---
c1,c2 = st.columns([3,1])
with c1:
    st.markdown(f"<h1 style='font-weight:800; letter-spacing:-1.5px;'>AGENCIA OS <span style='color:#7c3aed;'>AUTO</span></h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#888;'>Cliente: <b>{cliente}</b> • Auto-Connect Meta Graph API • {datetime.now().strftime('%d/%m/%Y %H:%M')} • Sin CSV</p>", unsafe_allow_html=True)
with c2:
    st.markdown("<div style='text-align:right; padding-top:14px;'><span style='background:#10b981; padding:7px 14px; border-radius:20px; font-size:12px; color:white; font-weight:700;'>● AUTO LIVE</span></div>", unsafe_allow_html=True)

# --- CARGA ---
if "df" in st.session_state:
    df = st.session_state["df"]
    gasto = st.session_state["gasto"]
    roas = st.session_state["roas"]
elif archivo:
    try:
        df = pd.read_csv(archivo, encoding='utf-8-sig') if archivo.name.endswith(".csv") else pd.read_excel(archivo)
        spend_col = next((c for c in df.columns if "spend" in c.lower() or "gasto" in c.lower()), df.columns[1])
        gasto = pd.to_numeric(df[spend_col], errors='coerce').fillna(0).sum()
        roas_col = next((c for c in df.columns if "roas" in c.lower()), None)
        if roas_col:
            roas = (pd.to_numeric(df[spend_col], errors='coerce').fillna(0)*pd.to_numeric(df[roas_col], errors='coerce').fillna(0)).sum()/gasto if gasto>0 else 0
        else: roas=2.7
        st.session_state["df"]=df; st.session_state["gasto"]=gasto; st.session_state["roas"]=roas
    except Exception as e:
        st.error(f"Error archivo: {e}"); df=pd.DataFrame(); gasto=0; roas=0
else:
    st.markdown("### 👇 Conectá Meta arriba para modo AUTO")
    st.info("Pegá tu Meta Token + act_ID y dale a BAJAR DATA AUTO. Sin necesidad de CSV, como decía Lula.")
    df = pd.DataFrame({"Campaign":["Demo Auto - Reels UGC","Demo Auto - Broad"],"Spend":[42500,40000],"ROAS":[4.2,0.85],"CTR":[2.27,1.47],"CPC":[10.12,12.9],"Conversions":[89,12]})
    gasto=df["Spend"].sum(); roas=2.5

if not df.empty:
    k1,k2,k3,k4 = st.columns(4)
    k1.metric("💸 Gasto", f"${gasto:,.0f}", f"{len(df)} campañas AUTO")
    k2.metric("📈 ROAS", f"{roas:.2f}x", "Auto" if "df" in st.session_state else "Demo")
    k3.metric("🔌 Fuente", "Meta API" if "df" in st.session_state and "Campaign" in df.columns else "Demo", "Sin CSV")
    k4.metric("🤖 IA", "Groq", "Llama 3.1")

    st.divider()
    t1,t2,t3 = st.tabs(["📊 Data Auto","🤖 Reporte IA","📄 PDF Auto"])
    with t1: st.dataframe(df, use_container_width=True, height=400)
    with t2:
        if st.button("🚀 GENERAR REPORTE AUTO CON GROQ", type="primary", use_container_width=True):
            with st.spinner("IA analizando data auto..."):
                insight = llamar_groq(cliente, gasto, roas, df.head(12).to_string(index=False), notas if 'notas' in locals() else "")
                st.session_state["insight"]=insight
        if "insight" in st.session_state:
            st.markdown(f"<div style='background:#111113; border:1px solid #2a2a30; border-radius:16px; padding:24px;'><h4 style='color:#a78bfa;'>📋 Reporte Auto - {cliente}</h4><p style='white-space:pre-wrap; color:#e4e4e7;'>{st.session_state['insight']}</p></div>", unsafe_allow_html=True)
    with t3:
        if "insight" in st.session_state:
            pdf = crear_pdf_auto(cliente, gasto, roas, st.session_state["insight"], df)
            if pdf: st.download_button("📄 Descargar PDF AUTO con Logo", data=pdf, file_name=f"Reporte_AUTO_{cliente}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf", mime="application/pdf", type="primary", use_container_width=True)
        else: st.info("Generá el reporte primero en pestaña 2")
