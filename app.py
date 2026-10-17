"""
MERGED SERVICE — Bot A + Bot B in ONE Render service (fits the free 750 hours).

The two bots are NOT changed. Their code lives, untouched, in:
  bot_a.py  -> Bot A (wallet 1)
  bot_b.py  -> Bot B (wallet 2)
This small file just starts both of them and shares out the web addresses.

ADDRESSES
  /manage            -> runs Bot A AND Bot B (UptimeRobot every 5 minutes)
  /status, /signals, /test, /resume, /balance on Telegram -> Bot B (same as before)
  /a/status, /a/signals, /a/test                          -> Bot A

RENDER ENVIRONMENT (service trend-bot-b)
  Already there (Bot B):  HL_PRIVATE_KEY, HL_WALLET_ADDR, TELEGRAM_TOKEN,
                          TELEGRAM_CHAT_ID, WALLET_A_ADDR
  NEW (Bot A's key):      BOT_A_PRIVATE_KEY  = HL_PRIVATE_KEY of hyperliquid-signer
  Bot A's wallet address is taken from WALLET_A_ADDR (already set).
"""
import os

from flask import Flask, jsonify
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# ---------- 1) start Bot A with ITS OWN wallet ----------
_b_key  = os.environ["HL_PRIVATE_KEY"]
_b_addr = os.environ["HL_WALLET_ADDR"]
_a_key  = os.environ.get("BOT_A_PRIVATE_KEY", "").strip()
_a_addr = (os.environ.get("BOT_A_WALLET_ADDR") or os.environ.get("WALLET_A_ADDR") or "").strip()

if not _a_key or not _a_addr:
    raise RuntimeError("Missing BOT_A_PRIVATE_KEY or WALLET_A_ADDR in Render > Environment")
if _a_addr.lower() == _b_addr.lower():
    raise RuntimeError("WALLET_A_ADDR is the same as HL_WALLET_ADDR: Bot A must use wallet 1")

os.environ["HL_PRIVATE_KEY"] = _a_key
os.environ["HL_WALLET_ADDR"] = _a_addr
import bot_a                                 # Bot A reads wallet 1 here

# ---------- 2) start Bot B with ITS OWN wallet ----------
os.environ["HL_PRIVATE_KEY"] = _b_key
os.environ["HL_WALLET_ADDR"] = _b_addr
import bot_b                                 # Bot B reads wallet 2 here

# ---------- 3) one /manage for both ----------
both = Flask(__name__)


@both.route("/manage", methods=["GET"])
def manage_both():
    out = {}
    for name, bot in (("bot_a", bot_a), ("bot_b", bot_b)):
        try:
            r = bot.app.test_client().get("/manage")
            out[name] = r.get_json(silent=True) or r.get_data(as_text=True)
        except Exception as e:                # one bot's problem never stops the other
            out[name] = {"status": "error", "reason": str(e)}
    return jsonify(out), 200


class _Router:
    """/manage -> both bots, /a/... -> Bot A, everything else -> Bot B."""

    def __init__(self):
        self.rest = DispatcherMiddleware(bot_b.app, {"/a": bot_a.app})

    def __call__(self, environ, start_response):
        if environ.get("PATH_INFO", "").rstrip("/") == "/manage":
            return both(environ, start_response)
        return self.rest(environ, start_response)


app = _Router()                              # Render start command: gunicorn app:app ...
