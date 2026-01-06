import os 
import sys
import logging
import warnings
import joblib
import pandas as pd
import pytz
import io
from io import BytesIO
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine

# Adiciona o diretório scripts ao PATH para evitar erros de importação
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

# Servidor e API
from fastapi import FastAPI, Request, Response
import uvicorn

# Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

# PDF e Gráficos
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
import matplotlib
matplotlib.use("Agg") # Necessário para rodar no Render (sem interface gráfica)
import matplotlib.pyplot as plt

# Importações customizadas
import database
from i18n import TEXTS
from handlers import (
    start_command, help_command, about_command, 
    status_command, language_callback, resolve_language,
    language_manual_command, healthcheck_command
)

# Configuração de Fuso Horário
BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')

logging.basicConfig(level=logging.INFO)
warnings.filterwarnings("ignore", category=UserWarning)

# ======================================================
# CONFIGURAÇÕES E RECURSOS
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_PATH = BASE_DIR / "models/pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models/features_metadata.joblib"
DB_PATH = BASE_DIR / "data/processed/df_mestre_consolidado.csv.gz"

# Caminho absoluto da Logo para o Render
LOGO_PATH = BASE_DIR / "assets" / "logo_ccbjj.png"

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Carregamento de Modelos e Dados
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
engine = create_engine(DATABASE_URL) if DATABASE_URL else None

df_base = pd.read_csv(DB_PATH, compression="gzip")
if "id_obra" in df_base.columns:
    df_base["id_obra"] = df_base["id_obra"].astype(str).str.strip()

# ======================================================
# LÓGICA DE RELATÓRIOS (GRÁFICO E PDF)
# ======================================================

def gerar_grafico_ia(risco_valor):
    """Gera gráfico visual de risco."""
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(8, 4))
    
    cor = 'green' if risco_valor <= 7 else 'orange' if risco_valor <= 10 else 'red'
    
    ax.barh(['Risco Estimado'], [risco_valor], color=cor, height=0.6)
    ax.set_xlim(0, max(15, risco_valor + 2))
    ax.set_xlabel('Dias de Atraso Previstos')
    ax.set_title('Análise Preditiva de Cronograma - CCBJJ', fontsize=14, pad=15)
    
    ax.axvline(10, color='red', linestyle='--', alpha=0.5, label='Limite Crítico')
    ax.legend()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

def gerar_pdf_corporativo(id_obra, risco, status, modo, grafico_buf):
    """Gera o PDF com capa, logo e detalhes técnicos."""
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    width, height = A4
    now_br = datetime.now(BR_TIMEZONE).strftime('%d/%m/%Y %H:%M')

    # --- CAPA ---
    if LOGO_PATH.exists():
        try:
            c.drawImage(str(LOGO_PATH), width/2 - 2*cm, height - 4*cm, width=4*cm, preserveAspectRatio=True)
        except:
            logging.error("Erro ao carregar a logo no PDF.")
    
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, height - 6.5*cm, "CCBJJ ENGENHARIA")
    
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, height - 7.5*cm, "RELATÓRIO DE INTELIGÊNCIA DE RISCO")
    
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width/2, height - 8.5*cm, f"Gerado em (Brasília): {now_br}")

    c.setStrokeColor(colors.grey)
    c.line(2*cm, height - 9.5*cm, width - 2*cm, height - 9.5*cm)

    # --- CONTEÚDO TÉCNICO ---
    text = c.beginText(2*cm, height - 11*cm)
    text.setFont("Helvetica-Bold", 12)
    text.textLine("DETALHAMENTO TÉCNICO DA ANÁLISE:")
    text.setFont("Helvetica", 11)
    text.moveCursor(0, 10)
    text.textLine(f"Identificador da Obra: {id_obra}")
    text.textLine(f"Status do Cronograma: {status}")
    text.textLine(f"Predição de Impacto: {risco:.2f} dias")
    text.textLine(f"Fonte de Dados: {modo}")
    c.drawText(text)

    # --- INSERIR GRÁFICO ---
    grafico_buf.seek(0)
    temp_img = f"temp_{id_obra}.png"
    with open(temp_img, "wb") as f:
        f.write(grafico_buf.read())
    
    c.drawImage(temp_img, 2*cm, height - 20*cm, width=17*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(width/2, 2*cm, "Documento gerado por Inteligência Artificial para fins de suporte à decisão.")
    
    c.showPage()
    c.save()
    
    if os.path.exists(temp_img):
        os.remove(temp_img)
        
    pdf_buf.seek(0)
    return pdf_buf

# ======================================================
# FUNÇÕES DE APOIO E HANDLERS
# ======================================================

def obter_menu_infra():
    keyboard = [[
        InlineKeyboardButton("📂 Modo CSV", callback_data='set_CSV'),
        InlineKeyboardButton("☁️ Modo Supabase", callback_data='set_DB'),
    ]]
    return InlineKeyboardMarkup(keyboard)

async def get_data(id_obra, user_id):
    mode = database.get_storage_mode(user_id)
    id_obra_clean = id_obra.strip()
    if mode == "SUPABASE" and engine:
        try:
            query = f"SELECT * FROM dashboard_obras WHERE id_obra ILIKE '{id_obra_clean}'"
            df = pd.read_sql(query, engine)
            if not df.empty: return df, "SUPABASE"
        except Exception as e:
            logging.error(f"Erro Supabase: {e}")
    
    df = df_base[df_base["id_obra"].str.contains(id_obra_clean, case=False, na=False)]
    return df, "CSV"

def preparar_X(df):
    X = df.copy()
    for col in features_order:
        if col not in X.columns: X[col] = 0
    return X[features_order].fillna(0)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = resolve_language(update)
    await update.message.reply_text(TEXTS[lang]["infra_select"], reply_markup=obter_menu_infra(), parse_mode=ParseMode.MARKDOWN)

async def config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode = "CSV" if query.data == 'set_CSV' else "SUPABASE"
    database.set_storage_mode(query.from_user.id, mode)
    lang = resolve_language(update)
    await query.edit_message_text(text=f"{TEXTS[lang]['mode_changed']}**{mode}**", parse_mode=ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip()
    lang = resolve_language(update)
    user_id = update.effective_user.id
    
    df_obra, modo_usado = await get_data(id_obra, user_id)
    if df_obra.empty:
        await update.message.reply_text(f"{TEXTS[lang]['not_found']} `{modo_usado}`.")
        return

    msg_wait = await update.message.reply_text("🤖 **Processando análise preditiva...**")

    try:
        X = preparar_X(df_obra)
        preds = pipeline.predict(X)
        risco_medio = float(preds.mean())
        status_ia = "🔴 Crítico" if risco_medio > 10 else "🟡 Alerta" if risco_medio > 7 else "🟢 Normal"
        
        # 1. Texto Detalhado
        texto = (
            f"📊 **Análise Preditiva CCBJJ**\n"
            f"📍 Obra: `{id_obra}`\n"
            f"🛠️ Base de Dados: `{modo_usado}`\n\n"
            f"O modelo de IA identificou um risco de **{risco_medio:.1f} dias**.\n"
            f"🚦 Status: {status_ia}\n\n"
            f"_Gerando relatórios visuais..._"
        )
        await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)

        # 2. Gráfico e PDF
        graf_buf = gerar_grafico_ia(risco_medio)
        await update.message.reply_photo(photo=graf_buf, caption=f"Análise de Risco: {id_obra}")
        
        graf_buf.seek(0)
        pdf_buf = gerar_pdf_corporativo(id_obra, risco_medio, status_ia, modo_usado, graf_buf)
        await update.message.reply_document(
            document=InputFile(pdf_buf, filename=f"Relatorio_{id_obra}.pdf"),
            caption="📄 Relatório Técnico Completo"
        )
        await msg_wait.delete()

    except Exception as e:
        logging.error(f"Erro IA: {e}")
        await update.message.reply_text("⚠️ Erro ao processar os arquivos do relatório.")

# ======================================================
# INICIALIZAÇÃO FASTAPI
# ======================================================
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    ptb_app = ApplicationBuilder().token(TOKEN).build()
    ptb_app.add_handler(CommandHandler("start", start_command))
    ptb_app.add_handler(CommandHandler("settings", settings_command))
    ptb_app.add_handler(CommandHandler("help", help_command))
    ptb_app.add_handler(CommandHandler("about", about_command))
    ptb_app.add_handler(CommandHandler("status", status_command))
    ptb_app.add_handler(CallbackQueryHandler(config_callback, pattern='^set_'))
    ptb_app.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
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

@app.get("/healthcheck")
async def health():
    return {"status": "ok", "timezone": "America/Sao_Paulo"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
