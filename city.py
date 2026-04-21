from telegram import Update
from telegram.ext import ContextTypes
from database import get_user, get_clan


async def city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user.get('clan_id'):
        await update.message.reply_text("❌ Вы не состоите в клане!")
        return
    
    clan = get_clan(user['clan_id'])
    if not clan:
        await update.message.reply_text("❌ Клан не найден!")
        return
    
    await update.message.reply_text(f"🏰 *Клановый город: {clan['name']}*\n🚧 В разработке", parse_mode='Markdown')


async def city_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚧 Строительство в разработке")


async def city_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📈 Улучшение в разработке")


async def city_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ Информация в разработке")
