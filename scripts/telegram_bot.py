import os
import logging
import warnings
from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Backend não-interativo para ambientes sem display (ex.: Render)
import matplotlib.pyplot as plt
import pandas as pd
import joblib

from fastapi import FastAPI, Request, Response, HTTPException
import uvicorn

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

warnings.filterwarnings("ignore", category=UserWarning)

# ======================================================
# CONFIGURAÇÃO DE LOG
# ======================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ccbjj_telegram_bot")

# ======================================================
# RESOLUÇÃO DE PATH (ROBUSTA PARA CLOUD / RENDER)
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_PATH = BASE_DIR / "models" / "pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models" / "features_metadata.joblib"
DB_PATH = BASE_DIR / "data" / "processed" / "df_mestre_consolidado.csv.gz"
DB_PATH_PARQUET = BASE_DIR / "data" / "processed" / "df_mestre_consolidado.parquet"

# ======================================================
# VARIÁVEIS DE AMBIENTE
# ======================================================
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
# Token secreto para validar requisições no webhook (opcional, mas recomendado)
TELEGRAM_SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")

if not TOKEN or not WEBHOOK_URL:
    # Fail-fast: não iniciar sem configuração crítica
    raise RuntimeError("❌ TELEGRAM_TOKEN ou WEBHOOK_URL não definidos no ambiente.")

# ======================================================
# FUNÇÃO DE VALIDAÇÃO DE ARQUIVOS
# ======================================================
def validar_arquivo(path: Path, nome: str):
    if not path.exists():
        raise FileNotFoundError(f"{nome} não encontrado em: {path}")

# ======================================================
# CARREGAMENTO DOS RECURSOS (FAIL FAST)
# ======================================================
try:
    validar_arquivo(PIPELINE_PATH, "Pipeline")
    validar_arquivo(FEATURES_PATH, "Features")

    pipeline = joblib.load(PIPELINE_PATH)
    features_order = joblib.load(FEATURES_PATH)

    # Preferir Parquet se existir (performance e menor uso de memória)
    if DB_PATH_PARQUET.exists():
        df_base = pd.read_parquet(DB_PATH_PARQUET)
        logger.info("✅ Base de dados carregada (Parquet).")
    else:
        validar_arquivo(DB_PATH, "Base de Dados (CSV gzip)")
        # Carregamento com opções que reduzem overhead
        df_base = pd.read_csv(
            DB_PATH,
            compression="gzip",
            low_memory=False,
            memory_map=True,
        )
        logger.info("✅ Base de dados carregada (CSV gzip).")

    # Checagem mínima de colunas usadas nos handlers
    required_cols = {"id_obra", "cidade", "tipo_solo", "nivel_chuva", "etapa", "material"}
    missing_required = required_cols.difference(df_base.columns)
    if missing_required:
        raise ValueError(f"Colunas obrigatórias ausentes na base: {missing_required}")

    logger.info("✅ Pipeline, features e base de dados carregados com sucesso.")

except Exception as e:
    logger.exception("❌ Erro crítico no carregamento dos recursos.")
    raise RuntimeError("Falha fatal ao iniciar a aplicação.") from e

# ======================================================
# FUNÇÕES DE NEGÓCIO
# ======================================================
def emoji_risco(dias: float) -> str:
    if dias > 10:
        return "🔴 Crítico"
    if dias > 7:
        return "🟡 Alerta"
    return "🟢 Normal"


def preparar_dados_predicao(df_obra: pd.DataFrame) -> pd.DataFrame:
    X = df_obra.copy()
    for col in features_order:
        if col not in X.columns:
            X[col] = 0
    return X[features_order]


def gerar_relatorio_inteligente(id_obra: str, df_obra: pd.DataFrame) -> str:
    try:
        X = preparar_dados_predicao(df_obra)
        preds = pipeline.predict(X)
        risco_medio = float(preds.mean())

        temp_df = df_obra.copy()
        temp_df["pred"] = preds
        pior_linha = temp_df.loc[temp_df["pred"].idxmax()]

        return (
            f"🏗️ *CCBJJ Engenharia & Inteligência de Risco*\n"
            f"----------------------------------\n"
            f"📍 *Obra:* {id_obra}\n"
            f"🏙️ *Cidade:* {str(df_obra['cidade'].iloc[0]).title()}\n"
            f"⛰️ *Solo:* {str(df_obra['tipo_solo'].iloc[0]).title()}\n"
            f"🌧️ *Chuva:* {float(df_obra['nivel_chuva'].iloc[0]):.0f} mm\n"
            f"----------------------------------\n"
            f"📊 *Diagnóstico da IA*\n"
            f"• Risco médio: `{risco_medio:.1f} dias`\n"
            f"• Status: {emoji_risco(risco_medio)}\n\n"
            f"⚠️ *Ponto Crítico*\n"
            f"A etapa mais sensível é *{pior_linha['etapa'].title()}*.\n"
            f"----------------------------------\n"
            f"💡 *Insight:* Revisar logística de *{pior_linha['material']}*."
        )

    except Exception:
        logger.exception(f"Erro ao gerar relatório para {id_obra}")
        return "⚠️ Não foi possível gerar relatório da obra."

# ======================================================
# HANDLERS DO TELEGRAM
# ======================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    await update.message.reply_text(
        f"Olá {user}! 👋\n\n"
        "Sou o *CCBJJ Bot Preditivo*.\n"
        "Envie o *ID da obra* para análise de risco.\n\n"
        "Exemplo:\n`CCbjj-100`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip()
    df_obra = df_base[df_base["id_obra"] == id_obra]

    if df_obra.empty:
        await update.message.reply_text(
            f"❌ Obra `{id_obra}` não encontrada.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    status_msg = await update.message.reply_text(
        "🔍 Processando análise preditiva...",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        # Relatório textual
        await update.message.reply_text(
            gerar_relatorio_inteligente(id_obra, df_obra),
            parse_mode=ParseMode.MARKDOWN,
        )

        # Gráfico
        plt.style.use("ggplot")
        X = preparar_dados_predicao(df_obra)
        preds = pipeline.predict(X)

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(df_obra["etapa"], preds, color="#1B5E20")
        ax.set_title(f"Risco por Etapa — {id_obra}")
        ax.set_ylabel("Dias de atraso")
        ax.set_xlabel("Etapas")

        img_buf = BytesIO()
        plt.tight_layout()
        plt.savefig(img_buf, format="png")
        img_buf.seek(0)
        plt.close(fig)

        await update.message.reply_photo(photo=img_buf)
    except Exception:
        logger.exception(f"Erro no processamento da obra {id_obra}")
        await update.message.reply_text(
            "⚠️ Erro ao processar a análise. Tente novamente.",
            parse_mode=ParseMode.MARKDOWN,
        )
    finally:
        # Garantir que o status seja removido sem quebrar fluxo
        try:
            await status_msg.delete()
        except Exception:
            logger.debug("Não foi possível remover a mensagem de status.")

# ======================================================
# FASTAPI + TELEGRAM WEBHOOK
# ======================================================
app = FastAPI()

# ptb_app será inicializado no startup (evita duplicações em reinícios)
ptb_app = None

@app.on_event("startup")
async def on_startup():
    global ptb_app

    # Construção da aplicação PTB dentro do ciclo de vida do FastAPI
    ptb_app = ApplicationBuilder().token(TOKEN).build()

    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await ptb_app.initialize()

    webhook_dest = f"{WEBHOOK_URL}/webhook"

    # Se token secreto estiver definido, configurar no webhook para validar origem
    if TELEGRAM_SECRET_TOKEN:
        await ptb_app.bot.set_webhook(
            url=webhook_dest,
            secret_token=TELEGRAM_SECRET_TOKEN,
            allowed_updates=["message"]
        )
        logger.info("✅ Webhook configurado com token secreto.")
    else:
        await ptb_app.bot.set_webhook(
            url=webhook_dest,
            allowed_updates=["message"]
        )
        logger.info("⚠️ Webhook configurado sem token secreto (recomendado definir TELEGRAM_SECRET_TOKEN).")

    await ptb_app.start()

    logger.info(f"🚀 Webhook configurado em: {webhook_dest}")


@app.on_event("shutdown")
async def on_shutdown():
    if ptb_app is not None:
        try:
            await ptb_app.stop()
            await ptb_app.shutdown()
        except Exception:
            logger.exception("Erro ao encerrar aplicação Telegram.")


@app.post("/webhook")
async def webhook_endpoint(request: Request):
    # Validação de origem via token secreto, se configurado
    if TELEGRAM_SECRET_TOKEN:
        header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not header_token or header_token != TELEGRAM_SECRET_TOKEN:
            logger.warning("Requisição ao webhook sem token secreto válido.")
            raise HTTPException(status_code=401, detail="Unauthorized")

    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=200)


@app.get("/")
async def healthcheck():
    return {"status": "CCBJJ API Online", "mode": "Webhook"}

# ======================================================
# ENTRYPOINT
# ======================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
