# city.py - Клановые города
# Версия: 1.0.0

import json
import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from config import logger
from database import Session, User, Clan
from core import is_admin, send_to_private
from utils import add_item_to_inventory, get_item_count


# ==================== КОНСТАНТЫ ====================

# Цены на здания и улучшения (в клановых кристаллах)
BUILDING_PRICES = {
    'residence': {1: 0, 2: 200, 3: 500, 4: 1200},  # резиденция (1 уровень бесплатно)
    'bank': {1: 100, 2: 300, 3: 700},
    'workshop': {1: 80, 2: 250, 3: 600},
    'factory': {1: 150, 2: 400, 3: 1000},
    'storage': {1: 50, 2: 150, 3: 400},
    'house': {1: 100, 2: 300, 3: 800},
    'tower': {1: 50, 2: 150, 3: 400},
    'mine': {1: 120, 2: 350, 3: 900},
}

# Лимиты на количество зданий (по уровням резиденции)
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

# Базовые эффекты зданий (на 1 уровень)
BUILDING_EFFECTS = {
    'bank': {'interest': 1, 'member_bonus': 0.25},
    'workshop': {'speed': 3},  # часы на аптечку
    'factory': {'speed': 3},    # часы на броню1
    'storage': {'capacity': 25},
    'house': {'members': 3},
    'tower': {'survive': 5, 'raid_notice': 1},
    'mine': {'crystals_min': 10, 'crystals_max': 50, 'chest_chances': [80, 10, 9, 1]},
}

# Бонусы за уровень (множители)
LEVEL_BONUS = {
    1: 1.0,
    2: 2.0,
    3: 4.0,
}

# Производственные рецепты (время в часах на 1 шт)
RECIPES = {
    # Мастерская (расходники)
    'medkit': {'building': 'workshop', 'time_base': 3, 'cost': {'rf': 1}},
    'energy': {'building': 'workshop', 'time_base': 3, 'cost': {'rf': 2}},
    'reducer': {'building': 'workshop', 'time_base': 3, 'cost': {'rf': 5}},
    # Завод (оружие и броня)
    'armor1': {'building': 'factory', 'time_base': 3, 'cost': {'rf': 5, 'rc': 100}},
    'armor2': {'building': 'factory', 'time_base': 6, 'cost': {'rf': 10, 'rc': 250}},
    'armor3': {'building': 'factory', 'time_base': 12, 'cost': {'rf': 20, 'rc': 500}},
    'armor4': {'building': 'factory', 'time_base': 24, 'cost': {'rf': 40, 'rc': 1000}},
    'armor5': {'building': 'factory', 'time_base': 48, 'cost': {'rf': 80, 'rc': 2500}},
    'shotgun': {'building': 'factory', 'time_base': 2, 'cost': {'rf': 3, 'rc': 50}},
    'harpoon': {'building': 'factory', 'time_base': 4, 'cost': {'rf': 6, 'rc': 100}},
    'rifle': {'building': 'factory', 'time_base': 12, 'cost': {'rf': 15, 'rc': 500}},
    'gauss': {'building': 'factory', 'time_base': 96, 'cost': {'rf': 50, 'rc': 2000}},
}

# Рейды мутантов
RAID_TYPES = {
    'small': {'required': 1, 'reward_rc': 1000, 'reward_rf': 50, 'reward_exp': 100},
    'medium': {'required': 0.5, 'reward_rc': 5000, 'reward_rf': 200, 'reward_exp': 500},
    'large': {'required': 0.7, 'reward_rc': 10000, 'reward_rf': 500, 'reward_exp': 1000},
}
RAID_WEEKDAYS = [3, 4, 5, 6]  # чт, пт, сб, вс
RAID_HOURS = range(12, 22)    # 12:00 - 21:00


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_buildings(clan):
    """Получить словарь зданий клана"""
    return json.loads(clan.city_buildings) if clan.city_buildings else {}

def save_buildings(clan, buildings):
    """Сохранить здания клана"""
    clan.city_buildings = json.dumps(buildings)

def get_production(clan):
    """Получить очередь производства"""
    return json.loads(clan.city_production) if clan.city_production else []

def save_production(clan, production):
    """Сохранить очередь производства"""
    clan.city_production = json.dumps(production)

def get_resources(clan):
    """Получить ресурсы клана"""
    return json.loads(clan.city_resources) if clan.city_resources else {'crystals': 0, 'storage': {}}

def save_resources(clan, resources):
    """Сохранить ресурсы клана"""
    clan.city_resources = json.dumps(resources)

def get_building_level(clan, building_type):
    """Получить уровень здания"""
    buildings = get_buildings(clan)
    return buildings.get(building_type, {}).get('level', 0)

def set_building_level(clan, building_type, level):
    """Установить уровень здания"""
    buildings = get_buildings(clan)
    if building_type not in buildings:
        buildings[building_type] = {}
    buildings[building_type]['level'] = level
    save_buildings(clan, buildings)

def get_building_count(clan, building_type):
    """Получить количество зданий данного типа"""
    buildings = get_buildings(clan)
    return len([b for b in buildings.values() if b.get('type') == building_type])

def get_residence_level(clan):
    """Получить уровень резиденции"""
    return get_building_level(clan, 'residence')

def get_storage_capacity(clan):
    """Рассчитать общую вместимость складов"""
    buildings = get_buildings(clan)
    capacity = 0
    for b_id, b_data in buildings.items():
        if b_data.get('type') == 'storage':
            level = b_data.get('level', 1)
            capacity += BUILDING_EFFECTS['storage']['capacity'] * LEVEL_BONUS.get(level, 1)
    return capacity

def get_storage_used(clan):
    """Рассчитать занятое место на складах"""
    resources = get_resources(clan)
    return sum(resources.get('storage', {}).values())

def can_add_to_storage(clan, item_name, count):
    """Проверить, поместится ли предмет на склад"""
    capacity = get_storage_capacity(clan)
    used = get_storage_used(clan)
    return used + count <= capacity

def add_to_storage(clan, item_name, count):
    """Добавить предмет на склад клана"""
    resources = get_resources(clan)
    if 'storage' not in resources:
        resources['storage'] = {}
    resources['storage'][item_name] = resources['storage'].get(item_name, 0) + count
    save_resources(clan, resources)

def remove_from_storage(clan, item_name, count):
    """Удалить предмет со склада клана"""
    resources = get_resources(clan)
    if resources['storage'].get(item_name, 0) >= count:
        resources['storage'][item_name] -= count
        if resources['storage'][item_name] <= 0:
            del resources['storage'][item_name]
        save_resources(clan, resources)
        return True
    return False

def get_clan_members_count(clan_id):
    """Получить количество участников клана"""
    session = Session()
    try:
        count = session.query(User).filter_by(clan_id=clan_id).count()
        return count
    finally:
        Session.remove()

def get_clan_members(clan_id):
    """Получить список участников клана"""
    session = Session()
    try:
        members = session.query(User).filter_by(clan_id=clan_id).all()
        return members
    finally:
        Session.remove()

def can_upgrade(clan, building_type):
    """Проверить, можно ли улучшить здание"""
    residence_level = get_residence_level(clan)
    current_level = get_building_level(clan, building_type)
    max_level = 3
    if building_type == 'residence':
        max_level = 4
    
    if current_level >= max_level:
        return False, "❌ Максимальный уровень достигнут"
    
    next_level = current_level + 1
    if next_level > residence_level and building_type != 'residence':
        return False, f"❌ Нужно улучшить резиденцию до {next_level} уровня"
    
    price = BUILDING_PRICES.get(building_type, {}).get(next_level)
    resources = get_resources(clan)
    if resources.get('crystals', 0) < price:
        return False, f"❌ Не хватает кристаллов. Нужно: {price}"
    
    return True, next_level

def upgrade_building(clan, building_type):
    """Улучшить здание"""
    can, next_level = can_upgrade(clan, building_type)
    if not can:
        return False, next_level
    
    price = BUILDING_PRICES.get(building_type, {}).get(next_level)
    resources = get_resources(clan)
    resources['crystals'] -= price
    set_building_level(clan, building_type, next_level)
    save_resources(clan, resources)
    
    return True, next_level

def can_build(clan, building_type):
    """Проверить, можно ли построить новое здание"""
    residence_level = get_residence_level(clan)
    current_count = get_building_count(clan, building_type)
    max_count = BUILDING_LIMITS.get(building_type, {}).get(residence_level, 0)
    
    if current_count >= max_count:
        return False, f"❌ Достигнут лимит зданий этого типа ({max_count})"
    
    price = BUILDING_PRICES.get(building_type, {}).get(1)
    resources = get_resources(clan)
    if resources.get('crystals', 0) < price:
        return False, f"❌ Не хватает кристаллов. Нужно: {price}"
    
    return True, price

def build_building(clan, building_type):
    """Построить новое здание"""
    can, price = can_build(clan, building_type)
    if not can:
        return False, price
    
    resources = get_resources(clan)
    resources['crystals'] -= price
    
    buildings = get_buildings(clan)
    new_id = f"{building_type}_{len(buildings)}"
    buildings[new_id] = {'type': building_type, 'level': 1}
    save_buildings(clan, buildings)
    save_resources(clan, resources)
    
    return True, new_id


# ==================== ПРОИЗВОДСТВО ====================

def get_production_time(clan, recipe_name):
    """Получить время производства для рецепта с учётом уровней зданий"""
    recipe = RECIPES.get(recipe_name)
    if not recipe:
        return None
    
    building_type = recipe['building']
    time_base = recipe['time_base']
    
    # Получаем средний уровень зданий этого типа
    buildings = get_buildings(clan)
    levels = [b['level'] for b in buildings.values() if b.get('type') == building_type]
    if not levels:
        return None
    
    avg_level = sum(levels) / len(levels)
    # Время уменьшается с уровнем: базовое / уровень (но не быстрее чем в 4 раза)
    time_hours = time_base / max(1, avg_level)
    return max(1, int(time_hours))

def can_start_production(clan, recipe_name, count):
    """Проверить, можно ли запустить производство"""
    recipe = RECIPES.get(recipe_name)
    if not recipe:
        return False, "❌ Неизвестный рецепт"
    
    building_type = recipe['building']
    buildings = [b for b in get_buildings(clan).values() if b.get('type') == building_type]
    if not buildings:
        return False, f"❌ Нет здания {building_type}"
    
    # Проверяем, достаточно ли ресурсов у клана для оплаты
    resources = get_resources(clan)
    for res, amount in recipe.get('cost', {}).items():
        if resources.get(res, 0) < amount * count:
            return False, f"❌ Не хватает {res}: нужно {amount * count}"
    
    # Проверяем, поместится ли результат на склад
    if not can_add_to_storage(clan, recipe_name, count):
        capacity = get_storage_capacity(clan)
        used = get_storage_used(clan)
        return False, f"❌ На складе нет места. Свободно: {capacity - used}"
    
    return True, None

def start_production(clan, recipe_name, count):
    """Запустить производство"""
    can, msg = can_start_production(clan, recipe_name, count)
    if not can:
        return False, msg
    
    recipe = RECIPES[recipe_name]
    time_hours = get_production_time(clan, recipe_name)
    
    # Списываем ресурсы
    resources = get_resources(clan)
    for res, amount in recipe.get('cost', {}).items():
        resources[res] = resources.get(res, 0) - (amount * count)
    save_resources(clan, resources)
    
    # Добавляем в очередь
    production = get_production(clan)
    now = datetime.now()
    for i in range(count):
        production.append({
            'recipe': recipe_name,
            'started': now.isoformat(),
            'finish': (now + timedelta(hours=time_hours)).isoformat()
        })
    save_production(clan, production)
    
    return True, f"✅ Производство запущено! {count} шт. Готово через {time_hours} ч."


# ==================== РЕЙДЫ ====================

def is_raid_time():
    """Проверить, может ли сейчас быть рейд"""
    now = datetime.now()
    return now.weekday() in RAID_WEEKDAYS and now.hour in RAID_HOURS

def get_random_raid_type():
    """Получить случайный тип рейда"""
    # 60% малый, 30% средний, 10% большой
    r = random.random()
    if r < 0.6:
        return 'small'
    elif r < 0.9:
        return 'medium'
    else:
        return 'large'

def get_raid_required_count(clan, raid_type):
    """Сколько участников нужно для отражения рейда"""
    members_count = get_clan_members_count(clan.id)
    required_ratio = RAID_TYPES[raid_type]['required']
    if raid_type == 'small':
        return 1
    elif raid_type == 'medium':
        return max(1, int(members_count * required_ratio))  # округление вниз
    else:  # large
        return max(1, int(members_count * required_ratio) + (1 if members_count * required_ratio % 1 > 0 else 0))  # округление вверх

def get_raid_participants_count(clan):
    """Сколько участников клана уже подтвердили участие в рейде"""
    # Временно храним в bot_data
    return 0  # TODO: реализовать

async def start_raid(clan, context):
    """Запустить рейд для клана"""
    raid_type = get_random_raid_type()
    required = get_raid_required_count(clan, raid_type)
    
    # Уведомляем клан
    members = get_clan_members(clan.id)
    raid_data = {
        'type': raid_type,
        'required': required,
        'started': datetime.now().isoformat(),
        'participants': []
    }
    
    # Сохраняем в bot_data или в БД
    context.bot_data[f'raid_{clan.id}'] = raid_data
    
    for member in members:
        try:
            await context.bot.send_message(
                member.user_id,
                f"🏰 *РЕЙД МУТАНТОВ!*\n\n"
                f"Клан {clan.name} атакован!\n"
                f"Тип: {raid_type}\n"
                f"Требуется участников: {required}\n"
                f"Для участия: `/raid`",
                parse_mode='Markdown'
            )
        except:
            pass

def get_raid_reward(raid_type):
    """Получить награду за рейд"""
    return RAID_TYPES[raid_type]

async def complete_raid(clan, raid_data, context):
    """Завершить рейд с наградой"""
    raid_type = raid_data['type']
    reward = get_raid_reward(raid_type)
    
    # Награда клану
    resources = get_resources(clan)
    resources['crystals'] += reward['reward_rc']
    save_resources(clan, resources)
    
    # Награда участникам
    members = get_clan_members(clan.id)
    for member in members:
        session = Session()
        try:
            user = session.query(User).filter_by(user_id=member.user_id).first()
            if user:
                user.radfragments += reward['reward_rf']
                user.experience += reward['reward_exp']
                session.commit()
                await context.bot.send_message(
                    member.user_id,
                    f"🏆 *РЕЙД ОТРАЖЁН!*\n\n"
                    f"Клан {clan.name} победил!\n"
                    f"💰 Награда: +{reward['reward_rf']} RF, +{reward['reward_exp']} опыта",
                    parse_mode='Markdown'
                )
        except:
            pass
        finally:
            Session.remove()
    
    # Удаляем данные рейда
    if f'raid_{clan.id}' in context.bot_data:
        del context.bot_data[f'raid_{clan.id}']


# ==================== ШАХТА ====================

def get_mine_level(clan):
    """Получить уровень шахты"""
    return get_building_level(clan, 'mine')

def get_mine_cooldown(clan, user_id):
    """Получить кулдаун шахты для игрока"""
    resources = get_resources(clan)
    return resources.get('mine_cooldowns', {}).get(str(user_id))

def set_mine_cooldown(clan, user_id, cooldown_until):
    """Установить кулдаун шахты для игрока"""
    resources = get_resources(clan)
    if 'mine_cooldowns' not in resources:
        resources['mine_cooldowns'] = {}
    resources['mine_cooldowns'][str(user_id)] = cooldown_until.isoformat()
    save_resources(clan, resources)

async def mine(update: Update, context: ContextTypes.DEFAULT_TYPE, clan):
    """Сходить в шахту"""
    user_id = update.effective_user.id
    
    # Проверяем кулдаун
    cooldown_until = get_mine_cooldown(clan, user_id)
    if cooldown_until:
        cooldown_time = datetime.fromisoformat(cooldown_until)
        if cooldown_time > datetime.now():
            remaining = cooldown_time - datetime.now()
            hours = remaining.seconds // 3600
            await update.message.reply_text(f"⏰ Шахта восстановится через {hours} часов.")
            return
    
    level = get_mine_level(clan)
    if level == 0:
        await update.message.reply_text("❌ В клане нет шахты!")
        return
    
    # Получаем награду
    effects = BUILDING_EFFECTS['mine']
    bonus = LEVEL_BONUS.get(level, 1)
    crystals_min = int(effects['crystals_min'] * bonus)
    crystals_max = int(effects['crystals_max'] * bonus)
    crystals = random.randint(crystals_min, crystals_max)
    
    # Кристаллы в казну клана
    resources = get_resources(clan)
    resources['crystals'] = resources.get('crystals', 0) + crystals
    save_resources(clan, resources)
    
    # Сундук
    chest_chances = effects['chest_chances']
    r = random.random() * 100
    chest_found = None
    if r < chest_chances[0]:
        chest_found = 'common'
    elif r < chest_chances[0] + chest_chances[1]:
        chest_found = 'rare'
    elif r < chest_chances[0] + chest_chances[1] + chest_chances[2]:
        chest_found = 'epic'
    else:
        chest_found = 'legendary'
    
    # Добавляем сундук игроку
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if user and chest_found:
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
    
    # Устанавливаем кулдаун (24-96 часов)
    cooldown_hours = random.randint(24, 96)
    cooldown_until = datetime.now() + timedelta(hours=cooldown_hours)
    set_mine_cooldown(clan, user_id, cooldown_until)
    
    await update.message.reply_text(
        f"⛏️ *Шахта*\n\n"
        f"Вы нашли {crystals} кристаллов в казну клана!\n"
        f"🎁 Сундук: {chest_found}\n"
        f"⏰ Следующий поход через {cooldown_hours} часов.",
        parse_mode='Markdown'
    )


# ==================== КОМАНДЫ ====================

async def clan_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню кланового города"""
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
        
        residence_level = get_residence_level(clan)
        resources = get_resources(clan)
        buildings = get_buildings(clan)
        
        text = f"🏰 *Клановый город {clan.name}*\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"📊 *Уровень резиденции:* {residence_level}\n"
        text += f"💎 *Кристаллов в казне:* {resources.get('crystals', 0)}\n"
        text += f"📦 *Склад:* {get_storage_used(clan)}/{get_storage_capacity(clan)}\n\n"
        
        text += "*🏛️ ЗДАНИЯ*\n"
        for b_id, b_data in buildings.items():
            b_type = b_data.get('type')
            level = b_data.get('level', 1)
            text += f"• {b_type}: ур.{level}\n"
        
        text += "\n📝 *Команды:*\n"
        text += "/clan_build [тип] — построить\n"
        text += "/clan_upgrade [тип] — улучшить\n"
        text += "/clan_produce [предмет] [кол-во] — произвести\n"
        text += "/clan_mine — сходить в шахту\n"
        text += "/clan_raid — отразить атаку"
        
        await send_to_private(update, context, text)
    finally:
        Session.remove()

async def clan_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Построить новое здание"""
    if not context.args:
        await update.message.reply_text("❌ /clan_build [тип]\nТипы: bank, workshop, factory, storage, house, tower, mine")
        return
    
    building_type = context.args[0].lower()
    if building_type not in BUILDING_PRICES:
        await update.message.reply_text("❌ Неизвестный тип здания")
        return
    
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
        
        if clan.leader_id != user.user_id:
            await update.message.reply_text("❌ Только лидер клана может строить!")
            return
        
        success, result = build_building(clan, building_type)
        if success:
            await update.message.reply_text(f"✅ *Здание {building_type} построено!*", parse_mode='Markdown')
        else:
            await update.message.reply_text(result, parse_mode='Markdown')
        
        session.commit()
    finally:
        Session.remove()

async def clan_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Улучшить здание"""
    if not context.args:
        await update.message.reply_text("❌ /clan_upgrade [тип]\nТипы: residence, bank, workshop, factory, storage, house, tower, mine")
        return
    
    building_type = context.args[0].lower()
    if building_type not in BUILDING_PRICES:
        await update.message.reply_text("❌ Неизвестный тип здания")
        return
    
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
        
        if clan.leader_id != user.user_id:
            await update.message.reply_text("❌ Только лидер клана может улучшать!")
            return
        
        success, result = upgrade_building(clan, building_type)
        if success:
            await update.message.reply_text(f"✅ *{building_type} улучшен до {result} уровня!*", parse_mode='Markdown')
        else:
            await update.message.reply_text(result, parse_mode='Markdown')
        
        session.commit()
    finally:
        Session.remove()

async def clan_produce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запустить производство"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ /clan_produce [предмет] [кол-во]\nДоступно: medkit, energy, reducer, armor1-5, shotgun, harpoon, rifle, gauss")
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
        if not clan:
            await update.message.reply_text("❌ Клан не найден!")
            return
        
        if clan.leader_id != user.user_id:
            await update.message.reply_text("❌ Только лидер клана может запускать производство!")
            return
        
        success, msg = start_production(clan, recipe_name, count)
        await update.message.reply_text(msg, parse_mode='Markdown')
        
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
        if not clan:
            await update.message.reply_text("❌ Клан не найден!")
            return
        
        raid_data = context.bot_data.get(f'raid_{clan.id}')
        if not raid_data:
            await update.message.reply_text("❌ Сейчас нет активного рейда!")
            return
        
        # Добавляем участника
        if user.user_id not in raid_data['participants']:
            raid_data['participants'].append(user.user_id)
            context.bot_data[f'raid_{clan.id}'] = raid_data
            await update.message.reply_text("✅ Вы записаны на отражение рейда!")
        else:
            await update.message.reply_text("✅ Вы уже участвуете в рейде!")
        
        # Проверяем, достаточно ли участников
        required = raid_data['required']
        current = len(raid_data['participants'])
        
        if current >= required:
            await complete_raid(clan, raid_data, context)
            await update.message.reply_text("🏆 *РЕЙД ОТРАЖЁН!* Награда получена!", parse_mode='Markdown')
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
        if not clan:
            await update.message.reply_text("❌ Клан не найден!")
            return
        
        await mine(update, context, clan)
        
        session.commit()
    finally:
        Session.remove()


# ==================== ФОНОВЫЕ ЗАДАЧИ ====================

async def check_production_complete(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет завершённые производства"""
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
                    # Производство завершено
                    recipe_name = item['recipe']
                    add_to_storage(clan, recipe_name, 1)
                    production.remove(item)
                    changed = True
            
            if changed:
                save_production(clan, production)
                session.commit()
    finally:
        Session.remove()

async def check_raid_trigger(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет, не пора ли запустить рейд"""
    if not is_raid_time():
        return
    
    session = Session()
    try:
        clans = session.query(Clan).filter(Clan.city_level > 0).all()
        for clan in clans:
            # Проверяем, не было ли недавнего рейда
            if clan.last_raid and datetime.now() - clan.last_raid < timedelta(days=7):
                continue
            
            # Рандомно запускаем рейд (шанс 20% в интервал)
            if random.random() < 0.2:
                clan.last_raid = datetime.now()
                session.commit()
                await start_raid(clan, context)
    finally:
        Session.remove()

async def check_daily_bonus(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневное начисление бонусов от банка"""
    session = Session()
    try:
        clans = session.query(Clan).filter(Clan.city_level > 0).all()
        for clan in clans:
            bank_level = get_building_level(clan, 'bank')
            if bank_level > 0:
                resources = get_resources(clan)
                bonus_percent = BUILDING_EFFECTS['bank']['interest'] * LEVEL_BONUS.get(bank_level, 1)
                member_bonus = BUILDING_EFFECTS['bank']['member_bonus'] * LEVEL_BONUS.get(bank_level, 1)
                
                # Бонус от текущей казны
                current = resources.get('crystals', 0)
                interest = int(current * bonus_percent / 100)
                
                # Бонус за участников
                members_count = get_clan_members_count(clan.id)
                member_interest = int(members_count * member_bonus)
                
                resources['crystals'] = resources.get('crystals', 0) + interest + member_interest
                save_resources(clan, resources)
                session.commit()
    finally:
        Session.remove()
