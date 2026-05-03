# collect.py - Сбор, охота, локации, питомцы, метро
# Версия: 4.0.0

import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from config import (
    logger, MAX_LEVEL, get_random_interval, calculate_reward,
    calculate_experience, get_exp_for_level, ENERGY_DRINKS, REDUCERS,
    get_energy_bonus, get_reducer_bonus
)
from core import send_to_private
from database import Session, User, Clan
from utils import (
    get_equipped, get_item_count, add_item_to_inventory,
    remove_item_from_inventory, apply_class_bonus,
    check_achievements, save_equipped, escape_markdown,
    safe_log_user_action
)

# Импортируем сообщения
from messages import (
    random_message, LOCATION_MESSAGES, METRO_ENCOUNTER_MESSAGES,
    BATTLE_RESULTS, HUNT_MUTANT_MESSAGES, HUNT_HUMAN_MESSAGES,
    COLLECT_RESULTS
)
from battle import get_battle_message, get_enemy_type


# ==================== БОНУСЫ РЮКЗАКА ====================

BACKPACK_BONUSES = {
    'рюкзак1': {'rc': 1.20, 'rf': 1.10, 'medkit': 1},    # +20% RC, +10% RF
    'рюкзак2': {'rc': 1.30, 'rf': 1.15, 'medkit': 1},    # +30% RC, +15% RF
    'рюкзак3': {'rc': 1.45, 'rf': 1.18, 'medkit': 2},    # +45% RC, +18% RF
}


def get_backpack_bonus(user):
    """Получить бонусы от экипированного рюкзака"""
    equipped = get_equipped(user)
    backpack = equipped.get('backpack')
    if backpack and backpack in BACKPACK_BONUSES:
        return BACKPACK_BONUSES[backpack]
    return {'rc': 1.0, 'rf': 1.0, 'medkit': 0}


def check_medkit_save(user):
    """Проверка спасения от смерти (аптечки из рюкзака)"""
    equipped = get_equipped(user)
    backpack_medkits = equipped.get('backpack_medkits', 0)
    
    if backpack_medkits <= 0:
        return False
    
    # Каждая аптечка в рюкзаке даёт 25% шанс
    for i in range(backpack_medkits):
        if random.random() < 0.25:
            # Тратим одну аптечку из рюкзака
            equipped['backpack_medkits'] -= 1
            save_equipped(user, equipped)
            return True
    
    return False


def get_mutant_survive_chance(user, mutant_level):
    """Возвращает шанс выжить против мутанта определённого уровня"""
    
    # База для мутантов
    base_chances = {
        1: 80,
        2: 60,
        3: 35,
        4: 5,  # босс
    }
    
    # Бонус брони
    armor_bonus = {
        None: 0,
        'броня1': 5,
        'броня2': 8,
        'броня3': 12,
        'броня4': 15,
        'броня5': 20,
    }
    
    # Бонус оружия
    weapon_bonus = {
        None: 0,
        'ружье': 5,
        'гарпун': 8,
        'винтовка': 12,
        'гаусс': 25,
    }
    
    equipped = get_equipped(user)
    armor = equipped.get('armor')
    weapon = equipped.get('weapon')
    
    chance = base_chances[mutant_level] + armor_bonus.get(armor, 0) + weapon_bonus.get(weapon, 0)
    
    # Учёт бонуса энергетика
    if user.energy_drink_until and user.energy_drink_until > datetime.now():
        energy_level = getattr(user, 'energy_drink_level', 'strike')
        energy_data = get_energy_bonus(energy_level)
        chance += energy_data['survive_bonus']
    
    return min(100, chance)


def get_human_survive_chance(user):
    """Возвращает шанс выжить против людей (зависит от брони и оружия)"""
    
    # Бонус брони
    armor_bonus = {
        None: 10,
        'броня1': 20,
        'броня2': 30,
        'броня3': 40,
        'броня4': 50,
        'броня5': 60,
    }
    
    # Бонус оружия
    weapon_bonus = {
        None: 0,
        'ружье': 10,
        'гарпун': 15,
        'винтовка': 20,
        'гаусс': 30,
    }
    
    equipped = get_equipped(user)
    armor = equipped.get('armor')
    weapon = equipped.get('weapon')
    
    chance = armor_bonus.get(armor, 10) + weapon_bonus.get(weapon, 0)
    
    # Учёт бонуса энергетика
    if user.energy_drink_until and user.energy_drink_until > datetime.now():
        energy_level = getattr(user, 'energy_drink_level', 'strike')
        energy_data = get_energy_bonus(energy_level)
        chance += energy_data['survive_bonus']
    
    return min(95, chance)


# ==================== СБОР РЕСУРСОВ ====================

async def collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбор ресурсов с учётом локаций (включая Метро)"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            user = User(user_id=user_id, username=username)
            session.add(user)
            session.commit()

        now = datetime.now()
        location = getattr(user, 'location', 'normal')
        
        # Проверка кулдауна
        if user.next_collection_time and now < user.next_collection_time:
            remaining = user.next_collection_time - now
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            await update.message.reply_text(f"⏰ *Следующий сбор через {hours}ч {minutes}мин.*", parse_mode='Markdown')
            return
        
        # Шаг 1: Вы отправляетесь на поиски
        step1 = "🚶‍♂️ *Вы отправляетесь на поиски...*\n   Вы покидаете лагерь и отправляетесь в опасное путешествие."
        
        # Шаг 2: Описание локации
        loc_messages = LOCATION_MESSAGES.get(location, LOCATION_MESSAGES['normal'])
        step2 = f"📍 *Локация: {location.upper()}*\n   {random_message(loc_messages)}"
        
        # Особый случай: МЕТРО (боевая локация)
        if location == 'metro':
            if user.level < 10:
                await update.message.reply_text("❌ *Метро доступно с 10 уровня!*", parse_mode='Markdown')
                return
            
            # Отправляем первые два сообщения
            await update.message.reply_text(
                f"📡 *Сбор ресурсов прерван!*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{step1}\n\n{step2}\n\n"
                f"⚠️ В Метро нельзя собирать ресурсы. Только бой!",
                parse_mode='Markdown'
            )
            
            # Вызов боя в метро
            await metro_battle(update, context, user, session)
            return
        
        # Обычный сбор (не метро)
        actual_level = min(user.level, MAX_LEVEL)
        base_rc = calculate_reward(actual_level)
        exp_gain = calculate_experience()
        
        # Бонусы локации
        rc_mult = rf_mult = exp_mult = pet_mult = chest_mult = 1
        
        if location == 'military':
            chest_mult = 3
            rc_mult = rf_mult = 0
            exp_gain = random.randint(25, 50)
        elif location == 'city':
            rc_mult = 1.5
            rf_mult = 0.5
        elif location == 'wasteland':
            rf_mult = 1.5
            rc_mult = 0.7
        elif location == 'lab':
            exp_mult = 2
            rc_mult = 0.5
        elif location == 'forest':
            pet_mult = 2
            rc_mult = 0.8
            rf_mult = 0
            exp_gain = random.randint(30, 80)
        elif location == 'market':
            rc_mult = 1.2
            rf_mult = 0
            chest_mult = 2
            exp_gain = random.randint(10, 30)
        
        # Аномалии
        anomaly_msg = ""
        phase = context.bot_data.get('phase', 1)
        if phase >= 3:
            anomaly_roll = random.random()
            if anomaly_roll < 0.1:
                base_rc = int(base_rc * 1.3)
                anomaly_msg = "\n✨ *Аномалия ДОБЫТЧИК!* Добыча +30%! ✨"
            elif anomaly_roll < 0.2:
                anomaly_msg = "\n🕸️ *Аномалия ЛОВЕЦ!* Кто-то наблюдает... 🕸️"
            elif anomaly_roll < 0.2001:
                reduction = random.randint(1, 5)
                actual_level = max(1, actual_level - reduction)
                anomaly_msg = f"\n🧠 *Аномалия СКЛЕРОЗИК!* Потеряно {reduction} уровней! 🧠"
        
        # Клановый бонус
        clan = None
        if user.clan_id:
            clan = session.query(Clan).filter_by(id=user.clan_id).first()
            if clan:
                exp_gain = int(exp_gain * (1 + clan.exp_bonus * 0.05))
        
        rc_gain = int(base_rc * rc_mult)
        exp_gain = int(exp_gain * exp_mult)
        fragment_gain = 0
        
        # Питомцы
        if user.pet == 'рысь':
            rc_gain = int(rc_gain * 1.1)
        if user.pet == 'попугай':
            exp_gain = int(exp_gain * 1.4)
        
        # Множители
        multiplier = 1
        double_chance = 9
        if clan:
            double_chance += clan.double_bonus
        if random.random() < 0.01:
            multiplier = 5
            user.crit_collects += 1
        elif random.random() < double_chance / 100:
            multiplier = 2
            user.crit_collects += 1
        rc_gain *= multiplier
        
        # Фрагменты
        fragment_chance = 1
        if user.pet == 'овчарка':
            fragment_chance += 5
        if random.random() < fragment_chance / 100:
            fragment_gain = random.randint(1, 5)
        fragment_gain = int(fragment_gain * rf_mult)
        
        # Бонус класса
        rc_gain, fragment_gain, exp_gain = apply_class_bonus(user, rc_gain, fragment_gain, exp_gain)
        
        # Кристаллы
        crystal_gain = 0
        if clan:
            crystal_gain = random.randint(1, 5)
            if user.pet == 'пума':
                crystal_gain = int(crystal_gain * 1.5)
            clan.treasury_crystals += crystal_gain
        
        # Бонус энергетика
        if user.energy_drink_until and user.energy_drink_until > now:
            energy_level = getattr(user, 'energy_drink_level', 'strike')
            energy_data = get_energy_bonus(energy_level)
            rc_gain = int(rc_gain * energy_data['rc_bonus'])
            fragment_gain = int(fragment_gain * energy_data['rf_bonus'])
            crystal_gain = int(crystal_gain * energy_data['crystal_bonus'])
        
        # Бонус рюкзака
        backpack_bonus = get_backpack_bonus(user)
        rc_gain = int(rc_gain * backpack_bonus['rc'])
        fragment_gain = int(fragment_gain * backpack_bonus['rf'])
        
        user.radcoins += rc_gain
        user.radfragments += fragment_gain
        user.experience += exp_gain
        user.total_collects += 1
        user.total_rc_earned += rc_gain
        if rc_gain > user.best_collect:
            user.best_collect = rc_gain
        
        level_up = False
        while user.level < MAX_LEVEL and user.experience >= get_exp_for_level(user.level + 1):
            user.level += 1
            level_up = True
        
        interval = get_random_interval(user)
        user.last_collection = now
        user.next_collection_time = now + timedelta(minutes=interval)
        
        # Серия сборов
        last_date = user.last_collect_date.date() if user.last_collect_date else None
        today = now.date()
        if last_date == today - timedelta(days=1):
            user.daily_streak += 1
        elif last_date != today:
            user.daily_streak = 1
        user.last_collect_date = now
        
        # Питомец
        pet_encounter = None
        if phase >= 2 and user.level >= 2:
            if random.random() < 0.005 * pet_mult:
                pets = ['овчарка', 'волк', 'рысь', 'пума', 'попугай', 'кайот']
                pet_encounter = random.choice(pets)
        
        # Достижения
        new_achievements = check_achievements(user)
        
        # Сундуки
        chest_found = None
        if phase >= 2 and chest_mult > 0:
            chest_roll = random.random() * 100
            if chest_roll < 1 * chest_mult:
                user.chest_legendary += 1
                chest_found = "🟠 Легендарный сундук"
            elif chest_roll < 4 * chest_mult:
                user.chest_mythic += 1
                chest_found = "🟡 Мифический сундук"
            elif chest_roll < 8 * chest_mult:
                user.chest_epic += 1
                chest_found = "🟣 Эпический сундук"
            elif chest_roll < 15 * chest_mult:
                user.chest_rare += 1
                chest_found = "🔵 Редкий сундук"
            elif chest_roll < 25 * chest_mult:
                user.chest_common += 1
                chest_found = "🟢 Обычный сундук"
        
        # Сохраняем данные
        log_user_id, log_username, log_rc, log_rf, log_crystals = (
            user.user_id, user.username, rc_gain, fragment_gain, crystal_gain
        )
        
        session.commit()
        
        # Логируем
        safe_log_user_action(log_user_id, log_username, 'collect',
                            amount_rc=log_rc, amount_rf=log_rf, amount_crystals=log_crystals)
        
        # Шаг 3: Результат сбора
        collect_result = random_message(COLLECT_RESULTS)
        result_text = f"🔍 {collect_result}\n\n"
        result_text += f"🎉 *Результат сбора:*\n"
        result_text += f"💰 +{rc_gain} ☢️ *РадКоинов*\n"
        result_text += f"⚠️ +{exp_gain} *опыта*\n"
        
        if fragment_gain > 0:
            result_text += f"☣️ +{fragment_gain} *РадФрагментов*\n"
        if crystal_gain > 0:
            result_text += f"💎 +{crystal_gain} *клановых кристаллов*\n"
        if multiplier > 1:
            result_text += f"✨ *Множитель x{multiplier}!*\n"
        if level_up:
            result_text += f"\n🎉 *УРОВЕНЬ ПОВЫШЕН!* Теперь вы {user.level} уровень! 🎉"
        if anomaly_msg:
            result_text += anomaly_msg
        if new_achievements:
            result_text += f"\n🏆 *Новые достижения:* {', '.join(new_achievements)}! 🏆"
        if chest_found:
            result_text += f"\n\n🎁 *Вы нашли {chest_found}!* /chest open"
        if pet_encounter:
            result_text += f"\n\n🐾 *Вы встречаете {pet_encounter}!*\nИспользуйте `/pet accept` чтобы приручить."
            context.user_data['pending_pet'] = pet_encounter
        
        # Отправляем сообщение
        await update.message.reply_text(
            f"🌄 *Сбор ресурсов*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{step1}\n\n{step2}\n\n{result_text}\n\n"
            f"⏰ *Следующий сбор через {interval//60}ч {interval%60}мин.*",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in collect: {e}")
        session.rollback()
        await update.message.reply_text("❌ Ошибка при сборе")
    finally:
        session.close()


# ==================== БОЙ В МЕТРО ====================

async def metro_battle(update: Update, context: ContextTypes.DEFAULT_TYPE, user, session):
    """Бой в метро с пошаговыми сообщениями"""
    
    # 60% шанс встречи
    if random.random() < 0.4:
        await update.message.reply_text(
            "🚇 *Метро*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "😌 Вы идёте по тёмным тоннелям, но сегодня вам везёт — никого не встретили.\n\n"
            "⏰ *Кулдаун сбора не изменился.*",
            parse_mode='Markdown'
        )
        return
    
    # Определяем тип врага (50% мутант / 50% люди)
    is_mutant = random.random() < 0.5
    
    # Получаем сообщение о встрече
    encounter_type = 'mutant' if is_mutant else 'human'
    encounter_msg = random_message(METRO_ENCOUNTER_MESSAGES[encounter_type])
    
    await update.message.reply_text(
        f"🚇 *Метро — ВСТРЕЧА!*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{encounter_msg}\n\n"
        f"⚔️ *Начинается бой!*",
        parse_mode='Markdown'
    )
    
    # Определяем бонусы от рюкзака
    backpack_bonus = get_backpack_bonus(user)
    max_medkits = backpack_bonus['medkit']
    equipped = get_equipped(user)
    current_medkits = equipped.get('backpack_medkits', 0)
    
    if is_mutant:
        # Мутант (2 уровень, фиксированный)
        mutant_level = 2
        survive_chance = get_mutant_survive_chance(user, mutant_level)
        reward_exp = random.randint(100, 250)
        
        # Пошаговый бой с аптечками
        medkit_used = 0
        survived = False
        
        for attempt in range(max_medkits + 1):
            if attempt > 0:
                # Используем аптечку
                await update.message.reply_text(
                    f"💊 *Вы используете аптечку ({attempt}/{max_medkits})*\n"
                    f"   {random_message(USE_NEXT_MEDKIT['вторую' if attempt == 1 else 'третью'])}",
                    parse_mode='Markdown'
                )
                
                if check_medkit_save(user):
                    await update.message.reply_text(
                        f"✅ *Аптечка помогла!*\n"
                        f"   {random_message(MEDKIT_EFFECT['помогает'])}",
                        parse_mode='Markdown'
                    )
                    survived = True
                    break
                else:
                    await update.message.reply_text(
                        f"❌ *Аптечка не помогла!*\n"
                        f"   {random_message(MEDKIT_EFFECT['не_помогает'])}",
                        parse_mode='Markdown'
                    )
                    if attempt == max_medkits:
                        survived = False
            else:
                # Первый раунд без аптечки
                if random.random() * 100 < survive_chance:
                    survived = True
                    break
            
            if attempt < max_medkits:
                await update.message.reply_text(
                    f"⚔️ *Бой продолжается...*\n   {random_message(BATTLE_CONTINUES['мутант'])}",
                    parse_mode='Markdown'
                )
        
        if survived:
            # Победа
            user.experience += reward_exp
            
            # Проверка на повышение уровня
            level_up = False
            while user.level < MAX_LEVEL and user.experience >= get_exp_for_level(user.level + 1):
                user.level += 1
                level_up = True
            
            session.commit()
            
            result_msg = f"🏆 *ПОБЕДА!*\n   {random_message(BATTLE_RESULTS['win_mutant'])}\n"
            result_msg += f"💰 *Награда:* +{reward_exp} ⚠️ опыта!\n"
            if level_up:
                result_msg += f"🎉 *УРОВЕНЬ ПОВЫШЕН!* Теперь вы {user.level} уровень! 🎉"
            
            await update.message.reply_text(
                f"🚇 *Метро — ИТОГ БОЯ*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n{result_msg}",
                parse_mode='Markdown'
            )
            
            safe_log_user_action(user.user_id, user.username, 'metro_mutant_win',
                                amount_rf=reward_exp)
        else:
            # Смерть
            await process_metro_death(update, context, user, session, is_mutant)
    
    else:
        # Люди (классовый враг)
        survive_chance = get_human_survive_chance(user)
        
        # Определяем класс врага
        class_name = getattr(user, 'user_class', 'stalker')
        if class_name == 'military':
            enemy_class = 'bandit'
        elif class_name == 'bandit':
            enemy_class = 'stalker'
        else:
            enemy_class = 'military'
        
        # Определяем размер группы
        group_roll = random.random() * 100
        if group_roll < 50:
            group_size = 'одиночка'
            reward_items = True
        elif group_roll < 85:
            group_size = 'толпа'
            reward_items = True
        else:
            group_size = 'караван'
            reward_items = True
        
        # Пошаговый бой с аптечками
        medkit_used = 0
        survived = False
        
        for attempt in range(max_medkits + 1):
            if attempt > 0:
                await update.message.reply_text(
                    f"💊 *Вы используете аптечку ({attempt}/{max_medkits})*\n"
                    f"   {random_message(USE_NEXT_MEDKIT['вторую' if attempt == 1 else 'третью'])}",
                    parse_mode='Markdown'
                )
                
                if check_medkit_save(user):
                    await update.message.reply_text(
                        f"✅ *Аптечка помогла!*\n"
                        f"   {random_message(MEDKIT_EFFECT['помогає'])}",
                        parse_mode='Markdown'
                    )
                    survived = True
                    break
                else:
                    await update.message.reply_text(
                        f"❌ *Аптечка не помогла!*\n"
                        f"   {random_message(MEDKIT_EFFECT['не_помогає'])}",
                        parse_mode='Markdown'
                    )
                    if attempt == max_medkits:
                        survived = False
            else:
                if random.random() * 100 < survive_chance:
                    survived = True
                    break
            
            if attempt < max_medkits:
                await update.message.reply_text(
                    f"⚔️ *Бой продолжается...*\n   {random_message(BATTLE_CONTINUES['люди'])}",
                    parse_mode='Markdown'
                )
        
        if survived:
            # Победа — случайный дроп
            weapons = ['ружье', 'гарпун', 'винтовка', 'гаусс']
            armors = ['броня1', 'броня2', 'броня3', 'броня4', 'броня5']
            energy_types = ['strike', 'tornado', 'adrenaline']
            reducer_types = ['basic', 'advanced']
            
            weapon = random.choice(weapons)
            armor = random.choice(armors)
            medkits = random.randint(1, 3)
            energies = random.randint(1, 3)
            reducers = random.randint(1, 2)
            
            energy_level = random.choice(energy_types)
            reducer_level = random.choice(reducer_types)
            
            add_item_to_inventory(user, weapon, 1)
            add_item_to_inventory(user, armor, 1)
            add_item_to_inventory(user, 'аптечка', medkits)
            add_item_to_inventory(user, f'энергетик_{energy_level}', energies)
            add_item_to_inventory(user, f'редуктор_{reducer_level}', reducers)
            
            # Проверка на повышение уровня
            level_up = False
            while user.level < MAX_LEVEL and user.experience >= get_exp_for_level(user.level + 1):
                user.level += 1
                level_up = True
            
            session.commit()
            
            weapon_names = {
                'ружье': '🔫 Ружьё', 'гарпун': '🎣 Гарпун',
                'винтовка': '🔫 Винтовка', 'гаусс': '⚡ Винтовка Гаусса'
            }
            armor_names = {
                'броня1': '🟢 Лёгкая броня', 'броня2': '🔵 Утяжеленная броня',
                'броня3': '🟣 Тактическая броня', 'броня4': '🟠 Тяжёлая броня',
                'броня5': '🔴 Силовая броня'
            }
            energy_names = {
                'strike': '⚡ Strike', 'tornado': '🌀 Tornado',
                'adrenaline': '💉 Adrenaline', 'redbull': '🔴 RedBull'
            }
            reducer_names = {
                'basic': '⏱️ Базовый редуктор',
                'advanced': '⚙️ Продвинутый редуктор',
                'quantum': '🌀 Квантовый редуктор'
            }
            
            result_msg = f"🏆 *ПОБЕДА!*\n   {random_message(BATTLE_RESULTS['win_human'])}\n"
            result_msg += f"📦 *Награда:*\n"
            result_msg += f"   • {weapon_names[weapon]}\n"
            result_msg += f"   • {armor_names[armor]}\n"
            result_msg += f"   • 💊 Аптечка x{medkits}\n"
            result_msg += f"   • {energy_names[energy_level]} x{energies}\n"
            result_msg += f"   • {reducer_names[reducer_level]} x{reducers}\n"
            if level_up:
                result_msg += f"\n🎉 *УРОВЕНЬ ПОВЫШЕН!* Теперь вы {user.level} уровень! 🎉"
            
            await update.message.reply_text(
                f"🚇 *Метро — ИТОГ БОЯ*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n{result_msg}",
                parse_mode='Markdown'
            )
            
            safe_log_user_action(user.user_id, user.username, 'metro_human_win',
                                item=f"{weapon},{armor},medkit x{medkits}")
        else:
            # Смерть
            await process_metro_death(update, context, user, session, is_mutant)


async def process_metro_death(update: Update, context: ContextTypes.DEFAULT_TYPE, user, session, is_mutant):
    """Обработка смерти в метро"""
    
    equipped = get_equipped(user)
    
    # Потеря оружия
    lost_weapon = None
    if equipped.get('weapon'):
        lost_weapon = equipped['weapon']
        equipped['weapon'] = None
    
    # Потеря рюкзака (вместе с аптечками)
    lost_backpack = None
    if equipped.get('backpack'):
        lost_backpack = equipped['backpack']
        equipped['backpack'] = None
        equipped['backpack_medkits'] = 0
    
    # Потеря 10% длительности эффектов
    now = datetime.now()
    if user.energy_drink_until and user.energy_drink_until > now:
        duration = user.energy_drink_until - now
        user.energy_drink_until = now + duration * 0.9
    if user.cooldown_reducer_until and user.cooldown_reducer_until > now:
        duration = user.cooldown_reducer_until - now
        user.cooldown_reducer_until = now + duration * 0.9
    
    save_equipped(user, equipped)
    
    # Увеличение кулдауна сбора на 200%
    interval = get_random_interval(user)
    user.next_collection_time = datetime.now() + timedelta(minutes=interval * 3)
    
    session.commit()
    
    # Сообщение о смерти
    death_msg = random_message(BATTLE_RESULTS['death_mutant' if is_mutant else 'death_human'])
    
    result_msg = f"💀 *СМЕРТЬ!*\n   {death_msg}\n\n"
    if lost_weapon:
        weapon_names = {
            'ружье': '🔫 Ружьё', 'гарпун': '🎣 Гарпун',
            'винтовка': '🔫 Винтовка', 'гаусс': '⚡ Винтовка Гаусса'
        }
        result_msg += f"⚔️ *Потеряно оружие:* {weapon_names.get(lost_weapon, lost_weapon)}\n"
    if lost_backpack:
        backpack_names = {
            'рюкзак1': '🎒 Маленький рюкзак',
            'рюкзак2': '🎒 Тактический рюкзак',
            'рюкзак3': '🎒 Профессиональный рюкзак'
        }
        result_msg += f"🎒 *Потерян рюкзак:* {backpack_names.get(lost_backpack, lost_backpack)}\n"
    result_msg += f"⏱️ *Эффекты сокращены на 10%*\n"
    result_msg += f"⏰ *Кулдаун сбора увеличен до {interval*3//60}ч {interval*3%60}мин.*"
    
    await update.message.reply_text(
        f"🚇 *Метро — ИТОГ БОЯ*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n{result_msg}",
        parse_mode='Markdown'
    )
    
    safe_log_user_action(user.user_id, user.username, 'metro_death',
                        item=f"lost {lost_weapon}, {lost_backpack}")


# ==================== ОХОТА ====================

async def hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Охота с учётом классов и новой системой боя"""
    user_id = update.effective_user.id
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            await update.message.reply_text("❌ Сначала /start")
            return
        
        if user.level < 2:
            await update.message.reply_text("❌ *Охота доступна со 2 уровня*", parse_mode='Markdown')
            return
        
        # Учёные не охотятся
        class_name = getattr(user, 'user_class', 'stalker')
        if class_name == 'scientist':
            await update.message.reply_text(
                "🔬 *Вы учёный!*\n\n"
                "Ваше место — лаборатория. Используйте `/lab` для проведения экспериментов.\n"
                "Охота — удел военных, бандитов и сталкеров.",
                parse_mode='Markdown'
            )
            return
        
        phase = context.bot_data.get('phase', 1)
        if phase < 2:
            await update.message.reply_text("❌ *Охота недоступна!* Фаза 2 или 3", parse_mode='Markdown')
            return
        
        now = datetime.now()
        
        # Кулдаун охоты (с учётом редуктора)
        cooldown = timedelta(days=1)
        if user.cooldown_reducer_until and user.cooldown_reducer_until > now:
            reducer_level = getattr(user, 'reducer_level', 'basic')
            reducer_data = get_reducer_bonus(reducer_level)
            cooldown = timedelta(hours=int(24 * reducer_data['cooldown_reduction']))
        if user.pet == 'кайот':
            cooldown = timedelta(hours=12)
        if (user.cooldown_reducer_until and user.cooldown_reducer_until > now) and user.pet == 'кайот':
            cooldown = timedelta(hours=6)
        
        if user.last_hunt and now - user.last_hunt < cooldown:
            remaining = cooldown - (now - user.last_hunt)
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            await update.message.reply_text(f"⏰ *Следующая охота через {hours}ч {minutes}мин.*", parse_mode='Markdown')
            return
        
        # Шаг 1: Отправка на охоту
        weapon_name = "🗡️ Обрез"
        equipped = get_equipped(user)
        if equipped.get('weapon'):
            weapon_names = {
                'ружье': '🔫 Ружьё', 'гарпун': '🎣 Гарпун',
                'винтовка': '🔫 Винтовка', 'гаусс': '⚡ Винтовка Гаусса'
            }
            weapon_name = weapon_names.get(equipped['weapon'], "🗡️ Обрез")
        
        armor_name = "Нет брони"
        if equipped.get('armor'):
            armor_names = {
                'броня1': '🟢 Лёгкая броня', 'броня2': '🔵 Утяжеленная броня',
                'броня3': '🟣 Тактическая броня', 'броня4': '🟠 Тяжёлая броня',
                'броня5': '🔴 Силовая броня'
            }
            armor_name = armor_names.get(equipped['armor'], "Броня")
        
        await update.message.reply_text(
            f"🏹 *Охота в Пустоши*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🚶‍♂️ Вы крадётесь по руинам с {weapon_name}. {armor_name} защищает вас.",
            parse_mode='Markdown'
        )
        
        # 50% мутанты / 50% люди
        if random.random() < 0.5:
            # МУТАНТЫ
            roll = random.random() * 100
            if roll < 60:
                mutant_level = 1
                reward_rf = 10
                reward_exp = 50
            elif roll < 90:
                mutant_level = 2
                reward_rf = 30
                reward_exp = 100
            elif roll < 99:
                mutant_level = 3
                reward_rf = 100
                reward_exp = 250
                user.mutants_lvl3 += 1
            else:
                mutant_level = 4
                reward_rf = 1000
                reward_exp = 500
                user.bosses_killed += 1
            
            user.mutants_killed += 1
            
            # Сообщение о встрече
            mutant_msg = random_message(HUNT_MUTANT_MESSAGES[mutant_level])
            await update.message.reply_text(
                f"👾 *Встреча с врагом!*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
