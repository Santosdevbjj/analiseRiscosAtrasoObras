import os 
import sys
import logging
import warnings
import joblib
import pandas as pd
import pytz
import csv
from io import BytesIO
from pathlib import Path
from datetime import datetime

# Adiciona o diretório scripts ao PATH para evitar erros de importação no servidor
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

# Servidor e API
from fastapi import FastAPI, Request, Response
import uvicorn

# Telegram
from telegram import Update, InputFile
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Relatórios PDF (ReportLab)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Importações customizadas
from i18n import TEXTS
from database import get_language, set_language
from handlers import (
    start_command, help_command, about_command, 
    status_command, language_callback, resolve_language,
    language_manual_command, example_command, healthcheck_command
)

# Configurações de Gráficos
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=UserWarning)

# ======================================================
# CONFIGURAÇÕES DE CAMINHOS E FUSO
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_PATH = BASE_DIR / "models/pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models/features_metadata.joblib"
DB_PATH = BASE_DIR / "data/processed/df_mestre_consolidado.csv.gz"
LOGO_PATH = BASE_DIR / "assets/logo_ccbjj.png"
HISTORY_PATH = BASE_DIR / "data/history/analises_history.csv"

# Garantir diretórios
HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')

# Carregamento e Normalização da Base de Dados
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)

df_base = pd.read_csv(DB_PATH, compression="gzip")
if "id_obra" in df_base.columns:
    df_base["id_obra"] = df_base["id_obra"].astype(str).str.strip().str.upper()

# ======================================================
# FUNÇÕES AUXILIARES E RELATÓRIOS
# ======================================================

def salvar_historico(user_id, id_obra, risco_medio, status, modo, lang):
    """Registra a consulta no histórico CSV."""
    data_hora = datetime.now(BR_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    file_exists = HISTORY_PATH.exists()
    with open(HISTORY_PATH, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "user_id", "id_obra", "risco_medio", "status", "modo", "lang"])
        writer.writerow([data_hora, user_id, id_obra, f"{risco_medio:.2f}", status, modo, lang])

def gerar_pdf_corporativo(id_obra, texto_md, grafico_buf, lang="pt", modo="Diretor"):
    """Gera PDF com Capa, Logo centralizada e Rodapé Interno ajustado."""
    if not REPORTLAB_AVAILABLE: return None
    
    pdf_buf = BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    largura, altura = A4
    data_br = datetime.now(BR_TIMEZONE).strftime("%d/%m/%Y %H:%M")

    # --- PÁGINA 1: CAPA CORPORATIVA ---
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), (largura/2) - 3*cm, altura - 8*cm, width=6*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica-Bold", 22)
    # Título traduzido
    pdf_title = "Risk Intelligence Report" if lang == "en" else "Relatório de Inteligência de Risco"
    c.drawCentredString(largura/2, altura - 11*cm, pdf_title)
    
    c.setFont("Helvetica", 12)
    c.drawCentredString(largura/2, altura - 12*cm, "CCBJJ Engenharia & Inteligência")
    
    # Box de Informações
    c.setStrokeColor(colors.dodgerblue)
    c.roundRect(3*cm, 8*cm, largura - 6*cm, 3*cm, 10, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(3.5*cm, 10.3*cm, f"PROJECT ID: {id_obra}" if lang == "en" else f"ID DA OBRA: {id_obra}")
    c.drawString(3.5*cm, 9.6*cm, f"DATE/TIME (BRT): {data_br}" if lang == "en" else f"DATA/HORA (BRT): {data_br}")
    c.drawString(3.5*cm, 8.9*cm, "DOCUMENT STATUS: OFFICIAL" if lang == "en" else "STATUS DO DOCUMENTO: OFICIAL")
    c.drawString(3.5*cm, 8.2*cm, "TECHNICAL LEAD: Sergio Luiz dos Santos")
    
    c.showPage()

    # --- PÁGINA 2: ANÁLISE DETALHADA ---
    # AJUSTE FINO: Logo no rodapé para não ser tampado pelo gráfico
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), largura - 3.5*cm, 0.8*cm, width=2*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica-Oblique", 8)
    footer_text = f"CCBJJ Risk Intelligence - {id_obra} - Generated on {data_br}" if lang == "en" else f"CCBJJ Risk Intelligence - {id_obra} - Gerado em {data_br}"
    c.drawString(2*cm, 1*cm, footer_text)
    
    # Conteúdo (Remove marcações Markdown para o PDF)
    texto_limpo = texto_md.replace("**", "").replace("`", "").replace("•", "-")
    text_obj = c.beginText(2*cm, altura - 3*cm)
    text_obj.setFont("Helvetica", 10)
    text_obj.setLeading(14)
    for line in texto_limpo.split('\n'):
        text_obj.textLine(line)
    c.drawText(text_obj)

    # AJUSTE FINO: Gráfico posicionado mais abaixo (2.5cm) para não tampar o logo de fundo ou texto
    img_path = f"temp_plot_{id_obra}.png"
    with open(img_path, "wb") as f:
        f.write(grafico_buf.getbuffer())
    c.drawImage(img_path, 2*cm, 2.5*cm, width=17*cm, preserveAspectRatio=True)
    
    c.showPage()
    c.save()
    if os.path.exists(img_path): os.remove(img_path)
    pdf_buf.seek(0)
    return pdf_buf

def preparar_X(df):
    X = df.copy()
    for col in features_order:
        if col not in X.columns: 
            X[col] = 0
    return X[features_order].fillna(0)

def gerar_grafico(df_obra, preds, id_obra, lang="pt"):
    cor_azul_ccbjj = '#0066CC' 
    
    plt.figure(figsize=(8, 4.5))
    plt.bar(df_obra["etapa"], preds, color=cor_azul_ccbjj, edgecolor='#003366', linewidth=1)
    
    title = f"Estimated Delay by Stage - {id_obra}" if lang == "en" else f"Atraso Estimado por Etapa - {id_obra}"
    ylabel = "Days of Delay" if lang == "en" else "Dias de Atraso"
    
    plt.title(title, fontsize=12, fontweight='bold', color='#2c3e50')
    plt.ylabel(ylabel, fontsize=10)
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    plt.xticks(rotation=20, fontsize=9)
    
    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    plt.close()
    return buf

# ======================================================
# HANDLER PRINCIPAL DE ANÁLISE
# ======================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip().upper()
    lang = resolve_language(update) # Obtém o idioma correto (pt ou en)
    user_id = update.effective_user.id
    
    df_obra = df_base[df_base["id_obra"] == id_obra]
    
    if df_obra.empty:
        df_obra = df_base[df_base["id_obra"].str.contains(id_obra, na=False, regex=False)]

    if df_obra.empty:
        not_found_msg = "❌ Project not found in our database." if lang == "en" else "❌ ID da obra não localizado em nossa base."
        await update.message.reply_text(not_found_msg)
        return

    try:
        # Processamento de IA
        X = preparar_X(df_obra)
        preds = pipeline.predict(X)
        risco_medio = preds.mean()
        
        idx_max = preds.argmax()
        etapa_critica = df_obra.iloc[idx_max]["etapa"]
        
        cidade = df_obra.iloc[0].get("cidade", "N/A")
        solo = df_obra.iloc[0].get("solo", "N/A")
        chuva = df_obra.iloc[0].get("precipitacao", "0")
        
        # Tradução de Status e Insights
        if lang == "en":
            status_ia = "🔴 Critical" if risco_medio > 10 else "🟡 Warning" if risco_medio > 7 else "🟢 Normal"
            insight = "Review logistics and supplies."
            if "estrutura" in etapa_critica.lower(): insight = "Review steel and formwork logistics."
            elif "fundação" in etapa_critica.lower(): insight = "Check drainage and soil conditions."
            
            labels = {
                "header": "CCBJJ Engineering & Risk Intelligence",
                "project": "Project", "city": "City", "soil": "Soil", "rain": "Rain",
                "diag": "AI Diagnosis", "risk": "Average Risk", "status": "Status",
                "critical": "Critical Point", "stage": "Stage", "insight": "Insight",
                "dev": "Developed by", "days": "days"
            }
        else:
            status_ia = "🔴 Crítico" if risco_medio > 10 else "🟡 Alerta" if risco_medio > 7 else "🟢 Normal"
            insight = "Revisar logística e suprimentos."
            if "estrutura" in etapa_critica.lower(): insight = "Revisar logística de aço e formas."
            elif "fundação" in etapa_critica.lower(): insight = "Verificar drenagem e condições do solo."
            
            labels = {
                "header": "CCBJJ Engenharia & Inteligência de Risco",
                "project": "Obra", "city": "Cidade", "soil": "Solo", "rain": "Chuva",
                "diag": "Diagnóstico da IA", "risk": "Risco médio", "status": "Status",
                "critical": "Ponto Crítico", "stage": "Etapa", "insight": "Insight",
                "dev": "Desenvolvido por", "days": "dias"
            }

        # Gerar Texto com Tradução Aplicada
        texto_resp = (
            f"🏗️ **{labels['header']}**\n"
            f"----------------------------------\n"
            f"📍 **{labels['project']}:** `{id_obra}`\n"
            f"🏙️ **{labels['city']}:** `{cidade}`\n"
            f"⛰️ **{labels['soil']}:** `{solo}`\n"
            f"🌧️ **{labels['rain']}:** `{chuva} mm`\n"
            f"----------------------------------\n"
            f"📊 **{labels['diag']}**\n"
            f"• {labels['risk']}: `{risco_medio:.1f} {labels['days']}`\n"
            f"• {labels['status']}: {status_ia}\n\n"
            f"⚠️ **{labels['critical']}**\n"
            f"{labels['stage']}: `{etapa_critica}`\n"
            f"----------------------------------\n"
            f"💡 **{labels['insight']}** {insight}\n\n"
            f"_{labels['dev']} Sergio Luiz dos Santos_"
        )
        
        salvar_historico(user_id, id_obra, risco_medio, status_ia, "Automático", lang)
        graf_buf = gerar_grafico(df_obra, preds, id_obra, lang=lang)
        
        await update.message.reply_text(texto_resp, parse_mode=ParseMode.MARKDOWN)
        
        graf_buf.seek(0)
        caption_trend = "📈 Trend Analysis" if lang == "en" else "📈 Análise de Tendência de Atrasos"
        await update.message.reply_photo(photo=graf_buf, caption=caption_trend)
        
        if REPORTLAB_AVAILABLE:
            graf_buf.seek(0)
            pdf_file = gerar_pdf_corporativo(id_obra, texto_resp, graf_buf, lang=lang)
            pdf_caption = "📄 Full Executive Report" if lang == "en" else "📄 Relatório Executivo Completo"
            await update.message.reply_document(
                document=InputFile(pdf_file, filename=f"Report_{id_obra}.pdf"),
                caption=pdf_caption
            )
            
    except Exception as e:
        logging.error(f"Error in processing: {e}")
        error_msg = "⚠️ Technical error processing project data." if lang == "en" else "⚠️ Erro técnico ao processar os dados da obra."
        await update.message.reply_text(error_msg)

# ======================================================
# APLICAÇÃO FASTAPI + BOT
# ======================================================
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    ptb_app = ApplicationBuilder().token(TOKEN).build()
    
    ptb_app.add_handler(CommandHandler("start", start_command))
    ptb_app.add_handler(CommandHandler("help", help_command))
    ptb_app.add_handler(CommandHandler("about", about_command))
    ptb_app.add_handler(CommandHandler("status", status_command))
    ptb_app.add_handler(CommandHandler("language", language_manual_command))
    ptb_app.add_handler(CommandHandler("example", example_command))
    ptb_app.add_handler(CommandHandler("healthcheck", healthcheck_command))
    ptb_app.add_handler(CallbackQueryHandler(language_callback))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await ptb_app.initialize()
    await ptb_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await ptb_app.start()

@app.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=200)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
