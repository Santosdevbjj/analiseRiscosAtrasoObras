from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import database
from i18n import TEXTS

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Menu de Idiomas inicial
    keyboard = [[
        InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt"),
        InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
    ]]
    await update.message.reply_text(
        "🏗️ **CCBJJ Engenharia & Inteligência**\nSelecione seu idioma / Select your language:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = database.get_language(user_id)
    # Importação tardia para evitar erro circular
    from telegram_bot import obter_menu_infra
    await update.message.reply_text(
        TEXTS[lang]["infra_select"],
        reply_markup=obter_menu_infra(),
        parse_mode=ParseMode.MARKDOWN
    )
