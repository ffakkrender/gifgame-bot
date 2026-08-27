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

last_user_bets = {}

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

roulette_round_active = False
roulette_bets = []
roulette_history = []  

megawheel_active = False
megawheel_bets = []
megawheel_pending = {}

active_mines = {}
active_hilo = {}

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
            [KeyboardButton(text="🎰 Игры"), KeyboardButton(text="🏦 Банк"), KeyboardButton(text="🆘 Помощь")]
        ],
        resize_keyboard=True
    )

@dp.message(F.text.lower().in_({"ласт", "last"}))
async def cmd_last_history(message: Message):
    target_id = message.from_user.id
    target_name = message.from_user.first_name
    
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name
        
    u_obj = get_user(target_id, target_name)
    
    if target_id not in user_history or not user_history[target_id]:
        return await message.reply(f"📜 У игрока **{u_obj['name']}** пока нет истории игр.", parse_mode="Markdown")
        
    history_list = user_history[target_id]
    text = f"📜 **Последние игры игрока {u_obj['name']}:**\n\n"
    for idx, item in enumerate(history_list, 1):
        text += f"{idx}. {item}\n"
        
    await message.reply(text, parse_mode="Markdown")

@dp.message(F.text.lower().in_({"повторить ставку", "повтор"}))
async def cmd_repeat_bet(message: Message):
    uid = message.from_user.id
    if uid not in last_user_bets:
        return await message.reply("⚠️ У вас нет сохраненных предыдущих ставок!")
    
    last = last_user_bets[uid]
    game = last["game"]
    stake = last["stake"]
    arg = last["arg"]
    
    if game == "х50":
        message.text = f"х50 {stake} {arg}"
        return await game_x50(message)
    elif game == "рул":
        message.text = f"рул {stake} {arg}"
        return await game_roulette_start(message)
    elif game == "мегавил":
        message.text = f"мв {stake} {arg}"
        return await game_megawheel_start(message)
    elif game == "охота":
        message.text = f"охота {stake}"
        return await game_hunt(message)
    elif game == "слоты":
        message.text = f"слоты {stake}"
        return await game_slots(message)
    elif game == "мины":
        message.text = f"мины {stake}"
        return await game_mines(message)
    elif game == "хило":
        message.text = f"хило {stake}"
        return await game_hilo(message)

@dp.message(F.text.in_({"📊 ЛБ", "лб", "lb"}))
async def cmd_leaderboard(message: Message):
    check_and_reset_leaderboard()
    rewards = [500000, 340000, 250000, 167000, 100000]
    positive_earnings = {uid: earn for uid, earn in lb_data["earnings"].items() if earn > 0}
    sorted_lb = sorted(positive_earnings.items(), key=lambda x: x[1], reverse=True)[:5]
    
    text = "📊 **Таблица лидеров (в плюсе):**\n\n"
    for idx in range(5):
        place = idx + 1
        reward_txt = f"Награда {rewards[idx]:,} гиф"
        if idx < len(sorted_lb):
            uid, earn = sorted_lb[idx]
            u_obj = db.get(uid)
            name = u_obj["name"] if u_obj else "Игрок"
            text += f"{place}. {name} — +{earn:,} гиф\n   🎁 {reward_txt}\n"
        else:
            text += f"{place}. Вакантно — 0 гиф\n   🎁 {reward_txt}\n"
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_lb")]
    ])
    await message.reply(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "refresh_lb")
async def cb_refresh_lb(cb: CallbackQuery):
    check_and_reset_leaderboard()
    rewards = [500000, 340000, 250000, 167000, 100000]
    positive_earnings = {uid: earn for uid, earn in lb_data["earnings"].items() if earn > 0}
    sorted_lb = sorted(positive_earnings.items(), key=lambda x: x[1], reverse=True)[:5]
    
    text = "📊 **Таблица лидеров (в плюсе):**\n\n"
    for idx in range(5):
        place = idx + 1
        reward_txt = f"Награда {rewards[idx]:,} гиф"
        if idx < len(sorted_lb):
            uid, earn = sorted_lb[idx]
            u_obj = db.get(uid)
            name = u_obj["name"] if u_obj else "Игрок"
            text += f"{place}. {name} — +{earn:,} гиф\n   🎁 {reward_txt}\n"
        else:
            text += f"{place}. Вакантно — 0 гиф\n   🎁 {reward_txt}\n"
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_lb")]
    ])
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await cb.answer("ЛБ обновлен!")

# --- МИНЫ ОЙЫНЫ ---

def get_mines_kb(game_state):
    grid = game_state["grid"]
    buttons = []
    for r in range(3):
        row = []
        for c in range(3):
            idx = r * 3 + c
            status = grid[idx]
            if status == "hidden":
                btn_text = "🟩"
                cb_data = f"mine_click_{idx}"
            elif status == "safe":
                btn_text = "💎"
                cb_data = "mine_noop"
            else:
                btn_text = "💥"
                cb_data = "mine_noop"
            row.append(InlineKeyboardButton(text=btn_text, callback_data=cb_data))
        buttons.append(row)
    
    if game_state["active"] and game_state["opened"] > 0:
        buttons.append([InlineKeyboardButton(text=f"💰 Забрать ({game_state['current_win']:,})", callback_data="mine_cashout")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(F.text.lower().startswith("мины"))
async def game_mines(message: Message):
    uid = message.from_user.id
    user = get_user(uid, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `мины 50к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
    user["balance"] -= stake
    save_data()
    
    last_user_bets[uid] = {"game": "мины", "stake": stake, "arg": ""}

    mine_pos = random.randint(0, 8)
    active_mines[uid] = {
        "stake": stake,
        "mine": mine_pos,
        "grid": ["hidden"] * 9,
        "opened": 0,
        "current_win": stake,
        "active": True
    }
    
    mults = [1.3, 1.8, 2.5, 3.6, 5.2, 7.8, 12.0, 20.0]
    text = f"💣 **Мины (3x3)**\n💰 Ставка: **{stake:,}**\n🎯 Открывайте безопасные ячейки, избегая мину!"
    await message.reply(text, reply_markup=get_mines_kb(active_mines[uid]), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("mine_"))
async def cb_mines(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in active_mines or not active_mines[uid]["active"]:
        return await cb.answer("⚠️ Активная игра Мины не найдена!", show_alert=True)
    
    game = active_mines[uid]
    
    if cb.data == "mine_noop":
        return await cb.answer()
    
    if cb.data == "mine_cashout":
        game["active"] = False
        user = get_user(uid, cb.from_user.first_name)
        user["balance"] += game["current_win"]
        profit = game["current_win"] - game["stake"]
        add_leaderboard_profit(uid, profit)
        add_history(uid, "Мины", f"+{game['current_win']:,}")
        save_data()
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="btn_repeat_mines")]])
        await cb.message.edit_text(f"💰 **Вы забрали выигрыш!**\nСумма: **+{game['current_win']:,} гиф**", reply_markup=kb, parse_mode="Markdown")
        return

    idx = int(cb.data.replace("mine_click_", ""))
    if game["grid"][idx] != "hidden":
        return await cb.answer()
        
    if idx == game["mine"]:
        game["active"] = game["grid"][idx] = "boom"
        game["grid"][game["mine"]] = "boom"
        profit = -game["stake"]
        add_leaderboard_profit(uid, profit)
        add_history(uid, "Мины", f"-{game['stake']:,}")
        save_data()
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="btn_repeat_mines")]])
        await cb.message.edit_text(f"💥 **БУМ! Вы подорвались на мине!**\nПроигрыш: **-{game['stake']:,}** 💔", reply_markup=kb, parse_mode="Markdown")
    else:
        game["grid"][idx] = "safe"
        game["opened"] += 1
        mults = [1.3, 1.8, 2.5, 3.6, 5.2, 7.8, 12.0, 20.0]
        mult = mults[min(game["opened"] - 1, len(mults) - 1)]
        game["current_win"] = int(game["stake"] * mult)
        
        if game["opened"] >= 8:
            game["active"] = False
            user = get_user(uid, cb.from_user.first_name)
            user["balance"] += game["current_win"]
            profit = game["current_win"] - game["stake"]
            add_leaderboard_profit(uid, profit)
            add_history(uid, "Мины", f"+{game['current_win']:,}")
            save_data()
            
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="btn_repeat_mines")]])
            await cb.message.edit_text(f"🏆 **Поздравляем! Вы прошли все мины!**\nВыигрыш: **+{game['current_win']:,}** 🎉", reply_markup=kb, parse_mode="Markdown")
        else:
            await cb.message.edit_reply_markup(reply_markup=get_mines_kb(game))
            await cb.answer(f"💎 Чисто! Коэффициент: x{mult}")

@dp.callback_query(F.data == "btn_repeat_mines")
async def cb_repeat_mines(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in last_user_bets or last_user_bets[uid]["game"] != "мины":
        return await cb.answer("У вас нет сохраненной ставки на мины!", show_alert=True)
    last = last_user_bets[uid]
    msg = cb.message
    msg.from_user = cb.from_user
    msg.text = f"мины {last['stake']}"
    await game_mines(msg)
    await cb.answer("Ставка на мины повторена!")

# --- ХИЛО ОЙЫНЫ ---

def get_hilo_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Больше / Равно", callback_data="hilo_high"), InlineKeyboardButton(text="📉 Меньше", callback_data="hilo_low")]
    ])

@dp.message(F.text.lower().startswith("хило"))
async def game_hilo(message: Message):
    uid = message.from_user.id
    user = get_user(uid, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `хило 50к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
    user["balance"] -= stake
    save_data()
    
    last_user_bets[uid] = {"game": "хило", "stake": stake, "arg": ""}

    card = random.choice(CARDS_LIST)
    active_hilo[uid] = {
        "stake": stake,
        "current_card": card,
        "streak": 0,
        "current_win": stake
    }
    
    await message.reply(
        f"🎴 **Hi-Lo**\n💰 Ставка: **{stake:,}**\n🃏 Открытая карта: **{card}**\n\nСледующая карта будет больше или меньше?",
        reply_markup=get_hilo_kb(), parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("hilo_"))
async def cb_hilo(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in active_hilo:
        return await cb.answer("⚠️ Активная игра Hi-Lo не найдена!", show_alert=True)
    
    game = active_hilo[uid]
    old_card = game["current_card"]
    old_val = CARDS_MAP[old_card]
    
    new_card = random.choice(CARDS_LIST)
    new_val = CARDS_MAP[new_card]
    
    choice = cb.data.replace("hilo_", "")
    success = False
    if choice == "high" and new_val >= old_val: success = True
    elif choice == "low" and new_val < old_val: success = True
    
    user = get_user(uid, cb.from_user.first_name)
    
    if success:
        game["streak"] += 1
        game["current_card"] = new_card
        game["current_win"] = int(game["current_win"] * 1.7)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📈 Больше", callback_data="hilo_high"), InlineKeyboardButton(text="📉 Меньше", callback_data="hilo_low")],
            [InlineKeyboardButton(text=f"💰 Забрать ({game['current_win']:,})", callback_data="hilo_cashout")]
        ])
        await cb.message.edit_text(
            f"🎴 **Hi-Lo**\n🃏 Прошлая: {old_card} | Новая карта: **{new_card}** ✅\n🔥 Успех! Серия: {game['streak']}\n💰 Текущий выигрыш: **{game['current_win']:,}**",
            reply_markup=kb, parse_mode="Markdown"
        )
    else:
        del active_hilo[uid]
        profit = -game["stake"]
        add_leaderboard_profit(uid, profit)
        add_history(uid, "Hi-Lo", f"-{game['stake']:,}")
        save_data()
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="btn_repeat_hilo")]])
        await cb.message.edit_text(f"🎴 Карты: {old_card} → **{new_card}** ❌\nВы проиграли ставку: **-{game['stake']:,}**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "hilo_cashout")
async def cb_hilo_cashout(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in active_hilo: return await cb.answer()
    game = active_hilo.pop(uid)
    user = get_user(uid, cb.from_user.first_name)
    user["balance"] += game["current_win"]
    profit = game["current_win"] - game["stake"]
    add_leaderboard_profit(uid, profit)
    add_history(uid, "Hi-Lo", f"+{game['current_win']:,}")
    save_data()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="btn_repeat_hilo")]])
    await cb.message.edit_text(f"💰 Вы забрали выигрыш в Hi-Lo: **+{game['current_win']:,} гиф** 🎉", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "btn_repeat_hilo")
async def cb_repeat_hilo(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in last_user_bets or last_user_bets[uid]["game"] != "хило":
        return await cb.answer("У вас нет сохраненной ставки на хило!", show_alert=True)
    last = last_user_bets[uid]
    msg = cb.message
    msg.from_user = cb.from_user
    msg.text = f"хило {last['stake']}"
    await game_hilo(msg)
    await cb.answer("Ставка на хило повторена!")

# --- MEGAWHEEL ---

MEGAWHEEL_SECTORS = [
    {"name": "1х", "mult": 1, "emo": "❄️", "weight": 40},
    {"name": "2х", "mult": 2, "emo": "🔵", "weight": 25},
    {"name": "5х", "mult": 5, "emo": "🟢", "weight": 15},
    {"name": "8х", "mult": 8, "emo": "🟡", "weight": 10},
    {"name": "10х", "mult": 10, "emo": "🟠", "weight": 5},
    {"name": "15х", "mult": 15, "emo": "🔴", "weight": 3},
    {"name": "20х", "mult": 20, "emo": "🟣", "weight": 1.5},
    {"name": "40х", "mult": 40, "emo": "🔥", "weight": 0.5},
]

def get_weighted_sector():
    sectors = MEGAWHEEL_SECTORS
    weights = [s["weight"] for s in sectors]
    return random.choices(sectors, weights=weights, k=1)[0]

def get_megawheel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❄️ 1х", callback_data="mw_1х"),
            InlineKeyboardButton(text="🔵 2х", callback_data="mw_2х"),
            InlineKeyboardButton(text="🟢 5х", callback_data="mw_5х"),
            InlineKeyboardButton(text="🟡 8х", callback_data="mw_8х")
        ],
        [
            InlineKeyboardButton(text="🟠 10х", callback_data="mw_10х"),
            InlineKeyboardButton(text="🔴 15х", callback_data="mw_15х"),
            InlineKeyboardButton(text="🟣 20х", callback_data="mw_20х"),
            InlineKeyboardButton(text="🔥 40х", callback_data="mw_40х")
        ]
    ])

@dp.message(F.text.lower().startswith("мв") | F.text.lower().startswith("мегавил"))
async def game_megawheel_start(message: Message):
    global megawheel_active, megawheel_bets, megawheel_pending
    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("⚠️ Формат: `мв [сумма]` немесе `мв [сумма] [сектор]`\nМысалы: `мв 50к` немесе `мв 50к 10х`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
    if len(parts) >= 3:
        choice = parts[2].lower().strip().replace("x", "х")
        valid_choices = ["1х", "2х", "5х", "8х", "10х", "15х", "20х", "40х"]
        if choice not in valid_choices:
            return await message.reply("⚠️ Қате сектор! Тек мыналарды таңдаңыз: `1х, 2х, 5х, 8х, 10х, 15х, 20х, 40х`")
        
        user["balance"] -= stake
        save_data()
        
        last_user_bets[message.from_user.id] = {"game": "мегавил", "stake": stake, "arg": choice}
        megawheel_bets.append({"user_id": message.from_user.id, "name": user["name"], "stake": stake, "choice": choice})
        
        await message.reply(f"🎡 **{user['name']}** поставил **{stake:,}** гиф на сектор **{choice}** в MegaWheel! (Ожидание 10 секунд...)")
        
        if not megawheel_active:
            megawheel_active = True
            await asyncio.sleep(10)
            await execute_megawheel(message)
        return

    megawheel_pending[message.from_user.id] = stake
    await message.reply(
        f"🎡 **MegaWheel**\n💰 Ставка: **{stake:,}** гиф\n🎯 **Секторды таңдаңыз:**",
        reply_markup=get_megawheel_kb(), parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("mw_"))
async def process_megawheel_choice(cb: CallbackQuery):
    global megawheel_active, megawheel_bets, megawheel_pending
    uid = cb.from_user.id
    if uid not in megawheel_pending:
        return await cb.answer("⚠️ Ставка табылмады немесе уақыты өтіп кетті!", show_alert=True)
        
    stake = megawheel_pending.pop(uid)
    user = get_user(uid, cb.from_user.first_name)
    
    if user["balance"] < stake:
        return await cb.answer("⚠️ Балансыңызда қаражат жеткіліксіз!", show_alert=True)
        
    user["balance"] -= stake
    save_data()
    
    choice = cb.data.replace("mw_", "")
    last_user_bets[uid] = {"game": "мегавил", "stake": stake, "arg": choice}

    megawheel_bets.append({
        "user_id": uid,
        "name": user["name"],
        "stake": stake,
        "choice": choice
    })
    
    await cb.message.edit_text(f"🎡 **{user['name']}** поставил **{stake:,}** гиф на сектор **{choice}** в MegaWheel!\n⏳ Ожидание начала (10 секунд)...")
    
    if not megawheel_active:
        megawheel_active = True
        await asyncio.sleep(10)
        await execute_megawheel(cb.message)

async def execute_megawheel(message_obj):
    global megawheel_active, megawheel_bets
    chosen_sector = get_weighted_sector()
    
    bonus_triggered = random.random() < 0.25
    bonus_mult_val = 1
    bonus_txt = ""
    
    if bonus_triggered:
        bonus_mult_val = random.choice([2, 3, 5])
        bonus_txt = f"\n⚡ БОНУСНЫЙ СЕКТОР: {chosen_sector['emo']} {bonus_mult_val}x"

    total_multiplier = chosen_sector["mult"] * bonus_mult_val
    
    result_msg = (
        f"🎡 **MegaWheel Результаты**\n\n"
        f"👥 Игроков: {len(megawheel_bets)}\n"
        f"💰 Общий банк ставок: {sum(b['stake'] for b in megawheel_bets):,} гиф\n"
        f"{bonus_txt}\n"
        f"🎯 ВЫПАЛ СЕКТОР: {chosen_sector['name']} {chosen_sector['emo']}\n\n"
    )
    
    if bonus_triggered:
        result_msg += f"🔥 **SUPER MULTIPLIER!** Итоговый коэффициент: **{total_multiplier}x**!\n\n"

    current_bets = megawheel_bets.copy()
    megawheel_bets.clear()
    megawheel_active = False

    for b in current_bets:
        u_id = b["user_id"]
        u_obj = db.get(u_id)
        if not u_obj: continue
        
        user_choice_clean = b["choice"].replace("x", "х")
        sector_clean = chosen_sector["name"].replace("x", "х")
        
        if user_choice_clean == sector_clean:
            win_amount = int(b["stake"] * total_multiplier)
            u_obj["balance"] += win_amount
            profit = win_amount - b["stake"]
            add_leaderboard_profit(u_id, profit)
            result_msg += f"{chosen_sector['emo']} {chosen_sector['name']}:\n💸 {b['name']} — ставка {b['stake']:,} → **+{win_amount:,} гиф** ({total_multiplier}x) ✅\n"
            add_history(u_id, "MegaWheel", f"+{win_amount:,} ({total_multiplier}x)")
        else:
            profit = -b["stake"]
            add_leaderboard_profit(u_id, profit)
            result_msg += f"{chosen_sector['emo']} {chosen_sector['name']}:\n❌ {b['name']} — ставка {b['stake']:,} — проигрыш ❌\n"
            add_history(u_id, "MegaWheel", f"-{b['stake']:,}")
    
    save_data()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="btn_repeat_megawheel")]
    ])
    await message_obj.bot.send_message(message_obj.chat.id, result_msg, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "btn_repeat_megawheel")
async def cb_repeat_megawheel(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in last_user_bets or last_user_bets[uid]["game"] != "мегавил":
        return await cb.answer("У вас нет сохраненной ставки на MegaWheel!", show_alert=True)
    
    last = last_user_bets[uid]
    msg = cb.message
    msg.from_user = cb.from_user
    msg.text = f"мв {last['stake']} {last['arg']}"
    await game_megawheel_start(msg)
    await cb.answer("Ставка на MegaWheel повторена!")

# --- Х50 ---

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
    
    last_user_bets[message.from_user.id] = {"game": "х50", "stake": stake, "arg": choice}

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
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="btn_repeat_x50")]
        ])
        await message.bot.send_message(message.chat.id, result_text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "btn_repeat_x50")
async def cb_repeat_x50(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in last_user_bets or last_user_bets[uid]["game"] != "х50":
        return await cb.answer("У вас нет сохраненной ставки на Х50!", show_alert=True)
    last = last_user_bets[uid]
    msg = cb.message
    msg.from_user = cb.from_user
    msg.text = f"х50 {last['stake']} {last['arg']}"
    await game_x50(msg)
    await cb.answer("Ставка на Х50 повторена!")

@dp.message(F.text.lower() == "дроп")
async def cmd_drop(message: Message):
    if not x50_history: return await message.reply("📜 История X50 пуста.")
    await message.reply("📜 **История X50:**\n" + " ".join(x50_history), parse_mode="Markdown")

# --- РУЛЕТКА ---

def get_roulette_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Красное", callback_data="rl_k"), InlineKeyboardButton(text="⚫ Черное", callback_data="rl_ch")],
        [InlineKeyboardButton(text="🟢 Четное", callback_data="rl_chet"), InlineKeyboardButton(text="🟠 Нечетное", callback_data="rl_nechet")],
        [InlineKeyboardButton(text="1-18", callback_data="rl_1_18"), InlineKeyboardButton(text="19-36", callback_data="rl_19_36")],
        [InlineKeyboardButton(text="🟢 ЗЕРО", callback_data="rl_z")]
    ])

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 17, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

@dp.message(F.text.lower().startswith("рул"))
async def game_roulette_start(message: Message):
    global roulette_round_active, roulette_bets
    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: 
        return await message.reply("⚠️ Пример: `рул 100к к`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
    if len(parts) >= 3:
        choice = parts[2].lower()
        user["balance"] -= stake
        save_data()
        
        last_user_bets[message.from_user.id] = {"game": "рул", "stake": stake, "arg": choice}
        roulette_bets.append({"user_id": message.from_user.id, "name": user["name"], "stake": stake, "choice": choice})
        
        msg = await message.reply(f"🎰 Рулетка: Игрок поставил {stake:,} gif. Рулетка крутится (3 сек)...")
        await asyncio.sleep(3)
        await execute_roulette(msg)
        return

    await message.reply(
        f"🎰 **РУЛЕТКА**\n💰 Ставка: **{stake:,}**\n🎯 **Выберите исход:**",
        reply_markup=get_roulette_kb(), parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("rl_"))
async def process_roulette_choice(cb: CallbackQuery):
    global roulette_bets
    uid = cb.from_user.id
    user = get_user(uid, cb.from_user.first_name)
    choice_raw = cb.data.replace("rl_", "")
    
    stake = 50000 
    if user["balance"] < stake:
        return await cb.answer("Недостаточно средств!", show_alert=True)
        
    user["balance"] -= stake
    save_data()
    
    last_user_bets[uid] = {"game": "рул", "stake": stake, "arg": choice_raw}
    roulette_bets.append({"user_id": uid, "name": user["name"], "stake": stake, "choice": choice_raw})
    
    await cb.message.edit_text("🎰 Рулетка крутится (3 сек)...")
    await asyncio.sleep(3)
    await execute_roulette(cb.message)

async def execute_roulette(message_obj):
    global roulette_bets
    num = random.randint(0, 36)
    color_emo = "🟢" if num == 0 else ("🔴" if num in RED_NUMBERS else "⚫️")
    roulette_history.insert(0, f"{num}{color_emo}")
    if len(roulette_history) > 10: roulette_history.pop()

    res_msg = f"🎡 **Рулетка Результат:** {color_emo} **{num}**\n\n"
    current_bets = roulette_bets.copy()
    roulette_bets.clear()

    for b in current_bets:
        uid = b["user_id"]
        u_obj = db.get(uid)
        if not u_obj: continue
        stake = b["stake"]
        choice = str(b["choice"]).lower()

        mult = 0
        if choice in ["k", "красное", "красный"] and num in RED_NUMBERS: mult = 1.9
        elif choice in ["ch", "черное", "черный", "ч"] and num not in RED_NUMBERS and num != 0: mult = 1.9
        elif choice in ["chet", "чет"] and num % 2 == 0 and num != 0: mult = 1.9
        elif choice in ["nechet", "нечет"] and num % 2 != 0: mult = 1.9
        elif choice == "1_18" and 1 <= num <= 18: mult = 1.9
        elif choice == "19_36" and 19 <= num <= 36: mult = 1.9
        elif choice in ["z", "зеро"] and num == 0: mult = 36.0

        if mult > 0:
            win = int(stake * mult)
            u_obj["balance"] += win
            profit = win - stake
            add_leaderboard_profit(uid, profit)
            add_history(uid, "Рулетка", f"+{win:,}")
            res_msg += f"💸 {b['name']} — ставка {stake:,} → выигрыш **+{win:,}** ✅\n"
        else:
            profit = -stake
            add_leaderboard_profit(uid, profit)
            add_history(uid, "Рулетка", f"-{stake:,}")
            res_msg += f"❌ {b['name']} — ставка {stake:,} — проигрыш ❌\n"

    save_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="btn_repeat_roulette")]
    ])
    await message_obj.bot.send_message(message_obj.chat.id, res_msg, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "btn_repeat_roulette")
async def cb_repeat_roulette(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in last_user_bets or last_user_bets[uid]["game"] != "рул":
        return await cb.answer("У вас нет сохраненной ставки на рулетку!", show_alert=True)
    last = last_user_bets[uid]
    msg = cb.message
    msg.from_user = cb.from_user
    msg.text = f"рул {last['stake']} {last['arg']}"
    await game_roulette_start(msg)
    await cb.answer("Ставка на рулетку повторена!")

@dp.message(F.text.lower() == "лог")
async def cmd_roulette_log(message: Message):
    if not roulette_history: return await message.reply("📃 История рулетки пуста.")
    await message.reply("📃 **История Рулетки:**\n" + " ".join(roulette_history), parse_mode="Markdown")

# --- ОХОТА И СЛОТЫ ---

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
    
    last_user_bets[uid] = {"game": "охота", "stake": stake, "arg": ""}

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
        add_history(uid, "Охота", f"+{win:,}")
        save_data()
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="btn_repeat_hunt")]])
        await msg.edit_text(f"🎯 **Успешная охота!** Выигрыш: **+{win:,}**", reply_markup=kb, parse_mode="Markdown")
    else:
        profit = -stake
        add_leaderboard_profit(uid, profit)
        add_history(uid, "Охота", f"-{stake:,}")
        save_data()
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="btn_repeat_hunt")]])
        await msg.edit_text(f"🎯 **Неудача!** Ставка сгорела: **-{stake:,}** 💔", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "btn_repeat_hunt")
async def cb_repeat_hunt(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in last_user_bets or last_user_bets[uid]["game"] != "охота":
        return await cb.answer("У вас нет сохраненной ставки на охоту!", show_alert=True)
    last = last_user_bets[uid]
    msg = cb.message
    msg.from_user = cb.from_user
    msg.text = f"охота {last['stake']}"
    await game_hunt(msg)
    await cb.answer("Ставка на охоту повторена!")

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
    
    last_user_bets[uid] = {"game": "слоты", "stake": stake, "arg": ""}

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
        add_history(uid, "Слоты", f"+{win:,}")
        save_data()
        txt = f"🎰 [ {res_str} ]\n🎉 **ДЖЕКПОТ!** Награда: **+{win:,}**"
    else:
        profit = -stake
        add_leaderboard_profit(uid, profit)
        add_history(uid, "Слоты", f"-{stake:,}")
        save_data()
        txt = f"🎰 [ {res_str} ]\n💔 Комбинация не сыграла."
        
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔁 Повторить ставку", callback_data="btn_repeat_slots")]])
    await msg.edit_text(txt, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "btn_repeat_slots")
async def cb_repeat_slots(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in last_user_bets or last_user_bets[uid]["game"] != "слоты":
        return await cb.answer("У вас нет сохраненной ставки на слоты!", show_alert=True)
    last = last_user_bets[uid]
    msg = cb.message
    msg.from_user = cb.from_user
    msg.text = f"слоты {last['stake']}"
    await game_slots(msg)
    await cb.answer("Ставка на слоты повторена!")

# --- СТАНДАРТНЫЕ БАЗОВЫЕ КОМАНДЫ ---

@dp.message(F.text.lower().startswith("выдать"))
async def cmd_admin_give(message: Message):
    if message.from_user.id != ADMIN_ID: return
    if not message.reply_to_message: return await message.reply("⚠️ Ответьте на сообщение игрока!")
    target_id = message.reply_to_message.from_user.id
    target_user = get_user(target_id, message.reply_to_message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: return await message.reply("⚠️ Пример: `выдать 1000кк`")
    amount, err = parse_stake(parts[1], 999_999_999_999_999_999)
    if err: return await message.reply(err)
    target_user["balance"] += amount
    save_data()
    await message.reply(f"👑 Игроку **{target_user['name']}** выдано: **+{amount:,}**", parse_mode="Markdown")

@dp.message(F.text.lower() == "обнулировать")
async def cmd_admin_zero(message: Message):
    if message.from_user.id != ADMIN_ID: return
    if not message.reply_to_message: return await message.reply("⚠️ Ответьте на сообщение игрока!")
    target_id = message.reply_to_message.from_user.id
    target_user = get_user(target_id, message.reply_to_message.from_user.first_name)
    target_user["balance"] = 0
    target_user["bank"] = 0
    save_data()
    await message.reply(f"🚨 Игрок **{target_user['name']}** обнулен!", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("дать"))
async def cmd_transfer(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2 or not message.reply_to_message:
        return await message.reply("⚠️ Ответьте на сообщение игрока: `дать 50к`")
    amount, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
    if user["transfer_limit_lvl"] < 10 and amount > user["transfer_limit"]:
        return await message.reply(f"⚠️ Ваш лимит перевода: **{user['transfer_limit']:,} гиф**!")
        
    target_id = message.reply_to_message.from_user.id
    if target_id == message.from_user.id: return await message.reply("⚠️ Нельзя переводить самому себе!")
    target_user = get_user(target_id, message.reply_to_message.from_user.first_name)
    user["balance"] -= amount
    target_user["balance"] += amount
    save_data()
    await message.reply(f"🤝 Вы перевели **{amount:,}** игроку **{target_user['name']}**!", parse_mode="Markdown")

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
    if current_lvl >= 10: return await message.reply("🔥 У вас максимальный 10-й уровень!")
    next_lvl = current_lvl + 1
    cfg = LEVELS_CONFIG[next_lvl]
    cost = cfg["cost"]
    if user["balance"] < cost: return await message.reply(f"⚠️ Недостаточно средств для повышения до Lvl {next_lvl} (нужно {cost:,} гиф)")
    user["balance"] -= cost
    user["transfer_limit_lvl"] = next_lvl
    user["transfer_limit"] = 999999999999999 if next_lvl == 10 else cfg["limit"]
    save_data()
    await message.reply(f"🚀 Успешно! Уровень повышен: **Lvl {next_lvl}**", parse_mode="Markdown")

@dp.message(F.text.in_({"🏆 Топ", "топ"}))
async def cmd_top(message: Message):
    if not db: return await message.reply("🏆 Список игроков пуст.")
    sorted_users = sorted(db.values(), key=lambda x: x["balance"] + x["bank"], reverse=True)[:10]
    res = "🏆 **ТОП-10 БОГАЧЕЙ БОТА:**\n\n"
    for idx, u in enumerate(sorted_users, 1):
        total = u["balance"] + u["bank"]
        res += f"{idx}. **{u['name']}** — {total:,}\n"
    await message.reply(res, parse_mode="Markdown")

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
    limit_str = "Бесконечно (∞) ♾️" if user["transfer_limit_lvl"] == 10 else f"{user['transfer_limit']:,} гиф"
    await message.reply(
        f"👤 **ПРОФИЛЬ**\n🆔 ID: `{message.from_user.id}`\n"
        f"💸 Баланс: **{user['balance']:,}**\n🏦 Банк: **{user['bank']:,}**\n"
        f"⭐ Уровень: **Lvl {user['transfer_limit_lvl']} / 10**\n"
        f"🤝 Лимит перевода: **{limit_str}**", parse_mode="Markdown"
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

@dp.message(F.text.in_({"/start", "меню", "Меню", "🎰 Игры"}))
async def cmd_start(message: Message):
    get_user(message.from_user.id, message.from_user.first_name)
    await message.reply(
        "🎰 **БОТ КАЗИНО**\n\n"
        "• `мв [сумма]` — MegaWheel 🎡\n"
        "• `мины [ставка]` — Мины 💣\n"
        "• `хило [ставка]` — Hi-Lo 🎴\n"
        "• `рул [ставка]` — Рулетка 🎰\n"
        "• `х50 [ставка] [ч/ф/к/з]`\n"
        "• `охота [ставка]` | `слоты [ставка]`\n\n"
        "🔄 `повторить ставку` немесе `повтор` — соңғы ставкуды қайталау",
        reply_markup=main_keyboard(), parse_mode="Markdown"
    )

async def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("🚀 Gifgame_bot Мины, Хило және Повтор функцияларымен толық іске қосылды!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
