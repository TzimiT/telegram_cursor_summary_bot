import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import openai
from telethon import TelegramClient
from telegram import Bot
from telegram.error import TelegramError, Forbidden, BadRequest

import config
from config import api_id, api_hash, telegram_bot_token, openai_api_key, FOLDER_NAME, DEBUG_MODE, DEBUG_USER_IDS
from src.get_channels import get_channels_fullinfo_from_folder, load_channels_from_json
from src.paths import DATA_DIR, resolve_data_path


DEFAULT_SUBSCRIBERS_FILE = DATA_DIR / "subscribers.json"
SUBSCRIBERS_FILE = resolve_data_path(getattr(config, "SUBSCRIBERS_FILE", DEFAULT_SUBSCRIBERS_FILE))
SENT_MESSAGES_LOG = DATA_DIR / "sent_messages.log"
SUMMARIES_LOG_FILE = DATA_DIR / "sent_summaries.log"
TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def load_subscribers():
    if not SUBSCRIBERS_FILE.exists():
        print("[WARN] Файл с подписчиками не найден, список пуст")
        return []
    try:
        with open(SUBSCRIBERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return [item['user_id'] for item in data.get('subscribers', []) if 'user_id' in item]
    except Exception as e:
        print(f"[ERROR] Ошибка чтения {SUBSCRIBERS_FILE}: {e}")
        return []


def get_day_range(target_date=None):
    if target_date is None:
        today = datetime.now(timezone.utc).date()
        target_date = today - timedelta(days=1)
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start, end


def get_week_range(target_date=None):
    """Возвращает диапазон дат за последние 7 дней (до target_date включительно)"""
    today = datetime.now(timezone.utc).date()
    end_date = target_date or today
    start = datetime.combine(end_date - timedelta(days=7), datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)
    return start, end


def _build_prompt(period, target_date, prompt_type):
    # Определяем диапазон дат в зависимости от периода
    if period == 'week':
        start, end = get_week_range(target_date=target_date)
        date_str = f"{start.strftime('%Y-%m-%d')} - {end.strftime('%Y-%m-%d')}"
        period_text = "неделю"
    else:
        start, end = get_day_range(target_date=target_date)
        date_str = start.strftime("%Y-%m-%d")
        period_text = "день"

    if prompt_type == "sport":
        return f"""
Ты — спортивный редактор новостной рассылки. Составь лаконичную, структурированную сводку спортивных новостей за {period_text} ({date_str}, UTC) из предоставленных фрагментов.

## ОСНОВНЫЕ ТРЕБОВАНИЯ

1. ЯЗЫК И СТИЛЬ:
   - Русский язык, нейтральный деловой стиль
   - Без эмоций, оценочных суждений и фанатских комментариев
   - Короткие предложения, активный залог
   - Термины и сокращения расшифровывай при первом упоминании (если не общеизвестны)

2. СТРУКТУРА СВОДКИ (выводи только разделы, без преамбул и заключений):

   **Главное**
   - 3–6 наиболее важных новостей дня
   - Приоритет: результаты ключевых матчей, важные травмы, официальные заявления, значимые санкции
   - Формат: 1–3 факта на пункт, без воды

   **Матчи и результаты** (только если есть релевантные новости)
   - Итоги матчей, турниров, этапов
   - Указывай счёт/результат и турнир/лигe

   **Трансферы и контракты** (только если есть релевантные новости)
   - Официальные переходы, продления, аренды, отступные
   - Не включай слухи без подтверждения

   **Остальное кратко**
   - Прочие спортивные новости (статистика, расписания, регламент, дисциплинарные решения)
   - Формат: буллеты по 1–2 строки

3. ОБРАБОТКА ИСТОЧНИКОВ:
   - После каждого пункта укажи 1–3 телеграм-ссылки в формате: (https://t.me/username/123)
   - Ссылки разделяй пробелом, сохраняй исходные t.me ссылки без изменений
   - Если несколько источников про одно событие — объединяй в один пункт, укажи 2–3 ссылки
   - Приоритет: ссылки на первоисточники, официальные каналы

4. ОБЪЕДИНЕНИЕ ДУБЛИКАТОВ:
   - Если несколько фрагментов про одно событие — создай один пункт
   - Выбери наиболее полную информацию из всех источников
   - Укажи ссылки на все релевантные источники (до 3)
   - Избегай повторений одной и той же новости в разных разделах

5. ФИЛЬТРАЦИЯ КОНТЕНТА:
   - ИГНОРИРУЙ: рекламу, опросы, призывы подписаться, эмодзи, декоративное оформление
   - ИГНОРИРУЙ: инсайды и слухи без подтверждения, мнения без фактов
   - ВКЛЮЧАЙ: официальные заявления, результаты, статистику, санкции, подтверждённые трансферы

6. ОБЪЁМ И ФОРМАТ:
   - Без вводных фраз типа "За сегодня произошло...", без заключений
   - Только разделы и пункты в указанном формате
   - Если раздел пуст — не выводи его

7. ПРИОРИТИЗАЦИЯ:
   - Сначала анализируй все новости и определяй наиболее важные
   - В "Главное" попадают события с наибольшим влиянием
   - Внутри раздела сортируй по важности (самое важное — первым)

## ФОРМАТ ВЫВОДА

Главное
• [Текст новости] (https://t.me/channel1/123)
• [Текст новости] (https://t.me/channel2/456 https://t.me/channel3/789)

Матчи и результаты
• [Команда A — команда B 2:1, Лига/турнир] (https://t.me/channel4/101)

Трансферы и контракты
• [Игрок X перешёл в клуб Y, контракт до 2028] (https://t.me/channel5/202)

Остальное кратко
• [Краткая новость] (https://t.me/channel6/303)
"""

    return f"""
Ты — профессиональный редактор новостной рассылки. Составь лаконичную, структурированную сводку новостей за {period_text} ({date_str}, UTC) из предоставленных фрагментов.

## ОСНОВНЫЕ ТРЕБОВАНИЯ

1. ЯЗЫК И СТИЛЬ:
   - Русский язык, нейтральный деловой стиль
   - Избегай эмоциональных оценок, субъективных комментариев
   - Используй активный залог, короткие предложения
   - Технические термины и аббревиатуры расшифровывай при первом упоминании (если не общеизвестны)

2. СТРУКТУРА СВОДКИ (выводи только разделы, без преамбул и заключений):

   **Главное**
   - 3–6 наиболее важных новостей дня
   - Приоритет: события с широким влиянием, прорывы, значимые объявления
   - Формат: 1–3 ключевых факта на пункт, без воды
   - Пример: "Компания X запустила сервис Y в 10 странах. Доступен с 1 марта, стоимость от $Z. (https://t.me/channel/123)"

   **AI/ML** (только если есть релевантные новости)
   - 2–6 новостей об искусственном интеллекте, машинном обучении, нейросетях
   - Можно чуть подробнее, но без излишней детализации
   - Включай: новые модели, исследования, продукты, инструменты, регуляцию

   **Остальное кратко**
   - Прочие новости, не вошедшие в "Главное" и "AI/ML"
   - Формат: буллеты по 1–2 строки
   - Приоритет: технологические, научные, бизнес-новости

3. ОБРАБОТКА ИСТОЧНИКОВ:
   - После каждого пункта укажи 1–3 телеграм-ссылки в формате: (https://t.me/username/123)
   - Ссылки разделяй пробелом, сохраняй исходные t.me ссылки без изменений
   - Если несколько источников про одно событие — объединяй в один пункт, укажи 2–3 ссылки
   - Приоритет: ссылки на первоисточники, официальные каналы

4. ОБЪЕДИНЕНИЕ ДУБЛИКАТОВ:
   - Если несколько фрагментов про одно событие — создай один пункт
   - Выбери наиболее полную информацию из всех источников
   - Укажи ссылки на все релевантные источники (до 3)
   - Избегай повторений одной и той же новости в разных разделах

5. ФИЛЬТРАЦИЯ КОНТЕНТА:
   - ИГНОРИРУЙ: рекламу, опросы, призывы подписаться, эмодзи, декоративное оформление
   - ИГНОРИРУЙ: личные мнения без фактов, сплетни, неподтверждённые слухи
   - ВКЛЮЧАЙ: фактические новости, анонсы продуктов, исследования, статистику, официальные заявления

6. ОБЪЁМ И ФОРМАТ:
   - Без вводных фраз типа "За сегодня произошло...", без заключений
   - Только разделы и пункты в указанном формате
   - Если раздел "AI/ML" пуст — не выводи его

7. ПРИОРИТИЗАЦИЯ:
   - Сначала анализируй все новости и определяй наиболее важные
   - В "Главное" попадают события с наибольшим влиянием
   - Внутри раздела сортируй по важности (самое важное — первым)

## ФОРМАТ ВЫВОДА

Главное
• [Текст новости] (https://t.me/channel1/123)
• [Текст новости] (https://t.me/channel2/456 https://t.me/channel3/789)

AI/ML
• [Текст новости] (https://t.me/channel4/101)

Остальное кратко
• [Краткая новость] (https://t.me/channel5/202)
• [Краткая новость] (https://t.me/channel6/303)
"""


def summarize_news(news_list, period='day', target_date=None, prompt_type="general"):
    """
    Суммаризирует новости за указанный период.

    Args:
        news_list: список новостей для суммаризации
        period: 'day' для дня или 'week' для недели
    """
    text = "\n\n".join(news_list)

    prompt_system = _build_prompt(period=period, target_date=target_date, prompt_type=prompt_type)

    client_ai = openai.OpenAI(api_key=openai_api_key)
    response = client_ai.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": prompt_system},
            {"role": "user", "content": text}
        ],
        max_tokens=1600,
        temperature=0.35
    )
    return response.choices[0].message.content.strip()


async def get_news(client, channels, period='day', target_date=None):
    """
    Собирает новости из каналов за указанный период.

    Args:
        client: Telethon клиент
        channels: список каналов
        period: 'day' для дня или 'week' для недели
    """
    all_news = []
    if period == 'week':
        start, end = get_week_range(target_date=target_date)
        period_name = "неделю"
    else:
        start, end = get_day_range(target_date=target_date)
        period_name = "день"

    print(f"[DEBUG] Диапазон фильтра за {period_name}: {start} ... {end}")
    for channel_info in channels:
        username = channel_info.get("username")
        if not username:
            continue
        async for message in client.iter_messages(username):
            msg_date = message.date
            if msg_date.tzinfo is None:
                msg_date = msg_date.replace(tzinfo=timezone.utc)
            msg_date_norm = msg_date.replace(microsecond=0)
            if msg_date_norm < start:
                break
            if start <= msg_date_norm < end and message.text:
                all_news.append(f"{message.text}\nИсточник: https://t.me/{username}/{message.id}\n")
                print(f"[DEBUG] {username} | id={message.id} | дата={msg_date_norm} - добавлено")
    return all_news


def split_message(text, max_length=TELEGRAM_MAX_MESSAGE_LENGTH):
    """
    Разбивает текст на части не длиннее max_length символов.
    Разделяет по абзацам, чтобы не резать посреди предложения.
    Если абзац длиннее лимита — делит тупо на куски.
    """
    paragraphs = text.split('\n\n')
    messages = []
    current_message = ""
    for para in paragraphs:
        if len(current_message) + len(para) + 2 <= max_length:
            if current_message:
                current_message += "\n\n" + para
            else:
                current_message = para
        else:
            if current_message:
                messages.append(current_message)
            if len(para) <= max_length:
                current_message = para
            else:
                # если параграф длиннее лимита, делим его тупо на куски
                for i in range(0, len(para), max_length):
                    messages.append(para[i:i+max_length])
                current_message = ""
    if current_message:
        messages.append(current_message)
    return messages


async def send_news(summary):
    # Сохраняем саммари в лог перед рассылкой
    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"\n{'='*80}\nДата отправки: {timestamp}\n{'='*80}\n{summary}\n"
        with open(SUMMARIES_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        print(f"[LOG] Саммари сохранена в {SUMMARIES_LOG_FILE}")
    except Exception as e:
        print(f"[WARN] Не удалось сохранить саммари в файл: {e}")

    subscribers = load_subscribers()
    if not subscribers:
        print("[WARN] Нет подписчиков для рассылки.")
        return

    # Фильтрация подписчиков в режиме отладки
    if DEBUG_MODE:
        # Убеждаемся, что DEBUG_USER_IDS - это список
        debug_ids = DEBUG_USER_IDS if isinstance(DEBUG_USER_IDS, list) else [DEBUG_USER_IDS]
        subscribers = [uid for uid in subscribers if uid in debug_ids]
        print(f"[DEBUG] Режим отладки включен. Рассылка только для тестовых пользователей: {subscribers}")
        if not subscribers:
            print("[WARN] Нет тестовых подписчиков для рассылки в режиме отладки.")
            return
    else:
        print(f"[LOG] Режим отладки выключен. Рассылка для всех подписчиков: {len(subscribers)} пользователей")

    bot = Bot(token=telegram_bot_token)
    blocked_subscribers = []  # Пользователи, которые заблокировали бота

    # Разбиваем summary на части не длиннее 4096 символов
    message_chunks = split_message(summary)

    # Вспомогательная функция для логирования каждого отправленного сообщения
    def log_sent_message(user_id, message_id, text):
        try:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            line = f"{ts}\tuser_id={user_id}\tmessage_id={message_id}\tlen={len(text)}\t{text}\n"
            with open(SENT_MESSAGES_LOG, 'a', encoding='utf-8') as lf:
                lf.write(line)
        except Exception as e:
            # Не прерываем рассылку из-за ошибок логирования
            print(f"[ERROR] Не удалось записать лог отправленного сообщения: {e}")

    for user_id in subscribers:
        try:
            for idx, chunk in enumerate(message_chunks):
                # Можно добавить нумерацию частей если сообщений больше одного
                if len(message_chunks) > 1:
                    part_text = f"Часть {idx+1}/{len(message_chunks)}\n\n{chunk}"
                else:
                    part_text = chunk
                result = await bot.send_message(chat_id=user_id, text=part_text)
                print(f"[LOG] Сообщение успешно отправлено пользователю {user_id}, message_id={result.message_id}")
                # Логируем полный отправленный текст с датой и временем
                log_sent_message(user_id=user_id, message_id=result.message_id, text=part_text)
                # Рекомендуется сделать небольшую паузу между отправками частей
                await asyncio.sleep(0.1)
        except Forbidden as e:
            # Пользователь заблокировал бота - удаляем из списка
            error_msg = str(e).lower()
            if "blocked" in error_msg or "bot was blocked" in error_msg:
                print(f"[WARN] Пользователь {user_id} заблокировал бота - будет удален из списка")
                blocked_subscribers.append(user_id)
            else:
                print(f"[ERROR] Не удалось отправить сообщение пользователю {user_id}: {e}")
        except BadRequest as e:
            # Chat not found - может быть временная проблема, оставляем в списке
            error_msg = str(e).lower()
            if "chat not found" in error_msg:
                print(f"[WARN] Чат с пользователем {user_id} не найден (возможно, временная проблема) - оставляем в списке")
            else:
                print(f"[ERROR] Не удалось отправить сообщение пользователю {user_id}: {e}")
        except TelegramError as e:
            # Другие ошибки Telegram API
            print(f"[ERROR] Ошибка Telegram API для пользователя {user_id}: {e}")
        except Exception as e:
            # Неожиданные ошибки
            print(f"[ERROR] Не удалось отправить сообщение пользователю {user_id}: {e}")

    # Удаляем из файла только тех, кто заблокировал бота
    # Остальных (включая тех, кому успешно отправили) оставляем
    try:
        with open(SUBSCRIBERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Удаляем только заблокированных пользователей
        new_subs = [sub for sub in data.get('subscribers', [])
                   if 'user_id' in sub and sub['user_id'] not in blocked_subscribers]
        with open(SUBSCRIBERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"subscribers": new_subs}, f, ensure_ascii=False, indent=2)
        if blocked_subscribers:
            print(f"[LOG] Удалено из списка подписчиков: {len(blocked_subscribers)} пользователей (заблокировали бота)")
    except Exception as e:
        print(f"[ERROR] Ошибка обновления активных подписчиков: {e}")


async def main():
    session_path = DATA_DIR / "anon_news.session"
    async with TelegramClient(str(session_path), api_id, api_hash) as client:
        # Шаг 1: Получить и сохранить полную инфу о каналах из папки
        await get_channels_fullinfo_from_folder(client, FOLDER_NAME)
        # Шаг 2: Загрузить полную инфу о каналах для рассылки
        channels = load_channels_from_json()
        print(f"[LOG] Каналы для агрегации: {[ch.get('username','?') for ch in channels]}")

        # Шаг 3: Собрать новости
        news = await get_news(client, channels)
        print(f"[LOG] Количество найденных новостей за вчера: {len(news)}")
        if not news:
            print("[LOG] Нет новостей за вчера. Прерываю рассылку.")
            return

        # Шаг 4: Суммаризация и рассылка
        summary = summarize_news(news)
        await send_news(summary)


if __name__ == "__main__":
    asyncio.run(main())
