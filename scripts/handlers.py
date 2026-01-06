import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import database
from i18n import TEXTS

logger = logging.getLogger(__name__)

def build_language_keyboard() -> InlineKeyboardMarkup:
    """Teclado dinâmico de idiomas baseado em TEXTS."""
    lang_labels = {
        "pt": "🇧🇷 Português",
        "en": "🇺🇸 English",
    }
    buttons = [
        InlineKeyboardButton(lang_labels[code], callback_data=f"lang_{code}")
        for code in lang_labels.keys() if code in TEXTS
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)

def build_infra_keyboard() -> InlineKeyboardMarkup:
    """Teclado para seleção de modo (CSV/Supabase)."""
    keyboard = [[
        InlineKeyboardButton("📂 Modo CSV Local", callback_data='set_CSV'),
        InlineKeyboardButton("☁️ Modo Supabase Cloud", callback_data='set_DB'),
    ]]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Boas-vindas com seleção de idioma. Usa effective_message para evitar None.
    """
    user = update.effective_user
    logger.info(f"/start acionado por {user.id} ({user.first_name})")
    msg = update.effective_message

    # Texto centralizado no i18n, com fallback
    welcome_text = TEXTS.get("pt", {}).get("start") + "\n\n" + TEXTS.get("en", {}).get("start", "")
    await msg.reply_text(
        welcome_text,
        reply_markup=build_language_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Reapresenta a escolha de idioma, útil para /language.
    """
    user = update.effective_user
    logger.info(f"/language acionado por {user.id}")
    msg = update.effective_message

    text_pt = TEXTS.get("pt", {}).get("start", "Selecione o idioma:")
    text_en = TEXTS.get("en", {}).get("start", "Select your language:")
    await msg.reply_text(
        f"{text_pt}\n\n{text_en}",
        reply_markup=build_language_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ajuda com fallback seguro.
    """
    user_id = update.effective_user.id
    logger.info(f"/help acionado por {user_id}")
    msg = update.effective_message

    lang = database.get_language(user_id)
    help_content = TEXTS.get(lang, {}).get("help") or TEXTS.get("pt", {}).get("help", "⚠️ Help not available. / Ajuda não disponível.")
    await msg.reply_text(help_content, parse_mode=ParseMode.MARKDOWN)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Reconfigura a infraestrutura (CSV/Supabase) sem importação circular.
    """
    user_id = update.effective_user.id
    lang = database.get_language(user_id)
    logger.info(f"/settings acionado por {user_id}")
    msg = update.effective_message

    text = TEXTS.get(lang, {}).get("infra_select", "Selecione o modo de dados / Select data mode:")
    await msg.reply_text(
        f"⚙️ **{text}**",
        reply_markup=build_infra_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
