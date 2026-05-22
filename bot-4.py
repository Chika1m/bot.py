import asyncio
import json
import time
import logging
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
MIN_RED_CANDLES = 5
COOLDOWN_SECS = 300

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)
candles = []
last_alert_time = 0

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"SpikeWatcher500 is running!")
    def log_message(self, *args): pass

def start_server():
    HTTPServer(("0.0.0.0", 10000), Handler).serve_forever()

async def send_telegram(session, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        async with session.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}) as r:
            log.info("Alert sent!" if r.status == 200 else f"Error {r.status}")
    except Exception as e:
        log.error(f"Telegram failed: {e}")

def is_green(c): return c["close"] > c["open"]
def is_red(c): return c["close"] < c["open"]

def check_signal():
    if len(candles) < MIN_RED_CANDLES + 1: return False
    latest = candles[-1]
    if not is_green(latest): return False
    prev = candles[-(MIN_RED_CANDLES + 1):-1]
    if not all(is_red(c) for c in prev): return False
    return True

async def run_bot():
    global last_alert_time
    async with aiohttp.ClientSession() as session:
        await send_telegram(session, "🤖 SpikeWatcher500 started!\nWatching Boom 500 M1...")
        while True:
            try:
                async with websockets.connect(DERIV_WS_URL, ping_interval=30) as ws:
                    log.info("Connected!")
                    await ws.send(json.dumps({"ticks_history": SYMBOL, "adjust_start_time": 1, "count": CANDLE_HISTORY, "end": "latest", "granularity": GRANULARITY, "style": "candles", "subscribe": 1}))
                    async for raw in ws:
                        msg = json.loads(raw)
                        t = msg.get("msg_type")
                        if t == "candles":
                            for c in msg["candles"]:
                                candles.append({"open": float(c["open"]), "high": float(c["high"]), "low": float(c["low"]), "close": float(c["close"]), "epoch": c["epoch"]})
                            while len(candles) > CANDLE_HISTORY: candles.pop(0)
                        elif t == "ohlc":
                            o = msg["ohlc"]
                            nc = {"open": float(o["open"]), "high": float(o["high"]), "low": float(o["low"]), "close": float(o["close"]), "epoch": o["epoch"]}
                            if candles and candles[-1]["epoch"] == nc["epoch"]:
                                candles[-1] = nc
                            else:
                                candles.append(nc)
                                while len(candles) > CANDLE_HISTORY: candles.pop(0)
                                log.info(f"Candle {'🟢' if is_green(nc) else '🔴'} C:{nc['close']}")
                                now = time.time()
                                if check_signal() and now - last_alert_time >= COOLDOWN_SECS:
                                    last_alert_time = now
                                    await send_telegram(session,
                                        "🚨 <b>SELL — Boom 500 Index</b>\n\n"
                                        "📉 First green candle after 5 red candles\n"
                                        "⏱ Duration: <b>4 minutes</b>\n"
                                        f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}\n\n"
                                        "⚠️ <i>Trade at your own risk</i>")
            except Exception as e:
                log.error(f"Error: {e} — retry in 5s")
                await asyncio.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()
    log.info("Web server started on port 10000")
    asyncio.run(run_bot())
