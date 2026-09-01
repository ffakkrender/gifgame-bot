import os
import asyncio
import random
import json
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, 
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton
)

RAW_TOKEN = "8990102475:AAFqraA1U4mfwodck74OIJl-VVEA3blWebk" 
BOT_TOKEN = RAW_TOKEN.strip()
ADMIN_IDS = {816157991, 7842338512}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

DB_FILE = "users_db.json"
DB_BAK = "users_db.json.bak"
PROMO_FILE = "promos_db.json"
LB_FILE = "lb_data.json"

db = {}
promos = {}
user_history = {}
pending_roulette_stakes = {}
lb_data = {"last_reset": datetime.now().isoformat(), "earnings": {}}

x50_last_bets = {}
mw_last_bets = {}
hunt_last_bets = {}
slots_last_bets = {}

def load_data():
    global db, promos, lb_data
    for file_path in [DB_FILE, DB_BAK]:
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_db = json.load(f)
                    db = {int(k): v for k, v in raw_db.items()}
                break
            except Exception as e:
                print(f"Ошибка загрузки {file_path}: {e}")
                db = {}

    if os.path.exists(PROMO_FILE):
        try:
            with open(PROMO_FILE, "r", encoding="utf-8") as f:
                promos = json.load(f)
        except Exception:
            promos = {}

    if os.path.exists(LB_FILE):
        try:
            with open(LB_FILE, "r", encoding="utf-8") as f:
                raw_lb = json.load(f)
                lb_data["last_reset"] = raw_lb.get("last_reset", datetime.now().isoformat())
                lb_data["earnings"] = {int(k): v for k, v in raw_lb.get("earnings", {}).items()}
        except Exception:
            pass

def save_data():
    try:
        tmp_db = f"{DB_FILE}.tmp"
        with open(tmp_db, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        if os.path.exists(DB_FILE):
            os.replace(DB_FILE, DB_BAK)
        os.replace(tmp_db, DB_FILE)

        with open(PROMO_FILE, "w", encoding="utf-8") as f:
            json.dump(promos, f, ensure_ascii=False, indent=2)
        with open(LB_FILE, "w", encoding="utf-8") as f:
            json.dump(lb_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения: {e}")

load_data()

def check_and_reset_leaderboard():
    try:
        last_reset_dt = datetime.fromisoformat(lb_data["last_reset"])
        if datetime.now() - last_reset_dt >= timedelta(hours=24):
            rewards = [500000, 340000, 250000, 167000, 100000]
            sorted_lb = sorted([item for item in lb_data["earnings"].items() if item[1] > 0], key=lambda x: x[1], reverse=True)[:5]
            
            for idx, (uid, _) in enumerate(sorted_lb):
                if uid in db:
                    db[uid]["balance"] += rewards[idx]
            
            lb_data["earnings"] = {}
            lb_data["last_reset"] = datetime.now().isoformat()
            save_data()
    except Exception:
        pass

def add_leaderboard_profit(user_id: int, profit: int):
    check_and_reset_leaderboard()
    if user_id not in lb_data["earnings"]:
        lb_data["earnings"][user_id] = 0
    lb_data["earnings"][user_id] += profit
    save_data()

x50_round_active = False
x50_bets = []
x50_history = []
x50_timer_task = None
x50_last_msg_id = None
x50_last_chat_id = None

mw_bets = []
mw_history = []
mw_task = None
mw_last_msg_id = None
mw_last_chat_id = None
mw_round_counter = 0

roulette_round_active = False
roulette_bets = []
roulette_history = []  

active_mines = {}
active_hilo = {}
active_bj = {}
active_rise = {}

CARDS_MAP = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14}
CARDS_LIST = list(CARDS_MAP.keys())

def safe_name(name: str) -> str:
    if not name:
        return "Игрок"
    return name.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")

def get_user(user_id: int, first_name: str):
    clean_name = safe_name(first_name)
    if user_id not in db:
        db[user_id] = {
            "name": clean_name,
            "custom_nick": False,
            "balance": 100000,
            "bank": 0,
            "transfer_limit_lvl": 1,
            "transfer_limit": 50000,
            "reg_date": datetime.now().strftime("%d.%m.%Y"),
            "last_bonus": None
        }
        save_data()
    else:
        if not db[user_id].get("custom_nick", False):
            db[user_id]["name"] = clean_name
        if "transfer_limit_lvl" not in db[user_id]:
            db[user_id]["transfer_limit_lvl"] = 1
        if "transfer_limit" not in db[user_id]:
            db[user_id]["transfer_limit"] = 50000
    return db[user_id]

def add_history(user_id: int, game_name: str, text: str):
    if user_id not in user_history:
        user_history[user_id] = []
    user_history[user_id].insert(0, f"[{game_name}] {text}")
    if len(user_history[user_id]) > 10:
        user_history[user_id].pop()

def parse_amount_strict(text_arg: str):
    val = text_arg.lower().strip().replace(',', '.')
    mult = 1
    
    if val.endswith(("ккк", "kkk", "млрд")):
        mult = 1_000_000_000
        for suf in ["ккк", "kkk", "млрд"]:
            if val.endswith(suf):
                val = val[:-len(suf)]
                break
    elif val.endswith(("кк", "kk", "м", "m", "млн")):
        mult = 1_000_000
        for suf in ["кк", "kk", "млн", "м", "m"]:
            if val.endswith(suf):
                val = val[:-len(suf)]
                break
    elif val.endswith(("к", "k")):
        mult = 1_000
        for suf in ["к", "k"]:
            if val.endswith(suf):
                val = val[:-len(suf)]
                break
    try:
        amount = int(float(val) * mult)
        return amount, None
    except ValueError:
        return 0, "⚠️ Неверный формат суммы!"

def parse_stake(text_arg: str, user_balance: int):
    if user_balance <= 0:
        return 0, "⚠️ У вас **0** глифов на балансе!"

    val = text_arg.lower().strip()
    if val in ["все", "вабанк", "всё", "all", "всего"]:
        stake = user_balance
    else:
        stake, err = parse_amount_strict(val)
        if err:
            return 0, err

    if stake <= 0:
        return 0, "⚠️ Ставка должна быть больше 0!"
    if stake > user_balance:
        return 0, f"⚠️ Недостаточно средств! Ваш баланс: **{user_balance:,}** глифов"
        
    return stake, None

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Бонус")],
            [KeyboardButton(text="🏆 Топ"), KeyboardButton(text="📊 ЛБ")],
            [KeyboardButton(text="🎰 Игры"), KeyboardButton(text="🏦 Банк"), KeyboardButton(text="🆘 Помощь")]
        ],
        resize_keyboard=True
    )

@dp.message(F.text.lower().startswith("ник ") | F.text.lower().startswith("сетник ") | F.text.lower().startswith("nick "))
async def cmd_set_nickname(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return await message.reply("⚠️ Пример: `ник [новый ник]`", parse_mode="Markdown")
    
    new_nick = safe_name(parts[1].strip()[:25])
    user["name"] = new_nick
    user["custom_nick"] = True
    save_data()
    await message.reply(f"✅ Ваш никнейм успешно изменен на **{new_nick}**!", parse_mode="Markdown")

@dp.message(F.text.lower().in_({"📊 лб", "лб", "lb"}))
async def cmd_leaderboard(message: Message):
    check_and_reset_leaderboard()
    rewards = [500000, 340000, 250000, 167000, 100000]
    positive_earnings = {uid: earn for uid, earn in lb_data["earnings"].items() if earn > 0}
    sorted_lb = sorted(positive_earnings.items(), key=lambda x: x[1], reverse=True)[:5]
    
    text = "📊 **Таблица лидеров (в плюсе):**\n\n"
    for idx in range(5):
        place = idx + 1
        reward_txt = f"Награда {rewards[idx]:,} глифов"
        if idx < len(sorted_lb):
            uid, earn = sorted_lb[idx]
            u_obj = db.get(uid)
            name = u_obj["name"] if u_obj else "Игрок"
            text += f"{place}. {name} — +{earn:,} глифов\n   🎁 {reward_txt}\n"
        else:
            text += f"{place}. Вакантно — 0 глифов\n   🎁 {reward_txt}\n"
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_lb")]
    ])
    await message.reply(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "refresh_lb")
async def cb_refresh_lb(cb: CallbackQuery):
    await cb.answer("ЛБ обновлен!")
    check_and_reset_leaderboard()
    rewards = [500000, 340000, 250000, 167000, 100000]
    positive_earnings = {uid: earn for uid, earn in lb_data["earnings"].items() if earn > 0}
    sorted_lb = sorted(positive_earnings.items(), key=lambda x: x[1], reverse=True)[:5]
    
    text = "📊 **Таблица лидеров (в плюсе):**\n\n"
    for idx in range(5):
        place = idx + 1
        reward_txt = f"Награда {rewards[idx]:,} глифов"
        if idx < len(sorted_lb):
            uid, earn = sorted_lb[idx]
            u_obj = db.get(uid)
            name = u_obj["name"] if u_obj else "Игрок"
            text += f"{place}. {name} — +{earn:,} глифов\n   🎁 {reward_txt}\n"
        else:
            text += f"{place}. Вакантно — 0 глифов\n   🎁 {reward_txt}\n"
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_lb")]
    ])
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass

@dp.message(F.text.lower().startswith("выдать"))
async def cmd_admin_give(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not message.reply_to_message:
        return await message.reply("⚠️ **Ответьте (Reply) на сообщение игрока!**", parse_mode="Markdown")
        
    target_id = message.reply_to_message.from_user.id
    target_user = get_user(target_id, message.reply_to_message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("⚠️ Пример: `выдать 1000кк`", parse_mode="Markdown")
    
    val = parts[1].lower()
    if val in ["все", "всё", "all"]:
        amount = 100_000_000_000_000
    else:
        amount, err = parse_amount_strict(val)
        if err: return await message.reply(err, parse_mode="Markdown")
        
    if amount < 100:
        return await message.reply("⚠️ Минимальная сумма для выдачи: **100**", parse_mode="Markdown")
        
    target_user["balance"] += amount
    save_data()
    await message.reply(f"👑 **АДМИН-ВЫДАЧА**\nИгроку **{target_user['name']}** выдано: **+{amount:,}**\n💸 Баланс: **{target_user['balance']:,}**", parse_mode="Markdown")

@dp.message(F.text.lower() == "обнулировать")
async def cmd_admin_zero(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not message.reply_to_message:
        return await message.reply("⚠️ **Ответьте (Reply) на сообщение игрока для обнуления!**", parse_mode="Markdown")
    target_id = message.reply_to_message.from_user.id
    target_user = get_user(target_id, message.reply_to_message.from_user.first_name)
    target_user["balance"] = 0
    target_user["bank"] = 0
    save_data()
    await message.reply(f"🚨 Игрок **{target_user['name']}** был полностью обнулен администратором!", parse_mode="Markdown")

@dp.message(F.text.lower() == "reset balance")
async def cmd_admin_reset_all(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    for uid in db:
        db[uid]["balance"] = 0
        db[uid]["bank"] = 0
    save_data()
    await message.reply("⚠️ **Глобальный сброс!** Балансы и банки абсолютно всех игроков обнулены (0).", parse_mode="Markdown")

@dp.message(F.text.lower() == "reset kuroven")
async def cmd_admin_reset_kuroven(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not message.reply_to_message:
        return await message.reply("⚠️ **Ответьте на сообщение игрока!**", parse_mode="Markdown")
    target_id = message.reply_to_message.from_user.id
    target_user = get_user(target_id, message.reply_to_message.from_user.first_name)
    target_user["transfer_limit_lvl"] = 1
    target_user["transfer_limit"] = 50000
    save_data()
    await message.reply(f"🔄 Уровень лимита игрока **{target_user['name']}** сброшен до базового (1-й уровень, лимит 50,000 глифов).", parse_mode="Markdown")

@dp.message(F.text.lower() == "max kuroven")
async def cmd_admin_max_kuroven(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not message.reply_to_message:
        return await message.reply("⚠️ **Ответьте на сообщение игрока!**", parse_mode="Markdown")
    target_id = message.reply_to_message.from_user.id
    target_user = get_user(target_id, message.reply_to_message.from_user.first_name)
    target_user["transfer_limit_lvl"] = 10
    target_user["transfer_limit"] = 999999999999999
    save_data()
    await message.reply(f"🚀 Уровень лимита игрока **{target_user['name']}** повышен до 10-го (бесконечный лимит).", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("global nakid"))
async def cmd_admin_global_nakid(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) < 3:
        return await message.reply("⚠️ Пример: `global nakid 100к`", parse_mode="Markdown")
    
    amount, err = parse_amount_strict(parts[2])
    if err:
        return await message.reply(err, parse_mode="Markdown")
    
    if not db:
        return await message.reply("⚠️ База данных игроков пуста!", parse_mode="Markdown")

    count = 0
    for uid in db:
        db[uid]["balance"] += amount
        count += 1
    save_data()
    await message.reply(f"🌍 Всем игрокам ({count} чел.) на баланс добавлено: **{amount:,}** глифов!", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("дать") | F.text.lower().startswith("give"))
async def cmd_transfer(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2 or not message.reply_to_message:
        return await message.reply("⚠️ Ответьте на сообщение игрока: `дать 50к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err:
        return await message.reply(err, parse_mode="Markdown")
    
    if user["transfer_limit_lvl"] < 10 and stake > user["transfer_limit"]:
        return await message.reply(f"⚠️ Ваш лимит перевода: **{user['transfer_limit']:,} глифов**!\nЧтобы повысить лимит: `куровень`", parse_mode="Markdown")
        
    target_id = message.reply_to_message.from_user.id
    if target_id == message.from_user.id:
        return await message.reply("⚠️ Нельзя переводить самому себе!")
    target_user = get_user(target_id, message.reply_to_message.from_user.first_name)
    user["balance"] -= stake
    target_user["balance"] += stake
    save_data()
    await message.reply(f"🤝 Вы перевели **{stake:,}** игроку **{target_user['name']}**!", parse_mode="Markdown")

LEVELS_CONFIG = {
    2: {"cost": 100000, "limit": 75000},
    3: {"cost": 200000, "limit": 100000},
    4: {"cost": 350000, "limit": 150000},
    5: {"cost": 600000, "limit": 250000},
    6: {"cost": 1000000, "limit": 400000},
    7: {"cost": 2000000, "limit": 700000},
    8: {"cost": 5000000, "limit": 1200000},
    9: {"cost": 12000000, "limit": 2000000},
    10: {"cost": 30000000, "limit": float('inf')} 
}

@dp.message(F.text.lower() == "куровень")
async def cmd_up_transfer_limit(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    current_lvl = user["transfer_limit_lvl"]
    
    if current_lvl >= 10:
        return await message.reply("🔥 У вас уже максимальный **10-й уровень** и бесконечный лимит!", parse_mode="Markdown")
        
    next_lvl = current_lvl + 1
    cfg = LEVELS_CONFIG[next_lvl]
    cost = cfg["cost"]
    
    if user["balance"] < cost:
        limit_text = "Бесконечно (∞)" if next_lvl == 10 else f"{cfg['limit']:,} глифов"
        return await message.reply(
            f"⚠️ **Повышение лимита ({next_lvl}-й уровень):**\n"
            f"💰 Стоимость: **{cost:,} глифов**\n"
            f"📈 Новый лимит: **{limit_text}**\n\n"
            f"У вас недостаточно средств на балансе!", parse_mode="Markdown"
        )
        
    user["balance"] -= cost
    user["transfer_limit_lvl"] = next_lvl
    if next_lvl == 10:
        user["transfer_limit"] = 999999999999999 
    else:
        user["transfer_limit"] = cfg["limit"]
        
    save_data()
    
    new_limit_str = "Бесконечно (∞) ♾️" if next_lvl == 10 else f"{user['transfer_limit']:,} глифов"
    await message.reply(f"🚀 Успешно! Уровень повышен: **Lvl {next_lvl}**\n💸 Новый лимит перевода: **{new_limit_str}**", parse_mode="Markdown")

@dp.message(F.text.lower().in_({"🏆 топ", "топ", "top"}))
async def cmd_top(message: Message):
    if not db: return await message.reply("🏆 Список игроков пуст.")
    sorted_users = sorted(db.values(), key=lambda x: x["balance"] + x["bank"], reverse=True)[:10]
    res = "🏆 **ТОП-10 БОГАЧЕЙ БОТА:**\n\n"
    for idx, u in enumerate(sorted_users, 1):
        total = u["balance"] + u["bank"]
        res += f"{idx}. **{u['name']}** — {total:,}\n"
    await message.reply(res, parse_mode="Markdown")

@dp.message(F.text.lower().startswith("создатьпромо"))
async def cmd_create_promo(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    parts = message.text.split()
    if len(parts) < 4: return await message.reply("⚠️ Пример: `создатьпромо КОД 100к 5` ")
    code = parts[1].upper()
    val, err = parse_amount_strict(parts[2])
    if err: return await message.reply(err, parse_mode="Markdown")
    uses = int(parts[3])
    promos[code] = {"amount": val, "uses": uses, "users": []}
    save_data()
    await message.reply(f"✅ Промокод `{code}` создан на сумму **{val:,}** ({uses} шт.)", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("промо"))
async def cmd_use_promo(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `промо КОД` ")
    code = parts[1].upper()
    if code not in promos: return await message.reply("❌ Промокод не найден!")
    pr = promos[code]
    if user_id in pr["users"]: return await message.reply("⚠️ Вы уже активировали этот промокод!")
    if pr["uses"] <= 0: return await message.reply("❌ Промокод исчерпан!")
    pr["uses"] -= 1
    pr["users"].append(user_id)
    user["balance"] += pr["amount"]
    save_data()
    await message.reply(f"🎉 Промокод активирован! **+{pr['amount']:,}** зачислено на баланс!", parse_mode="Markdown")

@dp.message(F.text.lower().in_({"б", "b", "баланс", "balance"}))
async def cmd_short_balance(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    await message.reply(f"💸 Баланс: **{user['balance']:,}**", parse_mode="Markdown")

@dp.message(F.text.lower().in_({"банк", "bank"}))
async def cmd_short_bank(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    await message.reply(f"🏦 Банк: **{user['bank']:,}**", parse_mode="Markdown")

@dp.message(F.text.lower().in_({"👤 профиль", "профиль", "profile"}))
async def cmd_profile(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    limit_str = "Бесконечно (∞) ♾️" if user["transfer_limit_lvl"] == 10 else f"{user['transfer_limit']:,} глифов"
    await message.reply(
        f"👤 **ПРОФИЛЬ**\n🆔 ID: `{message.from_user.id}`\n"
        f"✏️ Ник: **{user['name']}**\n"
        f"💸 Баланс: **{user['balance']:,}**\n🏦 Банк: **{user['bank']:,}**\n"
        f"⭐ Уровень: **Lvl {user['transfer_limit_lvl']} / 10**\n"
        f"🤝 Лимит перевода: **{limit_str}**", parse_mode="Markdown"
    )

@dp.message(F.text.lower().in_({"🎁 бонус", "бонус", "bonus"}))
async def cmd_bonus(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    now = datetime.now()
    if user["last_bonus"]:
        last_b = datetime.fromisoformat(user["last_bonus"])
        if now - last_b < timedelta(hours=12):
            rem = timedelta(hours=12) - (now - last_b)
            return await message.reply(f"⏳ Бонус доступен раз в 12 часов! Осталось: {rem.seconds // 3600}ч {(rem.seconds // 60) % 60}м.")
    bonus_val = random.randint(50000, 250000)
    user["balance"] += bonus_val
    user["last_bonus"] = now.isoformat()
    save_data()
    await message.reply(f"🎁 Бонус успешно получен: **+{bonus_val:,}**!", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("банк положить") | F.text.lower().startswith("bank deposit"))
async def cmd_bank_dep(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 3: return await message.reply("⚠️ Пример: `банк положить 50к` ")
    
    stake, err = parse_stake(parts[2], user["balance"])
    if err:
        return await message.reply(err, parse_mode="Markdown")
        
    user["balance"] -= stake
    user["bank"] += stake
    save_data()
    await message.reply(f"🏦 В банк положено: **+{stake:,}**", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("банк снять") | F.text.lower().startswith("bank withdraw"))
async def cmd_bank_wit(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 3: return await message.reply("⚠️ Пример: `банк снять 50к` ")
    
    stake, err = parse_stake(parts[2], user["bank"])
    if err:
        return await message.reply(err, parse_mode="Markdown")
        
    user["bank"] -= stake
    user["balance"] += stake
    save_data()
    await message.reply(f"🏦 Из банка снято: **{stake:,}**", parse_mode="Markdown")

# --- ИГРА MEGAWHEEL (МЕГАВИЛ) ---

MW_SECTORS = {
    "1": ("❄️", 1),
    "2": ("🔵", 2),
    "5": ("🟢", 5),
    "8": ("🟡", 8),
    "10": ("🟠", 10),
    "15": ("🔴", 15),
    "20": ("🟣", 20),
    "40": ("🔥", 40),
    "100": ("💎", 100),
    "500": ("👑", 500),
    "1000": ("⚡", 1000),
    "10000": ("🚀", 10000)
}

async def run_mw_game(chat_id):
    global mw_bets, mw_task, mw_last_msg_id, mw_last_chat_id, mw_round_counter
    
    # Ждем 10 секунд для сбора ставок
    await asyncio.sleep(10)
    
    if not mw_bets:
        if mw_last_msg_id:
            try:
                target_chat_id = chat_id if chat_id else mw_last_chat_id
                await bot.edit_message_text("⚠️ Ставка на раунд MegaWheel закрыта из-за отсутствия ставок!", chat_id=target_chat_id, message_id=mw_last_msg_id, parse_mode="Markdown")
            except Exception:
                pass
        mw_task = None
        mw_last_msg_id = None
        return

    mw_round_counter += 1

    total_bank = sum(b["stake"] for b in mw_bets)
    unique_players = len(set(b["user_id"] for b in mw_bets))
    
    target_chat_id = chat_id if chat_id else mw_last_chat_id
    prep_text = (
        f"🎡 **MegaWheel**\n\n"
        f"🎲 Ставки приняты! (Игроков: {unique_players} | Банк: {total_bank:,})\n"
        f"⏳ Крутим колесо..."
    )
    
    if mw_last_msg_id and target_chat_id:
        try:
            await bot.edit_message_text(prep_text, chat_id=target_chat_id, message_id=mw_last_msg_id, parse_mode="Markdown")
            prep_msg_id = mw_last_msg_id
        except Exception:
            prep_msg = await bot.send_message(target_chat_id, prep_text, parse_mode="Markdown")
            prep_msg_id = prep_msg.message_id
    else:
        prep_msg = await bot.send_message(target_chat_id, prep_text, parse_mode="Markdown")
        prep_msg_id = prep_msg.message_id

    # Ждем еще 3 секунды перед выводом результата
    await asyncio.sleep(3)
    
    # Мультиплеерные иксы и стандартные сектора сбалансированы
    sectors_list = [1, 2, 5, 8, 10, 15, 20, 40, 100, 500, 1000, 10000]
    weights      = [35, 25, 15, 10,  6,  4,  2,  1.5, 0.9, 0.4, 0.1,  0.05]
    
    win_sector_num = random.choices(sectors_list, weights=weights)[0]
    win_sector_code = str(win_sector_num)
    win_emo, final_mult = MW_SECTORS[win_sector_code]
    
    mw_history.insert(0, f"{win_emo} {win_sector_num}x")
    if len(mw_history) > 10: mw_history.pop()

    result_text = f"🎡 **MegaWheel: Результат — {win_emo} {win_sector_num}x!**\n\n"
    
    current_bets = mw_bets.copy()
    mw_bets.clear()
    mw_task = None
    mw_last_msg_id = None
    mw_last_chat_id = None

    grouped_bets = {}
    for b in current_bets:
        sec = b["sector"]
        if sec not in grouped_bets:
            grouped_bets[sec] = []
        grouped_bets[sec].append(b)

    for sec_code, bets_list in grouped_bets.items():
        sec_emo, _ = MW_SECTORS[sec_code]
        result_text += f"{sec_emo} Ставки на {sec_code}x:\n"
        for b in bets_list:
            u_id = b["user_id"]
            u_obj = db.get(u_id)
            is_win = (b["sector"] == win_sector_code)
            if is_win:
                win_amount = b["stake"] * final_mult
                if u_obj:
                    u_obj["balance"] += win_amount
                profit = win_amount - b["stake"]
                add_leaderboard_profit(u_id, profit)
                result_text += f"✅ [{b['name']}] — ставка {b['stake']:,} → +{win_amount:,} глифов\n"
                add_history(u_id, "Мегавил", f"+{win_amount:,}")
            else:
                profit = -b["stake"]
                add_leaderboard_profit(u_id, profit)
                result_text += f"❌ [{b['name']}] — ставка {b['stake']:,} → 0 глифов\n"
                add_history(u_id, "Мегавил", f"-{b['stake']:,}")
        result_text += "\n"
    
    save_data()
    
    repeat_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="mw_repeat_bet")]
    ])
    
    try:
        await bot.edit_message_text(result_text, chat_id=target_chat_id, message_id=prep_msg_id, reply_markup=repeat_kb, parse_mode="Markdown")
    except Exception:
        await bot.send_message(target_chat_id, result_text, reply_markup=repeat_kb, parse_mode="Markdown")

@dp.message(F.text.lower().startswith("мв") | F.text.lower().startswith("мегавил") | F.text.lower().startswith("mw"))
async def game_megawheel(message: Message):
    global mw_bets, mw_task, mw_last_msg_id, mw_last_chat_id

    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 3:
        return await message.reply("⚠️ Пример: `мв 2кк 20` или `мв 5к 10000`", parse_mode="Markdown")
    
    sector_arg = parts[2].lower()
    if sector_arg not in MW_SECTORS:
        return await message.reply("⚠️ Ошибка! Выберите сектор: `1`, `2`, `5`, `8`, `10`, `15`, `20`, `40`, `100`, `500`, `1000`, `10000`", parse_mode="Markdown")

    stake, err = parse_stake(parts[1], user["balance"])
    if err:
        return await message.reply(err, parse_mode="Markdown")
    
    user["balance"] -= stake
    save_data()
    
    sec_emo, _ = MW_SECTORS[sector_arg]
    uid = message.from_user.id

    if uid not in mw_last_bets:
        mw_last_bets[uid] = {}
        
    mw_last_bets[uid][sector_arg] = stake

    mw_bets.append({
        "user_id": uid,
        "name": user["name"],
        "stake": stake,
        "sector": sector_arg
    })

    mw_last_chat_id = message.chat.id
    bet_info_str = f"🎡 {sec_emo} [{user['name']}] поставил {stake:,} глифов на {sector_arg}х (Ожидание раунда: 10 сек...)"

    if mw_task is None:
        msg = await message.reply(bet_info_str, parse_mode="Markdown")
        mw_last_msg_id = msg.message_id
        mw_task = asyncio.create_task(run_mw_game(message.chat.id))
    else:
        await message.reply(bet_info_str, parse_mode="Markdown")

@dp.callback_query(F.data == "mw_repeat_bet")
async def cb_mw_repeat_bet(cb: CallbackQuery):
    global mw_bets, mw_task, mw_last_msg_id, mw_last_chat_id

    uid = cb.from_user.id
    user = get_user(uid, cb.from_user.first_name)
    
    if uid not in mw_last_bets or not mw_last_bets[uid]:
        return await cb.answer("⚠️ У вас нет сохраненных ставок в Мегавил!", show_alert=True)
    
    last_bets_dict = mw_last_bets[uid]
    total_needed = sum(last_bets_dict.values())
    
    if user["balance"] < total_needed:
        return await cb.answer(f"⚠️ Недостаточно средств! Требуется: {total_needed:,} глифов, у вас: {user['balance']:,}", show_alert=True)
    
    user["balance"] -= total_needed
    save_data()
    
    for sec, stake in last_bets_dict.items():
        mw_bets.append({
            "user_id": uid,
            "name": user["name"],
            "stake": stake,
            "sector": sec
        })
    
    await cb.answer("🔁 Ставки повторены!")
    mw_last_chat_id = cb.message.chat.id

    for sec, stake in last_bets_dict.items():
        sec_emo, _ = MW_SECTORS[sec]
        await cb.message.answer(f"🎡 {sec_emo} [{user['name']}] поставил {stake:,} глифов на {sec}х", parse_mode="Markdown")

    if mw_task is None:
        mw_task = asyncio.create_task(run_mw_game(cb.message.chat.id))

@dp.message(F.text.lower() == "вилог")
async def cmd_mw_log(message: Message):
    if not mw_history: 
        return await message.reply("📜 История выпадений MegaWheel пуста.")
    
    text = "📜 **История выпадений MegaWheel (Последние 10):**\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    for idx, item in enumerate(mw_history, 1):
        text += f"🔹 Раунд #{idx} — {item}\n"
    text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
    await message.reply(text, parse_mode="Markdown")

# --- ИГРА Х50 ---

X50_COLOR_MAP = {
    "ч": ("⚫️", "x2", 2), "черный": ("⚫️", "x2", 2), "черное": ("⚫️", "x2", 2), "b": ("⚫️", "x2", 2), "black": ("⚫️", "x2", 2),
    "ф": ("🟣", "x3", 3), "фиолетовый": ("🟣", "x3", 3), "фиолетовое": ("🟣", "x3", 3), "p": ("🟣", "x3", 3), "purple": ("🟣", "x3", 3),
    "к": ("🔴", "x5", 5), "красный": ("🔴", "x5", 5), "красное": ("🔴", "x5", 5), "r": ("🔴", "x5", 5), "red": ("🔴", "x5", 5),
    "з": ("🟢", "x50", 50), "зеленый": ("🟢", "x50", 50), "зеленое": ("🟢", "x50", 50), "g": ("🟢", "x50", 50), "green": ("🟢", "x50", 50)
}

async def run_x50_game(chat_id):
    global x50_round_active, x50_bets, x50_timer_task, x50_last_msg_id, x50_last_chat_id
    
    await asyncio.sleep(15)
    
    if not x50_bets:
        if x50_last_msg_id:
            try:
                target_chat_id = chat_id if chat_id else x50_last_chat_id
                await bot.edit_message_text("⚠️ Ставка на этот раунд закрыта!", chat_id=target_chat_id, message_id=x50_last_msg_id, parse_mode="Markdown")
            except Exception:
                pass
        x50_round_active = False
        x50_timer_task = None
        x50_last_msg_id = None
        return

    x50_round_active = True
    
    roll = random.random()
    if roll < 0.50: mult_str, mult, code, emo = "x2", 2, "ч", "⚫️"
    elif roll < 0.80: mult_str, mult, code, emo = "x3", 3, "ф", "🟣"
    elif roll < 0.95: mult_str, mult, code, emo = "x5", 5, "к", "🔴"
    else: mult_str, mult, code, emo = "x50", 50, "з", "🟢"
    
    x50_history.insert(0, f"{emo} {mult_str}")
    if len(x50_history) > 10: x50_history.pop()

    result_text = f"🎡 Рулетка X50: {emo} {mult_str}\n\n"
    
    current_bets = x50_bets.copy()
    x50_bets.clear()
    x50_round_active = False
    x50_timer_task = None
    x50_last_msg_id = None
    x50_last_chat_id = None

    categories = [
        ("ч", "⚫️ Ставки на x2:"),
        ("ф", "🟣 Ставки на x3:"),
        ("к", "🔴 Ставки на x5:"),
        ("з", "🟢 Ставки на x50:")
    ]

    for cat_code, cat_title in categories:
        cat_bets = [b for b in current_bets if b["choice"] == cat_code]
        if cat_bets:
            result_text += f"{cat_title}\n"
            for b in cat_bets:
                u_id = b["user_id"]
                u_obj = db.get(u_id)
                is_win = (b["choice"] == code)
                if is_win:
                    win_amount = b["stake"] * mult
                    if u_obj:
                        u_obj["balance"] += win_amount
                    profit = win_amount - b["stake"]
                    add_leaderboard_profit(u_id, profit)
                    result_text += f"✅ [{b['name']}] -- ставка {b['stake']:,} → +{win_amount:,} gif\n"
                    add_history(u_id, "Х50", f"+{win_amount:,}")
                else:
                    profit = -b["stake"]
                    add_leaderboard_profit(u_id, profit)
                    result_text += f"❌ [{b['name']}] -- ставка {b['stake']:,} → 0 gif\n"
                    add_history(u_id, "Х50", f"-{b['stake']:,}")
            result_text += "\n"
    
    save_data()
    
    repeat_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="x50_repeat_bet")]
    ])
    
    target_chat_id = chat_id if chat_id else x50_last_chat_id
    if x50_last_msg_id and target_chat_id:
        try:
            await bot.edit_message_text(result_text, chat_id=target_chat_id, message_id=x50_last_msg_id, reply_markup=repeat_kb, parse_mode="Markdown")
            return
        except Exception:
            pass
    await bot.send_message(target_chat_id, result_text, reply_markup=repeat_kb, parse_mode="Markdown")

@dp.message(F.text.lower().startswith("х50") | F.text.lower().startswith("x50"))
async def game_x50(message: Message):
    global x50_bets, x50_timer_task, x50_last_msg_id, x50_last_chat_id

    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 3:
        return await message.reply("⚠️ Пример: `Х50 1к ф` или `Х50 10k ч`", parse_mode="Markdown")
    
    choice_code = parts[2].lower()
    if choice_code not in X50_COLOR_MAP:
        return await message.reply("⚠️ Ошибка! Выберите цвет: `ч`, `ф`, `к` или `з`", parse_mode="Markdown")

    stake, err = parse_stake(parts[1], user["balance"])
    if err:
        return await message.reply(err, parse_mode="Markdown")
    
    user["balance"] -= stake
    save_data()
    
    color_emo, mult_str, mult_num = X50_COLOR_MAP[choice_code]
    
    norm_code = "ч" if choice_code in ["ч", "черный", "черное", "b", "black"] else \
                "ф" if choice_code in ["ф", "фиолетовый", "фиолетовое", "p", "purple"] else \
                "к" if choice_code in ["к", "красный", "красное", "r", "red"] else "з"

    uid = message.from_user.id
    if uid not in x50_last_bets:
        x50_last_bets[uid] = {}

    x50_last_bets[uid][norm_code] = stake

    x50_bets.append({
        "user_id": uid,
        "name": user["name"],
        "stake": stake,
        "choice": norm_code
    })
    
    x50_last_chat_id = message.chat.id
    bet_log_text = f"{color_emo} [{user['name']}] поставил {stake:,} gif на {mult_str}"

    if x50_timer_task is None:
        msg = await message.reply(bet_log_text, parse_mode="Markdown")
        x50_last_msg_id = msg.message_id
        x50_timer_task = asyncio.create_task(run_x50_game(message.chat.id))
    else:
        await message.reply(bet_log_text, parse_mode="Markdown")

@dp.callback_query(F.data == "x50_repeat_bet")
async def cb_x50_repeat_bet(cb: CallbackQuery):
    global x50_bets, x50_timer_task, x50_last_msg_id, x50_last_chat_id

    uid = cb.from_user.id
    user = get_user(uid, cb.from_user.first_name)
    
    if uid not in x50_last_bets or not x50_last_bets[uid]:
        return await cb.answer("⚠️ У вас нет сохраненных ставок в Х50!", show_alert=True)
    
    last_bets_dict = x50_last_bets[uid]
    total_needed = sum(last_bets_dict.values())
    
    if user["balance"] < total_needed:
        return await cb.answer(f"⚠️ Недостаточно средств! Требуется: {total_needed:,} глифов, баланс: {user['balance']:,}", show_alert=True)
    
    user["balance"] -= total_needed
    save_data()
    
    for norm_code, stake in last_bets_dict.items():
        x50_bets.append({
            "user_id": uid,
            "name": user["name"],
            "stake": stake,
            "choice": norm_code
        })
    
    x50_last_chat_id = cb.message.chat.id

    for norm_code, stake in last_bets_dict.items():
        color_emo, mult_str, _ = X50_COLOR_MAP[norm_code]
        await cb.message.answer(f"{color_emo} [{user['name']}] поставил {stake:,} gif на {mult_str}", parse_mode="Markdown")

    if x50_timer_task is None:
        x50_timer_task = asyncio.create_task(run_x50_game(cb.message.chat.id))

    await cb.answer("🔁 Ставки повторены!")

@dp.message(F.text.lower() == "дроп")
async def cmd_drop(message: Message):
    if not x50_history: return await message.reply("📜 История X50 пуста.")
    await message.reply("📜 **История X50:**\n" + "\n".join(f"• {item}" for item in x50_history), parse_mode="Markdown")

# --- ИГРА HILO ---

def get_hilo_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔼 Выше", callback_data="hilo_higher"),
            InlineKeyboardButton(text="🔽 Ниже", callback_data="hilo_lower")
        ],
        [
            InlineKeyboardButton(text="🤝 Равно", callback_data="hilo_equal"),
            InlineKeyboardButton(text="💰 Забрать", callback_data="hilo_take")
        ]
    ])

@dp.message(F.text.lower().startswith("хило") | F.text.lower().startswith("hilo"))
async def game_hilo_start(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `хило 50к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err:
        return await message.reply(err, parse_mode="Markdown")
    
    user["balance"] -= stake
    save_data()
    
    first_card = random.choice(CARDS_LIST)
    active_hilo[user_id] = {
        "stake": stake, 
        "current_card": first_card, 
        "streak": 0,
        "mult": 1.0
    }
    
    await message.reply(
        f"🎮 **HiLo** начался!\n"
        f"💰 Ставка: **{stake:,}**\n"
        f"🃏 Выпавшая карта: **{first_card}**\n\n"
        f"Сделайте свой выбор:",
        reply_markup=get_hilo_kb(), parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("hilo_"))
async def process_hilo_action(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    if uid not in active_hilo:
        return await cb.message.edit_text("⚠️ Игра HiLo не найдена или уже завершена!", parse_mode="Markdown")
    
    g = active_hilo[uid]
    action = cb.data.replace("hilo_", "")
    user = get_user(uid, cb.from_user.first_name)
    
    if action == "take":
        win = int(g["stake"] * g["mult"])
        user["balance"] += win
        profit = win - g["stake"]
        if profit > 0:
            add_leaderboard_profit(uid, profit)
        save_data()
        del active_hilo[uid]
        return await cb.message.edit_text(f"💰 **HiLo завершена!** Вы забрали выигрыш: **+{win:,}**", parse_mode="Markdown")
    
    old_card = g["current_card"]
    old_val = CARDS_MAP[old_card]
    new_card = random.choice(CARDS_LIST)
    new_val = CARDS_MAP[new_card]
    
    success = False
    if action == "higher" and new_val > old_val: success = True
    elif action == "lower" and new_val < old_val: success = True
    elif action == "equal" and new_val == old_val: success = True
    
    if success:
        g["streak"] += 1
        g["current_card"] = new_card
        g["mult"] = round(g["mult"] * 1.5, 2)
        win_preview = int(g["stake"] * g["mult"])
        
        await cb.message.edit_text(
            f"🎮 **HiLo**\n"
            f"🃏 Прошлая карта: {old_card} ➡️ Новая: **{new_card}** ✅\n"
            f"📈 Серия: **{g['streak']}** | Награда: **+{win_preview:,}**\n\n"
            f"Продолжаем игру?",
            reply_markup=get_hilo_kb(), parse_mode="Markdown"
        )
    else:
        stake_lost = g["stake"]
        add_leaderboard_profit(uid, -stake_lost)
        del active_hilo[uid]
        await cb.message.edit_text(
            f"🎮 **HiLo**\n"
            f"🃏 Прошлая карта: {old_card} ➡️ Новая: **{new_card}** ❌\n"
            f"💔 Вы проиграли! Потеряно: **-{stake_lost:,}**",
            parse_mode="Markdown"
        )

# --- ИГРА РАЙЗ ---

RISE_STAGES = [
    {"step": 1, "bombs": 2, "gems": 3, "mult": 1.25},
    {"step": 2, "bombs": 2, "gems": 3, "mult": 1.65},
    {"step": 3, "bombs": 3, "gems": 2, "mult": 2.30},
    {"step": 4, "bombs": 3, "gems": 2, "mult": 3.45},
    {"step": 5, "bombs": 4, "gems": 1, "mult": 5.50},
    {"step": 6, "bombs": 4, "gems": 1, "mult": 9.20},
    {"step": 7, "bombs": 4, "gems": 1, "mult": 16.50}
]

def get_rise_kb(stage_idx: int, revealed=None):
    row = []
    for i in range(5):
        if revealed and i in revealed:
            txt = revealed[i]
        else:
            txt = "❓"
        row.append(InlineKeyboardButton(text=txt, callback_data=f"rise_cell_{i}"))
    kb = [row]
    if stage_idx > 0:
        kb.append([InlineKeyboardButton(text="💰 Забрать выигрыш", callback_data="rise_take")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(F.text.lower().startswith("райз") | F.text.lower().startswith("рз") | F.text.lower().startswith("rise") | F.text.lower().startswith("rz"))
async def game_rise_start(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `рз 50к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err:
        return await message.reply(err, parse_mode="Markdown")
    
    user["balance"] -= stake
    save_data()
    
    st = RISE_STAGES[0]
    total_cells = 5
    bomb_indices = set(random.sample(range(total_cells), st["bombs"]))
    
    active_rise[user_id] = {
        "stake": stake,
        "stage": 0,
        "bombs": bomb_indices,
        "total_cells": total_cells,
        "history_lines": [], 
        "revealed": {}
    }
    
    await message.reply(
        f"Игра Райз началась!\n\n"
        f"🚀 Ставка райз: **{stake:,}**\n\n"
        f"❓ ❓ ❓ ❓ ❓\n"
        f"1-й этап | {st['bombs']} бомба, {st['gems']} алмаз | **{st['mult']}x**\n\n"
        f"Выберите ячейку:",
        reply_markup=get_rise_kb(0), parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("rise_"))
async def process_rise_action(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    if uid not in active_rise:
        return await cb.message.edit_text("⚠️ Игра Райз не найдена или уже завершена!", parse_mode="Markdown")
    
    g = active_rise[uid]
    user = get_user(uid, cb.from_user.first_name)
    
    if cb.data == "rise_take":
        if g["stage"] == 0:
            return
        prev_stage = g["stage"] - 1
        mult = RISE_STAGES[prev_stage]["mult"]
        win = int(g["stake"] * mult)
        user["balance"] += win
        profit = win - g["stake"]
        if profit > 0:
            add_leaderboard_profit(uid, profit)
        save_data()
        del active_rise[uid]
        return await cb.message.edit_text(f"Игра Райз завершена!\n\n💰 Вы забрали выигрыш: **+{win:,}** (Множитель: {mult}x)", parse_mode="Markdown")
    
    if cb.data.startswith("rise_cell_"):
        stage_idx = g["stage"]
        st = RISE_STAGES[stage_idx]
        cell_idx = int(cb.data.split("_")[2])
        
        if cell_idx in g["revealed"]:
            return
            
        if cell_idx in g["bombs"]:
            for i in range(g["total_cells"]):
                if i in g["bombs"]:
                    g["revealed"][i] = "💣"
                else:
                    g["revealed"][i] = "💎"
            
            line_str = " ".join([g["revealed"][i] for i in range(5)])
            g["history_lines"].append(line_str)
            
            stake_lost = g["stake"]
            add_leaderboard_profit(uid, -stake_lost)
            
            full_history_text = "\n".join(g["history_lines"])
            del active_rise[uid]
            return await cb.message.edit_text(
                f"Игра Райз завершена!\n\n"
                f"💥 **Райз ({stage_idx + 1}-й этап):** Вы попали на бомбу 💣!\n\n"
                f"{full_history_text}\n\n"
                f"💔 Проигрыш: **-{stake_lost:,}**", parse_mode="Markdown"
            )
        else:
            g["revealed"][cell_idx] = "💎"
            
            for i in range(5):
                if i in g["bombs"]:
                    g["revealed"][i] = "💣"
                else:
                    g["revealed"][i] = "💎"
            
            line_str = " ".join([g["revealed"][i] for i in range(5)])
            g["history_lines"].append(line_str)
            
            g["stage"] += 1
            if g["stage"] >= len(RISE_STAGES):
                mult = RISE_STAGES[-1]["mult"]
                win = int(g["stake"] * mult)
                user["balance"] += win
                profit = win - g["stake"]
                add_leaderboard_profit(uid, profit)
                save_data()
                full_history_text = "\n".join(g["history_lines"])
                del active_rise[uid]
                return await cb.message.edit_text(f"Игра Райз завершена!\n\n🏆 **ГРАНДИОЗНАЯ ПОБЕДА!** Вы прошли все 7 этапов!\n\n{full_history_text}\n\nВыигрыш: **+{win:,}** ({mult}x)", parse_mode="Markdown")
            
            next_st = RISE_STAGES[g["stage"]]
            g["bombs"] = set(random.sample(range(5), next_st["bombs"]))
            g["revealed"] = {}
            
            full_history_text = "\n".join(g["history_lines"])
            await cb.message.edit_text(
                f"Игра Райз продолжается!\n\n"
                f"🚀 Ставка райз: **{g['stake']:,}**\n\n"
                f"{full_history_text}\n\n"
                f"❓ ❓ ❓ ❓ ❓\n"
                f"{g['stage']+1}-й этап | {next_st['bombs']} бомба, {next_st['gems']} алмаз | **{next_st['mult']}x**\n\n"
                f"Выберите ячейку:",
                reply_markup=get_rise_kb(g["stage"]), parse_mode="Markdown"
            )

# --- ИГРА РУЛЕТКА ---

ROULETTE_HELP_TEXT = (
    "🎰 **РУЛЕТКА:**\n"
    "• `рул [ставка] [выбор]`\n"
    "• `рул [ставка]` (выбор кнопками)\n\n"
    "💡 **Виды ставок:**\n"
    "- Число (например `рул 50к 7` -> **34x**)\n"
    "- Диапазон (например `рул 50к 1-5` -> **8x**)\n"
    "- Цвета (`ч`, `к` -> **1.9x**)\n"
    "- Дюжины (`1д`, `2д`, `3д` -> **3.0x**)\n\n"
    "⚠️ **Для запуска рулетки:** После ставки напишите **«го»**!"
)

def get_roulette_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Красное", callback_data="rl_k"), InlineKeyboardButton(text="⚫ Черное", callback_data="rl_ch")],
        [InlineKeyboardButton(text="🟢 Четное", callback_data="rl_chet"), InlineKeyboardButton(text="🟠 Нечетное", callback_data="rl_nechet")],
        [InlineKeyboardButton(text="1-18", callback_data="rl_1_18"), InlineKeyboardButton(text="19-36", callback_data="rl_19_36")],
        [InlineKeyboardButton(text="1-я дюжина (1-12)", callback_data="rl_d1"), InlineKeyboardButton(text="2-я дюжина (13-24)", callback_data="rl_d2")],
        [InlineKeyboardButton(text="3-я дюжина (25-36)", callback_data="rl_d3")],
        [InlineKeyboardButton(text="🟢 ЗЕРО", callback_data="rl_z")]
    ])

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 17, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

def get_number_count_multiplier(count: int) -> float:
    if count <= 0: return 0.0
    if count == 1: return 34.0
    elif count == 2: return 17.0
    elif count == 3: return 13.0
    elif count == 4: return 10.0
    elif count == 5: return 8.0
    elif count == 6: return 6.5
    elif count == 7: return 5.5
    elif count == 8: return 4.8
    elif count == 9: return 4.2
    elif count == 10: return 3.8
    elif count == 11: return 3.4
    elif count == 12: return 3.0
    elif count == 18: return 1.9
    elif count >= 37: return 0.75
    else:
        if count > 30: return max(0.75, round(32.0 / count, 2))
        return round(36.0 / count, 2)

@dp.message(F.text.lower().startswith("рул") | F.text.lower().startswith("rul") | F.text.lower().startswith("рулетка"))
async def game_roulette_start(message: Message):
    global roulette_round_active, roulette_bets, pending_roulette_stakes
    user = get_user(message.from_user.id, message.from_user.first_name)
    
    parts = message.text.split()
    if len(parts) < 2: 
        return await message.reply(ROULETTE_HELP_TEXT, parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err:
        return await message.reply(err, parse_mode="Markdown")
    
    if len(parts) >= 3:
        choice_arg = " ".join(parts[2:]).lower().strip()
        
        if "-" in choice_arg and choice_arg.replace("-", "").isdigit():
            try:
                rng_parts = choice_arg.split("-")
                r_min, r_max = int(rng_parts[0]), int(rng_parts[1])
                r_min, r_max = min(r_min, r_max), max(r_min, r_max)
                if r_min < 0: r_min = 0
                if r_max > 36: r_max = 36
                
                count = (r_max - r_min) + 1
                mult = get_number_count_multiplier(count)
                
                user["balance"] -= stake
                save_data()
                
                roulette_bets.append({
                    "user_id": message.from_user.id,
                    "name": user["name"],
                    "stake": stake,
                    "choices": [r_min, r_max],
                    "type": "range",
                    "count": count,
                    "mult": mult
                })
                
                mult_txt = f"{mult}x" if mult > 0 else "-0.25x"
                await message.reply(
                    f"🎲 **{user['name']}** поставил **{stake:,} глифов** на диапазон `{r_min}-{r_max}` ({count} чисел, K: {mult_txt})\n"
                    f"💸 Баланс: **{user['balance']:,} глифов**\n\n"
                    f"💬 Напишите **го** для запуска рулетки!", parse_mode="Markdown"
                )
                return
            except Exception:
                pass

        raw_choices = parts[2:]
        numbers_chosen = []
        for item in raw_choices:
            if item.isdigit() and 0 <= int(item) <= 36:
                numbers_chosen.append(int(item))
                
        if numbers_chosen and len(numbers_chosen) == len(raw_choices):
            count = len(numbers_chosen)
            mult = get_number_count_multiplier(count)
            
            user["balance"] -= stake
            save_data()
            
            roulette_bets.append({
                "user_id": message.from_user.id,
                "name": user["name"],
                "stake": stake,
                "choices": numbers_chosen,
                "type": "numbers",
                "count": count,
                "mult": mult
            })
            
            nums_str = " ".join(map(str, numbers_chosen))
            await message.reply(
                f"🎲 **{user['name']}** поставил **{stake:,} глифов** на числа: `{nums_str}` (K: {mult}x)\n"
                f"💸 Баланс: **{user['balance']:,} глифов**\n\n"
                f"💬 Напишите **го** для запуска рулетки!", parse_mode="Markdown"
            )
            return

        choice = raw_choices[0].lower()
        user["balance"] -= stake
        save_data()
        
        roulette_bets.append({
            "user_id": message.from_user.id,
            "name": user["name"],
            "stake": stake,
            "choices": choice,
            "type": "single"
        })
        
        choice_name = choice
        if choice in ["ч", "черный", "черное", "b", "black"]: choice_name = "на чёрный цвет (1.9x)"
        elif choice in ["к", "красный", "красное", "r", "red"]: choice_name = "на красный цвет (1.9x)"
        elif choice in ["d1", "1д"]: choice_name = "на 1-ю дюжину (3.0x)"
        elif choice in ["d2", "2д"]: choice_name = "на 2-ю дюжину (3.0x)"
        elif choice in ["d3", "3д"]: choice_name = "на 3-ю дюжину (3.0x)"
        elif choice in ["chet", "чет"]: choice_name = "на четное (1.9x)"
        elif choice in ["nechet", "нечет"]: choice_name = "на нечетное (1.9x)"
        elif choice.isdigit(): choice_name = f"на число {choice} (34x)"
        
        await message.reply(
            f"🎲 **{user['name']}** поставил **{stake:,} глифов** {choice_name}\n"
            f"💸 Баланс: **{user['balance']:,} глифов**\n\n"
            f"💬 Напишите **го** для запуска рулетки!", parse_mode="Markdown"
        )
        return

    pending_roulette_stakes[message.from_user.id] = stake
    await message.reply(
        f"🎰 **РУЛЕТКА**\n💰 Ставка: **{stake:,}**\n🎯 **Выберите исход кнопкой или используйте текстовый ввод:**",
        reply_markup=get_roulette_kb(), parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("rl_"))
async def process_roulette_choice(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    user = get_user(uid, cb.from_user.first_name)
    choice_raw = cb.data.replace("rl_", "")
    
    stake = pending_roulette_stakes.pop(uid, 50000)
    if user["balance"] < stake:
        return await cb.message.edit_text(f"⚠️ Недостаточно средств на балансе! (Ваш баланс: **{user['balance']:,}**)", parse_mode="Markdown")
        
    user["balance"] -= stake
    save_data()
    
    roulette_bets.append({
        "user_id": uid,
        "name": user["name"],
        "stake": stake,
        "choices": choice_raw,
        "type": "single"
    })
    
    choice_name = choice_raw
    if choice_raw == "ch": choice_name = "на чёрный цвет"
    elif choice_raw == "k": choice_name = "на красный цвет"
    elif choice_raw == "1_18": choice_name = "на 1-18"
    elif choice_raw == "19_36": choice_name = "на 19-36"
    elif choice_raw == "d1": choice_name = "на 1-ю дюжину (1-12)"
    elif choice_raw == "d2": choice_name = "на 2-ю дюжину (13-24)"
    elif choice_raw == "d3": choice_name = "на 3-ю дюжину (25-36)"
    
    await cb.message.edit_text(f"🎲 Игрок **{user['name']}** поставил **{stake:,} глифов** {choice_name}\n💸 Баланс: **{user['balance']:,} глифов**\n\n💬 Напишите **го** для старта раунда!")

@dp.message(F.text.lower().in_({"го", "гоу", "go"}))
async def cmd_roulette_go(message: Message):
    global roulette_round_active, roulette_bets
    if not roulette_bets:
        return await message.reply("⚠️ **В рулетке нет активных ставок!**\nСначала сделайте ставку: `рул [ставка] [выбор]`", parse_mode="Markdown")
    
    await execute_roulette(message)

async def execute_roulette(message_obj):
    global roulette_round_active, roulette_bets
    roulette_round_active = False
    
    num = random.randint(0, 36)
    color_emo = "🟢" if num == 0 else ("🔴" if num in RED_NUMBERS else "⚫️")
    roulette_history.insert(0, f"{color_emo} {num}")
    if len(roulette_history) > 10: roulette_history.pop()

    res_msg = f"🎰 **Результат рулетки:** {color_emo} **{num}**\n\n"
    current_bets = roulette_bets.copy()
    roulette_bets.clear()

    for b in current_bets:
        uid = b["user_id"]
        u_obj = db.get(uid)
        if not u_obj: continue
        
        b_type = b.get("type", "single")
        stake = b["stake"]
        
        if b_type == "range":
            r_min, r_max = b["choices"]
            mult = b["mult"]
            if r_min <= num <= r_max:
                win = int(stake * mult)
                u_obj["balance"] += win
                profit = win - stake
                add_leaderboard_profit(uid, profit)
                res_msg += f"👤 {b['name']} ({stake:,} глифов) — выигрыш **+{win:,} глифов** ✅\n"
            else:
                profit = -stake
                add_leaderboard_profit(uid, profit)
                res_msg += f"👤 {b['name']} ({stake:,} глифов) — проигрыш ❌\n"
                
        elif b_type == "numbers":
            chosen_nums = b["choices"]
            mult = b["mult"]
            if num in chosen_nums:
                win = int(stake * mult)
                u_obj["balance"] += win
                profit = win - stake
                add_leaderboard_profit(uid, profit)
                res_msg += f"👤 {b['name']} ({stake:,} глифов) — выигрыш **+{win:,} глифов** ✅\n"
            else:
                profit = -stake
                add_leaderboard_profit(uid, profit)
                res_msg += f"👤 {b['name']} ({stake:,} глифов) — проигрыш ❌\n"
        else:
            choice = str(b["choices"]).lower()
            mult = 0
            
            if choice.isdigit():
                if int(choice) == num:
                    mult = 34.0
            else:
                if choice in ["k", "красное", "красный", "r", "red"] and num in RED_NUMBERS: mult = 1.9
                elif choice in ["ch", "черное", "черный", "ч", "b", "black"] and num not in RED_NUMBERS and num != 0: mult = 1.9
                elif choice in ["chet", "чет", "odd"] and num % 2 == 0 and num != 0: mult = 1.9
                elif choice in ["nechet", "нечет", "even"] and num % 2 != 0 and num != 0: mult = 1.9
                elif choice in ["1_18", "low"] and 1 <= num <= 18: mult = 1.9
                elif choice in ["19_36", "high"] and 19 <= num <= 36: mult = 1.9
                elif choice in ["d1", "1д"] and 1 <= num <= 12: mult = 3.0
                elif choice in ["d2", "2д"] and 13 <= num <= 24: mult = 3.0
                elif choice in ["d3", "3д"] and 25 <= num <= 36: mult = 3.0
                elif choice in ["z", "зеро"] and num == 0: mult = 34.0

            if mult > 0:
                win = int(stake * mult)
                u_obj["balance"] += win
                profit = win - stake
                add_leaderboard_profit(uid, profit)
                res_msg += f"👤 {b['name']} ({stake:,} глифов) — выигрыш **+{win:,} глифов** ✅\n"
            else:
                profit = -stake
                add_leaderboard_profit(uid, profit)
                res_msg += f"👤 {b['name']} ({stake:,} глифов) — проигрыш ❌\n"

    save_data()
    await message_obj.bot.send_message(message_obj.chat.id, res_msg, parse_mode="Markdown")

@dp.message(F.text.lower() == "лог")
async def cmd_roulette_log(message: Message):
    if not roulette_history: return await message.reply("📜 История рулетки пуста.")
    await message.reply("📜 **История рулетки:**\n" + "\n".join(f"• {item}" for item in roulette_history), parse_mode="Markdown")

# --- СЛОТЫ ---

SLOT_SYMBOLS = ["🍋", "🍒", "7️⃣", "🔔", "💎", "⭐", "🍉", "🍇", "☃️", "🍭"]

@dp.message(F.text.lower().startswith("слоты") | F.text.lower().startswith("slots"))
async def game_slots(message: Message):
    uid = message.from_user.id
    user = get_user(uid, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `слоты 50к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err:
        return await message.reply(err, parse_mode="Markdown")
    
    user["balance"] -= stake
    slots_last_bets[uid] = stake
    save_data()
    
    msg = await message.reply("🎰 [ 🔄 │ 🔄 │ 🔄 ]")
    
    for _ in range(3):
        await asyncio.sleep(0.3)
        tmp = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
        await msg.edit_text(f"🎰 [ {tmp[0]} │ {tmp[1]} │ {tmp[2]} ]")
    
    await asyncio.sleep(0.3)
    c = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
    
    multiplier = 0.0
    if c[0] == c[1] == c[2]:
        if c[0] in ["💎", "7️⃣", "⭐"]:
            multiplier = 10.0
        elif c[0] in ["🔔", "🍒", "🍇", "🍉"]:
            multiplier = 5.0
        else:
            multiplier = 3.5
    elif c[0] == c[1] or c[1] == c[2] or c[0] == c[2]:
        multiplier = random.choice([1.5, 1.8, 2.0])
    else:
        multiplier = 0.0

    repeat_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="slots_repeat_bet")]
    ])

    if multiplier > 0:
        win = int(stake * multiplier)
        user["balance"] += win
        profit = win - stake
        add_leaderboard_profit(uid, profit)
        save_data()
        
        txt = (
            f"🎰 **СЛОТЫ**\n\n"
            f"> 👤 **Игрок:** {user['name']}\n"
            f"> 💵 **Ставка:** {stake:,} глифов\n"
            f"> \n"
            f"> │ {c[0]} │ {c[1]} │ {c[2]} │\n"
            f"> \n"
            f"> 🎉 **ВЫИГРЫШ!**\n"
            f"> 💰 **Получено:** +{win:,} глифов\n"
            f"> 📈 **Множитель:** x{multiplier}"
        )
    else:
        profit = -stake
        add_leaderboard_profit(uid, profit)
        save_data()
        
        txt = (
            f"🎰 **СЛОТЫ**\n\n"
            f"> 👤 **Игрок:** {user['name']}\n"
            f"> 💵 **Ставка:** {stake:,} глифов\n"
            f"> \n"
            f"> │ {c[0]} │ {c[1]} │ {c[2]} │\n"
            f"> \n"
            f"> 💔 **ПРОИГРЫШ!**\n"
            f"> 💰 **Потеряно:** -{stake:,} глифов\n"
            f"> 📈 **Множитель:** x0"
        )
        
    await msg.edit_text(txt, reply_markup=repeat_kb, parse_mode="Markdown")

@dp.callback_query(F.data == "slots_repeat_bet")
async def cb_slots_repeat_bet(cb: CallbackQuery):
    uid = cb.from_user.id
    user = get_user(uid, cb.from_user.first_name)
    
    if uid not in slots_last_bets:
        return await cb.answer("⚠️ У вас нет сохраненных ставок в Слотах!", show_alert=True)
    
    stake = slots_last_bets[uid]
    if user["balance"] < stake:
        return await cb.answer(f"⚠️ Недостаточно средств! Требуется: {stake:,} глифов, у вас: {user['balance']:,}", show_alert=True)
    
    user["balance"] -= stake
    save_data()
    await cb.answer("🔁 Ставка повторена!")
    
    msg = await cb.message.answer("🎰 [ 🔄 │ 🔄 │ 🔄 ]")
    
    for _ in range(3):
        await asyncio.sleep(0.3)
        tmp = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
        await msg.edit_text(f"🎰 [ {tmp[0]} │ {tmp[1]} │ {tmp[2]} ]")
    
    await asyncio.sleep(0.3)
    c = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
    
    multiplier = 0.0
    if c[0] == c[1] == c[2]:
        if c[0] in ["💎", "7️⃣", "⭐"]:
            multiplier = 10.0
        elif c[0] in ["🔔", "🍒", "🍇", "🍉"]:
            multiplier = 5.0
        else:
            multiplier = 3.5
    elif c[0] == c[1] or c[1] == c[2] or c[0] == c[2]:
        multiplier = random.choice([1.5, 1.8, 2.0])
    else:
        multiplier = 0.0

    repeat_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="slots_repeat_bet")]
    ])

    if multiplier > 0:
        win = int(stake * multiplier)
        user["balance"] += win
        profit = win - stake
        add_leaderboard_profit(uid, profit)
        save_data()
        
        txt = (
            f"🎰 **СЛОТЫ**\n\n"
            f"> 👤 **Игрок:** {user['name']}\n"
            f"> 💵 **Ставка:** {stake:,} глифов\n"
            f"> \n"
            f"> │ {c[0]} │ {c[1]} │ {c[2]} │\n"
            f"> \n"
            f"> 🎉 **ВЫИГРЫШ!**\n"
            f"> 💰 **Получено:** +{win:,} глифов\n"
            f"> 📈 **Множитель:** x{multiplier}"
        )
    else:
        profit = -stake
        add_leaderboard_profit(uid, profit)
        save_data()
        
        txt = (
            f"🎰 **СЛОТЫ**\n\n"
            f"> 👤 **Игрок:** {user['name']}\n"
            f"> 💵 **Ставка:** {stake:,} глифов\n"
            f"> \n"
            f"> │ {c[0]} │ {c[1]} │ {c[2]} │\n"
            f"> \n"
            f"> 💔 **ПРОИГРЫШ!**\n"
            f"> 💰 **Потеряно:** -{stake:,} глифов\n"
            f"> 📈 **Множитель:** x0"
        )
        
    await msg.edit_text(txt, reply_markup=repeat_kb, parse_mode="Markdown")

@dp.message(F.text.lower().startswith("баскетбол") | F.text.lower().startswith("баск") | F.text.lower().startswith("bask"))
async def game_basket(message: Message):
    uid = message.from_user.id
    user = get_user(uid, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 3: 
        return await message.reply("⚠️ Пример: `баскетбол 50к попадание`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err:
        return await message.reply(err, parse_mode="Markdown")
    
    choice = parts[2].lower()
    user["balance"] -= stake
    save_data()
    
    dice_msg = await message.answer_dice("🏀")
    await asyncio.sleep(2.5)
    score = dice_msg.dice.value
    is_hit = score in [4, 5]
    user_guessed = (is_hit and choice.startswith("попад")) or (not is_hit and choice == "мимо")
    
    if user_guessed:
        win = int(stake * 1.9)
        user["balance"] += win
        profit = win - stake
        add_leaderboard_profit(uid, profit)
        save_data()
        await message.reply(f"🏀 **Точно в цель!** Выигрыш: **+{win:,}**", parse_mode="Markdown")
    else:
        profit = -stake
        add_leaderboard_profit(uid, profit)
        save_data()
        await message.reply(f"🏀 **Мимо кольца!** Проигрыш: **-{stake:,}**", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("охота") | F.text.lower().startswith("hunt"))
async def game_hunt(message: Message):
    uid = message.from_user.id
    user = get_user(uid, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `охота 50к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err:
        return await message.reply(err, parse_mode="Markdown")
    
    user["balance"] -= stake
    hunt_last_bets[uid] = stake
    save_data()
    
    scenarios = [
        "🌲 Вы отправились в глухой ночной лес в поисках дичи. Точный выстрел!",
        "🏜️ Жаркая пустыня. Из-за бархана показался редкий зверь. Вы прицелились...",
        "⛰️ Скалистые горы. Затаив дыхание, вы производите выстрел по горному барсу...",
        "🌊 Густые джунгли у реки. Из воды появился гигантский аллигатор!"
    ]
    
    msg = await message.reply(random.choice(scenarios))
    await asyncio.sleep(3)
    
    repeat_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="hunt_repeat_bet")]
    ])
    
    if random.random() > 0.45:
        win = int(stake * 1.88)
        user["balance"] += win
        profit = win - stake
        add_leaderboard_profit(uid, profit)
        save_data()
        await msg.edit_text(f"🎯 **Успешная охота!** Выигрыш: **+{win:,}**", reply_markup=repeat_kb, parse_mode="Markdown")
    else:
        profit = -stake
        add_leaderboard_profit(uid, profit)
        save_data()
        await msg.edit_text(f"🎯 **Неудача!** Ставка сгорела: **-{stake:,}** 💔", reply_markup=repeat_kb, parse_mode="Markdown")

@dp.callback_query(F.data == "hunt_repeat_bet")
async def cb_hunt_repeat_bet(cb: CallbackQuery):
    uid = cb.from_user.id
    user = get_user(uid, cb.from_user.first_name)
    
    if uid not in hunt_last_bets:
        return await cb.answer("⚠️ У вас нет сохраненных ставок в Охоте!", show_alert=True)
    
    stake = hunt_last_bets[uid]
    if user["balance"] < stake:
        return await cb.answer(f"⚠️ Недостаточно средств! Требуется: {stake:,} глифов, у вас: {user['balance']:,}", show_alert=True)
    
    user["balance"] -= stake
    save_data()
    await cb.answer("🔁 Ставка повторена!")
    
    scenarios = [
        "🌲 Вы отправились в глухой ночной лес в поисках дичи. Точный выстрел!",
        "🏜️ Жаркая пустыня. Из-за бархана показался редкий зверь. Вы прицелились...",
        "⛰️ Скалистые горы. Затаив дыхание, вы производите выстрел по горному барсу...",
        "🌊 Густые джунгли у реки. Из воды появился гигантский аллигатор!"
    ]
    
    msg = await cb.message.answer(random.choice(scenarios))
    await asyncio.sleep(3)
    
    repeat_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="hunt_repeat_bet")]
    ])
    
    if random.random() > 0.45:
        win = int(stake * 1.88)
        user["balance"] += win
        profit = win - stake
        add_leaderboard_profit(uid, profit)
        save_data()
        await msg.edit_text(f"🎯 **Успешная охота!** Выигрыш: **+{win:,}**", reply_markup=repeat_kb, parse_mode="Markdown")
    else:
        profit = -stake
        add_leaderboard_profit(uid, profit)
        save_data()
        await msg.edit_text(f"🎯 **Неудача!** Ставка сгорела: **-{stake:,}** 💔", reply_markup=repeat_kb, parse_mode="Markdown")

def get_mines_kb(user_id: int, revealed=None):
    g = active_mines[user_id]
    kb = []
    for r in range(5):
        row = []
        for c in range(5):
            idx = r * 5 + c
            if revealed and idx in revealed:
                txt = revealed[idx]
            elif idx in g["open"]:
                txt = "💎"
            else:
                txt = "❓"
            row.append(InlineKeyboardButton(text=txt, callback_data=f"m_step_{idx}"))
        kb.append(row)
    win = int(g["stake"] * g["mult"])
    kb.append([InlineKeyboardButton(text=f"💰 Забрать ({win:,})", callback_data="m_take")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(F.text.lower().startswith("мины") | F.text.lower().startswith("mines"))
async def game_mines_start(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `мины 50к 3`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err:
        return await message.reply(err, parse_mode="Markdown")
    
    bombs_cnt = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() and 1 <= int(parts[2]) <= 24 else 3
    user["balance"] -= stake
    save_data()
    active_mines[user_id] = {
        "stake": stake, "bombs": set(random.sample(range(25), bombs_cnt)),
        "open": set(), "mult": 1.0, "step_add": round(0.12 * bombs_cnt, 2)
    }
    await message.reply(f"💣 **МИННОЕ ПОЛЕ (5x5)** | Бомбы: **{bombs_cnt}**\nСтавка: **{stake:,}**", reply_markup=get_mines_kb(user_id), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("m_step_"))
async def m_step(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    if uid not in active_mines: return await cb.message.edit_text("⚠️ Игра мины не найдена или уже завершена!")
    g = active_mines[uid]
    idx = int(cb.data.split("_")[2])
    if idx in g["open"]: return
    
    if idx in g["bombs"]:
        revealed = {}
        for i in range(25):
            if i in g["bombs"]:
                revealed[i] = "💣"
            else:
                revealed[i] = "💎"
                
        stake_lost = g["stake"]
        add_leaderboard_profit(uid, -stake_lost)
        
        kb = get_mines_kb(uid, revealed)
        kb = InlineKeyboardMarkup(inline_keyboard=[row for row in kb.inline_keyboard if not any(btn.callback_data == "m_take" for btn in row)])
        
        del active_mines[uid]
        return await cb.message.edit_text(f"💥 **ВЗРЫВ! Игра окончена.**\nРасположение мин и алмазов показано ниже:\n\nПотеряно: -{stake_lost:,}", reply_markup=kb, parse_mode="Markdown")
        
    g["open"].add(idx)
    g["mult"] += g["step_add"]
    
    try:
        await cb.message.edit_reply_markup(reply_markup=get_mines_kb(uid))
    except Exception:
        pass

@dp.callback_query(F.data == "m_take")
async def m_take(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    if uid not in active_mines: return await cb.message.edit_text("⚠️ Игра мины не найдена или уже завершена!")
    g = active_mines[uid]
    user = get_user(uid, cb.from_user.first_name)
    
    revealed = {}
    for i in range(25):
        if i in g["bombs"]:
            revealed[i] = "💣"
        else:
            revealed[i] = "💎"

    win = int(g["stake"] * g["mult"])
    user["balance"] += win
    profit = win - g["stake"]
    if profit > 0:
        add_leaderboard_profit(uid, profit)
    save_data()
    
    kb = get_mines_kb(uid, revealed)
    kb = InlineKeyboardMarkup(inline_keyboard=[row for row in kb.inline_keyboard if not any(btn.callback_data == "m_take" for btn in row)])
    
    del active_mines[uid]
    await cb.message.edit_text(f"💎 **Выигрыш забрали!**\nРасположение мин и алмазов:\n\nНаграда: **+{win:,}**", reply_markup=kb, parse_mode="Markdown")

def calc_score(hand):
    val = sum(CARDS_MAP[c] for c in hand)
    aces = hand.count("A")
    while val > 21 and aces:
        val -= 10
        aces -= 1
    return val

@dp.message(F.text.lower().startswith("блэкджек") | F.text.lower().startswith("бж") | F.text.lower().startswith("bj") | F.text.lower().startswith("blackjack"))
async def game_bj_start(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `бж 50к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err:
        return await message.reply(err, parse_mode="Markdown")
    
    user["balance"] -= stake
    save_data()
    p_hand = [random.choice(CARDS_LIST), random.choice(CARDS_LIST)]
    d_hand = [random.choice(CARDS_LIST), random.choice(CARDS_LIST)]
    active_bj[user_id] = {"stake": stake, "p": p_hand, "d": d_hand}
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🃏 Еще", callback_data="bj_hit"),
        InlineKeyboardButton(text="✋ Хватит", callback_data="bj_stand")
    ]])
    await message.reply(f"🃏 **БЛЭКДЖЕК**\nВаши карты: {', '.join(p_hand)} (**Очки: {calc_score(p_hand)}**)\nКарта дилера: {d_hand[0]}, [❓]", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "bj_hit")
async def bj_hit(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    if uid not in active_bj: return await cb.message.edit_text("⚠️ Игра окончена!")
    g = active_bj[uid]
    g["p"].append(random.choice(CARDS_LIST))
    score = calc_score(g["p"])
    if score > 21:
        stake_lost = g["stake"]
        add_leaderboard_profit(uid, -stake_lost)
        del active_bj[uid]
        return await cb.message.edit_text(f"💔 **Перебор! У вас {score} очков.**\nПотеряно: -{stake_lost:,}")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🃏 Еще", callback_data="bj_hit"),
        InlineKeyboardButton(text="✋ Хватит", callback_data="bj_stand")
    ]])
    await cb.message.edit_text(f"🃏 **БЛЭКДЖЕК**\nВаши карты: {', '.join(g['p'])} (**Очки: {score}**)\nКарта дилера: {g['d'][0]}, [❓]", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "bj_stand")
async def bj_stand(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    if uid not in active_bj: return await cb.message.edit_text("⚠️ Игра окончена!")
    g = active_bj[uid]
    user = get_user(uid, cb.from_user.first_name)
    p_score = calc_score(g["p"])
    d_score = calc_score(g["d"])
    while d_score < 17:
        g["d"].append(random.choice(CARDS_LIST))
        d_score = calc_score(g["d"])
    res = f"Ваши очки: **{p_score}** | Очки дилера: **{d_score}**\n\n"
    if d_score > 21 or p_score > d_score:
        win = g["stake"] * 2
        user["balance"] += win
        profit = win - g["stake"]
        add_leaderboard_profit(uid, profit)
        res += f"🎉 **ПОБЕДА! Выигрыш: +{win:,}**"
    elif p_score == d_score:
        user["balance"] += g["stake"]
        res += "🤝 **Ничья! Ставка возвращена.**"
    else:
        profit = -g["stake"]
        add_leaderboard_profit(uid, profit)
        res += f"💔 **Проигрыш! Потеряно: -{g['stake']:,}**"
    save_data()
    del active_bj[uid]
    await cb.message.edit_text(res, parse_mode="Markdown")

@dp.message(F.text.lower().in_({"🆘 помощь", "помощь", "help"}))
async def cmd_help(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Игровой зал", callback_data="help_games")],
        [InlineKeyboardButton(text="Базовые команды", callback_data="help_base")],
        [InlineKeyboardButton(text="Связь с администрацией", callback_data="help_admins")]
    ])
    await message.reply("🆘 **Меню помощи:**\nВыберите интересующий вас раздел:", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("help_"))
async def process_help_callback(cb: CallbackQuery):
    await cb.answer()
    action = cb.data.replace("help_", "")
    if action == "back":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Игровой зал", callback_data="help_games")],
            [InlineKeyboardButton(text="Базовые команды", callback_data="help_base")],
            [InlineKeyboardButton(text="Связь с администрацией", callback_data="help_admins")]
        ])
        try:
            await cb.message.edit_text("🆘 **Меню помощи:**\nВыберите интересующий вас раздел:", reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        return

    if action == "games":
        text = (
            "🎮 **Игровой зал (Список игр):**\n\n"
            "• `мв [ставка] [сектор]` — Мегавил (MegaWheel). Доступны иксы: `1`, `2`, `5`, `8`, `10`, `15`, `20`, `40`, `100`, `500`, `1000`, `10000`\n"
            "• `х50 [ставка] [ч/ф/к/з]` — Х50 (цвета)\n"
            "• `рз [ставка]` — Райз (7 этажей)\n"
            "• `хило [ставка]` — HiLo (карты)\n"
            "• `рул [ставка]` — Рулетка (Старт: «го»)\n"
            "• `охота [ставка]` — Охота\n"
            "• `слоты [ставка]` — Слоты (джекпот)\n"
            "• `мины [ставка] [бомбы]` — Минное поле\n"
            "• `бж [ставка]` — Блэкджек\n"
            "• `баскетбол [ставка] [мимо/попадание]` — Баскетбол"
        )
    elif action == "base":
        text = (
            "📋 **Базовые команды:**\n\n"
            "• `баланс` (или `б`) — проверить баланс\n"
            "• `банк` — проверить банк\n"
            "• `ник [название]` — изменить никнейм\n"
            "• `профиль` — информация об аккаунте\n"
            "• `топ` — топ богачей\n"
            "• `лб` — таблица лидеров\n"
            "• `бонус` — получить бонус (раз в 12ч)\n"
            "• `куровень` — повысить лимит перевода\n"
            "• `дать [сумма]` — перевести игроку (ответом)\n"
            "• `банк положить [сумма]` — положить в банк\n"
            "• `банк снять [сумма]` — снять из банка\n"
            "• `промо [код]` — активировать промокод"
        )
    elif action == "admins":
        text = (
            "📞 **Связь с администрацией:**\n\n"
            "Владелец: @oyxenn\n"
            "Наш чат: https://t.me/+c2XxfkFvgpU5ZmVh"
        )
    else:
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="help_back")]
    ])
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass

@dp.message(F.text.in_({"/start", "меню", "Меню", "🎰 Игры"}))
async def cmd_start(message: Message):
    get_user(message.from_user.id, message.from_user.first_name)
    await message.reply(
        "🎰 **БОТ КАЗИНО**\n\n"
        "• `баланс` | `банк` | `профиль` | `ник [название]` | `топ` | `лб` | `бонус`\n"
        "• `куровень` (Повысить лимит до 10 уровня)\n"
        "• `дать [сумма]` (Ответом)\n\n"
        "🎮 **ИГРЫ:**\n"
        "• `мв [ставка] [сектор]` (MegaWheel, макс икс: **10000x**)\n"
        "• `х50 [ставка] [ч/ф/к/з]`\n"
        "• `рз [ставка]` (Райз - 7 этажей)\n"
        "• `хило [ставка]`\n"
        "• `рул [ставка]` (Запуск: «го»)\n"
        "• `охота [ставка]`\n"
        "• `слоты [ставка]`\n"
        "• `мины [ставка] [бомбы]`\n"
        "• `бж [ставка]`\n"
        "• `баскетбол [ставка] [мимо/попадание]`",
        reply_markup=main_keyboard(), parse_mode="Markdown"
    )

async def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("🚀 Бот успешно обновлен с Мегавил (10с + 3с) и мультиплеером до 10000x!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
