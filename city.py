# city.py - Клановые города
# Версия: 2.0.0

import json
import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from config import logger
from database import Session, User, Clan
from core import send_to_private
from utils import add_item_to_inventory, get_item_count


# ==================== КОНСТАНТЫ ====================

BUILDING_PRICES = {
    'residence': {1: 0, 2: 200, 3: 500, 4: 1200},
    'bank': {1: 100, 2: 300, 3: 700},
    'workshop': {1: 80, 2: 250, 3: 600},
    'factory': {1: 150, 2: 400, 3: 1000},
    'storage': {1: 50, 2: 150, 3: 400},
    'house': {1: 100, 2: 300, 3: 800},
    'tower': {1: 50, 2: 150, 3: 400},
    'mine': {1: 120, 2: 350, 3: 900},
}

BUILDING_NAMES_RU = {
    'residence': 'резиденция',
    'bank': 'банк',
    'workshop': 'мастерская',
    'factory': 'завод',
    'storage': 'склад',
    'house': 'жилой комплекс',
    'tower': 'вышка',
    'mine': 'шахта',
}

BUILDING_NAMES_EN = {
    'резиденция': 'residence',
    'банк': 'bank',
    'мастерская': 'workshop',
    'завод': 'factory',
    'склад': 'storage',
    'жк': 'house',
    'жилой комплекс': 'house',
    'вышка': 'tower',
    'шахта': 'mine',
}

BUILDING_LIMITS = {
    'residence': {1: 1, 2: 1, 3: 1, 4: 1},
    'bank': {1: 1, 2: 1, 3: 1, 4: 1},
    'workshop': {1: 1, 2: 2, 3: 3, 4: 4},
    'factory': {1: 0, 2: 1, 3: 2, 4: 3},
    'storage': {1: 1, 2: 2, 3: 3, 4: 4},
    'house': {1: 2, 2: 3, 3: 4, 4: 5},
    'tower': {1: 1, 2: 1, 3: 1, 4: 1},
    'mine': {1: 1, 2: 1, 3: 1, 4: 1},
}

BUILDING_EFFECTS = {
    'bank': {'interest': 1, 'member_bonus': 0.25},
    'workshop': {'speed': 3},
    'factory': {'speed': 3},
    'storage': {'capacity': 25},
    'house': {'members': 3},
    'tower': {'survive': 5, 'raid_notice': 1},
    'mine': {'crystals_min': 10, 'crystals_max': 50, 'chest_chances': [80, 10, 9, 1]},
}

LEVEL_BONUS = {1: 1.0, 2: 2.0, 3: 4.0}

RECIPES = {
    'аптечка': {'building': 'workshop', 'time_base': 3, 'cost': {'rf': 1}},
    'энергетик': {'building': 'workshop', 'time_base': 3, 'cost': {'rf': 2}},
    'редуктор': {'building': 'workshop', 'time_base': 3, 'cost': {'rf': 5}},
    'броня1': {'building': 'factory', 'time_base': 3, 'cost': {'rf': 5, 'rc': 100}},
    'броня2': {'building': 'factory', 'time_base': 6, 'cost': {'rf': 10, 'rc': 250}},
    'броня3': {'building': 'factory', 'time_base': 12, 'cost': {'rf': 20, 'rc': 500}},
    'броня4': {'building': 'factory', 'time_base': 24, 'cost': {'rf': 40, 'rc': 1000}},
    'броня5': {'building': 'factory', 'time_base': 48, 'cost': {'rf': 80, 'rc': 2500}},
    'ружьё': {'building': 'factory', 'time_base': 2, 'cost': {'rf': 3, 'rc': 50}},
    'гарпун': {'building': 'factory', 'time_base': 4, 'cost': {'rf': 6, 'rc': 100}},
    'винтовка': {'building': 'factory', 'time_base': 12, 'cost': {'rf': 15, 'rc': 500}},
    'гаусс': {'building': 'factory', 'time_base': 96, 'cost': {'rf': 50, 'rc': 2000}},
}

RAID_TYPES = {
    'small': {'name': 'малая', 'required': 1, 'reward_rc': 1000, 'reward_rf': 50, 'reward_exp': 100},
    'medium': {'name': 'средняя', 'required': 0.5, 'reward_rc': 5000, 'reward_rf': 200, 'reward_exp': 500},
    'large': {'name': 'большая', 'required': 0.7, 'reward_rc': 10000, 'reward_rf': 500, 'reward_exp': 1000},
}
RAID_WEEKDAYS = [3, 4, 5, 6]
RAID_HOURS = range(12, 22)


# ==================== КАРТА ГОРОДА ====================

MAP_ROWS = 9
MAP_COLS = 9

MAP_TILE_EMPTY = '⬜'
MAP_TILE_RESIDENCE = '🏰'
MAP_TILE_BANK = '🏦'
MAP_TILE_WORKSHOP = '🔧'
MAP_TILE_FACTORY = '🏭'
MAP_TILE_STORAGE = '📦'
MAP_TILE_HOUSE = '🏘️'
MAP_TILE_TOWER = '🗼'
MAP_TILE_MINE = '⛏️'

def get_tile_symbol(building_type):
    symbols = {
        'residence': MAP_TILE_RESIDENCE,
        'bank': MAP_TILE_BANK,
        'workshop': MAP_TILE_WORKSHOP,
        'factory': MAP_TILE_FACTORY,
        'storage': MAP_TILE_STORAGE,
        'house': MAP_TILE_HOUSE,
        'tower': MAP_TILE_TOWER,
        'mine': MAP_TILE_MINE,
    }
    return symbols.get(building_type, '❓')

def get_cell_coords(cell):
    cell = cell.upper()
    letters = ''
    number = ''
    for ch in cell:
        if 'А' <= ch <= 'Я' or 'A' <= ch <= 'Z':
            letters += ch
        elif ch.isdigit():
            number += ch
    if not letters or not number:
        return None
    col = 0
    for ch in letters:
        if 'А' <= ch <= 'Я':
            col = col * 33 + (ord(ch) - ord('А'))
        else:
            col = col * 26 + (ord(ch) - ord('A'))
    row = int(number) - 1
    if row < 0 or row >= MAP_ROWS or col < 0 or col >= MAP_COLS:
        return None
    return row, col

def get_cell_name(row, col):
    letters = ''
    c = col
    while c >= 0:
        letters = chr(c % 33 + ord('А')) + letters
        c = c // 33 - 1
        if c < 0:
            break
    return f"{letters}{row + 1}"

def get_building_at(clan, row, col):
    buildings = get_buildings(clan)
    for b_data in buildings.values():
        if b_data.get('row') == row and b_data.get('col') == col:
            return b_data
    return None

def is_cell_occupied(clan, row, col):
    return get_building_at(clan, row, col) is not None


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_buildings(clan):
    return json.loads(clan.city_buildings) if clan.city_buildings else {}

def save_buildings(clan, buildings):
    clan.city_buildings = json.dumps(buildings)

def get_production(clan):
    return json.loads(clan.city_production) if clan.city_production else []

def save_production(clan, production):
    clan.city_production = json.dumps(production)

def get_resources(clan):
    return json.loads(clan.city_resources) if clan.city_resources else {'crystals': 0, 'storage': {}}

def save_resources(clan, resources):
    clan.city_resources = json.dumps(resources)

def get_building_level(clan, building_type):
    buildings = get_buildings(clan)
    for b_data in buildings.values():
        if b_data.get('type') == building_type:
            return b_data.get('level', 1)
    return 0

def set_building_level(clan, building_type, level, row=None, col=None):
    buildings = get_buildings(clan)
    found_id = None
    for b_id, b_data in buildings.items():
        if b_data.get('type') == building_type:
            found_id = b_id
            break
    if found_id:
        buildings[found_id]['level'] = level
        if row is not None and col is not None:
            buildings[found_id]['row'] = row
            buildings[found_id]['col'] = col
    else:
        new_id = f"{building_type}_{len(buildings)}"
        buildings[new_id] = {
            'type': building_type,
            'level': level,
            'row': row,
            'col': col
        }
    save_buildings(clan, buildings)

def get_building_count(clan, building_type):
    buildings = get_buildings(clan)
    return len([b for b in buildings.values() if b.get('type') == building_type])

def get_residence_level(clan):
    return get_building_level(clan, 'residence')

def get_storage_capacity(clan):
    buildings = get_buildings(clan)
    capacity = 0
    for b_data in buildings.values():
        if b_data.get('type') == 'storage':
            level = b_data.get('level', 1)
            capacity += BUILDING_EFFECTS['storage']['capacity'] * LEVEL_BONUS.get(level, 1)
    return capacity

def get_storage_used(clan):
    resources = get_resources(clan)
    return sum(resources.get('storage', {}).values())

def can_add_to_storage(clan, item_name, count):
    return get_storage_used(clan) + count <= get_storage_capacity(clan)

def add_to_storage(clan, item_name, count):
    resources = get_resources(clan)
    if 'storage' not in resources:
        resources['storage'] = {}
    resources['storage'][item_name] = resources['storage'].get(item_name, 0) + count
    save_resources(clan, resources)

def get_clan_members_count(clan_id):
    session = Session()
    try:
        return session.query(User).filter_by(clan_id=clan_id).count()
    finally:
        Session.remove()

def get_clan_members(clan_id):
    session = Session()
    try:
        return session.query(User).filter_by(clan_id=clan_id).all()
    finally:
        Session.remove()


# ==================== КРИСТАЛЛЫ (СИНХРОНИЗАЦИЯ) ====================

def sync_clan_crystals(clan):
    """Синхронизирует городскую казну с клановой"""
    resources = get_resources(clan)
    if resources.get('crystals', 0) != clan.treasury_crystals:
        resources['crystals'] = clan.treasury_crystals
        save_resources(clan, resources)
    return resources

def add_crystals(clan, amount):
    """Добавить кристаллы в обе казны"""
    clan.treasury_crystals += amount
    resources = get_resources(clan)
    resources['crystals'] = resources.get('crystals', 0) + amount
    save_resources(clan, resources)

def remove_crystals(clan, amount):
    """Удалить кристаллы из обеих казн"""
    if clan.treasury_crystals >= amount:
        clan.treasury_crystals -= amount
        resources = get_resources(clan)
        resources['crystals'] = resources.get('crystals', 0) - amount
        save_resources(clan, resources)
        return True
    return False


# ==================== СТРОИТЕЛЬСТВО И УЛУЧШЕНИЯ ====================

def can_build(clan, building_type, row, col):
    sync_clan_crystals(clan)
    
    residence_level = get_residence_level(clan)
    current_count = get_building_count(clan, building_type)
    max_count = BUILDING_LIMITS.get(building_type, {}).get(residence_level, 0)
    if current_count >= max_count:
        return False, f"❌ Достигнут лимит зданий этого типа ({max_count})"
    if row < 0 or row >= MAP_ROWS or col < 0 or col >= MAP_COLS:
        return False, "❌ Клетка вне границ города"
    if is_cell_occupied(clan, row, col):
        return False, "❌ Эта клетка уже занята"
    
    price = BUILDING_PRICES.get(building_type, {}).get(1)
    if not price:
        return False, f"❌ Неизвестная цена для здания {building_type}"
    
    if clan.treasury_crystals >= price:
        return True, price
    else:
        return False, f"❌ Не хватает кристаллов. Нужно: {price} (в казне: {clan.treasury_crystals})"


def build_building(clan, building_type, row, col):
    can, price = can_build(clan, building_type, row, col)
    if not can:
        return False, price
    
    remove_crystals(clan, price)
    set_building_level(clan, building_type, 1, row, col)
    return True, None


def can_upgrade(clan, building_type):
    residence_level = get_residence_level(clan)
    current_level = get_building_level(clan, building_type)
    max_level = 3 if building_type != 'residence' else 4
    if current_level >= max_level:
        return False, "❌ Максимальный уровень достигнут"
    next_level = current_level + 1
    if next_level > residence_level and building_type != 'residence':
        return False, f"❌ Нужно улучшить резиденцию до {next_level} уровня"
    price = BUILDING_PRICES.get(building_type, {}).get(next_level)
    if clan.treasury_crystals < price:
        return False, f"❌ Не хватает кристаллов. Нужно: {price}"
    return True, next_level

def upgrade_building(clan, building_type):
    can, next_level = can_upgrade(clan, building_type)
    if not can:
        return False, next_level
    price = BUILDING_PRICES.get(building_type, {}).get(next_level)
    remove_crystals(clan, price)
    set_building_level(clan, building_type, next_level)
    return True, next_level


# ==================== ПРОИЗВОДСТВО ====================

def get_production_time(clan, recipe_name):
    recipe = RECIPES.get(recipe_name)
    if not recipe:
        return None
    building_type = recipe['building']
    time_base = recipe['time_base']
    buildings = get_buildings(clan)
    levels = [b['level'] for b in buildings.values() if b.get('type') == building_type]
    if not levels:
        return None
    avg_level = sum(levels) / len(levels)
    time_hours = time_base / max(1, avg_level)
    return max(1, int(time_hours))

def can_start_production(clan, recipe_name, count):
    recipe = RECIPES.get(recipe_name)
    if not recipe:
        return False, "❌ Неизвестный рецепт"
    building_type = recipe['building']
    buildings = [b for b in get_buildings(clan).values() if b.get('type') == building_type]
    if not buildings:
        return False, f"❌ Нет здания {BUILDING_NAMES_RU.get(building_type, building_type)}"
    resources = get_resources(clan)
    for res, amount in recipe.get('cost', {}).items():
        if resources.get(res, 0) < amount * count:
            return False, f"❌ Не хватает {res.upper()}: нужно {amount * count}"
    if not can_add_to_storage(clan, recipe_name, count):
        capacity = get_storage_capacity(clan)
        used = get_storage_used(clan)
        return False, f"❌ На складе нет места. Свободно: {capacity - used}"
    return True, None

def start_production(clan, recipe_name, count):
    can, msg = can_start_production(clan, recipe_name, count)
    if not can:
        return False, msg
    recipe = RECIPES[recipe_name]
    time_hours = get_production_time(clan, recipe_name)
    resources = get_resources(clan)
    for res, amount in recipe.get('cost', {}).items():
        resources[res] = resources.get(res, 0) - (amount * count)
    save_resources(clan, resources)
    production = get_production(clan)
    now = datetime.now()
    for _ in range(count):
        production.append({
            'recipe': recipe_name,
            'started': now.isoformat(),
            'finish': (now + timedelta(hours=time_hours)).isoformat()
        })
    save_production(clan, production)
    return True, f"✅ Производство запущено! {count} шт. Готово через {time_hours} ч."


# ==================== РЕЙДЫ ====================

def is_raid_time():
    now = datetime.now()
    return now.weekday() in RAID_WEEKDAYS and now.hour in RAID_HOURS

def get_random_raid_type():
    r = random.random()
    if r < 0.6:
        return 'small'
    elif r < 0.9:
        return 'medium'
    else:
        return 'large'

def get_raid_required_count(clan, raid_type):
    members_count = get_clan_members_count(clan.id)
    required_ratio = RAID_TYPES[raid_type]['required']
    if raid_type == 'small':
        return 1
    elif raid_type == 'medium':
        return max(1, int(members_count * required_ratio))
    else:
        return max(1, int(members_count * required_ratio) + (1 if members_count * required_ratio % 1 > 0 else 0))

async def start_raid(clan, context):
    raid_type = get_random_raid_type()
    required = get_raid_required_count(clan, raid_type)
    raid_data = {
        'type': raid_type,
        'required': required,
        'started': datetime.now().isoformat(),
        'participants': []
    }
    context.bot_data[f'raid_{clan.id}'] = raid_data
    for member in get_clan_members(clan.id):
        try:
            await context.bot.send_message(
                member.user_id,
                f"🏰 *РЕЙД МУТАНТОВ!*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Клан {clan.name} атакован!\n"
                f"📊 Тип: {RAID_TYPES[raid_type]['name']}\n"
                f"👥 Требуется участников: {required}\n\n"
                f"📝 Для участия: `/city raid`",
                parse_mode='Markdown'
            )
        except:
            pass

async def complete_raid(clan, raid_data, context):
    raid_type = raid_data['type']
    reward = RAID_TYPES[raid_type]
    add_crystals(clan, reward['reward_rc'])
    for member in get_clan_members(clan.id):
        session = Session()
        try:
            user = session.query(User).filter_by(user_id=member.user_id).first()
            if user:
                user.radfragments += reward['reward_rf']
                user.experience += reward['reward_exp']
                session.commit()
                await context.bot.send_message(
                    member.user_id,
                    f"🏆 *РЕЙД ОТРАЖЁН!*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Клан {clan.name} победил!\n"
                    f"💰 Награда: +{reward['reward_rf']} RF, +{reward['reward_exp']} опыта",
                    parse_mode='Markdown'
                )
        except:
            pass
        finally:
            Session.remove()
    if f'raid_{clan.id}' in context.bot_data:
        del context.bot_data[f'raid_{clan.id}']


# ==================== ШАХТА ====================

def get_mine_cooldown(clan, user_id):
    resources = get_resources(clan)
    return resources.get('mine_cooldowns', {}).get(str(user_id))

def set_mine_cooldown(clan, user_id, cooldown_until):
    resources = get_resources(clan)
    if 'mine_cooldowns' not in resources:
        resources['mine_cooldowns'] = {}
    resources['mine_cooldowns'][str(user_id)] = cooldown_until.isoformat()
    save_resources(clan, resources)

async def mine(update, context, clan):
    user_id = update.effective_user.id
    cooldown_until = get_mine_cooldown(clan, user_id)
    if cooldown_until:
        cooldown_time = datetime.fromisoformat(cooldown_until)
        if cooldown_time > datetime.now():
            remaining = cooldown_time - datetime.now()
            hours = remaining.seconds // 3600
            await update.message.reply_text(f"⏰ Шахта восстановится через {hours} часов.")
            return
    level = get_building_level(clan, 'mine')
    if level == 0:
        await update.message.reply_text("❌ В клане нет шахты!")
        return
    effects = BUILDING_EFFECTS['mine']
    bonus = LEVEL_BONUS.get(level, 1)
    crystals = random.randint(int(effects['crystals_min'] * bonus), int(effects['crystals_max'] * bonus))
    add_crystals(clan, crystals)
    chest_chances = effects['chest_chances']
    r = random.random() * 100
    if r < chest_chances[0]:
        chest_found = 'common'
    elif r < chest_chances[0] + chest_chances[1]:
        chest_found = 'rare'
    elif r < chest_chances[0] + chest_chances[1] + chest_chances[2]:
        chest_found = 'epic'
    else:
        chest_found = 'legendary'
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if user:
            if chest_found == 'common':
                user.chest_common += 1
            elif chest_found == 'rare':
                user.chest_rare += 1
            elif chest_found == 'epic':
                user.chest_epic += 1
            elif chest_found == 'legendary':
                user.chest_legendary += 1
            session.commit()
    finally:
        Session.remove()
    cooldown_hours = random.randint(24, 96)
    set_mine_cooldown(clan, user_id, datetime.now() + timedelta(hours=cooldown_hours))
    chest_names = {'common': '🟢 Обычный', 'rare': '🔵 Редкий', 'epic': '🟣 Эпический', 'legendary': '🟠 Легендарный'}
    await update.message.reply_text(
        f"⛏️ *Шахта*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Найдено кристаллов: +{crystals}\n"
        f"🎁 Сундук: {chest_names.get(chest_found, chest_found)}\n"
        f"⏰ Следующий поход через {cooldown_hours} часов.",
        parse_mode='Markdown'
    )


# ==================== ОСНОВНЫЕ КОМАНДЫ ====================

async def city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главная команда города (с обработкой подкоманд)"""
    if not context.args:
        session = Session()
        try:
            user = session.query(User).filter_by(user_id=update.effective_user.id).first()
            if not user or not user.clan_id:
                await update.message.reply_text("❌ Вы не в клане!")
                return
            
            clan = session.query(Clan).filter_by(id=user.clan_id).first()
            if not clan:
                await update.message.reply_text("❌ Клан не найден!")
                return
            
            sync_clan_crystals(clan)
            
            if clan.city_level == 0:
                if clan.leader_id != user.user_id:
                    await update.message.reply_text("❌ Только лидер клана может создать город!")
                    return
                
                clan.city_level = 1
                set_building_level(clan, 'residence', 1, 4, 4)
                save_resources(clan, {'crystals': clan.treasury_crystals, 'storage': {}})
                session.commit()
                
                await update.message.reply_text(
                    "🏰 *Клановый город создан!*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "📝 *Команды:*\n"
                    "• `/city` — это меню\n"
                    "• `/city map` — карта города\n"
                    "• `/city levels` — доступные уровни зданий\n"
                    "• `/city build [здание] [клетка]` — построить\n"
                    "• `/city upgrade [здание]` — улучшить\n"
                    "• `/city craft [предмет] [кол-во]` — произвести\n"
                    "• `/city mine` — шахта\n"
                    "• `/city raid` — отразить атаку\n\n"
                    "🏛️ *Доступные здания:*\n"
                    "• банк (100) — доход в казну\n"
                    "• мастерская (80) — расходники\n"
                    "• завод (150) — броня и оружие\n"
                    "• склад (50) — хранилище\n"
                    "• жк (100) — жилой комплекс\n"
                    "• вышка (50) — защита\n"
                    "• шахта (120) — кристаллы\n\n"
                    "📍 Пример: `/city build банк А1`",
                    parse_mode='Markdown'
                )
                return
            
            resources = get_resources(clan)
            buildings = get_buildings(clan)
            residence_level = get_residence_level(clan)
            
            text = f"🏰 *Клановый город {clan.name}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📊 *Резиденция:* {residence_level} ур.\n"
            text += f"💎 *Кристаллов:* {clan.treasury_crystals}\n"
            text += f"📦 *Склад:* {get_storage_used(clan)}/{get_storage_capacity(clan)}\n"
            
            if buildings:
                text += "\n🏛️ *Здания:*\n"
                for b_data in buildings.values():
                    b_type = b_data.get('type')
                    level = b_data.get('level', 1)
                    name_ru = BUILDING_NAMES_RU.get(b_type, b_type)
                    text += f"• {name_ru} (ур.{level})\n"
            
            text += "\n📝 *Команды:*\n"
            text += "• `/city map` — карта города\n"
            text += "• `/city levels` — доступные уровни зданий\n"
            text += "• `/city build [здание] [клетка]` — построить\n"
            text += "• `/city upgrade [здание]` — улучшить\n"
            text += "• `/city craft [предмет] [кол-во]` — произвести\n"
            text += "• `/city mine` — шахта\n"
            text += "• `/city raid` — отразить атаку"
            
            await send_to_private(update, context, text)
        finally:
            Session.remove()
        return
    
    subcommand = context.args[0].lower()
    
    if subcommand == 'map':
        await city_map(update, context)
    elif subcommand == 'levels':
        await city_levels(update, context)
    elif subcommand == 'build':
        context.args = context.args[1:]
        await clan_build(update, context)
    elif subcommand == 'upgrade':
        context.args = context.args[1:]
        await clan_upgrade(update, context)
    elif subcommand == 'craft':
        context.args = context.args[1:]
        await clan_craft(update, context)
    elif subcommand == 'mine':
        await clan_mine(update, context)
    elif subcommand == 'raid':
        await clan_raid(update, context)
    else:
        await update.message.reply_text("❌ Неизвестная подкоманда. Доступно: map, levels, build, upgrade, craft, mine, raid")


async def city_levels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать доступные уровни зданий в зависимости от резиденции"""
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не в клане!")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan or clan.city_level == 0:
            await update.message.reply_text("🏰 Город ещё не создан. Лидер может создать его командой `/city`", parse_mode='Markdown')
            return
        
        residence_level = get_residence_level(clan)
        
        text = f"🏛️ *Уровни зданий* (резиденция {residence_level} ур.)\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        max_res = 4
        text += f"• 🏰 Резиденция: {residence_level}/{max_res}\n"
        
        for building_type, name_ru in BUILDING_NAMES_RU.items():
            if building_type == 'residence':
                continue
            
            current_level = get_building_level(clan, building_type)
            max_level = 3
            limit = BUILDING_LIMITS.get(building_type, {}).get(residence_level, 0)
            
            text += f"• {get_tile_symbol(building_type)} {name_ru}: {current_level}/{max_level} ур."
            if limit > 0:
                text += f" (построено: {get_building_count(clan, building_type)}/{limit})\n"
            else:
                min_level = 1
                for lvl, lim in BUILDING_LIMITS.get(building_type, {}).items():
                    if lim > 0:
                        min_level = lvl
                        break
                text += f" (откроется на {min_level} ур. резиденции)\n"
        
        text += "\n💡 *Совет:* улучшайте резиденцию, чтобы открыть новые здания и увеличить лимиты!"
        
        await send_to_private(update, context, text)
    finally:
        Session.remove()


async def city_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать карту кланового города"""
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не в клане!")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan or clan.city_level == 0:
            await update.message.reply_text("🏰 Город ещё не создан. Лидер может создать его командой `/city`", parse_mode='Markdown')
            return
        
        buildings = get_buildings(clan)
        grid = [[MAP_TILE_EMPTY for _ in range(MAP_COLS)] for _ in range(MAP_ROWS)]
        
        for b_data in buildings.values():
            row = b_data.get('row')
            col = b_data.get('col')
            if row is not None and col is not None:
                grid[row][col] = get_tile_symbol(b_data.get('type'))
        
        letters = "   " + " ".join([chr(ord('А') + i) for i in range(MAP_COLS)])
        
        text = f"🗺️ *Карта города {clan.name}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n```\n{letters}\n"
        
        for i in range(MAP_ROWS):
            row_text = f"{i+1:2} " + " ".join(grid[i])
            text += row_text + "\n"
        
        text += "```\n\n📝 *Легенда:*\n"
        text += "⬜ — пусто, 🏰 — резиденция, 🏦 — банк, 🔧 — мастерская\n"
        text += "🏭 — завод, 📦 — склад, 🏘️ — жк, 🗼 — вышка, ⛏️ — шахта\n\n"
        text += "🏛️ *Ваши здания:*\n"
        
        for b_data in buildings.values():
            b_type = b_data.get('type')
            level = b_data.get('level', 1)
            row = b_data.get('row')
            col = b_data.get('col')
            cell = get_cell_name(row, col) if row is not None and col is not None else '?'
            name_ru = BUILDING_NAMES_RU.get(b_type, b_type)
            text += f"• {name_ru} (ур.{level}) — {cell}\n"
        
        if not buildings:
            text += "• пока нет\n"
        
        text += f"\n💎 *Кристаллов:* {clan.treasury_crystals}"
        text += f"\n📦 *Склад:* {get_storage_used(clan)}/{get_storage_capacity(clan)}"
        
        await send_to_private(update, context, text)
    finally:
        Session.remove()


async def clan_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Построить здание на указанной клетке"""
    if len(context.args) < 2:
        await update.message.reply_text("🏗️ *Строительство*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n📝 `/city build [здание] [клетка]`\nПример: `/city build банк А1`\n\nДоступные здания:\n• банк (100)\n• мастерская (80)\n• завод (150)\n• склад (50)\n• жк (100)\n• вышка (50)\n• шахта (120)", parse_mode='Markdown')
        return
    
    building_ru = context.args[0].lower()
    building_type = BUILDING_NAMES_EN.get(building_ru)
    if not building_type:
        await update.message.reply_text("❌ Неизвестное здание. Доступны: банк, мастерская, завод, склад, жк, вышка, шахта")
        return
    
    cell = context.args[1].upper()
    coords = get_cell_coords(cell)
    if not coords:
        await update.message.reply_text("❌ Неверный формат клетки. Пример: А1, Б2, В3")
        return
    
    row, col = coords
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не в клане!")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan or clan.city_level == 0:
            await update.message.reply_text("🏰 Город ещё не создан. Лидер может создать его командой `/city`", parse_mode='Markdown')
            return
        
        if clan.leader_id != user.user_id:
            await update.message.reply_text("❌ Только лидер клана может строить!")
            return
        
        success, msg = build_building(clan, building_type, row, col)
        if success:
            await update.message.reply_text(f"✅ *{BUILDING_NAMES_RU.get(building_type, building_type)} построен на клетке {cell}!*", parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        session.commit()
    finally:
        Session.remove()


async def clan_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Улучшить здание"""
    if not context.args:
        await update.message.reply_text("⬆️ *Улучшение*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n📝 `/city upgrade [здание]`\nДоступные здания:\n• резиденция, банк, мастерская, завод, склад, жк, вышка, шахта", parse_mode='Markdown')
        return
    
    building_ru = context.args[0].lower()
    building_type = BUILDING_NAMES_EN.get(building_ru, building_ru)
    if building_type not in BUILDING_PRICES:
        await update.message.reply_text("❌ Неизвестное здание")
        return
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не в клане!")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan or clan.city_level == 0:
            await update.message.reply_text("🏰 Город ещё не создан. Лидер может создать его командой `/city`", parse_mode='Markdown')
            return
        
        if clan.leader_id != user.user_id:
            await update.message.reply_text("❌ Только лидер клана может улучшать!")
            return
        
        success, result = upgrade_building(clan, building_type)
        if success:
            await update.message.reply_text(f"✅ *{BUILDING_NAMES_RU.get(building_type, building_type)} улучшен до {result} уровня!*", parse_mode='Markdown')
        else:
            await update.message.reply_text(result, parse_mode='Markdown')
        
        session.commit()
    finally:
        Session.remove()


async def clan_craft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запустить производство"""
    if len(context.args) < 2:
        await update.message.reply_text("🔨 *Производство*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n📝 `/city craft [предмет] [кол-во]`\nДоступно: аптечка, энергетик, редуктор, броня1-5, ружьё, гарпун, винтовка, гаусс", parse_mode='Markdown')
        return
    
    recipe_name = context.args[0].lower()
    try:
        count = int(context.args[1])
        if count < 1 or count > 100:
            await update.message.reply_text("❌ Количество от 1 до 100")
            return
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не в клане!")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan or clan.city_level == 0:
            await update.message.reply_text("🏰 Город ещё не создан. Лидер может создать его командой `/city`", parse_mode='Markdown')
            return
        
        if clan.leader_id != user.user_id:
            await update.message.reply_text("❌ Только лидер клана может запускать производство!")
            return
        
        success, msg = start_production(clan, recipe_name, count)
        await update.message.reply_text(msg, parse_mode='Markdown')
        
        session.commit()
    finally:
        Session.remove()


async def clan_mine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сходить в шахту"""
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не в клане!")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan or clan.city_level == 0:
            await update.message.reply_text("🏰 Город ещё не создан. Лидер может создать его командой `/city`", parse_mode='Markdown')
            return
        
        await mine(update, context, clan)
        session.commit()
    finally:
        Session.remove()


async def clan_raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отразить атаку мутантов"""
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        if not user or not user.clan_id:
            await update.message.reply_text("❌ Вы не в клане!")
            return
        
        clan = session.query(Clan).filter_by(id=user.clan_id).first()
        if not clan or clan.city_level == 0:
            await update.message.reply_text("🏰 Город ещё не создан. Лидер может создать его командой `/city`", parse_mode='Markdown')
            return
        
        raid_data = context.bot_data.get(f'raid_{clan.id}')
        if not raid_data:
            await update.message.reply_text("❌ Сейчас нет активного рейда!")
            return
        
        if user.user_id not in raid_data['participants']:
            raid_data['participants'].append(user.user_id)
            context.bot_data[f'raid_{clan.id}'] = raid_data
            await update.message.reply_text("✅ Вы записаны на отражение рейда!")
        else:
            await update.message.reply_text("✅ Вы уже участвуете в рейде!")
        
        if len(raid_data['participants']) >= raid_data['required']:
            await complete_raid(clan, raid_data, context)
            await update.message.reply_text("🏆 *РЕЙД ОТРАЖЁН!* Награда получена!", parse_mode='Markdown')
    finally:
        Session.remove()


# ==================== ФОНОВЫЕ ЗАДАЧИ ====================

async def check_production_complete(context):
    session = Session()
    try:
        clans = session.query(Clan).filter(Clan.city_production != '[]').all()
        now = datetime.now()
        for clan in clans:
            production = get_production(clan)
            changed = False
            for item in production[:]:
                finish = datetime.fromisoformat(item['finish'])
                if finish <= now:
                    add_to_storage(clan, item['recipe'], 1)
                    production.remove(item)
                    changed = True
            if changed:
                save_production(clan, production)
                session.commit()
    finally:
        Session.remove()

async def check_raid_trigger(context):
    if not is_raid_time():
        return
    session = Session()
    try:
        clans = session.query(Clan).filter(Clan.city_level > 0).all()
        for clan in clans:
            if clan.last_raid and datetime.now() - clan.last_raid < timedelta(days=7):
                continue
            if random.random() < 0.2:
                clan.last_raid = datetime.now()
                session.commit()
                await start_raid(clan, context)
    finally:
        Session.remove()

async def check_daily_bonus(context):
    session = Session()
    try:
        clans = session.query(Clan).filter(Clan.city_level > 0).all()
        for clan in clans:
            bank_level = get_building_level(clan, 'bank')
            if bank_level > 0:
                bonus_percent = BUILDING_EFFECTS['bank']['interest'] * LEVEL_BONUS.get(bank_level, 1)
                member_bonus = BUILDING_EFFECTS['bank']['member_bonus'] * LEVEL_BONUS.get(bank_level, 1)
                current = clan.treasury_crystals
                interest = int(current * bonus_percent / 100)
                members_count = get_clan_members_count(clan.id)
                member_interest = int(members_count * member_bonus)
                add_crystals(clan, interest + member_interest)
                session.commit()
    finally:
        Session.remove()
