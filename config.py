# config.py - Для тестового бота RadCoin Buddy (только кланы и города)
# Версия: 0.1.0

import logging
from datetime import datetime, timedelta

# ==================== НАСТРОЙКИ БОТА ====================
TOKEN = '8746321266:AAGKg_S2EQdgoOFAAk7FBqdvyl60xJ5XprI'
ADMIN_CODE = '1252836169043217'
SUPER_ADMIN_IDS = [6595788533]

# ==================== ИГРОВЫЕ КОНСТАНТЫ (минимум) ====================
MAX_LEVEL = 100
MAX_CLAN_BONUS = 10

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


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (для работы кланов) ====================

def get_exp_for_level(level):
    """Опыт для повышения уровня (минимум)"""
    if level <= 1:
        return 0
    if level > MAX_LEVEL:
        level = MAX_LEVEL
    total = 0
    for i in range(2, level + 1):
        total += 100 + (i - 2) * 50
    return total

def calculate_reward(level):
    """Заглушка"""
    import random
    return random.randint(11, 150)

def calculate_experience():
    """Заглушка"""
    import random
    return random.randint(10, 50)

def get_random_interval(user=None):
    """Заглушка"""
    import random
    return random.randint(30, 120)
