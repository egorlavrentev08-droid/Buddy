# main.py - Запуск и регистрация команд
# Версия: 2.0.0

from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import CommandHandler, MessageHandler, filters

# Импорты из config
from config import logger, TOKEN, CASINO_PUBLIC_CHANCE, CASINO_PUBLIC_CASH_MULT, SHOP_LIMITS

# Импорты из core (бэкапы и утилиты)
from core import backups, restore_backup, backup_now, auto_backup

# Импорты команд из user
from user import start, help_command, profile, stats, achievements, announce, phase_info, class_command, class_info

# Импорты команд из collect
from collect import collect, hunt, locate, pet_command

# Импорты команд из money
from money import shop, buy, sell, equip, casino, exchange, craft, inv, use_item

# Импорты команд из clan
from clan import clan_command, radion, radio, radio_register_group, aradio

# Импорты команд из chest
from chest import chest_command, factory, afactory

# Импорты команд из admin
from admin import (
    admin_giveme, admin_phase, admin_give, admin_take, admin_setlevel,
    admin_cd, admin_resethunt, admin_item, admin_pets, admin_manage, admins,
    admin_classes, call, lscall, admin_hide, top_command, acasino,
    advice_handler, gchest, admin_players, sale
)

# Импорты из city
from city import (
    city, city_map, clan_build, clan_upgrade, clan_craft,
    clan_raid, clan_mine, check_production_complete,
    check_raid_trigger, check_daily_bonus
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
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("achievements", achievements))
    app.add_handler(CommandHandler("announce", announce))
    app.add_handler(CommandHandler("phase_info", phase_info))

    # Ресурсы и охота
    app.add_handler(CommandHandler("collect", collect))
    app.add_handler(CommandHandler("hunt", hunt))
    app.add_handler(CommandHandler("locate", locate))
    app.add_handler(CommandHandler("pet", pet_command))

    # Экономика
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("equip", equip))
    app.add_handler(CommandHandler("casino", casino))
    app.add_handler(CommandHandler("exchange", exchange))
    app.add_handler(CommandHandler("craft", craft))
    app.add_handler(CommandHandler("inv", inv))
    app.add_handler(CommandHandler("use", use_item))

    # Классы
    app.add_handler(CommandHandler("class", class_command))
    app.add_handler(CommandHandler("class_info", class_info))

    # Кланы и радио
    app.add_handler(CommandHandler("clan", clan_command))
    app.add_handler(CommandHandler("radion", radion))
    app.add_handler(CommandHandler("radio", radio))
    app.add_handler(CommandHandler("aradio", aradio))

    # Клановые города
    app.add_handler(CommandHandler("clan_city", city))
    app.add_handler(CommandHandler("city", city))
    app.add_handler(CommandHandler("city_map", city_map))
    app.add_handler(CommandHandler("clan_build", clan_build))
    app.add_handler(CommandHandler("clan_upgrade", clan_upgrade))
    app.add_handler(CommandHandler("clan_craft", clan_craft))
    app.add_handler(CommandHandler("clan_raid", clan_raid))
    app.add_handler(CommandHandler("clan_mine", clan_mine))

    # Сундуки и фабрики
    app.add_handler(CommandHandler("chest", chest_command))
    app.add_handler(CommandHandler("factory", factory))
    app.add_handler(CommandHandler("afactory", afactory))

    # Таблица лидеров
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("hide", admin_hide))

    # Советы
    app.add_handler(CommandHandler("advice", advice_handler))

    # Бэкапы
    app.add_handler(CommandHandler("backups", backups))
    app.add_handler(CommandHandler("restore", restore_backup))
    app.add_handler(CommandHandler("backup_now", backup_now))

    # Распродажи
    app.add_handler(CommandHandler("sale", sale))

    # Админские команды
    app.add_handler(CommandHandler("givemeplsadmin", admin_giveme))
    app.add_handler(CommandHandler("phase", admin_phase))
    app.add_handler(CommandHandler("give", admin_give))
    app.add_handler(CommandHandler("take", admin_take))
    app.add_handler(CommandHandler("setlevel", admin_setlevel))
    app.add_handler(CommandHandler("cd", admin_cd))
    app.add_handler(CommandHandler("resethunt", admin_resethunt))
    app.add_handler(CommandHandler("item", admin_item))
    app.add_handler(CommandHandler("pets", admin_pets))
    app.add_handler(CommandHandler("players", admin_players))
    app.add_handler(CommandHandler("admins", admins))
    app.add_handler(CommandHandler("admin", admin_manage))
    app.add_handler(CommandHandler("classes", admin_classes))
    app.add_handler(CommandHandler("call", call))
    app.add_handler(CommandHandler("lscall", lscall))
    app.add_handler(CommandHandler("gchest", gchest))
    app.add_handler(CommandHandler("acasino", acasino))

    # Обработчик для регистрации групп в радио
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, radio_register_group))


# ==================== ИНИЦИАЛИЗАЦИЯ ====================

def init_bot_data(app):
    """Инициализация данных бота"""
    app.bot_data['phase'] = 1
    app.bot_data['casino_public_chance'] = CASINO_PUBLIC_CHANCE
    app.bot_data['casino_public_cash_mult'] = CASINO_PUBLIC_CASH_MULT
    app.bot_data['radio_groups'] = set()

    # Инициализация общих лимитов магазина
    app.bot_data['shop_limits'] = SHOP_LIMITS.copy()
    app.bot_data['last_shop_reset'] = datetime.now()

    # Инициализация распродажи (по умолчанию выключена)
    app.bot_data['sale_discount'] = 0
    app.bot_data['sale_until'] = None

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

    # Фоновые задачи для клановых городов
    scheduler.add_job(check_production_complete, 'interval', minutes=1, args=[app])
    scheduler.add_job(check_raid_trigger, 'interval', minutes=10, args=[app])
    scheduler.add_job(check_daily_bonus, 'interval', hours=24, args=[app])

    scheduler.start()

    logger.info("🌟 RadCoin Bot 2.0 запущен! Пустошь ждёт своих героев!")
    logger.info(f"🎰 Настройки казино: шанс {CASINO_PUBLIC_CHANCE}%, множитель x{CASINO_PUBLIC_CASH_MULT}")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    app.run_polling()


if __name__ == '__main__':
    main()
