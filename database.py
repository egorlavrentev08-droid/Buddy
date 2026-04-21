# database.py - База данных для тестового бота RadCoin Buddy
# Версия: 0.1.0

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

# ==================== СОЗДАНИЕ БАЗЫ ====================
Base = declarative_base()
engine = create_engine('sqlite:///radcoin_buddy.db', pool_size=10, max_overflow=20)
Session = scoped_session(sessionmaker(bind=engine))

# ==================== КОНСТАНТЫ ====================
SUPER_ADMIN_IDS = [6595788533]


# ==================== МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ (минимум) ====================

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True)
    username = Column(String)
    
    # Ресурсы
    radcoins = Column(Float, default=0)
    radfragments = Column(Integer, default=0)
    radcrystals = Column(Integer, default=0)
    
    # Прогресс (минимум)
    level = Column(Integer, default=1)
    experience = Column(Integer, default=0)
    
    # Кланы
    clan_id = Column(Integer, ForeignKey('clans.id'), nullable=True)
    clan_role = Column(String, default='member')
    
    # Админ
    is_admin = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)
    
    # Время последнего посещения
    last_seen = Column(DateTime, default=datetime.now)


# ==================== МОДЕЛЬ КЛАНА (с полями для города) ====================

class Clan(Base):
    __tablename__ = 'clans'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    leader_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    
    # Казна
    treasury_coins = Column(Float, default=0)
    treasury_crystals = Column(Integer, default=0)
    
    # Улучшения клана (базовые)
    collect_bonus = Column(Integer, default=0)
    exp_bonus = Column(Integer, default=0)
    double_bonus = Column(Integer, default=0)
    
    # ========== НОВЫЕ ПОЛЯ ДЛЯ КЛАНОВОГО ГОРОДА ==========
    city_map = Column(String, default='[]')           # JSON матрица 10х10
    buildings = Column(String, default='{}')          # JSON здания клана
    production_queue = Column(String, default='[]')   # JSON очередь производства
    storage_items = Column(String, default='{}')      # JSON предметы на складах
    
    last_raid = Column(DateTime, nullable=True)       # время последнего рейда
    raid_type = Column(String, nullable=True)         # тип текущего рейда
    raid_end_time = Column(DateTime, nullable=True)   # время окончания рейда


# ==================== ИНИЦИАЛИЗАЦИЯ ====================

def init_db():
    """Создание таблиц"""
    Base.metadata.create_all(engine)
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
