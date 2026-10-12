import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import os

st.set_page_config(page_title="AGENCIA OS - Cloud Auto", layout="wide", page_icon="👻")

# CONFIG GROQ - Lee de secrets o env
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))
# Si no hay secrets, usa placeholder para test local (pon tu nueva key aqui temporalmente)
if not GROQ_API_KEY:
    GROQ_API_KEY = "gsk_TU_NUEVA_KEY_AQUI"

LOGO_DIR = "logos"
os.makedirs(LOGO_DIR, exist_ok=True)
LOGO_AGENCIA_PATH = os.path.join(LOGO_DIR, "logo_agencia.png")
LOGO_CLIENTE_PATH = os.path.join(LOGO_DIR, "logo_cliente.png")

def detectar_columna(df, palabras):
    for col in df.columns:
        cl = col.lower()
        for p in palabras:
            if p in cl:
                return col
    return None

def llamar_groq(cliente, gasto, roas, datos, notas):
    if not GROQ_API_KEY or "TU_NUEVA" in GROQ_API_KEY:
        return "**LOGRO:** ROAS 4.20x en Reels superando meta 2.70x\n**ALERTA:** Prospecting $40k ROAS 0.85x sin ventas\n**PRÓXIMO PASO:** Pausar Prospecting y mover presupuesto a Reels UGC"
    try:
        prompt = f"Sos Director de Performance. Cliente: {cliente} Gasto: ${gasto:.0f} ROAS: {roas:.2f}x Datos: {datos} Notas: {notas}. Generá 3 bullets cortos: LOGRO, ALERTA, PRÓXIMO PASO. Usa números reales. Max 80 palabras."
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 300},
            timeout=30)
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"**LOGRO:** ROAS {roas:.2f}x con ${gasto:.0f}\n**ALERTA:** Revisar campañas con ROAS <1.5\n**PRÓXIMO PASO:** Escalar top performers\n(Error Groq: {e})"

def generar_pdf(cliente, gasto, roas, insight, df, logo_ag, logo_cl):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = []
    logo_row = []
    if logo_ag and os.path.exists(logo_ag):
        try: logo_row.append(RLImage(logo_ag, width=1.2*inch, height=0.6*inch, kind='proportional'))
        except: logo_row.append(Paragraph("AGENCIA OS", styles['Normal']))
    else: logo_row.append(Paragraph("AGENCIA OS", styles['Normal']))
    if logo_cl and os.path.exists(logo_cl):
        try: logo_row.append(RLImage(logo_cl, width=1.2*inch, height=0.6*inch, kind='proportional'))
        except: logo_row.append(Paragraph(cliente, styles['Normal']))
    else: logo_row.append(Paragraph(cliente, styles['Normal']))
    story.append(Table([logo_row], colWidths=[3*inch, 3*inch]))
    story.append(Spacer(1, 0.2*inch))
    title_style = ParagraphStyle('Title2', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor("#111827"))
    story.append(Paragraph(f"Reporte Performance - {cliente}", title_style))
    story.append(Paragraph(f"Fecha: {datetime.now().strftime('%d/%m/%Y')} | Automático Cloud | Groq Llama 3.1", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    data = [["KPI", "Valor"], ["Gasto Total", f"${gasto:,.2f}"], ["ROAS", f"{roas:.2f}x"], ["Campañas", str(len(df))]]
    t = Table(data, colWidths=[200, 200])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.black), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 1, colors.black)]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Insight IA:", styles['Heading2']))
    for line in insight.split("\n"):
        if line.strip():
            story.append(Paragraph(line.strip().replace("**",""), styles['Normal']))
    doc.build(story)
    buffer.seek(0)
    return buffer

with st.sidebar:
    st.title("👻 AGENCIA OS CLOUD")
    st.caption("v2.0 Automático")
    cliente = st.text_input("Cliente", "NOVALUX")
    st.divider()
    st.subheader("🎨 Logos")
    logo_agencia = st.file_uploader("Logo Agencia", type=["png","jpg","jpeg"], key="ag")
    logo_cliente = st.file_uploader(f"Logo {cliente}", type=["png","jpg","jpeg"], key="cl")
    if logo_agencia:
        with open(LOGO_AGENCIA_PATH, "wb") as f: f.write(logo_agencia.getbuffer())
        st.image(logo_agencia, width=120)
    if logo_cliente:
        with open(LOGO_CLIENTE_PATH, "wb") as f: f.write(logo_cliente.getbuffer())
        st.image(logo_cliente, width=120)
    st.divider()
    archivo = st.file_uploader("CSV Meta Ads", type=["csv","xlsx"])
    notas = st.text_area("Notas", "Reels funcionó muy bien. Prospecting gastó sin vender.")

st.title(f"AGENCIA OS AUTOMÁTICO 👻 | {cliente}")
st.info("🚀 Versión Cloud - No necesita tu PC prendida. Groq Llama 3.1 8B")

if archivo:
    try: df = pd.read_csv(archivo, encoding='utf-8-sig') if archivo.name.endswith(".csv") else pd.read_excel(archivo)
    except: df = pd.read_csv(archivo, encoding='latin-1')
else:
    df = pd.DataFrame({"Campaign Name": ["Reels - Venta", "Prospecting", "Retargeting"], "Amount Spent (ARS)": [42500, 40000, 18200], "ROAS": [4.2, 0.85, 3.1]})

spend_col = detectar_columna(df, ["spend","gasto","amount"]) or df.columns[1]
roas_col = detectar_columna(df, ["roas"])
try:
    gasto = pd.to_numeric(df[spend_col], errors='coerce').sum()
    roas = (pd.to_numeric(df[spend_col], errors='coerce') * pd.to_numeric(df[roas_col], errors='coerce')).sum() / gasto if roas_col else 2.7
except: gasto, roas = 175600, 2.7

tab1, tab2, tab3 = st.tabs(["📊 Datos", "🤖 Reporte IA", "📄 PDF"])
with tab1:
    st.metric("Gasto", f"${gasto:,.0f}")
    st.metric("ROAS", f"{roas:.2f}x")
    st.dataframe(df, use_container_width=True)
with tab2:
    if st.button("🚀 Generar Reporte Automático", type="primary", use_container_width=True):
        with st.spinner("Groq pensando..."):
            insight = llamar_groq(cliente, gasto, roas, df.head(10).to_string(), notas)
            st.session_state["insight"] = insight
            st.session_state["gasto"] = gasto
            st.session_state["roas"] = roas
    if "insight" in st.session_state:
        st.success(st.session_state["insight"])
with tab3:
    if "insight" in st.session_state:
        pdf = generar_pdf(cliente, st.session_state["gasto"], st.session_state["roas"], st.session_state["insight"], df, LOGO_AGENCIA_PATH if os.path.exists(LOGO_AGENCIA_PATH) else None, LOGO_CLIENTE_PATH if os.path.exists(LOGO_CLIENTE_PATH) else None)
        st.download_button("📄 Descargar PDF", data=pdf, file_name=f"Reporte_{cliente}.pdf", mime="application/pdf", type="primary", use_container_width=True)
