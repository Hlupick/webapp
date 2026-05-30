import logging
import os
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-key')

# Настройки 3x-ui (логин/пароль)
XUI_URL = os.getenv('XUI_URL')
XUI_USERNAME = os.getenv('XUI_USERNAME')
XUI_PASSWORD = os.getenv('XUI_PASSWORD')
XUI_INBOUND_ID = int(os.getenv('XUI_INBOUND_ID', 1))

session = requests.Session()
session.verify = False

def login_to_xui():
    """Авторизация, возвращает CSRF-токен"""
    try:
        resp = session.post(f'{XUI_URL}/login', json={
            'username': XUI_USERNAME,
            'password': XUI_PASSWORD
        }, timeout=10)
        if resp.status_code == 200:
            csrf = session.cookies.get('x-ui-csrf')
            if csrf:
                return csrf
        return None
    except Exception as e:
        app.logger.error(f"Login error: {e}")
        return None

def add_client_to_xui(email, gb_limit=0, days=30):
    csrf = login_to_xui()
    if not csrf:
        return {'success': False, 'error': 'Не удалось авторизоваться в панели'}

    expiry = int((datetime.utcnow() + timedelta(days=days)).timestamp() * 1000)
    client = {
        "id": "", "email": email, "flow": "xtls-rprx-vision",
        "limitIp": 2, "totalGB": gb_limit, "expiryTime": expiry,
        "enable": True, "tgId": "", "subId": "", "method": "",
        "security": "reality"
    }
    headers = {'X-CSRF-Token': csrf, 'Content-Type': 'application/json'}
    url = f'{XUI_URL}/panel/api/inbounds/addClient'

    try:
        resp = session.post(url, json={"client": client}, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success'):
                uuid = data.get('obj', {}).get('id') or data.get('clientId')
                host = XUI_URL.replace('https://', '').split(':')[0]
                link = (f"vless://{uuid}@{host}:{XUI_INBOUND_ID}"
                        f"?security=reality&flow=xtls-rprx-vision&encryption=none"
                        f"&sni=www.rijksoverheid.nl&type=tcp#CactusVPN")
                return {'success': True, 'link': link}
            else:
                return {'success': False, 'error': data.get('msg', 'Ошибка API')}
        else:
            return {'success': False, 'error': f'HTTP {resp.status_code}: {resp.text}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# Маршруты (без изменений)
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tariffs')
def tariffs():
    return jsonify([
        {'id': 1, 'name': '1 месяц', 'price_rub': 100, 'price_stars': 50, 'gb_limit': 100, 'days': 30,
         'features': ['3 устройства', 'До 200 Мбит/с', 'Поддержка 24/7']},
        {'id': 2, 'name': '6 месяцев', 'price_rub': 450, 'price_stars': 300, 'gb_limit': 200, 'days': 180,
         'features': ['3 устройства', 'До 200 Мбит/с', 'Поддержка 24/7']},
        {'id': 3, 'name': '12 месяцев', 'price_rub': 950, 'price_stars': 600, 'gb_limit': 0, 'days': 365,
         'features': ['3 устройства', 'До 200 Мбит/с', 'Поддержка 24/7']}
    ])

@app.route('/api/buy', methods=['POST'])
def buy():
    data = request.get_json()
    tariff_id = data.get('tariff_id')
    email = data.get('email')
    if not email:
        return jsonify({'success': False, 'error': 'Email required'}), 400

    tariff_map = {1: (100, 30), 2: (200, 180), 3: (0, 365)}
    if tariff_id not in tariff_map:
        return jsonify({'success': False, 'error': 'Invalid tariff'}), 400

    gb, days = tariff_map[tariff_id]
    result = add_client_to_xui(email, gb, days)
    if result['success']:
        return jsonify({'success': True, 'message': 'Ключ создан!', 'link': result['link']})
    else:
        return jsonify({'success': False, 'error': result['error']}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)