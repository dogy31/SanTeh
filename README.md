# Santech

Проект Django + Telegram/MAX уведомления + Web Push.

## Быстрый старт

1. Скопируйте `.env.example` в `.env` и заполните переменные.
2. Создайте виртуальное окружение и активируйте его:
   - Windows: `python -m venv venv` / `venv\Scripts\activate`
   - Linux/macOS: `python3 -m venv venv` / `source venv/bin/activate`
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
4. Выполните миграции:
   ```bash
   python manage.py migrate
   ```
5. Создайте суперпользователя:
   ```bash
   python manage.py createsuperuser
   ```
6. Запустите API-сервер уведомлений:
   ```bash
   python Messenger_bot/api_server.py
   ```
7. Запустите Telegram/MAX бота в отдельном терминале:
   ```bash
   python Messenger_bot/bot.py
   ```
8. Запустите Django:
   ```bash
   python manage.py runserver
   ```

## Важно для деплоя

- Файл `.env` не должен попадать в Git.
- Убедитесь, что `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DB_*`, `BOT_TOKEN`, `MAX_TOKEN`, `SMS_API_KEY`, `API_SERVER_URL`, `VAPID_EMAIL`, `VAPID_PUBLIC_KEY` и `VAPID_PRIVATE_KEY` настроены.
- В `settings.py` для production используется PostgreSQL.
- `gunicorn_config.py` уже настроен для запуска через Gunicorn.
- Сервис-воркер доступен по `/service-worker.js`.

## Нужные файлы и папки, которые не должны попасть в Git

- `venv/`
- `db.sqlite3`
- `bot.db`
- `media/`
- `logs/`
- `.env`
