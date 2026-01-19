"""
Разовый скрипт для обновления данных подписчиков в subscribers.json.
Заполняет недостающие поля (username, first_name, last_name, added_at) для всех пользователей.
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from telegram import Bot
from telegram.error import TelegramError, Forbidden, BadRequest
from telethon import TelegramClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
from src.paths import DATA_DIR, resolve_data_path

DEFAULT_SUBSCRIBERS_FILE = DATA_DIR / "subscribers.json"
SUBSCRIBERS_FILE = resolve_data_path(getattr(config, "SUBSCRIBERS_FILE", DEFAULT_SUBSCRIBERS_FILE))


def _load_subscribers():
    """Загружает список подписчиков из файла."""
    if not SUBSCRIBERS_FILE.exists():
        print(f"[ERROR] Файл {SUBSCRIBERS_FILE} не найден")
        return []
    try:
        with open(SUBSCRIBERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('subscribers', [])
    except Exception as e:
        print(f"[ERROR] Ошибка чтения {SUBSCRIBERS_FILE}: {e}")
        return []


def _save_subscribers(subscribers):
    """Сохраняет список подписчиков в файл."""
    try:
        # Создаем бэкап
        if SUBSCRIBERS_FILE.exists():
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            backup_file = SUBSCRIBERS_FILE.with_suffix(SUBSCRIBERS_FILE.suffix + f".{timestamp}.bak")
            with open(SUBSCRIBERS_FILE, 'rb') as src, open(backup_file, 'wb') as dst:
                dst.write(src.read())
            print(f"[LOG] Создан бэкап: {backup_file}")

        with open(SUBSCRIBERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"subscribers": subscribers}, f, ensure_ascii=False, indent=2)
        print(f"[LOG] Данные сохранены в {SUBSCRIBERS_FILE}")
    except Exception as e:
        print(f"[ERROR] Ошибка записи {SUBSCRIBERS_FILE}: {e}")


async def get_user_info_via_bot(bot: Bot, user_id: int):
    """
    Пытается получить информацию о пользователе через Bot API.
    Возвращает словарь с данными или None если не удалось.
    """
    try:
        chat = await bot.get_chat(chat_id=user_id)
        return {
            "user_id": user_id,
            "username": chat.username or "-",
            "first_name": chat.first_name or "-",
            "last_name": chat.last_name or "-",
        }
    except Forbidden:
        print(f"[WARN] Пользователь {user_id} заблокировал бота - используем только ID")
        return None
    except BadRequest as e:
        error_msg = str(e).lower()
        if "chat not found" in error_msg:
            print(f"[WARN] Чат с пользователем {user_id} не найден через Bot API")
        else:
            print(f"[WARN] Ошибка Bot API для {user_id}: {e}")
        return None
    except TelegramError as e:
        print(f"[WARN] Ошибка Telegram API для {user_id}: {e}")
        return None
    except Exception as e:
        print(f"[WARN] Неожиданная ошибка для {user_id}: {e}")
        return None


async def get_user_info_via_telethon(client: TelegramClient, user_id: int):
    """
    Пытается получить информацию о пользователе через Telethon.
    Возвращает словарь с данными или None если не удалось.
    """
    try:
        entity = await client.get_entity(user_id)
        return {
            "user_id": user_id,
            "username": getattr(entity, 'username', None) or "-",
            "first_name": getattr(entity, 'first_name', None) or "-",
            "last_name": getattr(entity, 'last_name', None) or "-",
        }
    except Exception as e:
        print(f"[WARN] Не удалось получить данные через Telethon для {user_id}: {e}")
        return None


async def update_subscribers_data():
    """Основная функция обновления данных подписчиков."""
    subscribers = _load_subscribers()
    if not subscribers:
        print("[ERROR] Список подписчиков пуст")
        return

    print(f"[LOG] Найдено подписчиков: {len(subscribers)}")

    bot = Bot(token=config.telegram_bot_token)
    updated_count = 0
    skipped_count = 0

    # Создаем Telethon клиент один раз для всех запросов
    telethon_available = False
    session_path = DATA_DIR / "anon_news.session"
    try:
        client = TelegramClient(str(session_path), config.api_id, config.api_hash)
        await client.start()
        telethon_available = True
        print("[LOG] Telethon клиент подключен")
    except Exception as e:
        print(f"[WARN] Не удалось подключиться к Telethon: {e}")
        print("[LOG] Будем использовать только Bot API")

    try:
        # Обновляем данные для каждого подписчика
        for idx, sub in enumerate(subscribers, 1):
            user_id = sub.get('user_id')
            if not user_id:
                print(f"[WARN] Пропущен подписчик #{idx}: отсутствует user_id")
                skipped_count += 1
                continue

            print(f"[LOG] [{idx}/{len(subscribers)}] Обработка user_id={user_id}...")

            # Проверяем, нужно ли обновлять данные
            has_all_fields = all(key in sub and sub[key] for key in ['username', 'first_name', 'last_name'])
            if has_all_fields and sub.get('username') != '-' and sub.get('first_name') != '-':
                print(f"  ✓ Данные уже полные, пропускаем")
                continue

            # Пытаемся получить данные через Bot API
            user_info = await get_user_info_via_bot(bot, user_id)

            # Если не получилось через Bot API, пробуем через Telethon
            if not user_info and telethon_available:
                try:
                    user_info = await get_user_info_via_telethon(client, user_id)
                except Exception as e:
                    print(f"  [WARN] Ошибка Telethon для {user_id}: {e}")

            # Обновляем данные
            if user_info:
                # Сохраняем существующие данные, если они есть и лучше новых
                if 'username' not in sub or sub.get('username') == '-' or not sub.get('username'):
                    sub['username'] = user_info.get('username', '-')
                if 'first_name' not in sub or sub.get('first_name') == '-' or not sub.get('first_name'):
                    sub['first_name'] = user_info.get('first_name', '-')
                if 'last_name' not in sub or sub.get('last_name') == '-' or not sub.get('last_name'):
                    sub['last_name'] = user_info.get('last_name', '-')

                # Добавляем дату, если её нет
                if 'added_at' not in sub or not sub.get('added_at'):
                    sub['added_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                updated_count += 1
                print(f"  ✓ Обновлено: @{sub['username']} ({sub['first_name']} {sub['last_name']})")
            else:
                # Если не удалось получить данные, заполняем минимально
                if 'username' not in sub:
                    sub['username'] = "-"
                if 'first_name' not in sub:
                    sub['first_name'] = "-"
                if 'last_name' not in sub:
                    sub['last_name'] = "-"
                if 'added_at' not in sub or not sub.get('added_at'):
                    sub['added_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                print(f"  ⚠ Не удалось получить данные, заполнены значения по умолчанию")
                updated_count += 1

            # Небольшая пауза между запросами
            await asyncio.sleep(0.2)
    finally:
        # Закрываем Telethon клиент
        if telethon_available:
            await client.disconnect()
            print("[LOG] Telethon клиент отключен")

    # Сохраняем обновленные данные
    _save_subscribers(subscribers)

    print(f"\n[LOG] Обновление завершено:")
    print(f"  - Обновлено записей: {updated_count}")
    print(f"  - Пропущено: {skipped_count}")
    print(f"  - Всего подписчиков: {len(subscribers)}")


if __name__ == "__main__":
    print("=" * 60)
    print("Скрипт обновления данных подписчиков")
    print("=" * 60)
    print()
    asyncio.run(update_subscribers_data())
