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
global_rise_counter = 0

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

active_rise = {}

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

# --- БАНК ---
@dp.message(F.text.in_({"🏦 Банк", "банк"}))
async def cmd_bank(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Положить", callback_data="bank_deposit"),
         InlineKeyboardButton(text="📤 Снять", callback_data="bank_withdraw")]
    ])
    await message.reply(
        f"🏦 **БАНК**\n\n"
        f"💵 На руках: **{user['balance']:,}** гифов\n"
        f"🔒 В банке: **{user['bank']:,}** гифов",
        reply_markup=kb, parse_mode="Markdown"
    )

@dp.callback_query(F.data.in_({"bank_deposit", "bank_withdraw"}))
async def cb_bank_actions(cb: CallbackQuery):
    user = get_user(cb.from_user.id, cb.from_user.first_name)
    if cb.data == "bank_deposit":
        if user["balance"] <= 0:
            return await cb.answer("У вас нет средств на руках!", show_alert=True)
        user["bank"] += user["balance"]
        user["balance"] = 0
        save_data()
        await cb.message.edit_text(f"🏦 Успешно внесено в банк! Баланс банка: **{user['bank']:,}**", parse_mode="Markdown")
    else:
        if user["bank"] <= 0:
            return await cb.answer("В банке нет средств!", show_alert=True)
        user["balance"] += user["bank"]
        user["bank"] = 0
        save_data()
        await cb.message.edit_text(f"🏦 Успешно снято из банка! Баланс на руках: **{user['balance']:,}**", parse_mode="Markdown")
    await cb.answer()

# --- ПРОМОКОДЫ ---
@dp.message(F.text.lower().startswith("промо"))
async def cmd_promo(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("⚠️ Введите промокод! Пример: `промо START`", parse_mode="Markdown")
    code = parts[1].strip()
    if code not in promos:
        return await message.reply("❌ Промокод не найден или устарел!")
    
    p_data = promos[code]
    uid = message.from_user.id
    user = get_user(uid, message.from_user.first_name)
    
    if uid in p_data.get("used_by", []):
        return await message.reply("⚠️ Вы уже использовали этот промокод!")
    
    if p_data["uses"] <= 0:
        return await message.reply("❌ Промокод исчерпан!")
    
    p_data["uses"] -= 1
    if "used_by" not in p_data:
        p_data["used_by"] = []
    p_data["used_by"].append(uid)
    
    user["balance"] += p_data["reward"]
    save_data()
    await message.reply(f"🎁 Промокод успешно активирован! Получено: **+{p_data['reward']:,} гифов**", parse_mode="Markdown")

# --- ПЕРЕВОДЫ ---
@dp.message(F.text.lower().startswith("передать"))
@dp.message(F.text.lower().startswith("pay"))
async def cmd_pay(message: Message):
    if not message.reply_to_message:
        return await message.reply("⚠️ Ответьте на сообщение пользователя командой `передать [сумма]`", parse_mode="Markdown")
    
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("⚠️ Укажите сумму для перевода!", parse_mode="Markdown")
    
    sender_id = message.from_user.id
    sender = get_user(sender_id, message.from_user.first_name)
    
    target_user = message.reply_to_message.from_user
    if target_user.id == sender_id:
        return await message.reply("⚠️ Нельзя переводить самому себе!")
    
    amount, err = parse_stake(parts[1], sender["balance"])
    if err:
        return await message.reply(err)
    
    if amount > sender["transfer_limit"]:
        return await message.reply(f"⚠️ Превышен лимит перевода! Ваш лимит: {sender['transfer_limit']:,}", parse_mode="Markdown")
        
    recipient = get_user(target_user.id, target_user.first_name)
    
    sender["balance"] -= amount
    recipient["balance"] += amount
    save_data()
    
    await message.reply(f"✅ Успешно передано **{amount:,} гифов** игроку {recipient['name']}!", parse_mode="Markdown")

# --- АДМИН-ПАНЕЛЬ ---
@dp.message(F.text.lower() == "админ")
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промо", callback_data="adm_create_promo")],
        [InlineKeyboardButton(text="💸 Выдать деньги", callback_data="adm_give_money")]
    ])
    await message.reply("👑 **Панель администратора:**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "adm_create_promo")
async def cb_adm_promo(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    code = f"PROMO{random.randint(100, 999)}"
    promos[code] = {"reward": 100000, "uses": 10, "used_by": []}
    save_data()
    await cb.message.edit_text(f"✅ Создан промокод: `{code}` на 100,000 гифов (10 активаций)", parse_mode="Markdown")

@dp.callback_query(F.data == "adm_give_money")
async def cb_adm_money(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    user = get_user(cb.from_user.id, cb.from_user.first_name)
    user["balance"] += 1000000
    save_data()
    await cb.answer("Выдано 1,000,000 гифов себе!", show_alert=True)

# --- ЛИДЕРБОРД ---
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
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_lb")]])
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
            
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_lb")]])
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await cb.answer("ЛБ обновлен!")

# --- ПРОФИЛЬ, БОНУС, ТОП ---
@dp.message(F.text.in_({"👤 Профиль", "профиль"}))
async def cmd_profile(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    await message.reply(
        f"👤 **ПРОФИЛЬ**\n🆔 ID: `{message.from_user.id}`\n"
        f"💸 Баланс: **{user['balance']:,}**\n🏦 Банк: **{user['bank']:,}**", parse_mode="Markdown"
    )

@dp.message(F.text.in_({"🎁 Бонус", "бонус"}))
async def cmd_bonus(message: Message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    bonus_val = random.randint(50000, 250000)
    user["balance"] += bonus_val
    save_data()
    await message.reply(f"🎁 Бонус успешно получен: **+{bonus_val:,}**!", parse_mode="Markdown")

@dp.message(F.text.in_({"🏆 Топ", "топ"}))
async def cmd_top(message: Message):
    if not db: return await message.reply("🏆 Список игроков пуст.")
    sorted_users = sorted(db.values(), key=lambda x: x["balance"] + x["bank"], reverse=True)[:10]
    res = "🏆 **ТОП-10 БОГАЧЕЙ БОТА:**\n\n"
    for idx, u in enumerate(sorted_users, 1):
        total = u["balance"] + u["bank"]
        res += f"{idx}. **{u['name']}** — {total:,}\n"
    await message.reply(res, parse_mode="Markdown")

@dp.message(F.text.in_({"🎰 Игры", "игры"}))
async def cmd_games(message: Message):
    await message.reply(
        "🎰 **ДОСТУПНЫЕ ИГРЫ:**\n\n"
        "• `рз [ставка]` или `рз все` — Райз (8 этажей)\n", parse_mode="Markdown"
    )

# ==========================================
# --- ИГРА РАЙЗ (РЗ) - 8 ЭТАПОВ С НАКОПИТЕЛЬНОЙ ИСТОРИЕЙ ---
# ==========================================

RISE_STAGES = [
    {"step": 1, "bombs": 1, "gems": 4, "mult": 1.44},
    {"step": 2, "bombs": 2, "gems": 3, "mult": 2.11},
    {"step": 3, "bombs": 3, "gems": 2, "mult": 4.67},
    {"step": 4, "bombs": 4, "gems": 1, "mult": 21.01},
    {"step": 5, "bombs": 3, "gems": 2, "mult": 67.67},
    {"step": 6, "bombs": 2, "gems": 3, "mult": 101.01},
    {"step": 7, "bombs": 1, "gems": 4, "mult": 500.8},
    {"step": 8, "bombs": 0, "gems": 5, "mult": 1000.0},
]

def get_rise_kb(can_take: bool = False):
    row = [InlineKeyboardButton(text="❓", callback_data=f"rise_cell_{i}") for i in range(5)]
    kb = [row]
    if can_take:
        kb.append([InlineKeyboardButton(text="💰 Забрать выигрыш", callback_data="rise_take")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(F.text.lower().startswith("райз"))
@dp.message(F.text.lower().startswith("рз"))
async def game_rise_start(message: Message):
    global global_rise_counter
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    parts = message.text.split()
    if len(parts) < 2: 
        return await message.reply("⚠️ Пример: `рз 50к` или `рз все`", parse_mode="Markdown")
    
    stake, err = parse_stake(parts[1], user["balance"])
    if err: return await message.reply(err)
    
    user["balance"] -= stake
    save_data()
    
    global_rise_counter += 1
    game_id = global_rise_counter
    
    st = RISE_STAGES[0]
    bomb_indices = set(random.sample(range(5), st["bombs"]))
    
    active_rise[user_id] = {
        "game_id": game_id,
        "stake": stake,
        "stage": 0,
        "bombs": bomb_indices,
        "history_lines": [],
        "revealed": {}
    }
    
    text = (
        f"Игра #{game_id} в райз начался!\n\n"
        f"❔ ❔ ❔ ❔ ❔\n\n"
        f"1 этаж {st['mult']}х"
    )
    await message.reply(text, reply_markup=get_rise_kb(can_take=False), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("rise_"))
async def process_rise_action(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in active_rise:
        return await cb.answer("Эта игра завершена или не найдена!", show_alert=True)
    
    g = active_rise[uid]
    user = get_user(uid, cb.from_user.first_name)
    
    if cb.data == "rise_take":
        if g["stage"] == 0:
            return await cb.answer("Нужно пройти хотя бы 1 этаж!", show_alert=True)
        prev_stage = g["stage"] - 1
        mult = RISE_STAGES[prev_stage]["mult"]
        win = int(g["stake"] * mult)
        user["balance"] += win
        profit = win - g["stake"]
        if profit > 0:
            add_leaderboard_profit(uid, profit)
        save_data()
        
        history_str = "\n".join(g["history_lines"])
        game_id = g["game_id"]
        del active_rise[uid]
        return await cb.message.edit_text(
            f"Игра #{game_id} в райз начался!\n\n"
            f"{history_str}\n\n"
            f"💰 **Успешно забрано!** Выигрыш: **+{win:,} гифов** ({mult}x)", parse_mode="Markdown"
        )
    
    if cb.data.startswith("rise_cell_"):
        stage_idx = g["stage"]
        st = RISE_STAGES[stage_idx]
        cell_idx = int(cb.data.split("_")[2])
        
        if cell_idx in g["revealed"]:
            return await cb.answer("Эта ячейка уже открыта!", show_alert=True)
            
        if cell_idx in g["bombs"]:
            current_row_res = []
            for i in range(5):
                if i in g["bombs"]:
                    current_row_res.append("💣")
                else:
                    current_row_res.append("💎")
            
            g["history_lines"].append(" ".join(current_row_res))
            history_str = "\n".join(g["history_lines"])
            
            stake_lost = g["stake"]
            add_leaderboard_profit(uid, -stake_lost)
            
            game_id = g["game_id"]
            del active_rise[uid]
            return await cb.message.edit_text(
                f"Игра #{game_id} в райз начался!\n\n"
                f"{history_str}\n\n"
                f"❌ **ПОРАЖЕНИЕ НА {stage_idx + 1} УРОВНЕ** (-{stake_lost:,} гифов)", parse_mode="Markdown"
            )
        else:
            g["revealed"][cell_idx] = "💎"
            gems_found = sum(1 for s in g["revealed"].values() if s == "💎")
            
            if gems_found >= st["gems"]:
                current_row_res = []
                for i in range(5):
                    if i in g["bombs"]:
                        current_row_res.append("💣")
                    else:
                        current_row_res.append("💎")
                
                g["history_lines"].append(" ".join(current_row_res))
                g["stage"] += 1
                
                if g["stage"] >= len(RISE_STAGES):
                    mult = RISE_STAGES[-1]["mult"]
                    win = int(g["stake"] * mult)
                    user["balance"] += win
                    add_leaderboard_profit(uid, win - g["stake"])
                    save_data()
                    
                    history_str = "\n".join(g["history_lines"])
                    game_id = g["game_id"]
                    del active_rise[uid]
                    return await cb.message.edit_text(
                        f"Игра #{game_id} в райз начался!\n\n"
                        f"{history_str}\n\n"
                        f"🏆 **ПОБЕДА! 8 УРОВНЕЙ ПРОЙДЕНЫ!** (+{win:,} гифов)", parse_mode="Markdown"
                    )
                
                next_st = RISE_STAGES[g["stage"]]
                g["bombs"] = set(random.sample(range(5), next_st["bombs"]))
                g["revealed"] = {}
                
                history_str = "\n".join(g["history_lines"])
                game_id = g["game_id"]
                
                text = (
                    f"Игра #{game_id} в райз начался!\n\n"
                    f"❔ ❔ ❔ ❔ ❔\n"
                    f"{history_str}\n\n"
                    f"{g['stage'] + 1} этаж {next_st['mult']}х"
                )
                await cb.message.edit_text(text, reply_markup=get_rise_kb(can_take=True), parse_mode="Markdown")
                await cb.answer("💎 Алмаз найден!")
            else:
                await cb.answer("💎 Алмаз найден! Продолжайте.")

# --- СТАРТ И МЕНЮ ---
@dp.message(F.text.in_({"/start", "меню", "Меню", "🆘 Помощь", "помощь"}))
async def cmd_start(message: Message):
    get_user(message.from_user.id, message.from_user.first_name)
    await message.reply(
        "🎰 **БОТ КАЗИНО**\n\n"
        "• `рз [ставка]` или `рз все` — Начать игру Райз\n"
        "• `баланс` | `профиль` | `топ` | `лб` | `бонус`",
        reply_markup=main_keyboard(), parse_mode="Markdown"
    )

async def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("🚀 Бот запущен, игра Райз исправлена точно по вашему описанию!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
