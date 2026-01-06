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

# Adiciona o diretório scripts ao PATH
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
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Importações customizadas
import database
from i18n import TEXTS
from handlers import (
    start_command, help_command, about_command, 
    status_command, language_callback, resolve_language,
    language_manual_command, example_command, healthcheck_command
)

logging.basicConfig(level=logging.INFO)
warnings.filterwarnings("ignore", category=UserWarning)

# ======================================================
# CONFIGURAÇÕES E RECURSOS
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_PATH = BASE_DIR / "models/pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models/features_metadata.joblib"
DB_PATH = BASE_DIR / "data/processed/df_mestre_consolidado.csv.gz"
LOGO_PATH = BASE_DIR / "assets/logo_ccbjj.png"  # Certifique-se que este arquivo existe

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

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
    """Gera gráfico de barra horizontal indicando o nível de risco."""
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(8, 4))
    
    # Define a cor baseada no risco
    cor = 'green' if risco_valor <= 7 else 'orange' if risco_valor <= 10 else 'red'
    
    ax.barh(['Risco Estimado'], [risco_valor], color=cor, height=0.6)
    ax.set_xlim(0, max(15, risco_valor + 2))
    ax.set_xlabel('Dias de Atraso Previstos')
    ax.set_title('Análise Preditiva de Cronograma - CCBJJ', fontsize=14, pad=15)
    
    # Adiciona linha de threshold crítico
    ax.axvline(10, color='red', linestyle='--', alpha=0.5, label='Limite Crítico')
    ax.legend()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

def gerar_pdf_corporativo(id_obra, risco, status, modo, grafico_buf):
    """Gera um PDF detalhado com capa, logo e gráfico."""
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    width, height = A4

    # --- CAPA ---
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), width/2 - 2*cm, height - 5*cm, width=4*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width/2, height - 8*cm, "RELATÓRIO DE INTELIGÊNCIA DE RISCO")
    
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height - 9*cm, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    # --- CONTEÚDO TÉCNICO ---
    c.setStrokeColor(colors.black)
    c.line(2*cm, height - 11*cm, width - 2*cm, height - 11*cm)
    
    text = c.beginText(2*cm, height - 12*cm)
    text.setFont("Helvetica-Bold", 14)
    text.textLine("Detalhamento da Análise:")
    text.setFont("Helvetica", 12)
    text.moveCursor(0, 15)
    text.textLine(f"Identificador da Obra: {id_obra}")
    text.textLine(f"Fonte de Dados Utilizada: {modo}")
    text.textLine(f"Status Resultante: {status}")
    text.textLine(f"Impacto Estimado no Cronograma: {risco:.2f} dias")
    c.drawText(text)

    # --- INSERIR GRÁFICO NO PDF ---
    grafico_buf.seek(0)
    with open("temp_chart.png", "wb") as f:
        f.write(grafico_buf.read())
    c.drawImage("temp_chart.png", 2*cm, height - 22*cm, width=17*cm, preserveAspectRatio=True)
    
    # Nota de rodapé
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(width/2, 2*cm, "Este relatório foi gerado automaticamente pela IA da CCBJJ Engenharia.")
    
    c.showPage()
    c.save()
    pdf_buf.seek(0)
    return pdf_buf

# ======================================================
# FUNÇÕES DE APOIO AO BOT
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
            return pd.read_sql(query, engine), "SUPABASE"
        except:
            return df_base[df_base["id_obra"].str.contains(id_obra_clean, case=False, na=False)], "CSV (Fallback)"
    return df_base[df_base["id_obra"].str.contains(id_obra_clean, case=False, na=False)], "CSV"

def preparar_X(df):
    X = df.copy()
    for col in features_order:
        if col not in X.columns: X[col] = 0
    return X[features_order].fillna(0)

# ======================================================
# HANDLERS
# ======================================================

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
        await update.message.reply_text(f"{TEXTS[lang]['not_found']}{modo_usado}.")
        return

    msg_wait = await update.message.reply_text("🤖 **Processando análise preditiva...**")

    try:
        X = preparar_X(df_obra)
        preds = pipeline.predict(X)
        risco_medio = float(preds.mean())
        status_ia = "🔴 Crítico" if risco_medio > 10 else "🟡 Alerta" if risco_medio > 7 else "🟢 Normal"
        
        # 1. TEXTO EXPLICATIVO
        texto = (
            f"📊 **Análise Preditiva CCBJJ**\n"
            f"Obra: `{id_obra}` | Base: `{modo_usado}`\n\n"
            f"O modelo Random Forest identificou um risco estimado de **{risco_medio:.1f} dias** de impacto no cronograma.\n"
            f"Status: {status_ia}\n\n"
            f"_Aguarde o gráfico e o relatório técnico abaixo..._"
        )
        await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)

        # 2. GRÁFICO
        grafico_buf = gerar_grafico_ia(risco_medio)
        await update.message.reply_photo(
            photo=grafico_buf, 
            caption=f"📈 Gráfico de Dispersão de Risco: {id_obra}\nLegenda: O gráfico indica o desvio projetado em relação à linha de base zero."
        )

        # 3. PDF COMPLETO
        grafico_buf.seek(0) # Reset para reuso
        pdf_buf = gerar_pdf_corporativo(id_obra, risco_medio, status_ia, modo_usado, grafico_buf)
        await update.message.reply_document(
            document=InputFile(pdf_buf, filename=f"Relatorio_Risco_{id_obra}.pdf"),
            caption="📄 **Relatório Técnico Detalhado (PDF)**"
        )
        
        await msg_wait.delete()

    except Exception as e:
        logging.error(f"Erro: {e}")
        await update.message.reply_text("⚠️ Erro ao gerar os relatórios técnicos.")

# ======================================================
# INICIALIZAÇÃO
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
    ptb_app.add_handler(CommandHandler("language", language_manual_command))
    ptb_app.add_handler(CommandHandler("healthcheck", healthcheck_command))
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
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
