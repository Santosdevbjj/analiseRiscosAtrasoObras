"""
scripts/telegram_bot.py — Bot de Inteligência Preditiva MRV 2.0
Versão Final Consolidada: IA + Clima + Geologia + PDF

Recursos:
- Token via variável de ambiente (TELEGRAM_TOKEN)
- Suporte a variáveis ambientais (Chuva e Solo)
- Relatório detalhado com métricas de engenharia
- Gráficos comparativos e exportação em PDF
"""

import os
import logging
from io import BytesIO
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -----------------------------
# Configurações
# -----------------------------
PIPELINE_PATH = "models/pipeline_random_forest.pkl"
DB_PATH = "data/raw/base_consulta_bot.csv"
REPORTS_PATH = "data/reports"
os.makedirs(REPORTS_PATH, exist_ok=True)

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("telegram_bot_mrv")

# -----------------------------
# Carregamento de Recursos
# -----------------------------
try:
    pipeline = joblib.load(PIPELINE_PATH)
    logger.info("✅ Pipeline RandomForest (Multivariado) carregado.")
except Exception as e:
    logger.error(f"❌ Erro ao carregar pipeline: {e}")
    pipeline = None

try:
    # A base agora deve conter: nivel_chuva e tipo_solo
    df_base = pd.read_csv(DB_PATH)
    logger.info("✅ Base detalhada com dados de Chuva/Solo carregada.")
except Exception as e:
    logger.error(f"❌ Erro ao carregar base CSV: {e}")
    df_base = None

# -----------------------------
# Utilitários
# -----------------------------
def emoji_risco(dias: float) -> str:
    if dias > 15: return "🔴"
    if dias > 7: return "🟡"
    return "🟢"

def gerar_relatorio_inteligente(id_obra: str, df_obra: pd.DataFrame) -> str:
    """Relatório preditivo consolidado incluindo Clima e Solo."""
    # Preparar dados para o pipeline (removendo id_obra se existir)
    X = df_obra.drop(columns=["id_obra"], errors="ignore")
    predicoes = pipeline.predict(X)
    
    df_res = df_obra.copy()
    df_res["predicao_atraso"] = predicoes

    risco_medio = float(df_res["predicao_atraso"].mean())
    pior_linha = df_res.loc[df_res["predicao_atraso"].idxmax()]

    # Dados contextuais (pegando da primeira linha da obra)
    cidade = str(df_res["cidade"].iloc[0])
    solo = str(df_res["tipo_solo"].iloc[0])
    chuva = float(df_res["nivel_chuva"].iloc[0])
    orcamento = float(df_res["orcamento_estimado"].iloc[0])
    
    status_geral = emoji_risco(risco_medio)

    relatorio = (
        f"{status_geral} *RELATÓRIO PREDITIVO MRV*\n"
        f"-------------------------------------------\n"
        f"📍 *Obra:* {id_obra} | 🏢 *{cidade}*\n"
        f"⛰️ *Solo:* {solo} | 🌧️ *Chuva:* {chuva:.0f}mm\n"
        f"💰 *Orçamento:* R$ {orcamento:,.2f}\n"
        f"-------------------------------------------\n"
        f"📊 *ANÁLISE DE IA*\n"
        f"• Risco Médio Estimado: `{risco_medio:.1f} dias`\n\n"
        f"⚠️ *PONTO CRÍTICO IDENTIFICADO*\n"
        f"• Etapa: {pior_linha['etapa']}\n"
        f"• Material: {pior_linha['material']}\n"
        f"• Atraso nesta Etapa: `{pior_linha['predicao_atraso']:.1f} dias`\n"
        f"-------------------------------------------\n"
        f"💡 *Sugestão:* O solo {solo} com chuva de {chuva:.0f}mm exige atenção redobrada na drenagem da etapa de {pior_linha['etapa']}."
    )
    return relatorio

def gerar_grafico_etapas(id_obra: str, df_obra: pd.DataFrame) -> BytesIO:
    """Gráfico de barras do risco por etapa."""
    X = df_obra.drop(columns=["id_obra"], errors="ignore")
    df_res = df_obra.copy()
    df_res["predicao_atraso"] = pipeline.predict(X)

    etapas_prev = df_res.groupby("etapa")["predicao_atraso"].mean().sort_values()

    plt.figure(figsize=(6.5, 4.5))
    etapas_prev.plot(kind="bar", color="#2E86C1", edgecolor="black")
    plt.title(f"Risco por Etapa — {id_obra}\n(Refletindo Solo e Chuva)")
    plt.ylabel("Dias de Atraso Previstos")
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return buf

def gerar_pdf_relatorio(id_obra: str, df_obra: pd.DataFrame, df_base_completa: pd.DataFrame) -> str:
    """PDF consolidado para análise offline."""
    pdf_path = os.path.join(REPORTS_PATH, f"relatorio_{id_obra}.pdf")
    # Limpa markdown para o PDF
    texto = gerar_relatorio_inteligente(id_obra, df_obra).replace("*", "").replace("`", "")

    with PdfPages(pdf_path) as pdf:
        # Pág 1: Relatório
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis("off")
        ax.text(0.06, 0.95, texto, va="top", fontsize=11, family='sans-serif', wrap=True)
        pdf.savefig(fig)
        plt.close(fig)

        # Pág 2: Gráfico de Etapas
        buf = gerar_grafico_etapas(id_obra, df_obra)
        img = plt.imread(buf)
        fig2, ax2 = plt.subplots(figsize=(8.5, 6))
        ax2.imshow(img)
        ax2.axis("off")
        pdf.savefig(fig2)
        plt.close(fig2)

    return pdf_path

# -----------------------------
# Handlers do Telegram
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏗️ *MRV Risk Intelligence Bot 2.0*\n\n"
        "Sistema atualizado com variáveis de **Chuva** e **Solo**.\n"
        "Envie o ID da obra (ex: `MRV-100`) para uma análise preditiva completa.",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_usuario = update.message.text.upper().strip()
    
    if df_base is None or pipeline is None:
        await update.message.reply_text("❌ Erro: Pipeline ou Base CSV não carregados.")
        return

    df_obra = df_base[df_base["id_obra"] == id_usuario]
    if df_obra.empty:
        await update.message.reply_text(f"❌ Obra `{id_usuario}` não encontrada.")
        return

    await update.message.reply_text(f"🔍 Analisando cronograma, solo e clima para {id_usuario}...")

    try:
        # 1. Relatório
        relatorio = gerar_relatorio_inteligente(id_usuario, df_obra)
        await update.message.reply_text(relatorio, parse_mode=ParseMode.MARKDOWN)

        # 2. Gráfico
        grafico = gerar_grafico_etapas(id_usuario, df_obra)
        await update.message.reply_photo(photo=grafico, caption="📊 Análise de Risco por Etapa")

        # 3. PDF
        pdf_path = gerar_pdf_relatorio(id_usuario, df_obra, df_base)
        with open(pdf_path, "rb") as f:
            await update.message.reply_document(document=f, filename=os.path.basename(pdf_path))

    except Exception as e:
        logger.error(f"Erro: {e}")
        await update.message.reply_text("⚠️ Erro ao processar os dados de IA.")

# -----------------------------
# Main
# -----------------------------
def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("Defina TELEGRAM_TOKEN")
        return

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("🚀 Bot MRV 2.0 Online!")
    app.run_polling()

if __name__ == "__main__":
    main()
