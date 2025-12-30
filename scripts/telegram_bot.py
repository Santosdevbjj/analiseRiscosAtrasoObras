"""
telegram_bot.py — Bot de risco de atraso de obras (MRV)
Melhorias:
- Token via variável de ambiente (TELEGRAM_TOKEN)
- Função única de predição (sem duplicidade)
- Opção de relatório com todas as etapas da obra ou apenas a última
- One-Hot Encoding robusto com alinhamento de colunas de treino
- Mensagens enriquecidas em Markdown
"""

import os
import logging
import pandas as pd
import joblib
from typing import List

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
MODEL_PATH = "models/modelo_random_forest.pkl"
DB_PATH = "data/raw/base_consulta_bot.csv"

# Se você salvou o encoder do treino (recomendado), informe o caminho aqui.
# Caso contrário, o código usa alinhamento por colunas de treino manualmente.
ENCODER_PATH = "models/onehot_encoder.pkl"  # opcional; pode não existir

# Mostra relatório de TODAS as etapas (True) ou só da ÚLTIMA etapa (False)
SHOW_ALL_STAGES = True

# Colunas usadas no treino (garantimos o alinhamento no encoding)
COLUNAS_TREINO: List[str] = [
    "orcamento_estimado",
    "rating_confiabilidade",
    "taxa_insucesso_fornecedor",
    "complexidade_obra",
    "risco_etapa",
    "material_Aço",
    "material_Brita",
    "material_Cimento",
    "material_Madeira",
    "material_Piso",
    "material_Revestimento",
    "material_Tintas",
    "cidade_Belo Horizonte",
    "cidade_Curitiba",
    "cidade_Rio de Janeiro",
    "cidade_Salvador",
    "cidade_São Paulo",
    "etapa_Acabamento",
    "etapa_Estrutura",
    "etapa_Fundação",
]

# -----------------------------
# Logging básico
# -----------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# -----------------------------
# Carregar recursos (modelo, base e encoder)
# -----------------------------
try:
    model = joblib.load(MODEL_PATH)
    logger.info("Modelo carregado com sucesso.")
except Exception as e:
    logger.error(f"Erro ao carregar o modelo: {e}")
    raise

try:
    db = pd.read_csv(DB_PATH)
    logger.info("Base de consulta carregada com sucesso.")
except Exception as e:
    logger.error(f"Erro ao carregar a base de consulta: {e}")
    raise

# Encoder é opcional; se não existir, seguimos com get_dummies + alinhamento
encoder = None
if os.path.exists(ENCODER_PATH):
    try:
        encoder = joblib.load(ENCODER_PATH)
        logger.info("Encoder carregado com sucesso.")
    except Exception as e:
        logger.warning(f"Não foi possível carregar o encoder: {e}. Usando get_dummies.")


# -----------------------------
# Utilitários de preparação de dados
# -----------------------------
def alinhar_colunas_treino(X_encoded: pd.DataFrame, colunas_treino: List[str]) -> pd.DataFrame:
    """Garante que todas as colunas de treino existam e na ordem correta."""
    for col in colunas_treino:
        if col not in X_encoded.columns:
            X_encoded[col] = 0
    return X_encoded[colunas_treino]


def preparar_features(obra_df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara o dataframe para predição:
    - Remove a coluna id_obra
    - One-Hot Encoding (encoder do treino, se disponível; senão get_dummies)
    - Alinha com as COLUNAS_TREINO
    """
    X_input = obra_df.drop(columns=["id_obra"], errors="ignore")

    cat_cols = ["material", "cidade", "etapa"]

    if encoder is not None:
        # Quando existe encoder do treino, aplicamos transform e reconstruímos o DataFrame
        try:
            X_num = X_input.drop(columns=cat_cols, errors="ignore")
            X_cat = X_input[cat_cols].astype(str)

            X_cat_enc = encoder.transform(X_cat)  # retorna array esparso ou denso
            # Se você salvou encoder com get_feature_names_out():
            try:
                cat_feature_names = encoder.get_feature_names_out(cat_cols)
            except Exception:
                # Fallback (pode variar conforme como o encoder foi salvo)
                cat_feature_names = [f"cat_{i}" for i in range(X_cat_enc.shape[1])]

            X_encoded = pd.concat(
                [X_num.reset_index(drop=True),
                 pd.DataFrame(X_cat_enc.toarray() if hasattr(X_cat_enc, "toarray") else X_cat_enc,
                              columns=cat_feature_names)],
                axis=1,
            )
        except Exception as e:
            logger.warning(f"Falha ao usar encoder salvo: {e}. Usando get_dummies.")
            X_encoded = pd.get_dummies(X_input, columns=cat_cols)
    else:
        # Sem encoder salvo: usamos get_dummies e alinhamos
        X_encoded = pd.get_dummies(X_input, columns=cat_cols)

    X_alinhado = alinhar_colunas_treino(X_encoded, COLUNAS_TREINO)
    return X_alinhado


def emoji_risco(dias: float) -> str:
    """Define o emoji conforme o risco de atraso."""
    if dias > 15:
        return "🔴"
    if dias > 5:
        return "🟡"
    return "🟢"


# -----------------------------
# Handlers do Telegram
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Digite o ID da obra (ex: MRV-100) para consultar o risco.\n"
        "Você pode enviar IDs uma por mensagem."
    )


async def prever_risco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Consulta risco de atraso para uma obra:
    - Se SHOW_ALL_STAGES=True: gera relatório para todas as etapas daquela obra.
    - Caso contrário: considera somente a última etapa registrada.
    """
    id_usuario = update.message.text.upper().strip()
    logger.info(f"Consulta recebida: {id_usuario}")

    obras_encontradas = db[db["id_obra"] == id_usuario]

    if obras_encontradas.empty:
        await update.message.reply_text(f"❌ Obra {id_usuario} não encontrada.")
        return

    # Seleção de linhas conforme estratégia
    if SHOW_ALL_STAGES:
        obras_para_relatorio = obras_encontradas.copy()
    else:
        obras_para_relatorio = obras_encontradas.tail(1)

    # Predições por etapa (uma ou várias linhas)
    relatorios = []
    for _, linha in obras_para_relatorio.iterrows():
        obra_df = pd.DataFrame([linha])

        X_alinhado = preparar_features(obra_df)
        predicao = float(model.predict(X_alinhado)[0])

        cor = emoji_risco(predicao)
        relatorios.append(
            f"{cor} Risco de atraso: `{predicao:.1f} dias`\n"
            f"- Cidade: {linha.get('cidade', 'N/A')}\n"
            f"- Etapa: {linha.get('etapa', 'N/A')}\n"
            f"- Material: {linha.get('material', 'N/A')}"
        )

    # Mensagem final
    titulo = f"🏗️ Relatório Preditivo MRV\n\n📍 Obra: *{id_usuario}*"
    separador = "\n---------------------------\n"
    corpo = f"\n{separador}".join(relatorios)

    await update.message.reply_text(
        f"{titulo}\n\n{corpo}",
        parse_mode=ParseMode.MARKDOWN,
    )


# -----------------------------
# Bootstrap do aplicativo
# -----------------------------
def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise RuntimeError(
            "Variável de ambiente TELEGRAM_TOKEN não encontrada. "
            "Defina TELEGRAM_TOKEN com o token do seu bot."
        )

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), prever_risco))

    logger.info("🚀 Bot da MRV Ativo e Operacional!")
    app.run_polling()


if __name__ == "__main__":
    main()
