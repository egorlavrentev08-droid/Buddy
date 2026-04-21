# city.py - Клановые города (с картой 10х10)
# Версия: 0.2.0

import random
import json
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from config import logger
from core import send_to_private, is_admin
from database import Session, User, Clan
from utils import add_item_to_inventory, get_item_count, remove_item_from_inventory


# ==================== КОНСТАНТЫ ====================

# Размер карты
MAP_SIZE = 10  # 10x10
MAP_COLUMNS = ['А', 'Б', 'В', 'Г', 'Д', 'Е', 'Ж', 'З', 'И', 'Й']
MAP_ROWS = list(range(1, 11))

# Типы клеток
CELL_EMPTY = '⬜'
CELL_WALL_1 = '|'      # стена 1 уровня
CELL_WALL_2 = '{'      # стена 2 уровня
CELL_WALL_3 = '['      # стена 3 уровня
CELL_BUILDING = '🏠'   # здание (резиденция, банк, мастерская и т.д.)

# Базовый лимит участников клана без ЖК
BASE_CLAN_MEMBERS_LIMIT = 5

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

# Ёмкость склада
STORAGE_CAPACITY = {1: 25, 2: 50, 3: 100}

# Бонусы
HOUSE_BONUS = {1: 3, 2: 7, 3: 10}
TOWER_BONUS = {1: 5, 2: 10, 3: 15}
BANK_COIN_BONUS = {1: 1, 2: 3, 3: 5}
BANK_MEMBER_BONUS = {1: 0.25, 2: 0.5, 3: 1.0}

# Шахта
MINE_CRYSTALS = {1: (10, 50), 2: (25, 100), 3: (50, 500)}
MINE_CHESTS = {
    1: {'common': 80, 'rare': 10, 'epic': 9, 'legendary': 1},
    2: {'common': 70, 'rare': 15, 'epic': 10, 'legendary': 5},
    3: {'common': 40, 'rare': 30, 'epic': 20, 'legendary': 10}
}

# Рейды
RAID_WEEKDAYS = [3, 4, 5, 6]
RAID_HOURS = range(12, 22)
RAID_TYPES = ['small', 'medium', 'large']
RAID_REQUIREMENTS = {'small': 1, 'medium': 'half', 'large': 'percent70'}
RAID_REWARDS = {
    'small': {'coins': 500, 'rf': 10, 'exp': 25},
    'medium': {'coins': 1500, 'rf': 30, 'exp': 75},
    'large': {'coins': 5000, 'rf': 100, 'exp': 250}
}

# Производство
PRODUCTION_TIMES = {
    'workshop': {'medkit': 3, 'energy': 3, 'reducer': 3},
    'factory': {
        'armor1': 3, 'armor2': 6, 'armor3': 12, 'armor4': 24, 'armor5': 48,
        'shotgun': 2, 'harpoon': 4, 'rifle': 12, 'gauss': 96
    }
}
PRODUCTION_MULTIPLIERS = {1: 1.0, 2: 0.66, 3: 0.5}


# ==================== РАБОТА С ДАННЫМИ ====================

def get_clan_city(clan):
    """Получить карту города (матрица 10х10)"""
    return json.loads(clan.city_map) if clan.city_map else [[CELL_EMPTY for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]


def save_clan_city(clan, city_map):
    """Сохранить карту города"""
    clan.city_map = json.dumps(city_map)


def get_clan_buildings(clan):
    """Получить словарь зданий клана"""
    return json.loads(clan.buildings) if clan.buildings else {}


def save_clan_buildings(clan, buildings):
    clan.buildings = json.dumps(buildings)


def parse_coordinates(coord: str):
    """Преобразует 'А1' в индексы (0,0), 'Й10' в (9,9)"""
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
    # Заголовок с буквами
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
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не состоите в клане!")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan:
            await update.message.reply_text("❌ Клан не найден!")
            return
        
        city_map = get_clan_city(clan)
        buildings = get_clan_buildings(clan)
        
        text = f"🏰 *Клановый город: {clan.name}*\n"
        text += format_city_map(city_map)
        text += "\n📊 *Здания:*\n"
        
        for building, data in buildings.items():
            text += f"• {building}: {data.get('count', 0)} шт (ур.{data.get('level', 1)})\n"
        
        text += "\n💡 *Команды:*\n"
        text += "/city — показать карту\n"
        text += "/city build [координаты] [тип_здания] — построить здание\n"
        text += "/city upgrade [тип_здания] — улучшить здание\n"
        text += "/city info [координаты] — информация о клетке"
        
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in city: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


async def city_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Построить здание на указанной клетке"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ /city build [координаты] [тип_здания]\nПример: `/city build А1 workshop`", parse_mode='Markdown')
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
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не состоите в клане!")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan:
            await update.message.reply_text("❌ Клан не найден!")
            return
        
        # Проверяем, не лидер ли клана (строить может только лидер)
        if clan.leader_id != user.user_id:
            await update.message.reply_text("❌ Только лидер клана может строить здания!")
            return
        
        city_map = get_clan_city(clan)
        buildings = get_clan_buildings(clan)
        
        # Проверяем, свободна ли клетка
        if city_map[row][col] != CELL_EMPTY:
            await update.message.reply_text(f"❌ Клетка {coord} уже занята!")
            return
        
        # Проверяем лимиты зданий
        current_count = buildings.get(building_type, {}).get('count', 0)
        if current_count >= BUILDING_LIMITS.get(building_type, 0):
            await update.message.reply_text(f"❌ Достигнут лимит на {building_type} (макс. {BUILDING_LIMITS.get(building_type, 0)})!")
            return
        
        # Проверяем, построена ли резиденция (если строим не её)
        if building_type != 'residence' and buildings.get('residence', {}).get('count', 0) == 0:
            await update.message.reply_text("❌ Сначала постройте Резиденцию!")
            return
        
        # Проверяем уровень резиденции для доступа к другим зданиям
        residence_level = buildings.get('residence', {}).get('level', 1)
        
        # Проверка доступности зданий по уровню резиденции
        building_requirements = {
            'bank': 1, 'workshop': 1,
            'storage': 2, 'house': 2, 'mine': 2,
            'factory': 3, 'tower': 3
        }
        required_level = building_requirements.get(building_type, 1)
        if residence_level < required_level:
            await update.message.reply_text(f"❌ Для строительства {building_type} нужна Резиденция {required_level} уровня! (сейчас {residence_level})")
            return
        
        # Проверка кристаллов
        price = BUILDING_PRICES[building_type][1]
        if clan.treasury_crystals < price:
            await update.message.reply_text(f"❌ Не хватает кристаллов! Нужно: {price}, в казне: {clan.treasury_crystals}")
            return
        
        # Строим
        clan.treasury_crystals -= price
        
        # Обновляем карту
        building_symbol = CELL_BUILDING
        city_map[row][col] = building_symbol
        save_clan_city(clan, city_map)
        
        # Обновляем здания
        if building_type not in buildings:
            buildings[building_type] = {'count': 0, 'level': 1}
        buildings[building_type]['count'] += 1
        save_clan_buildings(clan, buildings)
        
        session.commit()
        
        await update.message.reply_text(
            f"✅ *Построено {building_type} на {coord}!*\n"
            f"💰 Потрачено кристаллов: {price}\n"
            f"📊 Остаток в казне: {clan.treasury_crystals}",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in city_build: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


async def city_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Улучшить здание"""
    if len(context.args) < 1:
        await update.message.reply_text("❌ /city upgrade [тип_здания]\nПример: `/city upgrade bank`", parse_mode='Markdown')
        return
    
    building_type = context.args[0].lower()
    
    valid_buildings = ['residence', 'bank', 'workshop', 'factory', 'storage', 'house', 'tower', 'mine']
    if building_type not in valid_buildings:
        await update.message.reply_text(f"❌ Неизвестный тип здания. Доступны: {', '.join(valid_buildings)}")
        return
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не состоите в клане!")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan:
            await update.message.reply_text("❌ Клан не найден!")
            return
        
        if clan.leader_id != user.user_id:
            await update.message.reply_text("❌ Только лидер клана может улучшать здания!")
            return
        
        buildings = get_clan_buildings(clan)
        
        if building_type not in buildings or buildings[building_type]['count'] == 0:
            await update.message.reply_text(f"❌ У клана нет здания {building_type}!")
            return
        
        current_level = buildings[building_type]['level']
        next_level = current_level + 1
        
        if next_level not in BUILDING_PRICES[building_type]:
            await update.message.reply_text(f"❌ Максимальный уровень для {building_type} уже достигнут!")
            return
        
        price = BUILDING_PRICES[building_type][next_level]
        
        if clan.treasury_crystals < price:
            await update.message.reply_text(f"❌ Не хватает кристаллов! Нужно: {price}, в казне: {clan.treasury_crystals}")
            return
        
        clan.treasury_crystals -= price
        buildings[building_type]['level'] = next_level
        save_clan_buildings(clan, buildings)
        
        session.commit()
        
        await update.message.reply_text(
            f"✅ *Улучшен {building_type} до {next_level} уровня!*\n"
            f"💰 Потрачено кристаллов: {price}\n"
            f"📊 Остаток в казне: {clan.treasury_crystals}",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in city_upgrade: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()


async def city_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о клетке"""
    if len(context.args) < 1:
        await update.message.reply_text("❌ /city info [координаты]\nПример: `/city info А1`", parse_mode='Markdown')
        return
    
    coord = context.args[0]
    row, col = parse_coordinates(coord)
    if row is None:
        await update.message.reply_text("❌ Неверные координаты. Пример: А1, Б5, Й10")
        return
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не состоите в клане!")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan:
            await update.message.reply_text("❌ Клан не найден!")
            return
        
        city_map = get_clan_city(clan)
        cell = city_map[row][col]
        
        if cell == CELL_EMPTY:
            await update.message.reply_text(f"📍 *Клетка {coord}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n🌿 Пустое место. Можно построить здание.", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"📍 *Клетка {coord}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n🏠 Здесь находится здание.", parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in city_info: {e}")
        await update.message.reply_text("❌ Ошибка")
    finally:
        Session.remove()
