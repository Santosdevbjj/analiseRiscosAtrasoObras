"""
scripts/telegram_bot.py — Bot de Inteligência Preditiva MRV
Versão Final Consolidada: Data Science + Business Intelligence + Visualizações + PDF

Recursos:
- Token via variável de ambiente (TELEGRAM_TOKEN)
- Pipeline completo (pré-processamento + modelo RandomForest)
- Relatório consolidado por obra (risco médio previsto, pior etapa, fornecedor/material mais crítico)
- Gráfico por etapas da obra (risco previsto médio)
- Gráfico comparativo entre cidades (risco previsto médio)
- Exportação de relatório + gráficos em PDF consolidado para análise offline
- Logging e mensagens de erro amigáveis
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
    logger.info("✅ Pipeline RandomForest carregado.")
except Exception as e:
    logger.error(f"❌ Erro ao carregar pipeline: {e}")
    pipeline = None

try:
    df_base = pd.read_csv(DB_PATH)
    logger.info("✅ Base detalhada carregada.")
except Exception as e:
    logger.error(f"❌ Erro ao carregar base CSV: {e}")
    df_base = None

# -----------------------------
# Utilitários
# -----------------------------
def emoji_risco(dias: float) -> str:
    if dias > 15:
        return "🔴"
    if dias > 5:
        return "🟡"
    return "🟢"

def gerar_relatorio_inteligente(id_obra: str, df_obra: pd.DataFrame) -> str:
    """Relatório preditivo consolidado por obra."""
    predicoes = pipeline.predict(df_obra.drop(columns=["id_obra"], errors="ignore"))
    df_obra = df_obra.copy()
    df_obra["predicao_atraso"] = predicoes

    risco_medio_previsto = float(df_obra["predicao_atraso"].mean())
    pior_linha = df_obra.loc[df_obra["predicao_atraso"].idxmax()]

    cidade = str(df_obra["cidade"].iloc[0])
    orcamento = float(df_obra["orcamento_estimado"].iloc[0])
    fornecedor_critico = str(df_obra.loc[df_obra["taxa_insucesso_fornecedor"].idxmax(), "material"])
    taxa_critica = float(df_obra["taxa_insucesso_fornecedor"].max())

    status_geral = emoji_risco(risco_medio_previsto)

    relatorio = (
        f"{status_geral} *RELATÓRIO PREDITIVO MRV*\n"
        f"-------------------------------------------\n"
        f"📍 *Obra:* {id_obra}\n"
        f"🏢 *Cidade:* {cidade}\n"
        f"💰 *Orçamento:* R$ {orcamento:,.2f}\n"
        f"-------------------------------------------\n"
        f"📊 *MÉTRICAS DE IA*\n"
        f"• Risco Médio Estimado: `{risco_medio_previsto:.1f} dias`\n"
        f"• Fornecedor mais crítico: {fornecedor_critico} (taxa insucesso {taxa_critica:.2%})\n\n"
        f"⚠️ *PIOR CENÁRIO*\n"
        f"• Etapa: {pior_linha['etapa']}\n"
        f"• Material: {pior_linha['material']}\n"
        f"• Atraso Previsto: `{pior_linha['predicao_atraso']:.1f} dias`\n"
        f"• Taxa Fornecedor: {pior_linha['taxa_insucesso_fornecedor']:.2%}\n"
        f"-------------------------------------------\n"
        f"💡 *Sugestão:* Avalie redundância de fornecedores na etapa de {pior_linha['etapa']}."
    )
    return relatorio

def gerar_grafico_etapas(id_obra: str, df_obra: pd.DataFrame) -> BytesIO:
    """Gráfico de risco previsto médio por etapa da obra."""
    predicoes = pipeline.predict(df_obra.drop(columns=["id_obra"], errors="ignore"))
    df_obra = df_obra.copy()
    df_obra["predicao_atraso"] = predicoes

    etapas_prev = df_obra.groupby("etapa")["predicao_atraso"].mean().sort_values()

    plt.figure(figsize=(6.5, 4.5))
    etapas_prev.plot(kind="bar", color="#5DADE2", edgecolor="black")
    plt.title(f"Risco previsto médio por etapa — {id_obra}")
    plt.ylabel("Dias de atraso (previsto)")
    plt.xlabel("Etapa")
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return buf

def gerar_grafico_cidades(df_detalhada: pd.DataFrame) -> BytesIO:
    """Gráfico comparativo de risco previsto médio por cidade."""
    pred_all = pipeline.predict(df_detalhada.drop(columns=["id_obra"], errors="ignore"))
    df_all = df_detalhada.copy()
    df_all["predicao_atraso"] = pred_all

    cidades_prev = df_all.groupby("cidade")["predicao_atraso"].mean().sort_values()

    plt.figure(figsize=(7.5, 5))
    cidades_prev.plot(kind="bar", color="#F5B041", edgecolor="black")
    plt.title("Comparativo — Risco previsto médio por cidade")
    plt.ylabel("Dias de atraso (previsto)")
    plt.xlabel("Cidade")
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return buf

def gerar_pdf_relatorio(id_obra: str, df_obra: pd.DataFrame, df_detalhada: pd.DataFrame) -> str:
    """Gera PDF consolidado com relatório e gráficos."""
    pdf_path = os.path.join(REPORTS_PATH, f"relatorio_{id_obra}.pdf")
    relatorio_texto = gerar_relatorio_inteligente(id_obra, df_obra).replace("*", "").replace("`", "")

    with PdfPages(pdf_path) as pdf:
        # Página 1 — texto
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis("off")
        ax.text(0.06, 0.95, relatorio_texto, va="top", fontsize=12, wrap=True)
        pdf.savefig(fig)
        plt.close(fig)

        # Página 2 — gráfico por etapas
        buf_etapas = gerar_grafico_etapas(id_obra, df_obra)
        img = plt.imread(buf_etapas)
        fig2, ax2 = plt.subplots(figsize=(8.5, 6))
        ax2.imshow(img)
        ax2.axis("off")
        pdf.savefig(fig2)
        plt.close(fig2)

        # Página 3 — gráfico comparativo cidades
        buf_cidades = gerar_grafico_cidades(df_detalhada)
        img2 = plt.imread(buf_cidades)
        fig3, ax3 = plt.subplots(figsize=(8.5, 6))
        ax3.imshow(img2)
        ax3.axis("off")
        pdf.savefig(fig3)
        plt.close(fig3)

    return pdf_path

# -----------------------------
# Handlers do Telegram
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏗️ *Sistema de Risco MRV Ativo*\n\n"
        "Envie o ID da obra (ex: `MRV-100`) para receber:\n"
        "• Relatório preditivo consolidado\n"
        "• Gráfico por etapas\n"
        "• Comparativo por cidades\n"
        "• PDF consolidado para análise offline",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_usuario = update.message.text.upper().strip()
    logger.info(f"Consulta: {id_usuario}")

    if df_base is None or pipeline is None:
        await update.message.reply_text("❌ Sistema offline. Verifique os arquivos .pkl e .csv em data/raw.")
