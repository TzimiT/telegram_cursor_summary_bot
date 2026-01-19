import asyncio
import os
import sys
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

try:
    import qrcode
    _HAS_QR = True
except Exception:
    qrcode = None
    _HAS_QR = False

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
from src.paths import DATA_DIR


async def main():
    session_path = DATA_DIR / "anon_news.session"
    print(f"[INFO] Создаю user session: {session_path}")
    print("[INFO] Использую API_ID/API_HASH из config.py или env")
    print("[INFO] Введите номер телефона и код из Telegram")
    print("[INFO] Либо введите 'qr' для входа через QR-код")

    client = TelegramClient(str(session_path), config.api_id, config.api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        phone = os.getenv("TELEGRAM_PHONE")
        if not phone:
            phone = input("Телефон в формате +79991234567 (или 'qr'): ").strip()

        if phone.lower() == "qr":
            while True:
                qr_login = await client.qr_login()
                print("[INFO] Открой QR-код в приложении Telegram и подтверди вход:")
                if _HAS_QR:
                    qr = qrcode.QRCode(border=1)
                    qr.add_data(qr_login.url)
                    qr.make(fit=True)
                    qr.print_ascii(invert=True)
                else:
                    print("[WARN] Модуль qrcode не установлен.")
                    print("       Установи: pip install qrcode")
                    print("       Временная ссылка (может не открываться):")
                    print(qr_login.url)
                print("[INFO] После подтверждения вернись сюда — жду вход...")
                try:
                    await qr_login.wait()
                    break
                except TimeoutError:
                    print("[WARN] QR-код истёк. Сгенерирую новый...")
                    continue
                except SessionPasswordNeededError:
                    password = input("Введите пароль 2FA: ").strip()
                    await client.sign_in(password=password)
                    break
        else:
            sent = await client.send_code_request(phone)
            sent_type = type(sent.type).__name__
            delivery_map = {
                "SentCodeTypeApp": "приложение Telegram",
                "SentCodeTypeSms": "SMS",
                "SentCodeTypeCall": "звонок",
                "SentCodeTypeFlashCall": "flash-call",
            }
            print(f"[INFO] Код отправлен: {delivery_map.get(sent_type, sent_type)}")
            code = input("Код из Telegram: ").strip()
            try:
                await client.sign_in(phone=phone, code=code)
            except SessionPasswordNeededError:
                password = input("Введите пароль 2FA: ").strip()
                await client.sign_in(password=password)
    me = await client.get_me()

    if not me:
        raise RuntimeError("Не удалось авторизоваться. Проверь данные.")
    if getattr(me, "bot", False):
        await client.disconnect()
        backup_path = f"{session_path}.bot.bak"
        if session_path.exists():
            os.replace(session_path, backup_path)
            print(f"[WARN] Бот-сессия сохранена в {backup_path}")
        print("[INFO] Перезапускаю вход как пользователь...")
        client = TelegramClient(str(session_path), config.api_id, config.api_hash)
        await client.start()
        me = await client.get_me()
        if getattr(me, "bot", False):
            raise RuntimeError("Сессия снова принадлежит боту. Нужен пользовательский вход.")

    print(f"[OK] User session создана: {getattr(me, 'username', '-')}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
