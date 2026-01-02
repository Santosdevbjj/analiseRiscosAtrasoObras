import os
import logging
import warnings
from io import BytesIO
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# Novos imports para FastAPI e Webhook
import uvicorn
from fastapi import FastAPI, Request, Response
from telegram import Update, Bot
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

warnings.filterwarnings("ignore", category=UserWarning)

# --- Configurações e Recursos ---
PIPELINE_PATH = "models/pipeline_random_forest.pkl"
FEATURES_PATH = "models/features_metadata.joblib"
DB_PATH = "data/processed/df_mestre_consolidado.csv.gz"
REPORTS_PATH = "data/reports"
os.makedirs(REPORTS_PATH, exist_ok=True)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("telegram_bot_ccbjj")

# Carregamento Global
try:
    pipeline = joblib.load(PIPELINE_PATH)
    features_order = joblib.load(FEATURES_PATH)
    df_base = pd.read_csv(DB_PATH, compression='gzip')
    logger.info("✅ Recursos carregados com sucesso.")
except Exception as e:
    logger.error(f"❌ Erro ao carregar recursos: {e}")

# --- Funções de Negócio (Mantidas do seu original) ---
def emoji_risco(dias: float) -> str:
    if dias > 10: return "🔴 (Crítico)"
    if dias > 7: return "🟡 (Alerta)"
    return "🟢 (Normal)"

def formatar_texto_pdf(texto_markdown: str) -> str:
    chars = ["*", "`", "🏗️", "📍", "⛰️", "🌧️", "💰", "📊", "⚠️", "💡"]
    for char in chars:
        texto_markdown = texto_markdown.replace(char, "")
    return texto_markdown

def preparar_dados_predicao(df_obra: pd.DataFrame):
    X = df_obra.copy()
    if "id_obra" in X.columns: X = X.drop(columns=["id_obra"])
    if "risco_etapa" in X.columns: X = X.drop(columns=["risco_etapa"])
    return X[features_order]

def gerar_relatorio_inteligente(id_obra: str, df_obra: pd.DataFrame) -> str:
    X = preparar_dados_predicao(df_obra)
    predicoes = pipeline.predict(X)
    df_res = df_obra.copy()
    df_res["predicao_atraso"] = predicoes
    risco_medio = float(df_res["predicao_atraso"].mean())
    pior_linha = df_res.loc[df_res["predicao_atraso"].idxmax()]

    return (
        f"🏗️ *CCBJJ RISK INTELLIGENCE*\n"
        f"-------------------------------------------\n"
        f"📍 *Obra:* {id_obra} | {str(df_res['cidade'].iloc[0]).title()}\n"
        f"⛰️ *Geologia:* {str(df_res['tipo_solo'].iloc[0]).title()}\n"
        f"🌧️ *Clima:* {float(df_res['nivel_chuva'].iloc[0]):.0f}mm\n"
        f"💰 *Exposure:* R$ {float(df_res['orcamento_estimado'].iloc[0]):,.2f}\n"
        f"-------------------------------------------\n"
        f"📊 *DIAGNÓSTICO DA IA*\n"
        f"• Risco Médio: `{risco_medio:.1f} dias`\n"
        f"• Status: {emoji_risco(risco_medio)}\n\n"
        f"⚠️ *PONTO DE ATENÇÃO*\n"
        f"A etapa de *{pior_linha['etapa'].title()}* é a mais crítica.\n"
        f"-------------------------------------------\n"
        f"💡 *INSIGHT:* Revisar logística de {pior_linha['material']}."
    )

def gerar_grafico_etapas(id_obra: str, df_obra: pd.DataFrame) -> BytesIO:
    X = preparar_dados_predicao(df_obra)
    df_res = df_obra.copy()
    df_res["predicao_atraso"] = pipeline.predict(X)
    etapas_prev = df_res.groupby("etapa")["predicao_atraso"].mean().sort_values()
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ['#2E7D32' if x < 7 else '#C62828' for x in etapas_prev]
    ax.bar([e.title() for e in etapas_prev.index], etapas_prev.values, color=colors)
    ax.set_title(f"Atraso por Etapa - {id_obra}")
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=100)
    buf.seek(0)
    plt.close()
    return buf

def gerar_pdf_relatorio(id_obra: str, df_obra: pd.DataFrame) -> str:
    pdf_path = os.path.join(REPORTS_PATH, f"Relatorio_CCbjj_{id_obra}.pdf")
    texto_puro = formatar_texto_pdf(gerar_relatorio_inteligente(id_obra, df_obra))
    with PdfPages(pdf_path) as pdf:
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis("off")
        ax.text(0.1, 0.95, "CCBJJ ENGENHARIA - RELATÓRIO TÉCNICO", fontsize=14, fontweight='bold', color='#1B5E20')
        ax.text(0.1, 0.85, texto_puro, va="top", family='sans-serif', fontsize=11, linespacing=1.8)
        pdf.savefig(fig)
        plt.close(fig)
    return pdf_path

# --- Handlers do Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 *CCbjj Bot Online!*\nEnvie o ID da obra (ex: `CCbjj-100`)", parse_mode=ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip()
    df_obra = df_base[df_base["id_obra"] == id_obra]
    
    if df_obra.empty:
        await update.message.reply_text(f"❌ Obra `{id_obra}` não encontrada.")
        return

    try:
        await update.message.reply_text(gerar_relatorio_inteligente(id_obra, df_obra), parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_photo(photo=gerar_grafico_etapas(id_obra, df_obra))
        pdf = gerar_pdf_relatorio(id_obra, df_obra)
        with open(pdf, "rb") as f:
            await update.message.reply_document(document=f, filename=f"Risco_{id_obra}.pdf")
    except Exception as e:
        logger.error(f"Erro: {e}")

# --- Configuração FastAPI + Webhook ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") # URL que o Render te der + /webhook

app = FastAPI()
# Inicializa a aplicação do telegram mas não roda o polling
ptb_app = ApplicationBuilder().token(TOKEN).build()
ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

@app.on_event("startup")
async def on_startup():
    # Configura o webhook no Telegram ao iniciar o servidor
    await ptb_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    await ptb_app.initialize()

@app.post("/webhook")
async def webhook_endpoint(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=200)

@app.get("/")
async def index():
    return {"status": "CCbjj Bot is Running"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
