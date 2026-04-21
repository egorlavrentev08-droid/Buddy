# main.py - Запуск тестового бота RadCoin Buddy
# Версия: 0.1.0

from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import CommandHandler

# Импорты из config
from config import logger, TOKEN

# Импорты из core
from core import backups, restore_backup, backup_now, auto_backup

# Импорты команд из user (базовые)
from user import start, help_command, profile

# Импорты клановых команд
from clan import clan_command

# Импорты команд кланового города
from city import city, city_build, city_upgrade, city_info

# Импорты админ-команд
from admin import (
    admin_giveme, admin_give, admin_take, admin_setlevel,
    admin_players, admins
)

# Создаём шедулер
scheduler = AsyncIOScheduler()


# ==================== РЕГИСТРАЦИЯ КОМАНД ====================

def register_handlers(app):
    """Регистрация всех обработчиков команд"""
    
    # Основные команды пользователя
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("profile", profile))
    
    # Кланы
    app.add_handler(CommandHandler("clan", clan_command))
    
    # Клановый город
    app.add_handler(CommandHandler("city", city))
    app.add_handler(CommandHandler("city_build", city_build))
    app.add_handler(CommandHandler("city_upgrade", city_upgrade))
    app.add_handler(CommandHandler("city_info", city_info))
    
    # Админские команды
    app.add_handler(CommandHandler("givemeplsadmin", admin_giveme))
    app.add_handler(CommandHandler("give", admin_give))
    app.add_handler(CommandHandler("take", admin_take))
    app.add_handler(CommandHandler("setlevel", admin_setlevel))
    app.add_handler(CommandHandler("players", admin_players))
    app.add_handler(CommandHandler("admins", admins))
    
    # Бэкапы
    app.add_handler(CommandHandler("backups", backups))
    app.add_handler(CommandHandler("restore", restore_backup))
    app.add_handler(CommandHandler("backup_now", backup_now))


# ==================== ИНИЦИАЛИЗАЦИЯ ====================

def init_bot_data(app):
    """Инициализация данных бота"""
    app.bot_data['phase'] = 1
    logger.info("📦 Данные бота инициализированы")


# ==================== ЗАПУСК ====================

def main():
    """Запуск бота"""
    from telegram.ext import Application
    
    app = Application.builder().token(TOKEN).build()
    
    init_bot_data(app)
    register_handlers(app)
    
    # Запускаем планировщик для автобэкапов (каждый час)
    scheduler.add_job(auto_backup, 'interval', hours=1)
    scheduler.start()
    
    logger.info("🌟 RadCoin Buddy (тестовый бот) запущен!")
    logger.info("🏗️ Тестируем клановые города!")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    app.run_polling()


if __name__ == '__main__':
    main()
