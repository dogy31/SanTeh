# 📲 Система Уведомлений SanTech

Полная инструкция по настройке и запуску многоканальной системы уведомлений.

## 📋 Каналы Уведомлений

Система поддерживает 3 канала одновременно:
1. **Telegram** - для рабочих и администраторов
2. **MAX** - российский аналог WhatsApp
3. **Веб-уведомления** - прямо в браузер (Chrome, Safari и т.д.)

## 🔧 Предварительная Настройка

### 1. Переменные Окружения (.env)

Создайте файл `.env` в корне проекта:

```env
# Токены для ботов
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_HERE
MAX_TOKEN=YOUR_MAX_BOT_TOKEN_HERE
SMS_API_KEY=YOUR_SMS_API_KEY_HERE

# URL API сервера уведомлений (по умолчанию localhost)
API_SERVER_URL=http://127.0.0.1:5000

# Для продакшена на сервере Time web cloud:
# API_SERVER_URL=http://localhost:5000  # или IP сервера:5000
```

### 2. Установка Зависимостей

```bash
pip install -r requirements.txt
```

## 🚀 Запуск Системы Уведомлений

### Вариант 1: Локальная Разработка (с одного ПК)

#### Terminal 1: Django сервер
```bash
cd d:\Projeckt\santech
python manage.py runserver 0.0.0.0:8000
```

#### Terminal 2: API сервер уведомлений
```bash
cd d:\Projeckt\santech\Messenger_bot
python api_server.py
```

Сервер будет запущен на `http://127.0.0.1:5000`

### Вариант 2: Продакшен (На сервере Time web cloud)

#### Step 1: Запустить API сервер как фоновый процесс

**Вариант А: Использовать systemd (для Linux)**
```bash
# Создать Service файл
sudo nano /etc/systemd/system/santech-notifications.service
```

Содержимое файла:
```ini
[Unit]
Description=SanTech Notifications API Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/santech
Environment="API_SERVER_URL=http://127.0.0.1:5000"
ExecStart=/path/to/venv/bin/python Messenger_bot/api_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск:
```bash
sudo systemctl start santech-notifications
sudo systemctl enable santech-notifications
```

**Вариант Б: Использовать screen или tmux**
```bash
# Запуск в отдельной сессии screen
cd /path/to/santech/Messenger_bot
screen -d -m -S notifications python api_server.py

# Проверить:
screen -ls
```

**Вариант В: Использовать gunicorn с Flask**
```bash
pip install gunicorn
cd /path/to/santech/Messenger_bot
gunicorn -w 2 -b 0.0.0.0:5000 api_server:app --daemon
```

## 🧪 Тестирование Уведомлений

### 1. Проверить здоровье API сервера

```bash
curl -X GET http://127.0.0.1:5000/health
```

Ответ должен быть:
```json
{
  "status": "ok",
  "bot_token": "✅ или ❌",
  "max_token": "✅ или ❌"
}
```

### 2. Создать заявку и проверить логи

1. Откройте сайт в браузере
2. Создайте новую заявку
3. Проверьте консоль API сервера:
   - Должны быть логи отправки в Telegram/MAX
   - Браузер должен показать веб-уведомление

### 3. Логи Django

```bash
tail -f logs/django.log  # если логи в файл
```

## 🔍 Диагностика Проблем

### Проблема: Telegram уведомления не приходят

**Решение:**
1. Проверить, что токен скопирован **полностью** (обычно очень длинный)
2. Проверить, что пользователь привязал Telegram:
   - На странице регистрации получить код
   - Отправить код боту
   - Проверить БД: `SELECT * FROM users WHERE site_user_id = 'user_id'`

3. Проверить логи API сервера - есть ли ошибка SENT в Telegram

### Проблема: MAX уведомления не приходят

1. MAX API может иметь другой формат/адрес
2. Проверить API документацию MAX
3. Убедиться, что пользователь привязал MAX

### Проблема: Веб-уведомления не приходят в Safari на iOS

**Решение:**
- Safari на iOS не поддерживает полноценно Notification API
- Вместо этого используется `alert()` в качестве fallback
- Пользователь увидит всплывающее окно с уведомлением

### Проблема: API сервер не запускается

1. Проверить Python версию: `python --version`
2. Проверить зависимости: `pip list | grep flask`
3. Проверить порт 5000 не занят: `lsof -i :5000` (Linux) или `netstat -ano | findstr :5000` (Windows)

## 📱 Для Каждого Канала

### Telegram
- **Требует:** Telegram аккаунт
- **Настройка:** BOT_TOKEN от @BotFather
- **Сценарий:** 
  1. Пользователь получает код на сайте
  2. Отправляет код боту в TG
  3. Код сохраняется в БД
  4. Уведомления отправляются автоматически

### MAX
- **Требует:** MAX аккаунт
- **Настройка:** MAX_TOKEN от MAX Bot API
- **Процесс:** Аналогичен Telegram

### Веб-уведомления
- **Требует:** Разрешение в браузере
- **Поддержка:**
  - ✅ Chrome/Chromium
  - ✅ Firefox
  - ⚠️ Safari iOS (через alert fallback)
  - ✅ Microsoft Edge
- **Использование:** Добавить иконку сайта на рабочий стол

## 🔐 Безопасность

1. **Никогда** не коммитьте .env с токенами в Git
2. Используйте переменные окружения сервера
3. Ограничьте доступ к /health и другим эндпоинтам

## 📊 Структура Уведомлений

```
┌─────────────────────┐
│   Создание Заявки   │
│   (views.py)        │
└──────────┬──────────┘
           │
           ├─→ send_notification()
           │       │
           │       ├─→ send_telegram_notification()
           │       │       └─→ API_SERVER/send_notification (ch=telegram)
           │       │
           │       └─→ send_max_notification()
           │               └─→ API_SERVER/send_notification (ch=max)
           │
           └─→ showBrowserNotification() (фронтенд JavaScript)
                   └─→ Notion API браузера
```

## 🛠️ Команды для Быстрого Старта

### На локальной машине
```bash
# Terminal 1
python manage.py runserver

# Terminal 2
cd Messenger_bot && python api_server.py
```

### На сервере
```bash
# Запустить как сервис
sudo systemctl start santech-notifications

# Или через gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 api_server:app --daemon
```

## 📞 Контакты для Поддержки

Если уведомления не работают:
1. Проверьте логи API сервера
2. Проверьте .env переменные
3. Проверьте привязку пользователя (в БД таблица users)
4. Проверьте консоль браузера (F12) на ошибки JavaScript
