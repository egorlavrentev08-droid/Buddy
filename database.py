# database.py - База данных (полностью независимый модуль)
# Версия: 2.0.0

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

# ==================== СОЗДАНИЕ БАЗЫ ====================
Base = declarative_base()
engine = create_engine('sqlite:///radcoin_bot.db', pool_size=10, max_overflow=20)
Session = scoped_session(sessionmaker(bind=engine))

# ==================== КОНСТАНТЫ (дублируем, чтобы не было циклических импортов) ====================
SUPER_ADMIN_IDS = [6595788533]


# ==================== МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ ====================

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True)
    username = Column(String)
    
    # Ресурсы
    radcoins = Column(Float, default=0)
    radfragments = Column(Integer, default=0)
    radcrystals = Column(Integer, default=0)
    
    # Прогресс
    level = Column(Integer, default=1)
    experience = Column(Integer, default=0)
    
    # Таймеры
    last_collection = Column(DateTime, nullable=True)
    next_collection_time = Column(DateTime, nullable=True)
    last_hunt = Column(DateTime, nullable=True)
    cooldown_reducer_until = Column(DateTime, nullable=True)
    energy_drink_until = Column(DateTime, nullable=True)
    
    # Экипировка (только броня и оружие)
    armor_type = Column(String, default=None)
    weapon = Column(String, default=None)
    medkits = Column(Integer, default=0)
    
    # Статистика
    total_collects = Column(Integer, default=0)
    total_rc_earned = Column(Float, default=0)
    best_collect = Column(Float, default=0)
    mutants_killed = Column(Integer, default=0)
    mutants_lvl3 = Column(Integer, default=0)
    bosses_killed = Column(Integer, default=0)
    deaths = Column(Integer, default=0)
    crit_collects = Column(Integer, default=0)
    daily_streak = Column(Integer, default=0)
    last_collect_date = Column(DateTime, nullable=True)
    achievements = Column(String, default='[]')
    
    # Питомцы (алабай и лис удалены)
    pet = Column(String, nullable=True)  # овчарка, волк, рысь, пума, попугай, кайот
    
    # Кланы
    clan_id = Column(Integer, ForeignKey('clans.id'), nullable=True)
    clan_role = Column(String, default='member')
    total_purchases = Column(Integer, default=0)
    last_seen = Column(DateTime, default=datetime.now)
    notifications_enabled = Column(Boolean, default=False)
    
    # Сундуки
    chest_common = Column(Integer, default=0)
    chest_rare = Column(Integer, default=0)
    chest_epic = Column(Integer, default=0)
    chest_mythic = Column(Integer, default=0)
    chest_legendary = Column(Integer, default=0)
    
    # Локации (болото удалено)
    location = Column(String, default='normal')
    
    # Классы
    user_class = Column(String, default='stalker')
    last_free_class_change = Column(DateTime, nullable=True)
    
    # Радио
    radio_active = Column(Boolean, default=False)
    radio_code = Column(String, nullable=True)
    radio_banned = Column(Boolean, default=False)
    
    # Админ
    is_admin = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)
    is_admin_visible = Column(Boolean, default=True)
    
    # Фабрики
    factories = Column(String, default='[]')
    factory_bans = Column(String, default='[]')
    
    # Инвентарь и экипировка
    inventory = Column(String, default='[]')
    equipped = Column(String, default='{}')
    
    # Казино (персональные настройки)
    casino_chance = Column(Integer, nullable=True)      # NULL = используется публичный
    casino_cash_mult = Column(Integer, nullable=True)   # NULL = используется публичный
    
    # Эффекты (для /use)
    energy_drink_stacks = Column(Integer, default=0)       # количество активированных энергетиков
    reducer_stacks = Column(Integer, default=0)            # количество активированных редукторов
    
    # Лимиты магазина
    shop_purchases = Column(String, default='{}')          # JSON {"товар": количество_купленных}
    last_shop_reset = Column(DateTime, nullable=True)      # время последнего сброса лимитов


# ==================== МОДЕЛЬ КЛАНА ====================

class Clan(Base):
    __tablename__ = 'clans'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    leader_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    treasury_coins = Column(Float, default=0)
    treasury_crystals = Column(Integer, default=0)
    collect_bonus = Column(Integer, default=0)
    exp_bonus = Column(Integer, default=0)
    double_bonus = Column(Integer, default=0)
    
    # Клановые города (НОВЫЕ ПОЛЯ)
    city_level = Column(Integer, default=0)                     # 0 — нет города, 1-4 уровень резиденции
    city_buildings = Column(String, default='{}')              # JSON {"id": {"type": "bank", "level": 1}}
    city_resources = Column(String, default='{"crystals": 0, "storage": {}}')  # JSON ресурсы клана
    city_production = Column(String, default='[]')             # JSON очередь производства
    last_raid = Column(DateTime, nullable=True)                # время последнего рейда


# ==================== МИГРАЦИИ БАЗЫ ДАННЫХ ====================

def migrate_db():
    """Автоматическое добавление новых колонок при обновлении"""
    from sqlalchemy import inspect, text
    
    inspector = inspect(engine)
    
    # Список колонок, которые нужно добавить в таблицу users
    columns_to_add_users = {
        'energy_drink_stacks': 'INTEGER DEFAULT 0',
        'reducer_stacks': 'INTEGER DEFAULT 0',
        'shop_purchases': 'TEXT DEFAULT \'{}\'',
        'last_shop_reset': 'DATETIME',
    }
    
    # Список колонок, которые нужно добавить в таблицу clans
    columns_to_add_clans = {
        'city_level': 'INTEGER DEFAULT 0',
        'city_buildings': 'TEXT DEFAULT \'{}\'',
        'city_resources': 'TEXT DEFAULT \'{"crystals": 0, "storage": {}}\'',
        'city_production': 'TEXT DEFAULT \'[]\'',
        'last_raid': 'DATETIME',
    }
    
    # Проверяем и добавляем колонки в users
    existing_columns_users = [col['name'] for col in inspector.get_columns('users')]
    with engine.connect() as conn:
        for col_name, col_type in columns_to_add_users.items():
            if col_name not in existing_columns_users:
                try:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
                    print(f"✅ Добавлена колонка в users: {col_name}")
                except Exception as e:
                    print(f"⚠️ Ошибка при добавлении {col_name}: {e}")
    
    # Проверяем и добавляем колонки в clans
    existing_columns_clans = [col['name'] for col in inspector.get_columns('clans')]
    with engine.connect() as conn:
        for col_name, col_type in columns_to_add_clans.items():
            if col_name not in existing_columns_clans:
                try:
                    conn.execute(text(f"ALTER TABLE clans ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
                    print(f"✅ Добавлена колонка в clans: {col_name}")
                except Exception as e:
                    print(f"⚠️ Ошибка при добавлении {col_name}: {e}")


# ==================== ИНИЦИАЛИЗАЦИЯ ====================

def init_db():
    """Создание таблиц и миграция"""
    Base.metadata.create_all(engine)
    migrate_db()  # Автоматически добавляем новые колонки
    print("✅ База данных инициализирована")


def init_super_admin():
    """Добавление главных администраторов"""
    session = Session()
    try:
        for admin_id in SUPER_ADMIN_IDS:
            user = session.query(User).filter_by(user_id=admin_id).first()
            if not user:
                user = User(user_id=admin_id, username=f"admin_{admin_id}")
                session.add(user)
            user.is_admin = True
            user.is_blocked = False
            session.commit()
            print(f"✅ Главный администратор {admin_id} добавлен")
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")
    finally:
        Session.remove()


def get_user(user_id, username=None):
    """Получить или создать пользователя"""
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            user = User(user_id=user_id, username=username)
            session.add(user)
            session.commit()
        elif username and user.username != username:
            user.username = username
            session.commit()
        user.last_seen = datetime.now()
        session.commit()
        return user
    except Exception as e:
        print(f"Database error: {e}")
        session.rollback()
        return None
    finally:
        Session.remove()


# Запускаем инициализацию при импорте
init_db()
init_super_admin()
