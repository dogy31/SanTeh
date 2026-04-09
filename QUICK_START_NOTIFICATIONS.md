# 🚀 БЫСТРЫЙ ЗАПУСК УВЕДОМЛЕНИЙ

## ДЛЯ ЛОКАЛЬНОЙ РАЗРАБОТКИ

Откройте ДВА терминала:

### Terminal 1: Django
```powershell
cd d:\Projeckt\santech
python manage.py runserver
```

### Terminal 2: API Notifications Server
```powershell
cd d:\Projeckt\santech
python Messenger_bot/api_server.py
```

✅ Готово! Уведомления будут работать.

---

## ДЛЯ СЕРВЕРА Time web cloud

### Step 1: Установить systemd сервис (если Linux)

Создать файл `/etc/systemd/system/santech-notifications.service`:

```ini
[Unit]
Description=SanTech Notification API Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/santech
Environment="API_SERVER_URL=http://127.0.0.1:5000"
ExecStart=/var/www/santech/venv/bin/python /var/www/santech/Messenger_bot/api_server.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/santech-notifications.log
StandardError=append:/var/log/santech-notifications.log

[Install]
WantedBy=multi-user.target
```

Запуск:
```bash
sudo systemctl daemon-reload
sudo systemctl start santech-notifications
sudo systemctl enable santech-notifications
```

Проверка:
```bash
sudo systemctl status santech-notifications
```

### Step 2: Или использовать gunicorn (универсальный способ)

```bash
cd /path/to/santech
pip install gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 2 Messenger_bot.api_server:app --daemon
```

### Step 3: Или запустить в screen (простейший способ)

```bash
cd /path/to/santech/Messenger_bot
screen -d -m -S notifications python api_server.py
```

---

## ПРОВЕРКА РАБОТЫ

### 1. Проверить API сервер

```bash
curl http://127.0.0.1:5000/health
```

Ответ должен быть:
```json
{
  "status": "ok",
  "bot_token": "✅ или ❌",
  "max_token": "✅ или ❌"
}
```

### 2. Создать заявку в браузере

- Откройте http://localhost:8000 или сайт
- Откройте консоль браузера (F12)
- Создайте новую заявку
- Должно появиться веб-уведомление!
- Проверьте логи API сервера - должны быть строки отправки

### 3. Проверить Telegram уведомления

- Если рабочий привязал Telegram, он должен получить уведомление
- Проверьте логи API сервера команду `tail -f logs.txt`

---

## КОГДА ВСЕ РАБОТАЕТ

1. **Веб-уведомления** ✅ - появляются в браузере сразу
2. **Telegram** ✅ - если рабочий привязал TG-аккаунт
3. **MAX** ✅ - если рабочий привязал MAX-аккаунт

При наличии одной иконки сайта на рабочем столе:
- Уведомления будут приходить ВО ВСЕ КАНАЛЫ одновременно
- Работает на iOS, Android и Windows
- Никакие данные не сохраняются в БД (как и требовалось)

---

## TROUBLESHOOTING

**Q: Уведомления не приходят?**
A: 
1. Проверьте API сервер запущен: `curl localhost:5000/health`
2. Проверьте .env переменные (BOT_TOKEN, MAX_TOKEN)
3. Проверьте логи Django и API сервера
4. Убедитесь что пользователь привязал Telegram/MAX
