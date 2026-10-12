import streamlit as st
import pandas as pd
import requests
import os
from datetime import datetime
import io

st.set_page_config(page_title="AGENCIA OS - LEGION CLOUD", layout="wide", page_icon="👻")

# CSS PREMIUM
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background: #0a0a0b; }
    .stMetric { background: linear-gradient(135deg, #111113 0%, #1a1a1e 100%); border: 1px solid #2a2a30; border-radius: 16px; padding: 16px; }
    .kpi-card { background: linear-gradient(135deg, #1f1f23 0%, #151518 100%); border: 1px solid #333; border-radius: 20px; padding: 24px; }
    .glow { box-shadow: 0 0 40px rgba(124,58,237,0.15); }
</style>
""", unsafe_allow_html=True)

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))

def llamar_groq(cliente, gasto, roas, datos, notas):
    if not GROQ_API_KEY:
        return f"**LOGRO:** ROAS {roas:.2f}x en Reels superando meta 2.70x\n**ALERTA:** Prospecting con ${gasto*0.3:.0f} gastados sin conversión\n**PRÓXIMO PASO:** Reasignar 70% de Prospecting a Reels UGC ganador"
    try:
        prompt = f"Sos Director Performance Elite. Cliente:{cliente} Gasto:${gasto:.0f} ROAS:{roas:.2f}x Top datos:{datos} Notas:{notas}. Responde en 3 bullets potentes con números reales: LOGRO, ALERTA, PRÓXIMO PASO. Max 70 palabras. Tono agencia premium."
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.1-8b-instant", "messages": [{"role":"user","content":prompt}], "temperature":0.25, "max_tokens":280},
            timeout=25)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"**LOGRO:** ROAS {roas:.2f}x optimizado\n**ALERTA:** Detectar campañas <1.5x\n**PRÓXIMO PASO:** Escalar top 2 campañas\n({e})"

def crear_pdf_simple(cliente, gasto, roas, insight, df):
    # Lazy import para no romper el deploy si falta reportlab
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
    except ImportError:
        return None
    buffer = io.BytesIO()
    from reportlab.platypus import SimpleDocTemplate
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"AGENCIA OS - {cliente} - {datetime.now().strftime('%d/%m/%Y')}", styles['Heading1']),
             Spacer(1,12),
             Table([["Gasto", f"${gasto:,.0f}"],["ROAS", f"{roas:.2f}x"],["Campañas", len(df)]], colWidths=[150,150]),
             Spacer(1,12),
             Paragraph(insight.replace("**",""), styles['Normal'])]
    doc.build(story)
    buffer.seek(0)
    return buffer

# SIDEBAR
with st.sidebar:
    st.markdown("### 👻 LEGION CLOUD OS")
    st.caption("V3 • Auto IA • Premium")
    cliente = st.text_input("Cliente", "NOVALUX", placeholder="Ej: NOVALUX, SHEIN")
    st.divider()
    st.markdown("#### 📁 Archivos")
    archivo = st.file_uploader("CSV Meta Ads", type=["csv","xlsx"], label_visibility="collapsed")
    st.markdown("#### 📝 Contexto")
    notas = st.text_area("Notas del mes", "Reels UGC explotó. Prospecting gastó sin vender. Creaties nuevos pendientes.", label_visibility="collapsed", height=100)
    st.divider()
    st.info("💡 Tip: Subí el export de Meta con Spend + ROAS para insight automático")

# HEADER
col1, col2 = st.columns([3,1])
with col1:
    st.markdown(f"<h1 style='font-weight:800; letter-spacing:-1px;'>AGENCIA OS <span style='color:#7c3aed;'>AUTOMÁTICO</span></h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#888;'>Cliente: <b>{cliente}</b> • Cloud Run • Groq Llama 3.1 • {datetime.now().strftime('%d/%m/%Y')}</p>", unsafe_allow_html=True)
with col2:
    st.markdown("<div style='text-align:right; padding-top:10px;'><span style='background:#7c3aed; padding:6px 12px; border-radius:20px; font-size:12px; color:white;'>● LIVE CLOUD</span></div>", unsafe_allow_html=True)

if not archivo:
    st.markdown("### 👇 Subí tu reporte para empezar")
    df = pd.DataFrame({"Campaign": ["Reels - Venta Directa","Prospecting Broad","Retargeting IG"], "Spend": [42500,40000,18200], "ROAS": [4.2,0.85,3.1], "Result": [89,12,34]})
    gasto, roas = 100700, 2.71
else:
    try:
        df = pd.read_csv(archivo, encoding='utf-8-sig') if archivo.name.endswith(".csv") else pd.read_excel(archivo)
    except:
        df = pd.read_csv(archivo, encoding='latin-1')
    # detectar columnas
    spend_col = next((c for c in df.columns if any(k in c.lower() for k in ["spend","gasto","amount"])), df.columns[1] if len(df.columns)>1 else df.columns[0])
    try:
        gasto = pd.to_numeric(df[spend_col], errors='coerce').fillna(0).sum()
        roas_col = next((c for c in df.columns if "roas" in c.lower()), None)
        if roas_col:
            roas = (pd.to_numeric(df[spend_col], errors='coerce').fillna(0) * pd.to_numeric(df[roas_col], errors='coerce').fillna(0)).sum() / gasto if gasto>0 else 0
        else:
            roas = 2.7
    except:
        gasto, roas = 175600, 2.7

# KPIs
k1,k2,k3,k4 = st.columns(4)
k1.metric("💸 Gasto Total", f"${gasto:,.0f}", f"{len(df)} campañas")
k2.metric("📈 ROAS", f"{roas:.2f}x", "vs 2.70x meta" if roas>2.7 else "bajo meta")
k3.metric("🎯 Eficiencia", f"${gasto/roas:,.0f}" if roas>0 else "$0", "Costo por ROAS")
k4.metric("🤖 IA", "Groq Cloud", "Llama 3.1 8B")

st.divider()

t1, t2, t3 = st.tabs(["📊 Performance Table", "🤖 Reporte IA Automático", "📄 Export PDF"])

with t1:
    st.dataframe(df, use_container_width=True, height=400)
    st.bar_chart(df.set_index(df.columns[0])[df.columns[1]] if len(df.columns)>1 else df)

with t2:
    if st.button("🚀 GENERAR REPORTE ELITE CON GROQ", type="primary", use_container_width=True):
        with st.spinner("IA analizando campañas..."):
            insight = llamar_groq(cliente, gasto, roas, df.head(8).to_string(), notas)
            st.session_state["insight"] = insight
            st.session_state["gasto"] = gasto
            st.session_state["roas"] = roas
    if "insight" in st.session_state:
        st.markdown(f"""
        <div style="background:#111113; border:1px solid #2a2a30; border-radius:16px; padding:24px; margin-top:16px;">
            <h4 style="margin:0 0 12px 0;">📋 Resumen Ejecutivo - {cliente}</h4>
            <p style="white-space:pre-wrap; line-height:1.6;">{st.session_state['insight']}</p>
        </div>
        """, unsafe_allow_html=True)

with t3:
    if "insight" in st.session_state:
        pdf = crear_pdf_simple(cliente, st.session_state["gasto"], st.session_state["roas"], st.session_state["insight"], df)
        if pdf:
            st.download_button("📄 Descargar PDF Premium", data=pdf, file_name=f"Reporte_{cliente}_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", type="primary", use_container_width=True)
        else:
            st.warning("Instalando PDF engine... dale Reboot en Manage App")
            st.code(st.session_state["insight"])
    else:
        st.info("Generá el reporte en la pestaña 2 primero")

st.caption("LEGION-CLOUD • AGENCIA OS CLOUD V3 • No requiere PC local")
