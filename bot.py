import asyncio
import json
import time
import threading
import aiohttp
import websockets
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

TELEGRAM_TOKEN = "8904493218:AAF-YXwQXMAPX_2eE_qqR0FSWylQG9o_c9o"
CHAT_ID = "7452230597"
DERIV_WS_URL = "wss://ws.binaryws.com/websockets/v3?app_id=1089"
SYMBOL = "BOOM500"
GRANULARITY = 60
CANDLE_HISTORY = 10
COOLDOWN_SECS = 300
MIN_GAP_SIZE = 0.01

candles = []
last_alert_time = 0

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args): pass

def start_server():
    HTTPServer(("0.0.0.0", 10000), Handler).serve_forever()

async def send_telegram(session, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        async with session.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}) as r:
            pass
    except: pass

def check_gap():
    if len(candles) < 2:
        return False, 0
    prev_close = candles[-2]["close"]
    curr_open = candles[-1]["open"]
    gap = abs(curr_open - prev_close)
    if gap >= MIN_GAP_SIZE:
        return True, gap
    return False, gap

async def run_bot():
    global last_alert_time
    async with aiohttp.ClientSession() as session:
        await send_telegram(session, "🤖 SpikeWatcher500 started!\nWatching Boom 500 M1 for GAPS...")
        while True:
            try:
                async with websockets.connect(DERIV_WS_URL, ping_interval=30) as ws:
                    await ws.send(json.dumps({
                        "ticks_history": SYMBOL,
                        "adjust_start_time": 1,
                        "count": CANDLE_HISTORY,
                        "end": "latest",
                        "granularity": GRANULARITY,
                        "style": "candles",
                        "subscribe": 1
                    }))
                    async for raw in ws:
                        msg = json.loads(raw)
                        t = msg.get("msg_type")
                        if t == "candles":
                            for c in msg["candles"]:
                                candles.append({
                                    "open": float(c["open"]),
                                    "close": float(c["close"]),
                                    "epoch": c["epoch"]
                                })
                            while len(candles) > CANDLE_HISTORY: candles.pop(0)
                        elif t == "ohlc":
                            o = msg["ohlc"]
                            nc = {
                                "open": float(o["open"]),
                                "close": float(o["close"]),
                                "epoch": o["epoch"]
                            }
                            if candles and candles[-1]["epoch"] == nc["epoch"]:
                                candles[-1] = nc
                            else:
                                candles.append(nc)
                                while len(candles) > CANDLE_HISTORY: candles.pop(0)
                                now = time.time()
                                has_gap, gap_size = check_gap()
                                if has_gap and now - last_alert_time >= COOLDOWN_SECS:
                                    last_alert_time = now
                                    await send_telegram(session,
                                        "🚨 <b>SELL — Boom 500 Index</b>\n\n"
                                        f"📉 Gap detected: {gap_size:.3f} points\n"
                                        f"⏱ Duration: <b>4 minutes</b>\n"
                                        f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}\n\n"
                                        "⚠️ <i>Trade at your own risk</i>")
            except:
                await asyncio.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()
    asyncio.run(run_bot())
