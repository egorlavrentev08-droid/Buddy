# config.py - Централизованные настройки и константы
# Версия: 2.0.0
# Без зависимостей от других модулей!

import logging
from datetime import datetime, timedelta

# ==================== НАСТРОЙКИ БОТА ====================
TOKEN = '8492718356:AAFWFI79XqRH5L2aSQYoOTOOpu5shlra4Wc'
ADMIN_CODE = '1252836169043217'
SUPER_ADMIN_IDS = [6595788533]

# ==================== ИГРОВЫЕ КОНСТАНТЫ ====================
MAX_LEVEL = 100
MAX_CLAN_BONUS = 10
MAX_MEDKITS = 10

# ==================== ЛИМИТЫ ТОВАРОВ В МАГАЗИНЕ ====================
# ==================== ОБЩИЕ ЛИМИТЫ МАГАЗИНА ====================
# Сколько штук доступно ВСЕМ игрокам за 6 часов
SHOP_LIMITS = {
    'броня3': 10,
    'броня4': 7,
    'броня5': 5,
    'винтовка': 7,
    'гаусс': 5,
    'аптечка': 75,      # было 25, стало 75
    'редуктор': 30,     # было 10, стало 30
    'энергетик': 15,
}
SHOP_RESET_HOURS = 6
# ==================== НАСТРОЙКИ КАЗИНО ====================
CASINO_PUBLIC_CHANCE = 12      # 12% шанс выигрыша
CASINO_PUBLIC_CASH_MULT = 5    # x5 множитель при выигрыше
CASINO_MIN_BET = 100           # минимальная ставка
CASINO_MAX_BET = 100000        # максимальная ставка

# ==================== ФАБРИКИ (ТОЧКИ) ====================
FACTORIES = {
    'свалка': {
        'name': '🗑️ Свалка',
        'slots': 50,
        'price': 1500,
        'income': 1,
        'income_type': 'RF',
        'level': 1,
        'duration': 72
    },
    'мастерская': {
        'name': '🔧 Мастерская',
        'slots': 30,
        'price': 5000,
        'income': 5,
        'income_type': 'RF',
        'level': 5,
        'duration': 72
    },
    'станция': {
        'name': '⚡ Станция',
        'slots': 25,
        'price': 10000,
        'income': 12,
        'income_type': 'RF',
        'level': 7,
        'duration': 72
    },
    'дамба': {
        'name': '🌊 Дамба',
        'slots': 10,
        'price': 15000,
        'income': 25,
        'income_type': 'RF',
        'level': 10,
        'duration': 72
    },
    'химка': {
        'name': '🧪 Химка',
        'slots': 7,
        'price': 25000,
        'income': 40,
        'income_type': 'RF',
        'level': 15,
        'duration': 72
    },
    'комплекс': {
        'name': '🏭 Комплекс',
        'slots': 5,
        'price': 100000,
        'income': 100,
        'income_type': 'RF',
        'level': 25,
        'duration': 72
    },
    'реактор': {
        'name': '☢️ Реактор',
        'slots': 3,
        'price': 500000,
        'income': 1000,
        'income_type': 'RF',
        'level': 50,
        'duration': 72
    }
}

# ==================== ЛОГГЕР ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== БЭКАПЫ ====================
import os
BACKUP_DIR = '/app/data/backups'
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (БЕЗ ЗАВИСИМОСТЕЙ) ====================

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

def calculate_reward(level):
    """Базовая награда RC"""
    import random
    level = min(level, MAX_LEVEL)
    base = random.randint(11, 150)
    bonus = 1 + (level - 1) * 0.05
    if bonus > 1 + (MAX_LEVEL - 1) * 0.05:
        bonus = 1 + (MAX_LEVEL - 1) * 0.05
    return int(base * bonus)

def calculate_experience():
    """Базовая награда опыта"""
    import random
    return random.randint(10, 50)

def get_random_interval(user=None):
    """Интервал между сборами"""
    import random
    from datetime import datetime
    
    base = random.randint(30, 120)
    if user and hasattr(user, 'cooldown_reducer_until') and user.cooldown_reducer_until and user.cooldown_reducer_until > datetime.now():
        base = base // 2
    if user and hasattr(user, 'pet') and user.pet == 'кайот':
        base = base // 2
    return max(base, 5)
