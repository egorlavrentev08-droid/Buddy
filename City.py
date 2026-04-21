# city.py - Клановые города (Тестовая версия для RadCoin Buddy)
# Версия: 0.1.0

import random
import json
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

# Импорты из проекта
from config import logger
from core import send_to_private, is_admin
from database import Session, User, Clan
from utils import add_item_to_inventory, get_item_count, remove_item_from_inventory

# ==================== КОНСТАНТЫ ====================

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
HOUSE_BONUS = {1: 3, 2: 7, 3: 10}  # + участников
TOWER_BONUS = {1: 5, 2: 10, 3: 15}  # +% выживания
BANK_COIN_BONUS = {1: 1, 2: 3, 3: 5}  # % от казны
BANK_MEMBER_BONUS = {1: 0.25, 2: 0.5, 3: 1.0}  # % за участника

# Шахта
MINE_CRYSTALS = {1: (10, 50), 2: (25, 100), 3: (50, 500)}
MINE_CHESTS = {
    1: {'common': 80, 'rare': 10, 'epic': 9, 'legendary': 1},
    2: {'common': 70, 'rare': 15, 'epic': 10, 'legendary': 5},
    3: {'common': 40, 'rare': 30, 'epic': 20, 'legendary': 10}
}

# Рейды
RAID_WEEKDAYS = [3, 4, 5, 6]  # чт, пт, сб, вс
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

def get_clan_buildings(clan):
    return json.loads(clan.buildings) if clan.buildings else {}

def save_clan_buildings(clan, buildings):
    clan.buildings = json.dumps(buildings)

def get_production_queue(clan):
    return json.loads(clan.production_queue) if clan.production_queue else []

def save_production_queue(clan, queue):
    clan.production_queue = json.dumps(queue)

def get_storage_items(clan):
    return json.loads(clan.storage_items) if clan.storage_items else {}

def save_storage_items(clan, items):
    clan.storage_items = json.dumps(items)

def get_total_storage_capacity(clan):
    buildings = get_clan_buildings(clan)
    storage = buildings.get('storage', {})
    return storage.get('count', 0) * STORAGE_CAPACITY.get(storage.get('level', 0), 0)

def get_clan_member_limit(clan):
    buildings = get_clan_buildings(clan)
    house = buildings.get('house', {})
    return BASE_CLAN_MEMBERS_LIMIT + house.get('count', 0) * HOUSE_BONUS.get(house.get('level', 0), 0)


# ==================== КОМАНДЫ (ЗАГОТОВКИ) ====================

async def clan_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏗️ *Клановый город в разработке!*", parse_mode='Markdown')

async def clan_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏗️ *Строительство зданий временно недоступно.*", parse_mode='Markdown')

async def clan_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📈 *Улучшение зданий временно недоступно.*", parse_mode='Markdown')

async def clan_produce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ *Производство временно недоступно.*", parse_mode='Markdown')

async def clan_storage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📦 *Клановый склад временно недоступен.*", parse_mode='Markdown')

async def clan_raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚔️ *Рейды на мутантов временно недоступны.*", parse_mode='Markdown')

async def clan_mine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⛏️ *Шахта временно недоступна.*", parse_mode='Markdown')
