# city.py - Клановый город для тестового бота RadCoin Buddy
# Версия: 0.1.0

import random
import json
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from config import logger
from core import send_to_private, is_admin
from database import get_user, save_user, get_clan, save_clan, get_all_users


# ==================== КОНСТАНТЫ ====================

MAP_SIZE = 10
MAP_COLUMNS = ['А', 'Б', 'В', 'Г', 'Д', 'Е', 'Ж', 'З', 'И', 'Й']

CELL_EMPTY = '⬜'
CELL_BUILDING = '🏠'

# Цены на здания и улучшения (в кристаллах)
BUILDING_PRICES = {
    'residence': {1: 0, 2: 200, 3: 500, 4: 1200},
    'bank': {1: 100, 2: 300, 3: 700},
    'workshop': {1: 80, 2: 250, 3: 600},
    'factory': {1: 150, 2: 400, 3: 1000},
    'storage': {1: 50, 2: 150, 3: 400},
    'house': {1: 100, 2: 300, 3: 800},
    'tower': {1: 50, 2: 150, 3: 400},
    'mine': {1: 120, 2: 350, 3: 900}
}

# Лимиты на количество зданий
BUILDING_LIMITS = {
    'bank': 1, 'workshop': 4, 'factory': 3, 'storage': 4, 'house': 5, 'tower': 1, 'mine': 1
}

# Требования к уровню резиденции
BUILDING_REQUIREMENTS = {
    'bank': 1, 'workshop': 1,
    'storage': 2, 'house': 2, 'mine': 2,
    'factory': 3, 'tower': 3
}


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def parse_coordinates(coord: str):
    """Преобразует 'А1' в индексы (row, col)"""
    if len(coord) < 2:
        return None, None
    col_letter = coord[0].upper()
    row_str = coord[1:]
    if col_letter not in MAP_COLUMNS:
        return None, None
    try:
        row = int(row_str) - 1
    except ValueError:
        return None, None
    if row < 0 or row >= MAP_SIZE:
        return None, None
    col = MAP_COLUMNS.index(col_letter)
    return row, col


def format_city_map(city_map):
    """Форматирует карту для отправки в Telegram"""
    header = "   " + " ".join(MAP_COLUMNS)
    lines = [header]
    for i, row in enumerate(city_map):
        row_str = f"{i+1:2d} " + " ".join(row)
        lines.append(row_str)
    return "```\n" + "\n".join(lines) + "\n```"


# ==================== КОМАНДЫ ====================

async def city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать карту кланового города"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user.get('clan_id'):
        await update.message.reply_text("❌ Вы не состоите в клане!")
        return
    
    clan = get_clan(user['clan_id'])
    if not clan:
        await update.message.reply_text("❌ Клан не найден!")
        return
    
    city_map = clan.get('city_map')
    if not city_map:
        city_map = [[CELL_EMPTY for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
    
    buildings = clan.get('buildings', {})
    
    text = f"🏰 *Клановый город: {clan['name']}*\n"
    text += format_city_map(city_map)
    text += "\n📊 *Здания:*\n"
    
    if buildings:
        for building, data in buildings.items():
            building_name = {
                'residence': 'Резиденция', 'bank': 'Банк', 'workshop': 'Мастерская',
                'factory': 'Завод', 'storage': 'Склад', 'house': 'Жилой комплекс',
                'tower': 'Вышка', 'mine': 'Шахта'
            }.get(building, building)
            text += f"• {building_name}: {data.get('count', 0)} шт (ур.{data.get('level', 1)})\n"
    else:
        text += "❌ Нет построек\n"
    
    text += "\n💡 *Команды:*\n"
    text += "/city — показать карту\n"
    text += "/city_build [координаты] [тип] — построить\n"
    text += "/city_upgrade [тип] — улучшить\n"
    text += "/city_info [координаты] — информация о клетке"
    
    try:
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Markdown error in city: {e}")
        await update.message.reply_text(text)


async def city_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Построить здание на указанной клетке"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ /city_build [координаты] [тип_здания]\nПример: `/city_build А1 workshop`", parse_mode='Markdown')
        return
    
    coord = context.args[0]
    building_type = context.args[1].lower()
    
    valid_buildings = ['residence', 'bank', 'workshop', 'factory', 'storage', 'house', 'tower', 'mine']
    if building_type not in valid_buildings:
        await update.message.reply_text(f"❌ Неизвестный тип здания. Доступны: {', '.join(valid_buildings)}")
        return
    
    row, col = parse_coordinates(coord)
    if row is None:
        await update.message.reply_text("❌ Неверные координаты. Пример: А1, Б5, Й10")
        return
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user.get('clan_id'):
        await update.message.reply_text("❌ Вы не состоите в клане!")
        return
    
    clan = get_clan(user['clan_id'])
    if not clan:
        await update.message.reply_text("❌ Клан не найден!")
        return
    
    # Только лидер может строить
    if clan['leader_id'] != user_id:
        await update.message.reply_text("❌ Только лидер клана может строить здания!")
        return
    
    city_map = clan.get('city_map')
    if not city_map:
        city_map = [[CELL_EMPTY for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
    
    # Проверяем, свободна ли клетка
    if city_map[row][col] != CELL_EMPTY:
        await update.message.reply_text(f"❌ Клетка {coord} уже занята!")
        return
    
    buildings = clan.get('buildings', {})
    
    # Проверяем лимиты
    current_count = buildings.get(building_type, {}).get('count', 0)
    if current_count >= BUILDING_LIMITS.get(building_type, 0):
        await update.message.reply_text(f"❌ Достигнут лимит на {building_type} (макс. {BUILDING_LIMITS.get(building_type, 0)})!")
        return
    
    # Проверяем, построена ли резиденция
    if building_type != 'residence' and buildings.get('residence', {}).get('count', 0) == 0:
        await update.message.reply_text("❌ Сначала постройте Резиденцию!")
        return
    
    # Проверяем уровень резиденции
    residence_level = buildings.get('residence', {}).get('level', 1)
    required_level = BUILDING_REQUIREMENTS.get(building_type, 1)
    if residence_level < required_level:
        await update.message.reply_text(f"❌ Для строительства {building_type} нужна Резиденция {required_level} уровня! (сейчас {residence_level})")
        return
    
    # Проверяем кристаллы
    price = BUILDING_PRICES[building_type][1]
    if clan.get('treasury_crystals', 0) < price:
        await update.message.reply_text(f"❌ Не хватает кристаллов! Нужно: {price}, в казне: {clan.get('treasury_crystals', 0)}")
        return
    
    # Строим
    clan['treasury_crystals'] = clan.get('treasury_crystals', 0) - price
    city_map[row][col] = CELL_BUILDING
    
    if building_type not in buildings:
        buildings[building_type] = {'count': 0, 'level': 1}
    buildings[building_type]['count'] += 1
    
    clan['city_map'] = city_map
    clan['buildings'] = buildings
    save_clan(clan)
    
    building_name = {
        'residence': 'Резиденция', 'bank': 'Банк', 'workshop': 'Мастерская',
        'factory': 'Завод', 'storage': 'Склад', 'house': 'Жилой комплекс',
        'tower': 'Вышка', 'mine': 'Шахта'
    }.get(building_type, building_type)
    
    await update.message.reply_text(
        f"✅ *Построено {building_name} на {coord}!*\n"
        f"💰 Потрачено кристаллов: {price}\n"
        f"📊 Остаток в казне: {clan['treasury_crystals']}",
        parse_mode='Markdown'
    )


async def city_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Улучшить здание"""
    if len(context.args) < 1:
        await update.message.reply_text("❌ /city_upgrade [тип_здания]\nПример: `/city_upgrade bank`", parse_mode='Markdown')
        return
    
    building_type = context.args[0].lower()
    
    valid_buildings = ['residence', 'bank', 'workshop', 'factory', 'storage', 'house', 'tower', 'mine']
    if building_type not in valid_buildings:
        await update.message.reply_text(f"❌ Неизвестный тип здания. Доступны: {', '.join(valid_buildings)}")
        return
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user.get('clan_id'):
        await update.message.reply_text("❌ Вы не состоите в клане!")
        return
    
    clan = get_clan(user['clan_id'])
    if not clan:
        await update.message.reply_text("❌ Клан не найден!")
        return
    
    if clan['leader_id'] != user_id:
        await update.message.reply_text("❌ Только лидер клана может улучшать здания!")
        return
    
    buildings = clan.get('buildings', {})
    
    if building_type not in buildings or buildings[building_type].get('count', 0) == 0:
        await update.message.reply_text(f"❌ У клана нет здания {building_type}!")
        return
    
    current_level = buildings[building_type].get('level', 1)
    next_level = current_level + 1
    
    if next_level not in BUILDING_PRICES[building_type]:
        await update.message.reply_text(f"❌ Максимальный уровень для {building_type} уже достигнут!")
        return
    
    price = BUILDING_PRICES[building_type][next_level]
    
    if clan.get('treasury_crystals', 0) < price:
        await update.message.reply_text(f"❌ Не хватает кристаллов! Нужно: {price}, в казне: {clan.get('treasury_crystals', 0)}")
        return
    
    clan['treasury_crystals'] = clan.get('treasury_crystals', 0) - price
    buildings[building_type]['level'] = next_level
    clan['buildings'] = buildings
    save_clan(clan)
    
    building_name = {
        'residence': 'Резиденция', 'bank': 'Банк', 'workshop': 'Мастерская',
        'factory': 'Завод', 'storage': 'Склад', 'house': 'Жилой комплекс',
        'tower': 'Вышка', 'mine': 'Шахта'
    }.get(building_type, building_type)
    
    await update.message.reply_text(
        f"✅ *Улучшен {building_name} до {next_level} уровня!*\n"
        f"💰 Потрачено кристаллов: {price}\n"
        f"📊 Остаток в казне: {clan['treasury_crystals']}",
        parse_mode='Markdown'
    )


async def city_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о клетке"""
    if len(context.args) < 1:
        await update.message.reply_text("❌ /city_info [координаты]\nПример: `/city_info А1`", parse_mode='Markdown')
        return
    
    coord = context.args[0]
    row, col = parse_coordinates(coord)
    if row is None:
        await update.message.reply_text("❌ Неверные координаты. Пример: А1, Б5, Й10")
        return
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user.get('clan_id'):
        await update.message.reply_text("❌ Вы не состоите в клане!")
        return
    
    clan = get_clan(user['clan_id'])
    if not clan:
        await update.message.reply_text("❌ Клан не найден!")
        return
    
    city_map = clan.get('city_map')
    if not city_map:
        city_map = [[CELL_EMPTY for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
    
    cell = city_map[row][col]
    
    if cell == CELL_EMPTY:
        await update.message.reply_text(f"📍 *Клетка {coord}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n🌿 Пустое место. Можно построить здание.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"📍 *Клетка {coord}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n🏠 Здесь находится здание.", parse_mode='Markdown')
