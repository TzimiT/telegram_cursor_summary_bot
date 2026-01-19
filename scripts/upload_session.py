#!/usr/bin/env python3
"""
Вспомогательный скрипт для загрузки файла сессии Telethon в облако.
Используется для конвертации .session файла в base64 для загрузки через переменные окружения.
"""
import base64
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.paths import DATA_DIR

SESSION_FILE = DATA_DIR / "anon_news.session"


def encode_session_to_base64():
    """Конвертирует файл сессии в base64 строку для загрузки в облако"""
    if not SESSION_FILE.exists():
        print(f"❌ Файл {SESSION_FILE} не найден!")
        print("💡 Запустите один раз scripts/run_daily.py локально, чтобы создать файл сессии")
        sys.exit(1)

    with open(SESSION_FILE, 'rb') as f:
        session_data = f.read()

    encoded = base64.b64encode(session_data).decode('utf-8')

    print("=" * 80)
    print("✅ Файл сессии закодирован в base64")
    print("=" * 80)
    print("\nСкопируйте следующую строку и добавьте как переменную окружения:")
    print(f"TELEGRAM_SESSION_B64={encoded}")
    print("\nИли сохраните в файл:")
    print(f"echo '{encoded}' > session_base64.txt")
    print("=" * 80)


def decode_session_from_base64(encoded_str=None, output_file=SESSION_FILE):
    """Декодирует base64 строку обратно в файл сессии"""
    if encoded_str is None:
        # Попробуем прочитать из переменной окружения
        encoded_str = os.getenv('TELEGRAM_SESSION_B64')
        if not encoded_str:
            print("❌ Переменная окружения TELEGRAM_SESSION_B64 не найдена")
            print("💡 Использование: python scripts/upload_session.py decode <base64_string>")
            sys.exit(1)

    try:
        session_data = base64.b64decode(encoded_str)
        with open(output_file, 'wb') as f:
            f.write(session_data)
        print(f"✅ Файл сессии восстановлен: {output_file}")
    except Exception as e:
        print(f"❌ Ошибка декодирования: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "decode":
        if len(sys.argv) > 2:
            decode_session_from_base64(sys.argv[2])
        else:
            decode_session_from_base64()
    else:
        encode_session_to_base64()
