from flask import Flask, request, jsonify
import database
import random
import string
import requests
import os
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")


def generate_code():
    return ''.join(random.choices(string.digits, k=6))


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

    site_user_id = request.json["user_id"]
    text = request.json["text"]

    telegram_id = database.get_telegram(site_user_id)

    print("telegram_id:", telegram_id)

    if telegram_id:

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        response = requests.post(url, json={
            "chat_id": telegram_id[0],
            "text": f"📩 Новая заявка для {site_user_id}:\n{text}"
        })

        print("telegram response:", response.text)

    return {"status": "sent"}


app.run(port=5000)