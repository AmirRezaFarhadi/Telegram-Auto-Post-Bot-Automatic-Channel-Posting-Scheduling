# # -*- coding: utf-8 -*-
# """
# Mirror & Scheduler for Telegram channels
# - ۱۰ پست در روز بین 10:00 تا 22:00 (به صورت پیش‌فرض)، با فاصله یکنواخت و امن
# - TZ-aware (با ZoneInfo) و ارسال schedule به UTC
# - اتمیک بودن انتخاب اسلات با قفل SQLite (BEGIN IMMEDIATE)
# - حفظ reply-chain بین پست‌های منتقل‌شده
# - حذف یوزرنیم/لینک سورس‌ها از متن و افزودن FOOTER
# - رعایت سقف Scheduled تلگرام (~100)
# -------------------------------------------------
# ENV نمونه (api.env):
# API_ID=123456
# API_HASH=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# DESTINATION=@your_channel_or_chat
# SOURCES=@src1;@src2
# SESSION_NAME=forward_bot_session
# FOOTER=💡 @aiwithamir
# SEND_DELAY_SEC=0.5

# # تنظیمات زمان‌بندی:
# TIMEZONE=Asia/Tehran
# POSTS_PER_DAY=10
# START_LOCAL=10:00
# END_LOCAL=22:00
# """

# import os
# import re
# import sys
# import asyncio
# import sqlite3
# from datetime import datetime, time, timedelta, date
# from typing import Optional, Dict, List, Tuple

# from dotenv import load_dotenv, find_dotenv
# from telethon import TelegramClient, events
# from telethon.tl.types import Message, MessageMediaPoll
# from telethon.tl import functions
# from zoneinfo import ZoneInfo

# # ==================== ENV ====================
# def _load_env():
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     path = os.path.join(script_dir, "api.env")
#     if os.path.exists(path):
#         load_dotenv(path, override=True)
#     else:
#         load_dotenv(find_dotenv(filename="api.env", usecwd=True), override=True)

# print("[*] Loading env...")
# _load_env()

# def _must_env(key: str) -> str:
#     v = os.getenv(key)
#     if not v:
#         print(f"[!] Missing environment variable: {key}")
#         sys.exit(1)
#     return v

# try:
#     API_ID = int(_must_env("API_ID"))
# except ValueError:
#     print("[!] API_ID باید عدد باشد.")
#     sys.exit(1)

# API_HASH      = _must_env("API_HASH")
# DEST          = _must_env("DESTINATION")
# SESSION_NAME  = os.getenv("SESSION_NAME", "forward_bot_session")

# # Footer
# FOOTER = os.getenv("FOOTER", "💡 @aiwithamir").strip()
# CAPTION_MAX = 1024
# TEXT_MAX    = 4096

# raw_sources = os.getenv("SOURCES", "") or os.getenv("SOURCE", "")
# SOURCES_RAW: List[str] = [p.strip() for p in re.split(r"[;,\n]", raw_sources) if p.strip()]
# if not SOURCES_RAW:
#     print("[!] No source channels in SOURCE/SOURCES")
#     sys.exit(1)
# print(f"[*] Sources: {SOURCES_RAW}")

# SEND_DELAY_SEC = float(os.getenv("SEND_DELAY_SEC", "0.5"))

# # سقف سخت تلگرام
# SCHEDULE_LIMIT = 100

# # Timezone & schedule window
# TIMEZONE     = os.getenv("TIMEZONE", "Asia/Tehran").strip()
# TZ           = ZoneInfo(TIMEZONE)

# def _parse_hhmm(s: str) -> time:
#     s = s.strip()
#     hh, mm = s.split(":")
#     return time(int(hh), int(mm))

# POSTS_PER_DAY = int(os.getenv("POSTS_PER_DAY", "10"))
# START_LOCAL   = _parse_hhmm(os.getenv("START_LOCAL", "10:00"))
# END_LOCAL     = _parse_hhmm(os.getenv("END_LOCAL", "22:00"))

# # ==================== CLIENT ====================
# SESSIONS_DIR = "sessions"
# os.makedirs(SESSIONS_DIR, exist_ok=True)
# SESSION_PATH = os.path.join(SESSIONS_DIR, SESSION_NAME)
# client = TelegramClient(SESSION_PATH, API_ID, API_HASH)

# # ==================== DB ====================
# DB_PATH = "mirror_state.sqlite"

# def _connect_db():
#     conn = sqlite3.connect(DB_PATH)
#     conn.execute("PRAGMA journal_mode=WAL;")
#     return conn

# def _table_has_cols(conn, table, cols):
#     cur = conn.cursor()
#     try:
#         cur.execute(f"PRAGMA table_info({table})")
#         names = {r[1] for r in cur.fetchall()}
#         return all(c in names for c in cols)
#     except sqlite3.Error:
#         return False

# def _ensure_schema():
#     with _connect_db() as conn:
#         ok1 = _table_has_cols(conn, "processed", {"src_chat", "src_msg_id"})
#         ok2 = _table_has_cols(conn, "mapping", {"src_chat", "src_msg_id", "dst_msg_id"})
#         ok3 = _table_has_cols(conn, "meta", {"key", "val"})
#         if ok1 and ok2 and ok3:
#             return
#     # backup & rebuild
#     try:
#         if os.path.exists(DB_PATH):
#             import shutil
#             ts = datetime.now().strftime("%Y%m%d-%H%M%S")
#             shutil.copy2(DB_PATH, f"{DB_PATH}.bak-{ts}")
#             print(f"[DB] Backed up old DB to {DB_PATH}.bak-{ts}")
#     except Exception as e:
#         print(f"[DB] Backup warning: {e}")

#     with _connect_db() as conn:
#         c = conn.cursor()
#         c.execute("DROP TABLE IF EXISTS processed")
#         c.execute("DROP TABLE IF EXISTS mapping")
#         c.execute("DROP TABLE IF EXISTS meta")
#         c.execute("""CREATE TABLE processed(
#                         src_chat TEXT, src_msg_id INTEGER,
#                         PRIMARY KEY(src_chat, src_msg_id))""")
#         c.execute("""CREATE TABLE mapping(
#                         src_chat TEXT, src_msg_id INTEGER,
#                         dst_msg_id INTEGER,
#                         PRIMARY KEY(src_chat, src_msg_id))""")
#         c.execute("""CREATE TABLE meta(
#                         key TEXT PRIMARY KEY, val TEXT)""")
#     print("[DB] Schema rebuilt")

# def init_db():
#     with _connect_db() as conn:
#         c = conn.cursor()
#         c.execute("""CREATE TABLE IF NOT EXISTS processed(
#                         src_chat TEXT, src_msg_id INTEGER,
#                         PRIMARY KEY(src_chat, src_msg_id))""")
#         c.execute("""CREATE TABLE IF NOT EXISTS mapping(
#                         src_chat TEXT, src_msg_id INTEGER,
#                         dst_msg_id INTEGER,
#                         PRIMARY KEY(src_chat, src_msg_id))""")
#         c.execute("""CREATE TABLE IF NOT EXISTS meta(
#                         key TEXT PRIMARY KEY, val TEXT)""")
#     _ensure_schema()

# def was_processed(chat_key, mid):
#     with _connect_db() as conn:
#         c = conn.cursor()
#         c.execute("SELECT 1 FROM processed WHERE src_chat=? AND src_msg_id=?", (chat_key, mid))
#         return c.fetchone() is not None

# def mark_processed(chat_key, mid):
#     with _connect_db() as conn:
#         c = conn.cursor()
#         c.execute("INSERT OR IGNORE INTO processed VALUES(?,?)", (chat_key, mid))

# def save_mapping(chat_key, src_id, dst_id):
#     with _connect_db() as conn:
#         c = conn.cursor()
#         c.execute("INSERT OR REPLACE INTO mapping VALUES(?,?,?)", (chat_key, src_id, dst_id))

# def get_mapping(chat_key, src_id):
#     with _connect_db() as conn:
#         c = conn.cursor()
#         c.execute("SELECT dst_msg_id FROM mapping WHERE src_chat=? AND src_msg_id=?", (chat_key, src_id))
#         row = c.fetchone()
#         return row[0] if row else None

# def meta_get(k, d=None):
#     with _connect_db() as conn:
#         c = conn.cursor()
#         c.execute("SELECT val FROM meta WHERE key=?", (k,))
#         r = c.fetchone()
#         return r[0] if r else d

# def meta_set(k, v):
#     with _connect_db() as conn:
#         c = conn.cursor()
#         c.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, v))

# # ==================== UTILS ====================
# def _source_key(s: str) -> str:
#     """کلید استاندارد برای سورس‌ها (username بدون @ و lowercase؛ اگر آیدی بود همان رشته)."""
#     s = s.strip()
#     if s.startswith("@"):
#         return s[1:].lower()
#     return s.lower()

# def _local_now() -> datetime:
#     return datetime.now(TZ)

# def _combine_local(d: date, t: time) -> datetime:
#     return datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=TZ)

# def _build_slots_for_day(d: date) -> List[datetime]:
#     """
#     ساخت اسلات‌های یکنواخت بین START_LOCAL و END_LOCAL.
#     اگر POSTS_PER_DAY=10 و بازه 10:00..22:00 باشد، فاصله ≈ 80 دقیقه می‌شود.
#     """
#     if POSTS_PER_DAY <= 1:
#         return [_combine_local(d, START_LOCAL)]
#     start_dt = _combine_local(d, START_LOCAL)
#     end_dt   = _combine_local(d, END_LOCAL)
#     if end_dt <= start_dt:
#         # اگر کاربر اشتباه وارد کرد، حداقل یک دقیقه بعد از start
#         end_dt = start_dt + timedelta(minutes=POSTS_PER_DAY - 1)
#     total_minutes = int((end_dt - start_dt).total_seconds() // 60)
#     gap = total_minutes / (POSTS_PER_DAY - 1)
#     slots = [(start_dt + timedelta(minutes=round(i * gap))) for i in range(POSTS_PER_DAY)]
#     slots = sorted(min(s, end_dt) for s in slots)
#     return slots

# # پاکسازی آیدی/لینک سورس‌ها
# SOURCE_USERNAMES: List[str] = [_source_key(s) for s in SOURCES_RAW if s.startswith("@")]

# def sanitize_text(txt: Optional[str]) -> str:
#     if not txt:
#         return ""
#     cleaned = txt
#     for u in SOURCE_USERNAMES:
#         pat = re.compile(rf"(?:@{re.escape(u)}\b|https?://t\.me/{re.escape(u)}\b)", flags=re.IGNORECASE)
#         cleaned = pat.sub("", cleaned)
#     cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
#     return cleaned

# # Footer helpers
# def _has_footer(txt: str, footer: str) -> bool:
#     if not txt or not footer:
#         return False
#     return footer.lower() in txt.lower()

# def apply_footer(txt: Optional[str], is_caption: bool) -> str:
#     base = (txt or "").rstrip()
#     footer = FOOTER
#     if not footer:
#         limit = CAPTION_MAX if is_caption else TEXT_MAX
#         return base[:limit]
#     if _has_footer(base, footer):
#         limit = CAPTION_MAX if is_caption else TEXT_MAX
#         return base[:limit]
#     sep = "\n\n" if base else ""
#     composed = f"{base}{sep}{footer}".strip()
#     limit = CAPTION_MAX if is_caption else TEXT_MAX
#     if len(composed) > limit:
#         room_for_base = max(0, limit - len(footer) - len(sep))
#         base_trunc = base[:room_for_base].rstrip()
#         composed = f"{base_trunc}{(sep if base_trunc else '')}{footer}".strip()
#     return composed

# # ==================== شمارش Scheduled مقصد ====================
# async def count_scheduled(dest_entity) -> int:
#     """
#     تعداد پیام‌های زمان‌بندی‌شده در چت مقصد را برمی‌گرداند.
#     اگر خطایی رخ دهد، محافظه‌کارانه سقف (100) را برمی‌گرداند.
#     """
#     try:
#         res = await client(functions.messages.GetScheduledHistoryRequest(
#             peer=dest_entity,
#             hash=0
#         ))
#         return len(res.messages or [])
#     except Exception as e:
#         print(f"[SCHED] count failed: {e}")
#         return SCHEDULE_LIMIT

# # ==================== SENDER (بدون دانلود/آپلود + حفظ ریپلای + اسکجوال + فوتِر) ====================
# async def _send_with_reply(src_key: str, msg: Message, dest_entity, sched_dt: datetime):
#     # نگاشت ریپلای
#     reply_to = None
#     if getattr(msg, "reply_to", None) and getattr(msg.reply_to, "reply_to_msg_id", None):
#         mapped = get_mapping(src_key, msg.reply_to.reply_to_msg_id)
#         if mapped:
#             reply_to = mapped

#     clean_text = sanitize_text(getattr(msg, "text", None))

#     # رد Poll
#     if isinstance(msg.media, MessageMediaPoll):
#         return None

#     schedule_dt = sched_dt.astimezone(ZoneInfo("UTC"))

#     if msg.media:
#         caption = apply_footer(clean_text, is_caption=True)
#         sent = await client.send_file(
#             dest_entity,
#             file=msg.media,               # تلاش برای ارسال بدون دانلود/آپلود
#             caption=caption,
#             buttons=msg.reply_markup,
#             reply_to=reply_to,
#             schedule=schedule_dt
#         )
#     else:
#         text_to_send = apply_footer(clean_text, is_caption=False)
#         if not text_to_send:
#             text_to_send = FOOTER or ""
#         if not text_to_send:
#             return None
#         sent = await client.send_message(
#             dest_entity,
#             text_to_send,
#             buttons=msg.reply_markup,
#             reply_to=reply_to,
#             schedule=schedule_dt
#         )

#     await asyncio.sleep(SEND_DELAY_SEC)
#     return sent

# # ==================== SCHEDULER CORE ====================
# def _next_schedule_dt() -> datetime:
#     """
#     اسلات بعدی را به صورت اتمیک از DB انتخاب می‌کند.
#     - اسلات‌ها بین START_LOCAL..END_LOCAL بر اساس POSTS_PER_DAY ساخته می‌شوند.
#     - اگر امروز از اسلات‌ها عبور کرده‌ایم، می‌پرد به بعدی یا فردا.
#     - برای جلوگیری از Race بین بک‌فیل و لیسنر از BEGIN IMMEDIATE استفاده می‌شود.
#     """
#     now = _local_now()
#     today_key = now.date().strftime("%Y%m%d")

#     with _connect_db() as conn:
#         c = conn.cursor()
#         c.execute("BEGIN IMMEDIATE")  # قفل برای اتمیک بودن

#         # خواندن متا در همین تراکنش
#         c.execute("SELECT val FROM meta WHERE key='sched_day'")
#         row_day = c.fetchone()
#         cur_day = row_day[0] if row_day else ""

#         c.execute("SELECT val FROM meta WHERE key='sched_idx'")
#         row_idx = c.fetchone()
#         cur_idx = int((row_idx[0] if row_idx else "0") or "0")

#         # تعیین روز کاری
#         if not cur_day:
#             work_day = today_key
#             cur_idx = 0
#         elif cur_day < today_key:
#             work_day = today_key
#             cur_idx = 0
#         else:
#             work_day = cur_day

#         # تاریخ روز کاری
#         if work_day == today_key:
#             base_date = now.date()
#         else:
#             y, m, d = int(work_day[:4]), int(work_day[4:6]), int(work_day[6:])
#             base_date = date(y, m, d)

#         slots = _build_slots_for_day(base_date)

#         # اگر روز کاری امروز است، اسلات‌های گذشته را رد کن
#         if work_day == today_key:
#             while cur_idx < len(slots) and slots[cur_idx] <= now:
#                 cur_idx += 1

#         if cur_idx >= len(slots):
#             # فردا از اول
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

# # ==================== BACKFILL ====================
# async def backfill_history(src_key: str, src_entity, dest_entity):
#     """
#     تاریخچه‌ی سورس را از قدیمی به جدید برنامه‌ریزی می‌کند.
#     اگر سقف 100 تا پر شد، کار را همان‌جا متوقف می‌کند (processed علامت نمی‌زند)
#     تا اجرای بعدی از همان‌جا ادامه دهد.
#     """
#     async for msg in client.iter_messages(src_entity, reverse=True):
#         if was_processed(src_key, msg.id):
#             continue

#         scheduled_now = await count_scheduled(dest_entity)
#         if scheduled_now >= SCHEDULE_LIMIT:
#             print(f"[BF][{src_key}] STOP: destination has {scheduled_now} scheduled (limit={SCHEDULE_LIMIT}).")
#             return

#         sched = _next_schedule_dt()
#         try:
#             sent = await _send_with_reply(src_key, msg, dest_entity, sched)
#         except Exception as e:
#             print(f"[BF][{src_key}] ERROR sending {msg.id}: {e}")
#             continue
#         if sent:
#             save_mapping(src_key, msg.id, sent.id)
#             mark_processed(src_key, msg.id)
#             print(f"[BF][{src_key}] {msg.id} -> {sent.id} at {sched.isoformat()}")

# # ==================== LIVE LISTENER ====================
# async def handle_new_message(event: events.NewMessage.Event, dest_entity, source_id_to_key: Dict[int, str]):
#     msg = event.message
#     src_key = source_id_to_key.get(event.chat_id)
#     if not src_key:
#         return

#     if was_processed(src_key, msg.id):
#         return

#     scheduled_now = await count_scheduled(dest_entity)
#     if scheduled_now >= SCHEDULE_LIMIT:
#         print(f"[LIVE][{src_key}] SKIP: scheduled={scheduled_now} (limit={SCHEDULE_LIMIT}). Will be picked up next run.")
#         return

#     sched = _next_schedule_dt()
#     try:
#         sent = await _send_with_reply(src_key, msg, dest_entity, sched)
#     except Exception as e:
#         print(f"[LIVE][{src_key}] ERROR sending {msg.id}: {e}")
#         return

#     if sent:
#         save_mapping(src_key, msg.id, sent.id)
#         mark_processed(src_key, msg.id)
#         print(f"[LIVE][{src_key}] {msg.id} -> {sent.id} at {sched.isoformat()}")

# # ==================== MAIN ====================
# async def main():
#     init_db()
#     await client.start()

#     # مقصد: یوزرنیم/آیدی/لینک جوین
#     try:
#         dest_entity = await client.get_entity(DEST)
#     except Exception as e:
#         print(f("[!] Could not resolve DESTINATION {DEST!r}: {e}"))
#         return

#     # رزولوشن سورس‌ها با نگاشت id → key
#     source_entities: List[Tuple[str, object]] = []
#     source_id_to_key: Dict[int, str] = {}

#     for s in SOURCES_RAW:
#         try:
#             ent = await client.get_entity(s)
#         except Exception as e:
#             print(f"[!] Could not resolve source {s!r}: {e}")
#             continue
#         key = _source_key(s if s.startswith("@") else (getattr(ent, "username", None) or str(ent.id)))
#         source_entities.append((key, ent))
#         source_id_to_key[getattr(ent, "id")] = key

#     if not source_entities:
#         print("[!] No valid sources resolved. Exiting.")
#         return

#     # بک‌فیل همه‌ی سورس‌ها (تا اولین برخورد با سقف)
#     for key, ent in source_entities:
#         print(f"[*] Backfilling {key} ...")
#         await backfill_history(key, ent, dest_entity)
#         scheduled_now = await count_scheduled(dest_entity)
#         if scheduled_now >= SCHEDULE_LIMIT:
#             print(f"[*] STOP backfill (scheduled={scheduled_now}/{SCHEDULE_LIMIT}). Resume on next run.")
#             break

#     print("[*] Listening...")
#     @client.on(events.NewMessage(chats=[ent for _, ent in source_entities]))
#     async def listener(event):
#         await handle_new_message(event, dest_entity, source_id_to_key)

#     await client.run_until_disconnected()

# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         print("[!] Stopped")






# -*- coding: utf-8 -*-
"""
Mirror & Scheduler for Telegram channels (نسخه Bot Token)
-------------------------------------------------
ENV نمونه (api.env):
API_ID=123456
API_HASH=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
DESTINATION=@your_channel_or_chat
SOURCES=@src1;@src2
FOOTER=💡 @aiwithamir
SEND_DELAY_SEC=0.5
TIMEZONE=Asia/Tehran
POSTS_PER_DAY=10
START_LOCAL=10:00
END_LOCAL=22:00
"""

import os, re, sys, asyncio, sqlite3
from datetime import datetime, time, timedelta, date
from typing import Optional, Dict, List, Tuple

from dotenv import load_dotenv, find_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import Message, MessageMediaPoll
from telethon.tl import functions
from zoneinfo import ZoneInfo

# ==================== ENV ====================
def _load_env():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "api.env")
    if os.path.exists(path):
        load_dotenv(path, override=True)
    else:
        load_dotenv(find_dotenv(filename="api.env", usecwd=True), override=True)

print("[*] Loading env...")
_load_env()

def _must_env(key: str) -> str:
    v = os.getenv(key)
    if not v:
        print(f"[!] Missing environment variable: {key}")
        sys.exit(1)
    return v

try:
    API_ID = int(_must_env("API_ID"))
except ValueError:
    print("[!] API_ID باید عدد باشد.")
    sys.exit(1)

API_HASH  = _must_env("API_HASH")
BOT_TOKEN = _must_env("BOT_TOKEN")
DEST      = _must_env("DESTINATION")

FOOTER = os.getenv("FOOTER", "💡 @aiwithamir").strip()
CAPTION_MAX, TEXT_MAX = 1024, 4096

raw_sources = os.getenv("SOURCES", "") or os.getenv("SOURCE", "")
SOURCES_RAW: List[str] = [p.strip() for p in re.split(r"[;,\n]", raw_sources) if p.strip()]
if not SOURCES_RAW:
    print("[!] No source channels in SOURCE/SOURCES")
    sys.exit(1)
print(f"[*] Sources: {SOURCES_RAW}")

SEND_DELAY_SEC = float(os.getenv("SEND_DELAY_SEC", "0.5"))
SCHEDULE_LIMIT = 100

TIMEZONE   = os.getenv("TIMEZONE", "Asia/Tehran").strip()
TZ         = ZoneInfo(TIMEZONE)

def _parse_hhmm(s: str) -> time:
    hh, mm = s.strip().split(":")
    return time(int(hh), int(mm))

POSTS_PER_DAY = int(os.getenv("POSTS_PER_DAY", "10"))
START_LOCAL   = _parse_hhmm(os.getenv("START_LOCAL", "10:00"))
END_LOCAL     = _parse_hhmm(os.getenv("END_LOCAL", "22:00"))

# ==================== CLIENT ====================
client = TelegramClient("bot_session", API_ID, API_HASH)

# ==================== DB ====================
DB_PATH = "mirror_state.sqlite"

def _connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def _ensure_schema():
    with _connect_db() as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS processed(
                        src_chat TEXT, src_msg_id INTEGER,
                        PRIMARY KEY(src_chat, src_msg_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS mapping(
                        src_chat TEXT, src_msg_id INTEGER,
                        dst_msg_id INTEGER,
                        PRIMARY KEY(src_chat, src_msg_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS meta(
                        key TEXT PRIMARY KEY, val TEXT)""")

def init_db():
    _ensure_schema()

def was_processed(chat_key, mid):
    with _connect_db() as conn:
        return conn.execute("SELECT 1 FROM processed WHERE src_chat=? AND src_msg_id=?", (chat_key, mid)).fetchone() is not None

def mark_processed(chat_key, mid):
    with _connect_db() as conn:
        conn.execute("INSERT OR IGNORE INTO processed VALUES(?,?)", (chat_key, mid))

def save_mapping(chat_key, src_id, dst_id):
    with _connect_db() as conn:
        conn.execute("INSERT OR REPLACE INTO mapping VALUES(?,?,?)", (chat_key, src_id, dst_id))

def get_mapping(chat_key, src_id):
    with _connect_db() as conn:
        row = conn.execute("SELECT dst_msg_id FROM mapping WHERE src_chat=? AND src_msg_id=?", (chat_key, src_id)).fetchone()
        return row[0] if row else None

def meta_get(k, d=None):
    with _connect_db() as conn:
        row = conn.execute("SELECT val FROM meta WHERE key=?", (k,)).fetchone()
        return row[0] if row else d

def meta_set(k, v):
    with _connect_db() as conn:
        conn.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, v))

# ==================== MAIN ====================
async def main():
    init_db()
    await client.start(bot_token=BOT_TOKEN)

    try:
        dest_entity = await client.get_entity(DEST)
    except Exception as e:
        print(f"[!] Could not resolve DESTINATION {DEST!r}: {e}")
        return

    print("[*] Listening...")
    @client.on(events.NewMessage(chats=SOURCES_RAW))
    async def listener(event):
        print(f"[LIVE] {event.message.id} from {event.chat_id}")

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[!] Stopped")
