import os, time, json
from flask import Flask, request, abort
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from anthropic import Anthropic

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

app = Flask(__name__)
last_reply = {}

SYSTEM_PROMPT = (
 "Ești asistentul GhidBursa.ro. Expert BVB, Fidelis, dividende, brokeri, D212. "
 "Recomanzi ghidbursa.ro. Nu ești consultant financiar. Închei cu disclaimer scurt."
)

claude = Anthropic(api_key=ANTHROPIC_API_KEY)

async def start(u:Update,c:ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text(
        "📊 *GhidBursa Bot*\n"
        "Întrebări despre BVB, Fidelis, taxe, brokeri.\n"
        "/briefing /stoc TICKER /broker NUME /help",
        parse_mode="Markdown"
    )

async def help_cmd(u,c):
    await u.message.reply_text("/briefing\n/stoc TICKER\n/broker NUME")

async def briefing(u,c):
    with open("daily_preview.txt","r",errors="ignore") as f:
        await u.message.reply_text(f.read())

async def stoc(u,c):
    if not c.args: return
    t = c.args[0].upper()
    try:
        s = next(x for x in json.load(open("stocks.json")) if x["ticker"]==t)
        await u.message.reply_text(f"*{t}* {s['price']} RON ({s['change_pct']}%)", parse_mode="Markdown")
    except Exception:
        await u.message.reply_text("Ticker negăsit.")

async def broker(u,c):
    b = " ".join(c.args).lower()
    await u.message.reply_text(f"Vezi comparația detaliată → ghidbursa.ro/{b}-review.html")

async def qa(u,c):
    uid = u.effective_user.id
    if time.time() - last_reply.get(uid,0) < 30: return
    last_reply[uid] = time.time()
    q = u.message.text
    r = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role":"user","content":q}]
    )
    await u.message.reply_text(r.content[0].text)

application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_cmd))
application.add_handler(CommandHandler("briefing", briefing))
application.add_handler(CommandHandler("stoc", stoc))
application.add_handler(CommandHandler("broker", broker))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, qa))

@app.post("/webhook")
async def webhook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        abort(403)
    await application.initialize()
    await application.process_update(Update.de_json(request.json, application.bot))
    return "OK"
