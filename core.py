# core.py - Ядро тестового бота RadCoin Buddy
# Версия: 0.1.0

import os
import shutil
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from config import logger, BACKUP_DIR
from database import Session, User


# ==================== ПРОВЕРКА АДМИНА ====================

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверить, является ли пользователь администратором"""
    user_id = update.effective_user.id
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            return False
        return user.is_admin and not user.is_blocked
    except Exception as e:
        logger.error(f"Error checking admin: {e}")
        return False
    finally:
        Session.remove()


# ==================== ОТПРАВКА В ЛИЧКУ ====================

async def send_to_private(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Отправляет сообщение в личку, если команда вызвана в группе"""
    try:
        if update.effective_chat.type != 'private':
            await update.message.reply_text("📩 Информация отправлена в личные сообщения.")
            await context.bot.send_message(chat_id=update.effective_user.id, text=text)
        else:
            await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Error sending to private: {e}")


# ==================== АВТОБЭКАП ====================

def auto_backup():
    """Автоматическое создание бэкапа базы данных"""
    try:
        db_path = 'radcoin_buddy.db'
        if os.path.exists(db_path):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"radcoin_buddy.db.backup_{timestamp}.db"
            backup_path = os.path.join(BACKUP_DIR, backup_name)
            shutil.copy(db_path, backup_path)
            backups_list = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('radcoin_buddy.db.backup')])
            if len(backups_list) > 24:
                for old_backup in backups_list[:-24]:
                    os.remove(os.path.join(BACKUP_DIR, old_backup))
            logger.info(f"✅ Автобэкап: {backup_name}")
    except Exception as e:
        logger.error(f"❌ Ошибка автобэкапа: {e}")


# ==================== КОМАНДЫ БЭКАПОВ ====================

async def backups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список бэкапов"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    try:
        backups_list = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('radcoin_buddy.db.backup')])
        if not backups_list:
            await update.message.reply_text("📋 *Нет бэкапов*", parse_mode='Markdown')
            return
        text = "💾 *Список бэкапов*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, backup in enumerate(backups_list[-10:], 1):
            text += f"{i}. `{backup}`\n"
        text += "\n📌 /restore [имя] — восстановить\n📌 /backup_now — создать бэкап"
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in backups: {e}")
        await update.message.reply_text("❌ Ошибка")


async def restore_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Восстановить бэкап"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    if not context.args:
        await update.message.reply_text("❌ /restore [имя_бэкапа]")
        return
    backup_name = context.args[0]
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.exists(backup_path):
        await update.message.reply_text(f"❌ Бэкап `{backup_name}` не найден!")
        return
    auto_backup()
    shutil.copy(backup_path, 'radcoin_buddy.db')
    await update.message.reply_text(f"✅ *База восстановлена!* Перезапустите бота.")
    os._exit(0)


async def backup_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создать бэкап сейчас"""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Нет прав!")
        return
    try:
        if os.path.exists('radcoin_buddy.db'):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"radcoin_buddy.db.backup_{timestamp}.db"
            backup_path = os.path.join(BACKUP_DIR, backup_name)
            shutil.copy('radcoin_buddy.db', backup_path)
            await update.message.reply_text(f"✅ *Бэкап создан:* `{backup_name}`", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ База не найдена!")
    except Exception as e:
        logger.error(f"Error in backup_now: {e}")
        await update.message.reply_text("❌ Ошибка")
