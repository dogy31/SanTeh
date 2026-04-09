from flask import Flask, request, jsonify
import database
import random
import string
import re
import requests
import os
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAX_TOKEN = os.getenv("MAX_TOKEN")

print(f"\n{'='*60}")
print(f"[API SERVER] Запуск сервера уведомлений")
print(f"[API SERVER] BOT_TOKEN: {'✅ загруженн' if BOT_TOKEN else '❌ НЕ ЗАГРУЖЕН'}")
print(f"[API SERVER] MAX_TOKEN: {'✅ загруженн' if MAX_TOKEN else '❌ НЕ ЗАГРУЖЕН'}")
print(f"{'='*60}\n")


def generate_code():
    return ''.join(random.choices(string.digits, k=6))


def make_phone_clickable(text):
    def repl(match):
        raw = match.group(0)
        digits = re.sub(r'\D', '', raw)
        if digits.startswith('8'):
            digits = '7' + digits[1:]
        if len(digits) != 11:
            return raw
        return f'<a href="tel:+{digits}">{raw}</a>'
    return re.sub(r'(\+7|8)[\d\-\s\(\)]{9,}', repl, text)


@app.route("/register", methods=["POST"])
def register():
    site_user_id = request.json["user_id"]
    code = generate_code()
    database.save_code(site_user_id, code)
    return jsonify({
        "code": code,
        "message": "Отправьте код боту"
    })


@app.route("/send_notification", methods=["POST"])
def send_notification():
    """Универсальный endpoint для отправки уведомлений"""
    site_user_id = request.json.get("user_id")
    text = request.json.get("text")
    channel = request.json.get("channel", "all")
    
    print(f"\n{'='*60}")
    print(f"[API] Получен запрос на отправку уведомления")
    print(f"[API] User ID: {site_user_id}")
    print(f"[API] Channel: {channel}")
    print(f"[API] Text: {text[:100]}...")
    
    telegram_id = database.get_telegram(site_user_id)
    max_id = database.get_max(site_user_id)
    
    print(f"[API] Telegram ID в БД: {telegram_id}")
    print(f"[API] MAX ID в БД: {max_id}")
    
    sent_count = 0
    results = {"telegram": False, "max": False}
    
    # Отправляем в Telegram
    if channel in ["telegram", "all"]:
        if telegram_id and telegram_id[0] and BOT_TOKEN:
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                response = requests.post(url, json={
                    "chat_id": telegram_id[0],
                    "text": make_phone_clickable(text),
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True
                }, timeout=5)
                print(f"[TELEGRAM] Статус: {response.status_code}")
                print(f"[TELEGRAM] Ответ: {response.text[:200]}")
                if response.status_code == 200:
                    results["telegram"] = True
                    sent_count += 1
            except Exception as e:
                print(f"[TELEGRAM] ❌ Ошибка: {e}")
        else:
            print(f"[TELEGRAM] ⚠️ Не отправлено (telegram_id={telegram_id}, BOT_TOKEN={'✅' if BOT_TOKEN else '❌'})")
    
    # Отправляем в MAX
    if channel in ["max", "all"]:
        if max_id and max_id[0] and MAX_TOKEN:
            try:
                # MAX API может различаться в зависимости от провайдера
                # Стандартный формат для большинства ботов
                url = f"https://api.max.im/bot{MAX_TOKEN}/sendMessage"
                response = requests.post(url, json={
                    "chat_id": max_id[0],
                    "text": text
                }, timeout=5)
                print(f"[MAX] Статус: {response.status_code}")
                print(f"[MAX] Ответ: {response.text[:200]}")
                if response.status_code == 200:
                    results["max"] = True
                    sent_count += 1
            except Exception as e:
                print(f"[MAX] ❌ Ошибка: {e}")
        else:
            print(f"[MAX] ⚠️ Не отправлено (max_id={max_id}, MAX_TOKEN={'✅' if MAX_TOKEN else '❌'})")
    
    print(f"[API] Итого отправлено: {sent_count}")
    print(f"{'='*60}\n")
    
    return jsonify({
        "status": "sent",
        "sent_count": sent_count,
        "results": results,
        "message": f"Отправлено {sent_count} уведомлений"
    }), 200 if sent_count > 0 else 206


@app.route("/health", methods=["GET"])
def health():
    """Проверка здоровья сервера"""
    return jsonify({
        "status": "ok",
        "bot_token": "✅" if BOT_TOKEN else "❌",
        "max_token": "✅" if MAX_TOKEN else "❌"
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)