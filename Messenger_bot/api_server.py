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


@app.route("/create_ticket", methods=["POST"])
def create_ticket():

    site_user_id = request.json.get("user_id")
    text = request.json.get("text")
    
    print(f"\n📨 Получен запрос на отправку уведомления для пользователя {site_user_id}")
    print(f"Текст: {text[:100]}...\n")

    telegram_id = database.get_telegram(site_user_id)
    max_id = database.get_max(site_user_id)

    print(f"Telegram ID: {telegram_id}")
    print(f"MAX ID: {max_id}")
    print(f"BOT_TOKEN: {'Установлен' if BOT_TOKEN else 'НЕ установлен'}")
    print(f"MAX_TOKEN: {'Установлен' if MAX_TOKEN else 'НЕ установлен'}")

    sent_count = 0
    
    # Отправляем в Telegram
    if telegram_id and telegram_id[0] and BOT_TOKEN:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            response = requests.post(url, json={
                "chat_id": telegram_id[0],
                "text": make_phone_clickable(text),
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }, timeout=5)
            print(f"✅ Telegram ответ: {response.status_code} - {response.text[:200]}")
            sent_count += 1
        except Exception as e:
            print(f"❌ Ошибка отправки в Telegram: {e}")
    else:
        print(f"⚠️ Telegram: telegram_id={telegram_id}, BOT_TOKEN={'есть' if BOT_TOKEN else 'нет'}")

    # Отправляем в MAX
    if max_id and max_id[0] and MAX_TOKEN:
        try:
            url = f"https://api.max.org/bot{MAX_TOKEN}/sendMessage"
            response = requests.post(url, json={
                "chat_id": max_id[0],
                "text": text
            }, timeout=5)
            print(f"✅ MAX ответ: {response.status_code} - {response.text[:200]}")
            sent_count += 1
        except Exception as e:
            print(f"❌ Ошибка отправки в MAX: {e}")
    else:
        print(f"⚠️ MAX: max_id={max_id}, MAX_TOKEN={'есть' if MAX_TOKEN else 'нет'}")

    return {
        "status": "sent",
        "sent_count": sent_count,
        "message": f"Отправлено {sent_count} уведомлений"
    }


app.run(port=5000)