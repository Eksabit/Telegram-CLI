# util.py
import os
import aiofiles
from telethon import utils

def human_size(n):
    # простая функция для отображения размера в удобном виде
    for unit in ['B','KB','MB','GB','TB']:
        if n < 1024.0:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"

async def save_media_to_file(message, out_path):
    # out_path может быть папкой или файлом. Используем Telethon .download_media
    # возвращает путь
    # если out_path — папка, файл сохраняется с оригинальным именем (если есть)
    if os.path.isdir(out_path):
        dst = await message.download_media(file=out_path)
    else:
        # если путь заканчивается на / — трактуем как каталог
        if out_path.endswith(os.sep):
            os.makedirs(out_path, exist_ok=True)
            dst = await message.download_media(file=out_path)
        else:
            dirn = os.path.dirname(out_path)
            if dirn:
                os.makedirs(dirn, exist_ok=True)
            dst = await message.download_media(file=out_path)
    return dst
