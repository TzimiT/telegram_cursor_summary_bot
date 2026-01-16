import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient
from telegram import Bot

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
from src.get_channels import get_channels_fullinfo_from_folder, load_channels_from_json
from src.news_bot_part import get_news, summarize_news, send_news


DEFAULT_SUBSCRIBERS_FILE = ROOT_DIR / "subscribers.json"
SUBSCRIBERS_FILE = Path(getattr(config, 'SUBSCRIBERS_FILE', DEFAULT_SUBSCRIBERS_FILE))
if not SUBSCRIBERS_FILE.is_absolute():
    SUBSCRIBERS_FILE = ROOT_DIR / SUBSCRIBERS_FILE

SUMMARIES_LOG_FILE = ROOT_DIR / "sent_summaries.log"


def _backup_file(path: Path):
    if path.exists():
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        bak = path.with_suffix(path.suffix + f".{ts}.bak")
        try:
            with open(path, 'rb') as src, open(bak, 'wb') as dst:
                dst.write(src.read())
            print(f"[LOG] Создан бэкап {bak}")
        except Exception as e:
            print(f"[WARN] Не удалось создать бэкап {path}: {e}")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Ошибка чтения {path}: {e}")
        return default


def _save_json(path: Path, data):
    _backup_file(path)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_summary_to_log(summary: str):
    """
    Сохраняет текст саммари в файл с датой и временем отправки.
    Вызывается после саммаризации и перед рассылкой пользователям.
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"\n{'='*80}\nДата отправки: {timestamp}\n{'='*80}\n{summary}\n"
        with open(SUMMARIES_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        print(f"[LOG] Саммари сохранена в {SUMMARIES_LOG_FILE}")
    except Exception as e:
        print(f"[WARN] Не удалось сохранить саммари в файл: {e}")


async def verify_subscribers_delivery(bot: Bot):
    """
    Лёгкая проверка доступности: отправляет chat action (typing) каждому подписчику.
    Это менее навязчиво, чем тестовое сообщение. Недоступные вызов падает с исключением.
    Возвращает список доступных user_id (по результатам попыток).
    В режиме отладки проверяет только тестовых пользователей.
    """
    data = _load_json(SUBSCRIBERS_FILE, {"subscribers": []})
    subs = [s.get('user_id') for s in data.get('subscribers', []) if 'user_id' in s]

    # Фильтрация подписчиков в режиме отладки
    if getattr(config, 'DEBUG_MODE', False):
        debug_ids = getattr(config, 'DEBUG_USER_IDS', [])
        if isinstance(debug_ids, int):
            debug_ids = [debug_ids]
        subs = [uid for uid in subs if uid in debug_ids]
        print(f"[DEBUG] Режим отладки включен. Проверка доступности только для тестовых пользователей: {subs}")

    ok = []
    for uid in subs:
        try:
            # у python-telegram-bot v21 Bot.send_chat_action переименована в send_chat_action
            await bot.send_chat_action(chat_id=uid, action="typing")
            ok.append(uid)
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"[WARN] Недоступен для рассылки user_id={uid}: {e}")
            await asyncio.sleep(0.05)
    print(f"[LOG] Проверка доступности: {len(ok)}/{len(subs)} пользователей ок")
    return ok


async def run_pipeline(args):
    # 1) Создание клиентов
    bot = Bot(token=config.telegram_bot_token)

    # 2) Обновление каналов
    channels = None
    if args.channels or args.news or args.send:
        session_path = ROOT_DIR / "anon_news.session"
        if not session_path.exists():
            raise FileNotFoundError(
                f"Не найдена user-сессия Telethon: {session_path}. "
                "Положи файл anon_news.session в корень проекта"
            )

        async with TelegramClient(str(session_path), config.api_id, config.api_hash) as client:
            me = await client.get_me()
            if not me:
                raise RuntimeError("Telethon сессия не авторизована как пользователь.")
            if getattr(me, "bot", False):
                raise RuntimeError(
                    "Telethon сессия принадлежит боту. Нужна user session "
                    "(вход по телефону) в файле anon_news.session."
                )
            if args.channels:
                await get_channels_fullinfo_from_folder(client, config.FOLDER_NAME)
            channels = load_channels_from_json()
            if args.news or args.send:
                # Определяем период: неделя или день
                period = 'week' if args.weekly else 'day'
                period_name = "неделю" if args.weekly else "вчера"

                print(f"[LOG] Каналы для агрегации: {[ch.get('username','?') for ch in channels]}")
                news = await get_news(client, channels, period=period)
                print(f"[LOG] Найдено новостей за {period_name}: {len(news)}")
                if args.news and not args.send:
                    # Только сбор новостей
                    return
                if not news:
                    print(f"[LOG] Нет новостей за {period_name} — рассылка пропущена")
                    return
                summary = summarize_news(news, period=period)

                if args.summary_only:
                    out = args.summary_only if isinstance(args.summary_only, str) else 'summary.txt'
                    with open(out, 'w', encoding='utf-8') as f:
                        f.write(summary)
                    print(f"[LOG] Итоговая сводка сохранена в {out}")
                    return

                # Сохраняем саммари в лог перед рассылкой
                save_summary_to_log(summary)

                # 3) Предварительная проверка доступности (опционально)
                if args.verify:
                    await verify_subscribers_delivery(bot)

                if args.dry_run:
                    print("[DRY-RUN] Рассылка не выполнялась. Предпросмотр (начало):\n")
                    print(summary[:800])
                    return

                # 4) Рассылка (send_news уже фильтрует недоступных и обновляет файл)
                await send_news(summary)


def build_arg_parser():
    p = argparse.ArgumentParser(description="Единый запуск: каналы → проверка → новости → рассылка")
    p.add_argument('--channels', action='store_true', help='Обновить channels.json из телеграм-папки')
    p.add_argument('--verify', action='store_true', help='Проверить доступность подписчиков перед рассылкой')
    p.add_argument('--news', action='store_true', help='Только собрать новости (без отправки)')
    p.add_argument('--send', action='store_true', help='Собрать новости, суммаризировать и отправить')
    p.add_argument('--weekly', action='store_true', help='Собрать саммаризацию за неделю (по умолчанию за день)')
    p.add_argument('--dry-run', action='store_true', help='Не отправлять, только показать превью')
    p.add_argument('--summary-only', nargs='?', const=True, help='Сохранить сводку в файл (по умолчанию summary.txt) и завершить')
    return p


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    # По умолчанию выполняем полный цикл: channels + send
    if not any([args.channels, args.verify, args.news, args.send, args.dry_run, args.summary_only]):
        args.channels = True
        args.send = True

    asyncio.run(run_pipeline(args))


if __name__ == '__main__':
    main()
