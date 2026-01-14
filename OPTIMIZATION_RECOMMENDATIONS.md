# Рекомендации по оптимизации кода

## 🔴 Критические проблемы

### 1. Дублирование кода `_load_json` и `_save_json`
**Проблема:** Функции определены в `get_users.py` и `run_daily.py` с одинаковой логикой.

**Решение:** Создать общий модуль `utils.py`:
```python
# utils.py
import json
import os
import logging
from pathlib import Path

def load_json(path: str, default):
    """Универсальная функция загрузки JSON"""
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"[WARN] Ошибка чтения {path}: {e}")
        return default

def save_json(path: str, data, backup=True):
    """Универсальная функция сохранения JSON с опциональным бэкапом"""
    if backup and os.path.exists(path):
        from datetime import datetime
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        bak = f"{path}.{ts}.bak"
        try:
            Path(path).copy(bak)
        except Exception as e:
            logging.warning(f"[WARN] Не удалось создать бэкап: {e}")
    
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"[ERROR] Ошибка записи {path}: {e}")
```

### 2. Множественные чтения файла подписчиков
**Проблема:** `load_subscribers()` вызывается несколько раз, каждый раз читая файл с диска.

**Текущий код:**
```python
def save_subscriber(user):
    subscribers = load_subscribers()  # Чтение 1
    # ...
    
def remove_subscriber(user_id):
    subscribers = load_subscribers()  # Чтение 2
    # ...
```

**Решение:** Кэширование с инвалидацией:
```python
from functools import lru_cache
from typing import Dict, List

_subscribers_cache: Dict[str, List] = {}
_cache_timestamp: float = 0

def load_subscribers(force_reload=False):
    """Загрузка подписчиков с кэшированием"""
    global _subscribers_cache, _cache_timestamp
    cache_key = SUBSCRIBERS_FILE
    
    if not force_reload and cache_key in _subscribers_cache:
        # Проверяем, не изменился ли файл
        import os
        mtime = os.path.getmtime(SUBSCRIBERS_FILE)
        if mtime <= _cache_timestamp:
            return _subscribers_cache[cache_key]
    
    # Загружаем заново
    data = load_json(SUBSCRIBERS_FILE, {"subscribers": []})
    subscribers = data.get('subscribers', [])
    _subscribers_cache[cache_key] = subscribers
    _cache_timestamp = os.path.getmtime(SUBSCRIBERS_FILE) if os.path.exists(SUBSCRIBERS_FILE) else 0
    return subscribers

def invalidate_subscribers_cache():
    """Инвалидировать кэш подписчиков"""
    global _subscribers_cache, _cache_timestamp
    _subscribers_cache.pop(SUBSCRIBERS_FILE, None)
    _cache_timestamp = 0
```

### 3. Синхронный I/O в асинхронном коде
**Проблема:** В `get_users.py` используются синхронные операции с файлами в async-функциях.

**Решение:** Использовать `aiofiles`:
```python
import aiofiles
import aiofiles.os

async def load_subscribers_async():
    if not await aiofiles.os.path.exists(SUBSCRIBERS_FILE):
        return []
    async with aiofiles.open(SUBSCRIBERS_FILE, 'r', encoding='utf-8') as f:
        data = json.loads(await f.read())
        return data.get('subscribers', [])
```

## 🟡 Важные оптимизации

### 4. Неэффективный поиск в списках
**Проблема:** Использование `any()` для проверки подписки - O(n) сложность.

**Текущий код:**
```python
is_subscribed = any('user_id' in sub and sub['user_id'] == user.id for sub in subscribers)
```

**Решение:** Использовать множества:
```python
def load_subscribers():
    # ...
    subscribers = data.get('subscribers', [])
    # Создаем индекс для быстрого поиска
    subscribers_dict = {s['user_id']: s for s in subscribers if 'user_id' in s}
    return subscribers, subscribers_dict

# Использование:
subscribers, subs_dict = load_subscribers()
is_subscribed = user.id in subs_dict
```

### 5. Множественное создание Bot клиента
**Проблема:** В `news_bot_part.py` и `run_daily.py` создается новый `Bot` при каждом вызове.

**Решение:** Singleton или передача через параметры:
```python
# В run_daily.py
async def run_pipeline(args):
    bot = Bot(token=config.telegram_bot_token)  # Создать один раз
    # Передавать bot как параметр в функции
    await send_news(summary, bot=bot)
```

### 6. Последовательная отправка сообщений
**Проблема:** Сообщения отправляются по одному, что медленно.

**Текущий код:**
```python
for user_id in subscribers:
    await bot.send_message(chat_id=user_id, text=part_text)
    await asyncio.sleep(0.1)
```

**Решение:** Параллельная отправка с ограничением:
```python
import asyncio
from typing import List

async def send_news_parallel(summary, bot, subscribers, max_concurrent=10):
    """Отправка с ограничением параллелизма"""
    semaphore = asyncio.Semaphore(max_concurrent)
    message_chunks = split_message(summary)
    
    async def send_to_user(user_id):
        async with semaphore:
            try:
                for chunk in message_chunks:
                    await bot.send_message(chat_id=user_id, text=chunk)
                    await asyncio.sleep(0.05)
                return user_id, True
            except Exception as e:
                return user_id, False
    
    tasks = [send_to_user(uid) for uid in subscribers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### 7. Дублирование логики DEBUG_MODE
**Проблема:** Фильтрация по DEBUG_MODE повторяется в нескольких местах.

**Решение:** Вынести в отдельную функцию:
```python
def filter_subscribers_by_debug_mode(subscribers: List[int]) -> List[int]:
    """Фильтрует подписчиков в зависимости от режима отладки"""
    if not getattr(config, 'DEBUG_MODE', False):
        return subscribers
    
    debug_ids = getattr(config, 'DEBUG_USER_IDS', [])
    if isinstance(debug_ids, int):
        debug_ids = [debug_ids]
    
    filtered = [uid for uid in subscribers if uid in debug_ids]
    logging.info(f"[DEBUG] Режим отладки: {len(filtered)}/{len(subscribers)} пользователей")
    return filtered
```

## 🟢 Улучшения качества кода

### 8. Использование dataclasses вместо словарей
**Проблема:** Работа с подписчиками через словари не типобезопасна.

**Решение:**
```python
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Subscriber:
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    added_at: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username or '-',
            'first_name': self.first_name or '-',
            'last_name': self.last_name or '-',
            'added_at': self.added_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
```

### 9. Константы вместо магических чисел
**Проблема:** Хардкод значений в коде.

**Решение:**
```python
# constants.py
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
SEND_MESSAGE_DELAY = 0.1  # секунды между сообщениями
MAX_CONCURRENT_SENDS = 10
CACHE_TTL = 60  # секунды для кэша
```

### 10. Улучшенная обработка ошибок
**Проблема:** Повторяющийся код обработки ошибок.

**Решение:** Декоратор для обработки ошибок:
```python
from functools import wraps
from typing import Callable

def handle_telegram_errors(func: Callable):
    """Декоратор для обработки ошибок Telegram API"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Forbidden as e:
            error_msg = str(e).lower()
            if "blocked" in error_msg:
                # Обработка блокировки
                pass
            raise
        except BadRequest as e:
            # Обработка BadRequest
            pass
        except TelegramError as e:
            # Общая обработка
            pass
    return wrapper
```

### 11. Оптимизация `get_news()`
**Проблема:** Итерация по всем сообщениям канала может быть медленной.

**Решение:** Использовать поиск по дате, если API поддерживает:
```python
async def get_news(client, channels):
    all_news = []
    start, end = get_yesterday_range()
    
    for channel_info in channels:
        username = channel_info.get("username")
        if not username:
            continue
        
        # Попытка использовать поиск по дате (если доступно)
        try:
            # Используем iter_messages с фильтром по дате
            messages = client.iter_messages(
                username,
                offset_date=end,
                reverse=True
            )
            async for message in messages:
                if message.date < start:
                    break
                if message.text:
                    all_news.append(f"{message.text}\nИсточник: https://t.me/{username}/{message.id}\n")
        except Exception as e:
            logging.warning(f"Ошибка при получении сообщений из {username}: {e}")
    
    return all_news
```

### 12. Логирование в файл вместо print
**Проблема:** Смешение `print()` и `logging`.

**Решение:** Использовать только logging:
```python
import logging

# Настройка в начале приложения
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
# Вместо print() использовать logger.info(), logger.warning(), etc.
```

## 📊 Ожидаемые улучшения производительности

1. **Кэширование подписчиков:** Сокращение времени чтения файла на 90%+
2. **Параллельная отправка:** Ускорение рассылки в 5-10 раз (зависит от лимитов API)
3. **Использование множеств:** Поиск подписчика O(1) вместо O(n)
4. **Async I/O:** Неблокирующие операции с файлами
5. **Переиспользование Bot:** Меньше накладных расходов на создание объектов

## 🔧 Приоритет внедрения

1. **Высокий приоритет:**
   - Устранение дублирования кода (utils.py)
   - Кэширование подписчиков
   - Использование множеств для поиска

2. **Средний приоритет:**
   - Параллельная отправка сообщений
   - Переиспользование Bot клиента
   - Вынос DEBUG_MODE логики

3. **Низкий приоритет:**
   - Dataclasses
   - Async I/O (если нет проблем с производительностью)
   - Декораторы обработки ошибок
