#!/usr/bin/env python3
# client.py
import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient, events, types, errors
from telethon.tl.types import InputPeerUser, InputPeerChannel
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from util import human_size, save_media_to_file

load_dotenv()
API_ID = int(os.getenv("API_ID") or 0)
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION_NAME", "session")

if not API_ID or not API_HASH:
    print("Заполните .env: API_ID и API_HASH")
    raise SystemExit(1)

client = TelegramClient(SESSION, API_ID, API_HASH)

# state helpers
current_peer = None  # выбранный чат (entity)
lang = "ru"  # "ru" or "en"

PROMPTS = {
    "ru": {
        "prompt": "tg> ",
        "help": """Доступные команды:
help — показать эту справку
me — информация о текущем пользователе
dialogs — список чатов
select <num> — выбрать чат по номеру из списка dialogs
history [n] — показать последние n сообщений (по умолчанию 20)
send <text> — отправить текст в выбранный чат
sendfile <путь> — отправить файл/картинку/аудио
download <msg_id> <путь> — скачать медиа из сообщения (по id в истории)
lang — переключить язык (ru/en)
exit — выйти""",
        "no_peer": "Чат не выбран. Используйте dialogs и select <num>.",
        "no_msgs": "Нет сообщений.",
        "selected": "Выбран чат:",
    },
    "en": {
        "prompt": "tg> ",
        "help": """Commands:
help — show this help
me — current user info
dialogs — list chats
select <num> — select chat by number from dialogs
history [n] — show last n messages (default 20)
send <text> — send text to selected chat
sendfile <path> — send file/image/audio
download <msg_id> <path> — download media from message (id from history)
lang — toggle language (ru/en)
exit — quit""",
        "no_peer": "No chat selected. Use dialogs and select <num>.",
        "no_msgs": "No messages.",
        "selected": "Selected chat:",
    },
}

async def list_dialogs():
    dialogs = []
    async for dialog in client.iter_dialogs():
        dialogs.append(dialog)
    for i, d in enumerate(dialogs, 1):
        name = d.name or getattr(d.entity, "username", "—")
        typ = "Channel" if d.is_channel else "Chat" if d.is_user is False else "User"
        print(f"{i}. {name} ({typ}) — id={d.id}")
    return dialogs

async def show_history(entity, limit=20):
    msgs = await client.get_messages(entity, limit=limit)
    if not msgs:
        print(PROMPTS[lang]["no_msgs"])
        return msgs
    for m in reversed(msgs):
        mid = m.id
        who = getattr(m.sender, "first_name", None) or getattr(m.sender, "username", None) or "?"
        text_preview = m.message or ""
        media_info = ""
        if m.media:
            mt = type(m.media).__name__
            size = ""
            if getattr(m.media, "size", None):
                size = f" ({human_size(m.media.size)})"
            media_info = f" [MEDIA:{mt}{size}]"
        print(f"[{mid}] {who}: {text_preview}{media_info}")
    return msgs

@client.on(events.NewMessage)
async def handler(event):
    # простые уведомления в консоль
    sender = await event.get_sender()
    name = sender.first_name if sender and getattr(sender, "first_name", None) else (sender.username if sender else "Unknown")
    print(f"\n\n---\nNew from {name}: {event.raw_text}\n---\n{PROMPTS[lang]['prompt']}", end="", flush=True)

async def interactive_loop():
    global current_peer, lang
    print("Telegram CLI (Telethon). Для помощи введите help")
    while True:
        try:
            cmd = input(PROMPTS[lang]["prompt"]).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not cmd:
            continue
        parts = cmd.split(maxsplit=1)
        c = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        if c == "help":
            print(PROMPTS[lang]["help"])
        elif c == "lang":
            lang = "en" if lang == "ru" else "ru"
            print("Language:", lang)
        elif c == "me":
            me = await client.get_me()
            print(f"{me.first_name} @{me.username} id={me.id}")
        elif c == "dialogs":
            await list_dialogs()
        elif c == "select":
            if not arg:
                print("select <num>")
                continue
            try:
                idx = int(arg) - 1
            except:
                print("Неверный номер")
                continue
            dialogs = []
            async for d in client.iter_dialogs():
                dialogs.append(d)
            if idx < 0 or idx >= len(dialogs):
                print("Индекс вне диапазона")
                continue
            current_peer = dialogs[idx].entity
            print(PROMPTS[lang]["selected"], dialogs[idx].name)
        elif c == "history":
            if not current_peer:
                print(PROMPTS[lang]["no_peer"])
                continue
            n = 20
            if arg:
                try:
                    n = int(arg)
                except:
                    pass
            await show_history(current_peer, limit=n)
        elif c == "send":
            if not current_peer:
                print(PROMPTS[lang]["no_peer"])
                continue
            if not arg:
                print("send <text>")
                continue
            await client.send_message(current_peer, arg)
            print("OK")
        elif c == "sendfile":
            if not current_peer:
                print(PROMPTS[lang]["no_peer"])
                continue
            path = arg.strip()
            if not path:
                print("sendfile <path>")
                continue
            if not os.path.exists(path):
                print("Файл не найден")
                continue
            # send file (auto-detect)
            await client.send_file(current_peer, path)
            print("Отправлено")
        elif c == "download":
            if not current_peer:
                print(PROMPTS[lang]["no_peer"])
                continue
            if not arg:
                print("download <msg_id> <path>")
                continue
            sp = arg.split(maxsplit=1)
            if len(sp) < 2:
                print("download <msg_id> <path>")
                continue
            try:
                mid = int(sp[0])
            except:
                print("Неверный id")
                continue
            path = sp[1]
            msgs = await client.get_messages(current_peer, ids=[mid])
            if not msgs:
                print("Сообщение не найдено")
                continue
            m = msgs[0]
            if not m.media:
                print("В сообщении нет медиа")
                continue
            out = await save_media_to_file(m, path)
            print("Сохранено в", out)
        elif c == "exit" or c == "quit":
            break
        else:
            print("Неизвестная команда. help для списка.")
    await client.disconnect()

async def main():
    await client.start()
    print("Авторизация выполнена.")
    # запустить интерактивный loop параллельно с клиентом (обработчик событий уже зарегистрирован)
    await interactive_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

# Ветка main
