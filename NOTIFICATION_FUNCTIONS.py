# ============================================================================
# ФУНКЦИИ ОТПРАВКИ УВЕДОМЛЕНИЙ ДЛЯ VIEWS.PY
# Скопируйте эти функции в main/views.py вместо старых send_notification
# ============================================================================

import os
import requests

API_SERVER_URL = os.getenv('API_SERVER_URL', 'http://127.0.0.1:5000')

def send_telegram_notification(profile, title, text):
    """Отправляет уведомление в Telegram"""
    try:
        if not profile or not profile.tg_code:
            print('[TELEGRAM] Profile не имеет привязанного Telegram')
            return False
        
        site_user_id = str(profile.user.id) if profile.user else None
        formatted_text = "📌 " + title + "\n\n" + text
        
        payload = {
            'user_id': site_user_id,
            'text': formatted_text,
            'channel': 'telegram'
        }
        response = requests.post(
            API_SERVER_URL + '/send_notification',
            json=payload,
            timeout=5
        )
        status = response.status_code == 200
        print('[TELEGRAM] Отправлено для ' + str(site_user_id) + ': ' + str(response.status_code))
        return status
    except Exception as e:
        print('[TELEGRAM] Ошибка: ' + str(e))
        return False

def send_max_notification(profile, title, text):
    """Отправляет уведомление в MAX"""
    try:
        if not profile or not profile.max_code:
            print('[MAX] Profile не имеет привязанного MAX')
            return False
        
        site_user_id = str(profile.user.id) if profile.user else None
        formatted_text = "📌 " + title + "\n\n" + text
        
        payload = {
            'user_id': site_user_id,
            'text': formatted_text,
            'channel': 'max'
        }
        response = requests.post(
            API_SERVER_URL + '/send_notification',
            json=payload,
            timeout=5
        )
        status = response.status_code == 200
        print('[MAX] Отправлено для ' + str(site_user_id) + ': ' + str(response.status_code))
        return status
    except Exception as e:
        print('[MAX] Ошибка: ' + str(e))
        return False

def send_notification(user, notification_type, title, text, request_obj=None):
    """
    Отправляет уведомление на все доступные каналы:
    - Telegram (если привязан)
    - MAX (если привязан)
    notification_type: 'new_request', 'reassign', 'cancel', 'complete'
    """
    if not user:
        print('[NOTIFICATION] Пользователь не указан')
        return
    
    print('[NOTIFICATION] Начало отправки уведомления')
    print('[NOTIFICATION] Пользователь: ' + user.username)
    print('[NOTIFICATION] Тип: ' + notification_type)
    print('[NOTIFICATION] Заголовок: ' + title)
    
    try:
        if hasattr(user, 'profile'):
            tg_sent = send_telegram_notification(user.profile, title, text)
            max_sent = send_max_notification(user.profile, title, text)
            tg_status = 'OK' if tg_sent else 'FAIL'
            max_status = 'OK' if max_sent else 'FAIL'
            print('[NOTIFICATION] Результаты - Telegram: ' + tg_status + ', MAX: ' + max_status)
        else:
            print('[NOTIFICATION] У пользователя нет профиля')
        
        print('[NOTIFICATION] Уведомление обработано')
    except Exception as e:
        print('[NOTIFICATION] Ошибка: ' + str(e))
