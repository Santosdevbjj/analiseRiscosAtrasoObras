from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import database
from i18n import TEXTS

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Força a escolha de idioma inicial
    keyboard = [[
        InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt"),
        InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
    ]]
    await update.message.reply_text(
        "🏗️ **CCBJJ ENGENHARIA**\nSelecione o idioma para começar / Select language:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = database.get_language(update.effective_user.id)
    await update.message.reply_text(TEXTS[lang]["help"], parse_mode=ParseMode.MARKDOWN)
