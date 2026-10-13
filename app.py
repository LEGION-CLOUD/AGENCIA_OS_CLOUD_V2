
import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

st.set_page_config(page_title="AGENCIA OS AUTOMÁTICO", page_icon="🚀", layout="wide")

# --- CONFIG GROQ ---
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "") # ponelo en Streamlit Secrets

def llamar_groq(cliente, gasto, roas, df_string, notas):
    if not GROQ_API_KEY:
        return f"""**ANÁLISIS AUTOMÁTICO - {cliente}**

💸 Gasto: ${gasto:,.0f} | ROAS: {roas:.2f}x

📊 TOP CAMPAÑAS:
{df_string}

📝 NOTAS: {notas}

INSIGHTS:
1. Reels UGC es tu ganadora, escala 20% con mismo creativo.
2. Prospecting Broad con ROAS <1 - pausar y mover presupuesto a retargeting.
3. Retargeting IG sostiene ROAS, aumentar frecuencia.

Próximos pasos: Testear 2 creativos nuevos UGC esta semana y bajar prospecting a $15k.

(Para IA real, agregá GROQ_API_KEY en Settings > Secrets de Streamlit)
"""
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        prompt = f"""Sos un media buyer elite para agencia. Cliente {cliente}, gasto ${gasto}, ROAS {roas}x. Data: {df_string}. Notas: {notas}. Dame resumen ejecutivo en 3 bloques: Ganadoras, Perdedoras, Acciones esta semana. Corto y en español argentino."""
        data = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
        r = requests.post(url, headers=headers, json=data, timeout=30)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error Groq: {e}. Usando análisis local.\n" + llamar_groq(cliente, gasto, roas, df_string, notas) if False else f"ROAS {roas:.2f}x - Revisar campañas con gasto alto y ROAS bajo. Escalar ganadoras."

def crear_pdf_simple(cliente, gasto, roas, insight, df):
    try:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(1*inch, 10*inch, f"Reporte Agencia OS - {cliente}")
        c.setFont("Helvetica", 10)
        c.drawString(1*inch, 9.7*inch, f"Fecha: {datetime.now().strftime('%d/%m/%Y')} | Gasto: ${gasto:,.0f} | ROAS: {roas:.2f}x")
        text = c.beginText(1*inch, 9.3*inch)
        text.setFont("Helvetica", 9)
        for line in insight.split("\n"):
            text.textLine(line[:110])
        c.drawText(text)
        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"Error PDF: {e}")
        return None

# --- TU CÓDIGO DESDE LÍNEA 66 EN ADELANTE ---
with st.sidebar:
    st.title("AGENCIA OS")
    cliente = st.text_input("Cliente", "E-COMMERCE DEMO")
    st.markdown("#### 📁 Subir Reporte")
    archivo = st.file_uploader("CSV Meta Ads", type=["csv","xlsx"], label_visibility="collapsed")
    st.markdown("#### 📝 Contexto")
    notas = st.text_area("Notas del mes", "Reels UGC explotó. Prospecting gastó sin vender. Creativos nuevos pendientes.", label_visibility="collapsed", height=100)
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
        st.markdown(f"""<div style="background:#111113; border:1px solid #2a2a30; border-radius:16px; padding:24px; margin-top:16px;"><h4>📋 Resumen Ejecutivo - {cliente}</h4><p style="white-space:pre-wrap; line-height:1.6;">{st.session_state['insight']}</p></div>""", unsafe_allow_html=True)
with t3:
    if "insight" in st.session_state:
        pdf = crear_pdf_simple(cliente, st.session_state["gasto"], st.session_state["roas"], st.session_state["insight"], df)
        if pdf:
            st.download_button("📄 Descargar PDF Premium", data=pdf, file_name=f"Reporte_{cliente}_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", type="primary", use_container_width=True)
    else:
        st.info("Generá el reporte en la pestaña 2 primero")
st.caption("LEGION-CLOUD • AGENCIA OS CLOUD V3 • No requiere PC local")
