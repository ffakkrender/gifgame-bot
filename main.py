import os
import asyncio
import random
import time
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
ADMIN_ID = 816157991

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

DB_FILE = "users_db.json"
PROMO_FILE = "promos_db.json"
LB_FILE = "lb_data.json"

db = {}
promos = {}
user_history = {}
lb_data = {"last_reset": datetime.now().isoformat(), "earnings": {}}

def load_data():
    global db, promos, lb_data
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                raw_db = json.load(f)
                db = {int(k): v for k, v in raw_db.items()}
        except Exception:
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
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
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
            sorted_lb = sorted(lb_data["earnings"].items(), key=lambda x: x[1], reverse=True)[:5]
            
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
            "balance": 100000,
            "bank": 0,
            "transfer_limit_lvl": 1,
            "transfer_limit": 50000,
            "reg_date": datetime.now().strftime("%d.%m.%Y"),
            "last_bonus": None
        }
        save_data()
    else:
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

def parse_stake(text_arg: str, user_balance: int):
    val = text_arg.lower().strip()
    if val in ["все", "вабанк", "всё"]:
        stake = user_balance
    else:
        mult = 1
        if val.endswith("кк"): mult = 1_000_000; val = val[:-2]
        elif val.endswith("к"): mult = 1_000; val = val[:-1]
        elif val.endswith("м"): mult = 1_000_000; val = val[:-1]
        try:
            stake = int(float(val) * mult)
        except ValueError:
            return 0, "⚠️ Неверный формат суммы!"

    if stake <= 0:
        return 0, "⚠️ Ставка должна быть больше 0!"
    if stake > user_balance:
        return 0, "⚠️ Недостаточно средств на балансе!"
        
    return stake, None

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Бонус")],
            [KeyboardButton(text="🏆 Топ"), KeyboardButton(text="📊 ЛБ")],
            [KeyboardButton(text="🎰 Игры"), KeyboardButton(text="🏦 Банк")]
        ],
        resize_keyboard=True
    )

# --- ЛИДЕРБОРД (ЛБ) ---

@dp.message(F.text.in_({"📊 ЛБ", "лб", "lb"}))
async def cmd_leaderboard(message: Message):
    check_and_reset_leaderboard()
    rewards = [500000, 340000, 250000, 167000, 100000]
    sorted_lb = sorted(lb_data["earnings"].items(), key=lambda x: x[1], reverse=True)[:5]
    
    text = "📊 **Лидерборд игроков:**\n\n"
    for idx in range(5):
        place = idx + 1
        reward_txt = f"Награда {rewards[idx]:,} гиф"
        if idx < len(sorted_lb):
            uid, earn = sorted_lb[idx]
            u_obj = db.get(uid)
            name = u_obj["name"] if u_obj else "Игрок"
            text += f"{place}  {name} — {earn:,} гиф\n   🎁 {reward_txt}\n"
        else:
            text += f"{place}  Вакантно — 0 гиф\n   🎁 {reward_txt}\n"
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_lb")]
    ])
    await message.reply(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "refresh_lb")
async def cb_refresh_lb(cb: CallbackQuery):
    check_and_reset_leaderboard()
    rewards = [500000, 340000, 250000, 167000, 100000]
    sorted_lb = sorted(lb_data["earnings"].items(), key=lambda x: x[1], reverse=True)[:5]
    
    text = "📊 **Лидерборд игроков:**\n\n"
    for idx in range(5):
        place = idx + 1
        reward_txt = f"Награда {rewards[idx]:,} гиф"
        if idx < len(sorted_lb):
            uid, earn = sorted_lb[idx]
            u_obj = db.get(uid)
            name = u_obj["name"] if u_obj else "Игрок"
            text += f"{place}  {name} — {earn:,} гиф\n   🎁 {reward_txt}\n"
        else:
            text += f"{place}  Вакантно — 0 гиф\n   🎁 {reward_txt}\n"
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_lb")]
    ])
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await cb.answer("ЛБ обновлен!")

# --- АДМИНКА, ПЕРЕВОДЫ, ТОП, ПРОМО ---

@dp.message(F.text.lower().startswith("выдать"))
async def cmd_admin_give(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.reply_to_message:
        return await message.reply("⚠️ **Ответьте (Reply) на сообщение игрока!**", parse_mode="Markdown")
        
    target_id = message.reply_to_message.from_user.id
    target_user = get_user(target_id, message.reply_to_message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("⚠️ Пример: `выдать 1000кк`", parse_mode="Markdown")
    
    val = parts[1].lower()
    if val in ["все", "всё"]:
        amount = 100_000_000_000_000
    else:
        amount, err = parse_stake(val, 999_999_999_999_999_999)
        if err: return await message.reply(err)
        
    if amount < 100:
        return await message.reply("⚠️ Минимальная сумма для выдачи: **100**", parse_mode="Markdown")
        
    target_user["balance"] += amount
    save_data()
    await message.reply(f"👑 **АДМИН-ВЫДАЧА**\nИгроку **{target_user['name']}** выдано: **+{amount:,}**\n💸 Баланс: **{target_user['balance']:,}**", parse_mode="Markdown")

@dp.message(F.text.lower() == "обнулировать")
async def cmd_admin_zero(message: Message):
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
        return
    for uid in db:
        db[uid]["balance"] = 0
        db[uid]["bank"] = 0
    save_data()
    await message.reply("⚠️ **Глобальный сброс!** Балансы и банки абсолютно всех игроков обнулены (0).", parse_mode="Markdown")

@dp.message(F.text.lower() == "reset limit")
async def cmd_admin_reset_limit(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.reply_to_message:
        return await message.reply("⚠️ **Ответьте (Reply) на сообщение игрока для сброса лимита!**", parse_mode="Markdown")
    target_id = message.reply_to_message.from_user.id
    target_user = get_user(target_id, message.reply_to_message.from_user.first_name)
    target_user["transfer_limit_lvl"] = 1
    target_user["transfer_limit"] = 50000
    save_data()
    await message.reply(f"🔄 Игроку **{target_user['name']}** лимит перевода сброшен до базового (1-й уровень, 50,000 гиф).", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("дать"))
async def cmd_transfer(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2 or not message.reply_to_message:
        return await message.reply("⚠️ Ответьте на сообщение игрока: `дать 50к`", parse_mode="Markdown")
    amount, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
    if user["transfer_limit_lvl"] < 10 and amount > user["transfer_limit"]:
        return await message.reply(f"⚠️ Сіздің аудару лимитіңіз: **{user['transfer_limit']:,} гиф**!\nЛимитті көтеру үшін: `куровень`", parse_mode="Markdown")
        
    target_id = message.reply_to_message.from_user.id
    target_user = get_user(target_id, message.reply_to_message.from_user.first_name)
    user["balance"] -= amount
    target_user["balance"] += amount
    save_data()
    await message.reply(f"🤝 Вы перевели **{amount:,}** игроку **{target_user['name']}**!", parse_mode="Markdown")

# --- КУРОВЕНЬ (10 УРОВНЕЙ ЛИМИТА) ---

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
        return await message.reply("🔥 Сізде қазірдің өзінде **максималды 10-шы деңгей** және шексіз лимит бар!", parse_mode="Markdown")
        
    next_lvl = current_lvl + 1
    cfg = LEVELS_CONFIG[next_lvl]
    cost = cfg["cost"]
    
    if user["balance"] < cost:
        limit_text = "Шексіз (∞)" if next_lvl == 10 else f"{cfg['limit']:,} гиф"
        return await message.reply(
            f"⚠️ **Лимитті көтеру ({next_lvl}-ші деңгей):**\n"
            f"💰 Қажетті сома: **{cost:,} гиф**\n"
            f"📈 Жаңа лимит: **{limit_text}**\n\n"
            f"Сіздің балансыңыз жеткіліксіз!", parse_mode="Markdown"
        )
        
    user["balance"] -= cost
    user["transfer_limit_lvl"] = next_lvl
    if next_lvl == 10:
        user["transfer_limit"] = 999999999999999 
    else:
        user["transfer_limit"] = cfg["limit"]
        
    save_data()
    
    new_limit_str = "Шексіз (∞) ♾️" if next_lvl == 10 else f"{user['transfer_limit']:,} гиф"
    await message.reply(f"🚀 Құттықтаймыз! Деңгей сәтті көтерілді: **Lvl {next_lvl}**\n💸 Жаңа аудару лимиті: **{new_limit_str}**", parse_mode="Markdown")

@dp.message(F.text.in_({"🏆 Топ", "топ"}))
async def cmd_top(message: Message):
    if not db: return await message.reply("🏆 Список игроков пуст.")
    sorted_users = sorted(db.values(), key=lambda x: x["balance"] + x["bank"], reverse=True)[:10]
    res = "🏆 **ТОП-10 БОГАЧЕЙ БОТА:**\n\n"
    for idx, u in enumerate(sorted_users, 1):
        total = u["balance"] + u["bank"]
        res += f"{idx}. **{u['name']}** — {total:,}\n"
    await message.reply(res, parse_mode="Markdown")

# --- ПРОМОКОДЫ ---

@dp.message(F.text.lower().startswith("создатьпромо"))
async def cmd_create_promo(message: Message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split()
    if len(parts) < 4: return await message.reply("⚠️ Пример: `создатьпромо КОД 100к 5`")
    code = parts[1].upper()
    val, err = parse_stake(parts[2], 999_999_999_999_999_999)
    if err: return await message.reply(err)
    uses = int(parts[3])
    promos[code] = {"amount": val, "uses": uses, "users": []}
    save_data()
    await message.reply(f"✅ Промокод `{code}` создан на сумму **{val:,}** ({uses} шт.)", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("промо"))
async def cmd_use_promo(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `промо КОД`")
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

# --- ПРОФИЛЬ, БАНК, БОНУС ---

@dp.message(F.text.lower().in_({"б", "баланс"}))
async def cmd_short_balance(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    await message.reply(f"💸 Баланс: **{user['balance']:,}**", parse_mode="Markdown")

@dp.message(F.text.lower() == "банк")
async def cmd_short_bank(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    await message.reply(f"🏦 Банк: **{user['bank']:,}**", parse_mode="Markdown")

@dp.message(F.text.in_({"👤 Профиль", "профиль"}))
async def cmd_profile(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    limit_str = "Шексіз (∞) ♾️" if user["transfer_limit_lvl"] == 10 else f"{user['transfer_limit']:,} гиф"
    await message.reply(
        f"👤 **ПРОФИЛЬ**\n🆔 ID: `{message.from_user.id}`\n"
        f"💸 Баланс: **{user['balance']:,}**\n🏦 Банк: **{user['bank']:,}**\n"
        f"⭐ Деңгей: **Lvl {user['transfer_limit_lvl']} / 10**\n"
        f"🤝 Аудару лимиті: **{limit_str}**", parse_mode="Markdown"
    )

@dp.message(F.text.in_({"🎁 Бонус", "бонус"}))
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

@dp.message(F.text.lower().startswith("банк положить"))
async def cmd_bank_dep(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 3: return await message.reply("⚠️ Пример: `банк положить 50к`")
    amount, err = parse_stake(parts[2], user["balance"])
    if err: return await message.reply(err)
    user["balance"] -= amount
    user["bank"] += amount
    save_data()
    await message.reply(f"🏦 В банк положено: **+{amount:,}**", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("банк снять"))
async def cmd_bank_wit(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 3: return await message.reply("⚠️ Пример: `банк снять 50к`")
    amount, err = parse_stake(parts[2], user["bank"])
    if err: return await message.reply(err)
    user["bank"] -= amount
    user["balance"] += amount
    save_data()
    await message.reply(f"🏦 Из банка снято: **{amount:,}**", parse_mode="Markdown")

# --- ИГРА Х50 ---

@dp.message(F.text.lower().startswith("х50"))
async def game_x50(message: Message):
    global x50_round_active, x50_bets
    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 3:
        return await message.reply("⚠️ Пример: `х50 50к ч`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
    choice = parts[2].lower()
    if choice not in ["ч", "ф", "к", "з"]:
        return await message.reply("⚠️ Ошибка! Выберите цвет: `ч`, `ф`, `к` или `з`")

    user["balance"] -= stake
    save_data()
    
    x50_bets.append({
        "user_id": message.from_user.id,
        "name": user["name"],
        "stake": stake,
        "choice": choice
    })
    
    color_desc = {"ч": "черный", "ф": "фиолетовый", "к": "красный", "з": "зеленый"}[choice]
    await message.reply(f"📥 **{user['name']}** сделал ставку: **{stake:,}** на {color_desc} цвет!")

    if not x50_round_active:
        x50_round_active = True
        await asyncio.sleep(7)
        
        roll = random.random()
        if roll < 0.50: color_name, mult, code, emo = "Черная", 2, "ч", "⚫️"
        elif roll < 0.80: color_name, mult, code, emo = "Фиолетовая", 3, "ф", "🟣"
        elif roll < 0.95: color_name, mult, code, emo = "Красная", 5, "к", "🔴"
        else: color_name, mult, code, emo = "Зеленая", 50, "з", "🟢"
        
        x50_history.insert(0, f"{emo}")
        if len(x50_history) > 10: x50_history.pop()

        result_text = f"🎡 **Результат розыгрыша X50:** {emo}\n\n"
        
        current_bets = x50_bets.copy()
        x50_bets.clear()
        x50_round_active = False

        for b in current_bets:
            u_id = b["user_id"]
            u_obj = db.get(u_id)
            if not u_obj: continue
            
            is_win = (b["choice"] == code)
            if is_win:
                win_amount = b["stake"] * mult
                u_obj["balance"] += win_amount
                profit = win_amount - b["stake"]
                add_leaderboard_profit(u_id, profit)
                result_text += f"{b['name']} {b['stake']:,} — выигрыш {win_amount:,} ✅\n"
                add_history(u_id, "Х50", f"+{win_amount:,}")
            else:
                profit = -b["stake"]
                add_leaderboard_profit(u_id, profit)
                result_text += f"{b['name']} {b['stake']:,} — проигрыш ❌\n"
                add_history(u_id, "Х50", f"-{b['stake']:,}")
        
        save_data()
        await message.bot.send_message(message.chat.id, result_text, parse_mode="Markdown")

@dp.message(F.text.lower() == "дроп")
async def cmd_drop(message: Message):
    if not x50_history: return await message.reply("📜 История X50 пуста.")
    await message.reply("📜 **История X50:**\n" + " ".join(x50_history), parse_mode="Markdown")

# --- ИГРА HILO #1 ---

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

@dp.message(F.text.lower().startswith("хило"))
@dp.message(F.text.lower().startswith("hilo"))
async def game_hilo_start(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `хило 50к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
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
        f"🎮 **HiLo #1** начался!\n"
        f"💰 Ставка: **{stake:,}**\n"
        f"🃏 Выпавшая карта: **{first_card}**\n\n"
        f"Сделайте свой выбор:",
        reply_markup=get_hilo_kb(), parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("hilo_"))
async def process_hilo_action(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in active_hilo:
        return await cb.answer("Игра HiLo не найдена или уже завершена!", show_alert=True)
    
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
        return await cb.message.edit_text(f"💰 **HiLo #1 завершена!** Вы забрали выигрыш: **+{win:,}**", parse_mode="Markdown")
    
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
            f"🎮 **HiLo #1**\n"
            f"🃏 Прошлая карта: {old_card} ➡️ Новая: **{new_card}** ✅\n"
            f"📈 Серия: **{g['streak']}** | Награда: **+{win_preview:,}**\n\n"
            f"Продолжаем игру?",
            reply_markup=get_hilo_kb(), parse_mode="Markdown"
        )
        await cb.answer("Верно!")
    else:
        stake_lost = g["stake"]
        add_leaderboard_profit(uid, -stake_lost)
        del active_hilo[uid]
        await cb.message.edit_text(
            f"🎮 **HiLo #1**\n"
            f"🃏 Прошлая карта: {old_card} ➡️ Новая: **{new_card}** ❌\n"
            f"💔 Вы проиграли! Потеряно: **-{stake_lost:,}**",
            parse_mode="Markdown"
        )
        await cb.answer("Неверно!", show_alert=True)

# --- ИГРА РАЙЗ (РЗ) ---

RISE_STAGES = [
    {"step": 1, "bombs": 1, "gems": 4, "mult": 1.44},
    {"step": 2, "bombs": 2, "gems": 3, "mult": 2.11},
    {"step": 3, "bombs": 3, "gems": 2, "mult": 4.78},
    {"step": 4, "bombs": 4, "gems": 1, "mult": 21.67},
    {"step": 5, "bombs": 3, "gems": 2, "mult": 100.01},
    {"step": 6, "bombs": 2, "gems": 3, "mult": 500.8},
    {"step": 7, "bombs": 1, "gems": 4, "mult": 1000.0},
]

def get_rise_kb(stage_idx: int):
    total_cells = RISE_STAGES[stage_idx]["bombs"] + RISE_STAGES[stage_idx]["gems"]
    row = [InlineKeyboardButton(text="❔", callback_data=f"rise_cell_{i}") for i in range(total_cells)]
    kb = [row]
    if stage_idx > 0:
        kb.append([InlineKeyboardButton(text="💰 Забрать выигрыш", callback_data="rise_take")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(F.text.lower().startswith("райз"))
@dp.message(F.text.lower().startswith("рз"))
async def game_rise_start(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `рз 50к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
    user["balance"] -= stake
    save_data()
    
    active_rise[user_id] = {
        "stake": stake,
        "stage": 0,
        "current_mult": 1.0
    }
    
    st = RISE_STAGES[0]
    await message.reply(
        f"🚀 Ставка райз: **{stake:,}**\n\n"
        f"❔ ❔ ❔ ❔ ❔ 1-шы саты | {st['bombs']} бомба, {st['gems']} алмаз | **{st['mult']}x**\n\n"
        f"Таңдаңыз бір ұяшықты:",
        reply_markup=get_rise_kb(0), parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("rise_"))
async def process_rise_action(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in active_rise:
        return await cb.answer("Игра Райз не найдена или уже завершена!", show_alert=True)
    
    g = active_rise[uid]
    user = get_user(uid, cb.from_user.first_name)
    
    if cb.data == "rise_take":
        if g["stage"] == 0:
            return await cb.answer("Сначала пройдите хотя бы 1 этап!", show_alert=True)
        prev_stage = g["stage"] - 1
        mult = RISE_STAGES[prev_stage]["mult"]
        win = int(g["stake"] * mult)
        user["balance"] += win
        profit = win - g["stake"]
        if profit > 0:
            add_leaderboard_profit(uid, profit)
        save_data()
        del active_rise[uid]
        return await cb.message.edit_text(f"💰 **Райз завершена!** Вы забрали выигрыш: **+{win:,}** (Множитель: {mult}x)", parse_mode="Markdown")
    
    if cb.data.startswith("rise_cell_"):
        stage_idx = g["stage"]
        st = RISE_STAGES[stage_idx]
        total_cells = st["bombs"] + st["gems"]
        
        bomb_indices = set(random.sample(range(total_cells), st["bombs"]))
        cell_idx = int(cb.data.split("_")[2])
        
        if cell_idx in bomb_indices:
            stake_lost = g["stake"]
            add_leaderboard_profit(uid, -stake_lost)
            del active_rise[uid]
            return await cb.message.edit_text(
                f"💥 **Райз ({stage_idx + 1}-саты):** Вы попали на бомбу 💣!\n"
                f"💔 Проигрыш: **-{stake_lost:,}**", parse_mode="Markdown"
            )
        else:
            g["stage"] += 1
            if g["stage"] >= len(RISE_STAGES):
                mult = RISE_STAGES[-1]["mult"]
                win = int(g["stake"] * mult)
                user["balance"] += win
                profit = win - g["stake"]
                add_leaderboard_profit(uid, profit)
                save_data()
                del active_rise[uid]
                return await cb.message.edit_text(f"🏆 **ГРАНДИОЗНАЯ ПОБЕДА!** Вы прошли все 7 саты!\nВыигрыш: **+{win:,}** ({mult}x)", parse_mode="Markdown")
            
            next_st = RISE_STAGES[g["stage"]]
            await cb.message.edit_text(
                f"🚀 Ставка райз: **{g['stake']:,}**\n"
                f"✅ {g['stage']}-ші саты сәтті өтті! ({RISE_STAGES[g['stage']-1]['mult']}x)\n\n"
                f"Келесі саты: {g['stage']+1}-ші саты | {next_st['bombs']} бомба, {next_st['gems']} алмаз | **{next_st['mult']}x**\n"
                f"Таңдаңыз келесі ұяшықты:",
                reply_markup=get_rise_kb(g["stage"]), parse_mode="Markdown"
            )
            await cb.answer("Алмаз таптыңыз! 💎")

# --- ИГРА РУЛЕТКА ---

def get_roulette_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Красное", callback_data="rl_k"), InlineKeyboardButton(text="⚫ Черное", callback_data="rl_ch")],
        [InlineKeyboardButton(text="🟢 Четное", callback_data="rl_chet"), InlineKeyboardButton(text="🟠 Нечетное", callback_data="rl_nechet")],
        [InlineKeyboardButton(text="1-18", callback_data="rl_1_18"), InlineKeyboardButton(text="19-36", callback_data="rl_19_36")],
        [InlineKeyboardButton(text="1-я дюжина", callback_data="rl_d1"), InlineKeyboardButton(text="2-я дюжина", callback_data="rl_d2")],
        [InlineKeyboardButton(text="3-я дюжина", callback_data="rl_d3")],
        [InlineKeyboardButton(text="🟢 ЗЕРО", callback_data="rl_z")]
    ])

@dp.message(F.text.lower().startswith("рул"))
async def game_roulette_start(message: Message):
    global roulette_round_active, roulette_bets
    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: 
        return await message.reply("⚠️ Пример: `рул 100к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
    if len(parts) >= 3:
        choice = parts[2].lower()
        user["balance"] -= stake
        save_data()
        roulette_bets.append({"user_id": message.from_user.id, "name": user["name"], "stake": stake, "choice": choice})
        await message.reply(f"🎰 **{user['name']}** поставил **{stake:,}** на `{choice}` в рулетку!\nНапишите `го` для запуска раунда.")
        
        if not roulette_round_active:
            roulette_round_active = True
            async def auto_run():
                await asyncio.sleep(10)
                if roulette_round_active:
                    await execute_roulette(message)
            asyncio.create_task(auto_run())
        return

    await message.reply(
        f"🎰 **РУЛЕТКА**\n💰 Ставка: **{stake:,}**\n🎯 **Выберите исход:**",
        reply_markup=get_roulette_kb(), parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("rl_"))
async def process_roulette_choice(cb: CallbackQuery):
    global roulette_round_active, roulette_bets
    uid = cb.from_user.id
    user = get_user(uid, cb.from_user.first_name)
    choice_raw = cb.data.replace("rl_", "")
    
    stake = 50000 
    if user["balance"] < stake:
        return await cb.answer("Недостаточно средств!", show_alert=True)
        
    user["balance"] -= stake
    save_data()
    
    roulette_bets.append({"user_id": uid, "name": user["name"], "stake": stake, "choice": choice_raw})
    await cb.message.edit_text(f"🎰 **{user['name']}** поставил **{stake:,}** на `{choice_raw}`\nНапишите **го** для старта раунда!")

    if not roulette_round_active:
        roulette_round_active = True
        async def auto_run():
            await asyncio.sleep(10)
            if roulette_round_active:
                await execute_roulette(cb.message)
        asyncio.create_task(auto_run())

@dp.message(F.text.lower() == "го")
async def cmd_roulette_go(message: Message):
    global roulette_round_active
    if not roulette_round_active or not roulette_bets:
        return
    roulette_round_active = False
    await execute_roulette(message)

async def execute_roulette(message_obj):
    global roulette_round_active, roulette_bets
    roulette_round_active = False
    
    num = random.randint(0, 36)
    color_emo = "🟢" if num == 0 else ("🔴" if num % 2 != 0 else "⚫️")
    roulette_history.insert(0, f"{num}{color_emo}")
    if len(roulette_history) > 10: roulette_history.pop()

    res_msg = f"🎰 Выпавшее число: **{num} {color_emo}**\n\n"
    current_bets = roulette_bets.copy()
    roulette_bets.clear()

    for b in current_bets:
        uid = b["user_id"]
        u_obj = db.get(uid)
        if not u_obj: continue
        stake = b["stake"]
        choice = b["choice"]

        mult = 0
        if choice in ["k", "красное"] and num % 2 != 0 and num != 0: mult = 1.9
        elif choice in ["ch", "черное"] and num % 2 == 0 and num != 0: mult = 1.9
        elif choice in ["chet", "чет"] and num % 2 == 0 and num != 0: mult = 1.9
        elif choice in ["nechet", "нечет"] and num % 2 != 0: mult = 1.9
        elif choice == "1_18" and 1 <= num <= 18: mult = 1.9
        elif choice == "19_36" and 19 <= num <= 36: mult = 1.9
        elif choice == "d1" and 1 <= num <= 12: mult = 3.0
        elif choice == "d2" and 13 <= num <= 24: mult = 3.0
        elif choice == "d3" and 25 <= num <= 36: mult = 3.0
        elif choice in ["z", "зеро"] and num == 0: mult = 36.0

        win = int(stake * mult)
        if win > 0:
            u_obj["balance"] += win
            profit = win - stake
            add_leaderboard_profit(uid, profit)
            res_msg += f"{b['name']} {stake:,} — выигрыш {win:,} ✅\n"
        else:
            profit = -stake
            add_leaderboard_profit(uid, profit)
            res_msg += f"{b['name']} {stake:,} — проигрыш ❌\n"

    save_data()
    await message_obj.bot.send_message(message_obj.chat.id, res_msg, parse_mode="Markdown")

@dp.message(F.text.lower() == "лог")
async def cmd_roulette_log(message: Message):
    if not roulette_history: return await message.reply("📃 История рулетки пуста.")
    await message.reply("📃 **История Рулетки:**\n" + " ".join(roulette_history), parse_mode="Markdown")

# --- ДРУГИЕ ИГРЫ ---

@dp.message(F.text.lower().startswith("баскетбол"))
async def game_basket(message: Message):
    uid = message.from_user.id
    user = get_user(uid, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 3: 
        return await message.reply("⚠️ Пример: `баскетбол 50к попадание`", parse_mode="Markdown")
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
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

@dp.message(F.text.lower().startswith("охота"))
async def game_hunt(message: Message):
    uid = message.from_user.id
    user = get_user(uid, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `охота 50к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
    user["balance"] -= stake
    save_data()
    
    scenarios = [
        "🌲 Вы отправились в глухой ночной лес в поисках дичи. Точный выстрел!",
        "🏜️ Жаркая пустыня. Из-за бархана показался редкий зверь. Вы прицелились...",
        "⛰️ Скалистые горы. Затаив дыхание, вы производите выстрел по горному барсу...",
        "🌊 Густые джунгли у реки. Из воды появился гигантский аллигатор!"
    ]
    
    msg = await message.reply(random.choice(scenarios))
    await asyncio.sleep(3)
    
    if random.random() > 0.45:
        win = int(stake * 1.88)
        user["balance"] += win
        profit = win - stake
        add_leaderboard_profit(uid, profit)
        save_data()
        await msg.edit_text(f"🎯 **Успешная охота!** Выигрыш: **+{win:,}**", parse_mode="Markdown")
    else:
        profit = -stake
        add_leaderboard_profit(uid, profit)
        save_data()
        await msg.edit_text(f"🎯 **Неудача!** Ставка сгорела: **-{stake:,}** 💔", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("слоты"))
async def game_slots(message: Message):
    uid = message.from_user.id
    user = get_user(uid, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `слоты 50к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
    user["balance"] -= stake
    save_data()
    
    msg = await message.reply("🎰 [ 🔄 🔄 🔄 ]")
    symbols = ["🍋", "🍒", "7️⃣", "🔔", "💎", "⭐", "🍉", "🍇"]
    
    for _ in range(4):
        await asyncio.sleep(0.4)
        tmp_symbols = [random.choice(symbols), random.choice(symbols), random.choice(symbols)]
        await msg.edit_text(f"🎰 [ {tmp_symbols[0]} {tmp_symbols[1]} {tmp_symbols[2]} ]")
    
    await asyncio.sleep(0.4)
    c = [random.choice(symbols) for _ in range(3)]
    res_str = f"{c[0]} {c[1]} {c[2]}"
    
    if c[0] == c[1] == c[2]:
        win = int(stake * 3.5)
        user["balance"] += win
        profit = win - stake
        add_leaderboard_profit(uid, profit)
        save_data()
        txt = f"🎰 [ {res_str} ]\n🎉 **ДЖЕКПОТ!** Награда: **+{win:,}**"
    else:
        profit = -stake
        add_leaderboard_profit(uid, profit)
        save_data()
        txt = f"🎰 [ {res_str} ]\n💔 Комбинация не сыграла."
        
    await msg.edit_text(txt, parse_mode="Markdown")

# --- МИНЫ ---

def get_mines_kb(user_id: int):
    g = active_mines[user_id]
    kb = []
    for r in range(5):
        row = []
        for c in range(5):
            idx = r * 5 + c
            txt = "💎" if idx in g["open"] else "❓"
            row.append(InlineKeyboardButton(text=txt, callback_data=f"m_step_{idx}"))
        kb.append(row)
    win = int(g["stake"] * g["mult"])
    kb.append([InlineKeyboardButton(text=f"💰 Забрать ({win:,})", callback_data="m_take")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(F.text.lower().startswith("мины"))
async def game_mines_start(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `мины 50к 3`", parse_mode="Markdown")
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
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
    uid = cb.from_user.id
    if uid not in active_mines: return await cb.answer("Игра уже завершена!")
    g = active_mines[uid]
    idx = int(cb.data.split("_")[2])
    if idx in g["open"]: return await cb.answer()
    if idx in g["bombs"]:
        stake_lost = g["stake"]
        add_leaderboard_profit(uid, -stake_lost)
        del active_mines[uid]
        return await cb.message.edit_text(f"💥 **ВЗРЫВ!** Потеряно: -{stake_lost:,}")
    g["open"].add(idx)
    g["mult"] += g["step_add"]
    await cb.message.edit_reply_markup(reply_markup=get_mines_kb(uid))
    await cb.answer()

@dp.callback_query(F.data == "m_take")
async def m_take(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in active_mines: return await cb.answer("Игра уже завершена!")
    g = active_mines[uid]
    user = get_user(uid, cb.from_user.first_name)
    win = int(g["stake"] * g["mult"])
    user["balance"] += win
    profit = win - g["stake"]
    if profit > 0:
        add_leaderboard_profit(uid, profit)
    save_data()
    del active_mines[uid]
    await cb.message.edit_text(f"💎 **Выигрыш забрали!** Награда: **+{win:,}**", parse_mode="Markdown")

# --- БЛЭКДЖЕК ---

def calc_score(hand):
    val = sum(CARDS_MAP[c] for c in hand)
    aces = hand.count("A")
    while val > 21 and aces:
        val -= 10
        aces -= 1
    return val

@dp.message(F.text.lower().startswith("блэкджек"))
@dp.message(F.text.lower().startswith("бж"))
async def game_bj_start(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `бж 50к`", parse_mode="Markdown")
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
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
    uid = cb.from_user.id
    if uid not in active_bj: return await cb.answer("Игра окончена!")
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
    await cb.answer()

@dp.callback_query(F.data == "bj_stand")
async def bj_stand(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in active_bj: return await cb.answer("Игра окончена!")
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
        res += "🤝 **Ничья! Ставка возвращена.**"
    else:
        profit = -g["stake"]
        add_leaderboard_profit(uid, profit)
        res += f"💔 **Проигрыш! Потеряно: -{g['stake']:,}**"
    save_data()
    del active_bj[uid]
    await cb.message.edit_text(res, parse_mode="Markdown")
    await cb.answer()

@dp.message(F.text.in_({"/start", "меню", "Меню", "🆘 Помощь", "помощь"}))
async def cmd_start(message: Message):
    get_user(message.from_user.id, message.from_user.first_name)
    await message.reply(
        "🎰 **БОТ КАЗИНО**\n\n"
        "• `баланс` | `банк` | `профиль` | `топ` | `лб` | `бонус`\n"
        "• `куровень` (Көтеру лимиті 10 деңгейге дейін)\n"
        "• `дать [сумма]` (Ответом)\n\n"
        "🎮 **ИГРЫ:**\n"
        "• `рз [ставка]` (Райз)\n"
        "• `х50 [ставка] [ч/ф/к/з]`\n"
        "• `хило [ставка]`\n"
        "• `рул [ставка]`\n"
        "• `охота [ставка]`\n"
        "• `слоты [ставка]`\n"
        "• `мины [ставка] [бомбы]`\n"
        "• `бж [ставка]`\n"
        "• `баскетбол [ставка] [мимо/попадание]`",
        reply_markup=main_keyboard(), parse_mode="Markdown"
    )

async def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("🚀 Gifgame_bot обновлен (без прокси)!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
