import asyncio
import json
import os
from datetime import datetime

from telegram import Bot

# Локальные настройки/секреты
import config  # должен содержать telegram_bot_token


SUBSCRIBERS_FILE = "subscribers.json"


def _load_subscribers():
    """
    Загружает список подписчиков в формате {"subscribers": [ {...} ]}.
    Возвращает список словарей подписчиков.
    """
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    try:
        with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("subscribers", []) or []
    except Exception as e:
        print(f"[ERROR] Ошибка чтения {SUBSCRIBERS_FILE}: {e}")
        return []


def _save_subscribers(subscribers_list):
    """Сохраняет список подписчиков в SUBSCRIBERS_FILE в ожидаемом формате."""
    try:
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump({"subscribers": subscribers_list}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] Ошибка записи {SUBSCRIBERS_FILE}: {e}")


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def backfill_from_updates():
    """
    Одноразовый сбор пользователей, которые писали боту личные текстовые сообщения,
    из очереди Bot API (getUpdates), с добавлением их в subscribers.json.

    Важно: Перед запуском нужно остановить основной процесс бота (polling/webhook),
    чтобы не конфликтовать за очередь апдейтов.
    """
    bot = Bot(token=config.telegram_bot_token)

    # Загружаем существующих подписчиков для дедупликации
    existing = _load_subscribers()
    existing_ids = {int(item.get("user_id")) for item in existing if "user_id" in item}

    # Сюда будем добавлять новые записи
    new_records = []

    offset = None
    total_updates = 0
    total_candidates = 0

    print("[LOG] Начинаю одноразовый сбор отправителей приватных текстовых сообщений...")
    while True:
        try:
            updates = await bot.get_updates(
                offset=offset,
                limit=100,
                timeout=10,
                allowed_updates=["message"],
            )
        except Exception as e:
            print(f"[ERROR] Ошибка получения обновлений: {e}")
            break

        if not updates:
            break

        for u in updates:
            total_updates += 1
            offset = u.update_id + 1

            msg = getattr(u, "message", None)
            if not msg:
                continue
            if not getattr(msg, "text", None):
                # Учитываем только текстовые сообщения
                continue
            chat = getattr(msg, "chat", None)
            if not chat or getattr(chat, "type", None) != "private":
                # Только личные диалоги
                continue

            user = getattr(msg, "from_user", None)
            if not user:
                continue

            total_candidates += 1
            try:
                uid = int(user.id)
            except Exception:
                continue

            if uid in existing_ids:
                continue

            record = {
                "user_id": uid,
                "username": user.username or "-",
                "first_name": user.first_name or "-",
                "last_name": user.last_name or "-",
                "added_at": _now_str(),
            }
            new_records.append(record)
            existing_ids.add(uid)

    if new_records:
        # Сортируем итоговый список по user_id для консистентности
        merged = existing + new_records
        merged_sorted = sorted(merged, key=lambda x: int(x.get("user_id", 0)))
        _save_subscribers(merged_sorted)

    print(
        f"[LOG] Обработано апдейтов: {total_updates}. Кандидатов найдено: {total_candidates}. "
        f"Новых добавлено: {len(new_records)}. Итоговый размер списка: {len(existing_ids)}."
    )


if __name__ == "__main__":
    # Напоминание в консоль
    print(
        "[INFO] Перед запуском убедитесь, что основной бот остановлен (polling/webhook),\n"
        "       чтобы избежать конкуренции за getUpdates.\n"
        "       Запуск: python backfill_users_once.py\n"
    )
    asyncio.run(backfill_from_updates())
