# utils.py - Утилиты и механики
# Версия: 2.0.0

import json
import random
from datetime import datetime, timedelta

# Импортируем из config, а не из core!
from config import logger, MAX_MEDKITS, MAX_LEVEL
from database import Session, User

# ==================== ИНВЕНТАРЬ ====================

def get_inventory(user):
    """Получить инвентарь пользователя"""
    return json.loads(user.inventory) if user.inventory else []

def save_inventory(user, inventory):
    """Сохранить инвентарь"""
    user.inventory = json.dumps(inventory)

def get_equipped(user):
    """Получить экипировку"""
    return json.loads(user.equipped) if user.equipped else {}

def save_equipped(user, equipped):
    """Сохранить экипировку"""
    user.equipped = json.dumps(equipped)

def add_item_to_inventory(user, item_name, count=1, expires=None):
    """Добавить предмет в инвентарь"""
    inventory = get_inventory(user)
    for i in inventory:
        if i['item'] == item_name:
            i['count'] += count
            if expires and 'expires' not in i:
                i['expires'] = expires.isoformat() if expires else None
            save_inventory(user, inventory)
            return
    new_item = {'item': item_name, 'count': count}
    if expires:
        new_item['expires'] = expires.isoformat()
    inventory.append(new_item)
    save_inventory(user, inventory)

def remove_item_from_inventory(user, item_name, count=1):
    """Удалить предмет из инвентаря"""
    inventory = get_inventory(user)
    for i in inventory:
        if i['item'] == item_name:
            i['count'] -= count
            if i['count'] <= 0:
                inventory.remove(i)
            save_inventory(user, inventory)
            return True
    return False

def get_item_count(user, item_name):
    """Узнать количество предмета"""
    inventory = get_inventory(user)
    for i in inventory:
        if i['item'] == item_name:
            return i['count']
    return 0

# ==================== ДОСТУПНЫЕ ПРЕДМЕТЫ ====================
# Броня: броня1, броня2, броня3, броня4, броня5
# Оружие: ружье, гарпун, винтовка, гаусс
# Расходники: аптечка, энергетик, редуктор

# ==================== БОНУСЫ КЛАССОВ ====================

def apply_class_bonus(user, rc_gain, fragment_gain, exp_gain):
    """Применить бонусы от класса"""
    class_name = user.user_class if hasattr(user, 'user_class') else 'stalker'
    
    if class_name == 'military':
        rc_gain = int(rc_gain * 1.2)
        exp_gain = int(exp_gain * 1.3)
        fragment_gain = int(fragment_gain * 0.7)
    elif class_name == 'bandit':
        rc_gain = int(rc_gain * 1.15)
        fragment_gain = int(fragment_gain * 1.4)
        exp_gain = int(exp_gain * 0.75)
    elif class_name == 'scientist':
        exp_gain = int(exp_gain * 1.5)
        fragment_gain = int(fragment_gain * 1.25)
        rc_gain = int(rc_gain * 0.8)
    
    return rc_gain, fragment_gain, exp_gain

# ==================== ВЫЖИВАЕМОСТЬ ====================

def calculate_survive_chance(user, target_level):
    """Расчёт шанса выжить в охоте"""
    armor_bonus = {
        'light': 25,
        'heavy': 40,
        'tactical': 50,
        'reinforced': 60,
        'power': 75
    }
    
    base = 10
    equipped = get_equipped(user)
    armor = equipped.get('armor')
    
    if armor:
        armor_map = {
            'броня1': 'light', 'броня2': 'heavy', 'броня3': 'tactical',
            'броня4': 'reinforced', 'броня5': 'power'
        }
        armor_type = armor_map.get(armor)
        if armor_type and armor_type in armor_bonus:
            base = armor_bonus[armor_type]
    
    if target_level == 3:
        base = min(100, base + 25)
    
    # Обычная аптечка +25%
    if get_item_count(user, 'аптечка') > 0:
        base = min(100, base + 25)
    
    return base

# ==================== ДОСТИЖЕНИЯ ====================

def check_achievements(user, session):
    """Проверка и выдача достижений"""
    achievements = json.loads(user.achievements) if user.achievements else []
    new_achievements = []
    
    if user.total_collects >= 10 and 'добытчик' not in achievements:
        new_achievements.append('добытчик')
    if user.level >= 10 and 'кандидат' not in achievements:
        new_achievements.append('кандидат')
    if user.level >= 50 and 'мастер' not in achievements:
        new_achievements.append('мастер')
    if user.level >= MAX_LEVEL and 'легенда' not in achievements:
        new_achievements.append('легенда')
    if user.daily_streak >= 7 and 'терпила' not in achievements:
        new_achievements.append('терпила')
    if user.daily_streak >= 30 and 'старатель' not in achievements:
        new_achievements.append('старатель')
    if user.total_purchases >= 10 and 'постоянный_клиент' not in achievements:
        new_achievements.append('постоянный_клиент')
    if user.radcoins >= 100000 and 'миллионер' not in achievements:
        new_achievements.append('миллионер')
    
    if new_achievements:
        achievements.extend(new_achievements)
        user.achievements = json.dumps(achievements)
        session.commit()
        return new_achievements
    return []

# ==================== ОПЫТ ДЛЯ УРОВНЯ ====================

def get_exp_for_level(level):
    """Опыт для повышения уровня"""
    if level <= 1:
        return 0
    if level > MAX_LEVEL:
        level = MAX_LEVEL
    total = 0
    for i in range(2, level + 1):
        total += 100 + (i - 2) * 50
    return total

def get_user_by_username(session, username):
    """Найти пользователя по username (без учёта регистра)"""
    from sqlalchemy import func
    return session.query(User).filter(func.lower(User.username) == username.lower()).first()
