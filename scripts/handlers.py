import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import database
from i18n import TEXTS

# Configuração de logging para monitoramento de uso
logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Inicia o fluxo de boas-vindas. 
    O texto é buscado dinamicamente para suportar internacionalização desde o primeiro contato.
    """
    user = update.effective_user
    logger.info(f"Comando /start acionado pelo usuário {user.id} ({user.first_name})")

    # Texto de boas-vindas bilíngue para a primeira interação
    # Após a escolha, o bot seguirá apenas o idioma selecionado.
    welcome_text = (
        "🏗️ **CCBJJ ENGENHARIA & AI**\n\n"
        "Selecione o idioma para começar:\n"
        "Select your language to begin:"
    )

    # Geração dinâmica do teclado baseado nas chaves disponíveis em TEXTS
    # Isso permite adicionar 'es', 'fr', etc., apenas editando o i18n.py
    keyboard = []
    lang_options = {
        "pt": "🇧🇷 Português",
        "en": "🇺🇸 English"
        # Adicione novos idiomas aqui ou mapeie dinamicamente de TEXTS
    }

    buttons = [
        InlineKeyboardButton(label, callback_data=f"lang_{code}")
        for code, label in lang_options.items() if code in TEXTS
    ]
    
    # Organiza em linhas de 2 botões
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]

    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Exibe a ajuda com fallback seguro para evitar crash caso a chave não exista.
    """
    user_id = update.effective_user.id
    logger.info(f"Comando /help acionado pelo usuário {user_id}")

    # Recupera idioma do banco
    lang = database.get_language(user_id)

    # Fallback multinível: 
    # 1. Tenta o idioma do usuário. 
    # 2. Se falhar, tenta 'pt'. 
    # 3. Se falhar, usa mensagem fixa de segurança.
    help_content = TEXTS.get(lang, {}).get("help")
    if not help_content:
        help_content = TEXTS.get("pt", {}).get("help", "⚠️ Help not available. / Ajuda não disponível.")

    await update.message.reply_text(
        help_content,
        parse_mode=ParseMode.MARKDOWN
    )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando atalho para reconfigurar o modo de infraestrutura (CSV/DB).
    """
    user_id = update.effective_user.id
    lang = database.get_language(user_id)
    
    logger.info(f"Comando /settings acionado pelo usuário {user_id}")

    # Importação tardia para evitar referência circular com telegram_bot.py
    from telegram_bot import obter_menu_infra
    
    text = TEXTS.get(lang, {}).get("infra_select", "Selecione o modo de dados / Select data mode:")
    
    await update.message.reply_text(
        f"⚙️ **{text}**",
        reply_markup=obter_menu_infra(),
        parse_mode=ParseMode.MARKDOWN
    )
