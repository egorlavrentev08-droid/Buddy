# database.py - Упрощённая версия без SQLAlchemy
# Для тестового бота RadCoin Buddy

import json
import os
from datetime import datetime

DATA_FILE = 'radcoin_buddy_data.json'

# Загрузка данных из файла
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'users': {}, 'clans': {}, 'next_user_id': 1, 'next_clan_id': 1}

# Сохранение данных в файл
def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ==================== ПОЛЬЗОВАТЕЛИ ====================

class User:
    def __init__(self, user_id, username=None):
        self.user_id = user_id
        self.username = username
        self.radcoins = 0
        self.radfragments = 0
        self.radcrystals = 0
        self.level = 1
        self.experience = 0
        self.clan_id = None
        self.clan_role = 'member'
        self.is_admin = False
        self.is_blocked = False
        self.last_seen = datetime.now().isoformat()


def get_user(user_id, username=None):
    data = load_data()
    user_key = str(user_id)
    
    if user_key not in data['users']:
        user = User(user_id, username)
        data['users'][user_key] = {
            'user_id': user.user_id,
            'username': user.username,
            'radcoins': user.radcoins,
            'radfragments': user.radfragments,
            'radcrystals': user.radcrystals,
            'level': user.level,
            'experience': user.experience,
            'clan_id': user.clan_id,
            'clan_role': user.clan_role,
            'is_admin': user.is_admin,
            'is_blocked': user.is_blocked,
            'last_seen': user.last_seen
        }
        save_data(data)
    else:
        # Обновляем username если изменился
        if username and data['users'][user_key]['username'] != username:
            data['users'][user_key]['username'] = username
            save_data(data)
    
    return data['users'][user_key]


def save_user(user_data):
    data = load_data()
    data['users'][str(user_data['user_id'])] = user_data
    save_data(data)


def get_all_users():
    data = load_data()
    return list(data['users'].values())


# ==================== КЛАНЫ ====================

class Clan:
    def __init__(self, name, leader_id):
        self.id = None
        self.name = name
        self.leader_id = leader_id
        self.created_at = datetime.now().isoformat()
        self.treasury_coins = 0
        self.treasury_crystals = 0
        self.collect_bonus = 0
        self.exp_bonus = 0
        self.double_bonus = 0
        self.city_map = [[ '⬜' for _ in range(10)] for _ in range(10)]
        self.buildings = {}
        self.production_queue = []
        self.storage_items = {}
        self.last_raid = None
        self.raid_type = None
        self.raid_end_time = None


def create_clan(name, leader_id):
    data = load_data()
    clan_id = data['next_clan_id']
    data['next_clan_id'] = clan_id + 1
    
    clan = {
        'id': clan_id,
        'name': name,
        'leader_id': leader_id,
        'created_at': datetime.now().isoformat(),
        'treasury_coins': 0,
        'treasury_crystals': 0,
        'collect_bonus': 0,
        'exp_bonus': 0,
        'double_bonus': 0,
        'city_map': [['⬜' for _ in range(10)] for _ in range(10)],
        'buildings': {},
        'production_queue': [],
        'storage_items': {},
        'last_raid': None,
        'raid_type': None,
        'raid_end_time': None
    }
    
    data['clans'][str(clan_id)] = clan
    save_data(data)
    return clan


def get_clan(clan_id):
    data = load_data()
    return data['clans'].get(str(clan_id))


def get_clan_by_name(name):
    data = load_data()
    for clan in data['clans'].values():
        if clan['name'].lower() == name.lower():
            return clan
    return None


def get_all_clans():
    data = load_data()
    return list(data['clans'].values())


def save_clan(clan):
    data = load_data()
    data['clans'][str(clan['id'])] = clan
    save_data(data)


def update_user_clan(user_id, clan_id):
    data = load_data()
    user_key = str(user_id)
    if user_key in data['users']:
        data['users'][user_key]['clan_id'] = clan_id
        save_data(data)


# ==================== ИНИЦИАЛИЗАЦИЯ ====================

def init_super_admin():
    admin_id = 6595788533
    admin = get_user(admin_id, f"admin_{admin_id}")
    if not admin.get('is_admin'):
        admin['is_admin'] = True
        save_user(admin)
        print(f"✅ Главный администратор {admin_id} добавлен")
