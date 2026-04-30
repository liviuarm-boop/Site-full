import os, json, datetime, pytz, requests
from anthropic import Anthropic

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

def telegram_send(md):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": md,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True
    }, timeout=10)
    r.raise_for_status()

def fear_greed(pct):
    if pct > 1.5: return "🟢 Lăcomie"
    if pct < -1.5: return "🔴 Teamă"
    return "🟡 Neutru"

def generate_comment(context):
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=80,
        system="Analist BVB concis, română, 1–2 propoziții.",
        messages=[{"role":"user","content":context}]
    )
    return msg.content[0].text.strip()

def main():
    try:
        with open("stocks.json") as f:
            stocks = json.load(f)
    except Exception:
        stocks = []

    movers = sorted(stocks, key=lambda x: abs(x.get("change_pct",0)), reverse=True)[:3]
    avg = sum(x.get("change_pct",0) for x in stocks) / max(len(stocks),1)
    sentiment = fear_greed(avg)

    lines = []
    for m in movers:
        t = m.get("ticker","?")
        c = m.get("change_pct",0)
        e = "📈" if c >= 0 else "📉"
        lines.append(f"{e} *{t}* {c:+.2f}%")

    comment = generate_comment(f"Mediu BVB azi: {avg:.2f}%.")

    md = (
        "⏰ *Briefing BVB – Ziua de tranzacționare*\n\n"
        + "\n".join(lines)
        + f"\n\n{sentiment}\n"
        + f"💬 {comment}\n\n"
        + "👉 ghidbursa.ro"
    )
    telegram_send(md)

if __name__ == "__main__":
    ro = pytz.timezone("Europe/Bucharest")
    now = datetime.datetime.now(ro)
    if now.weekday() < 5:
        main()
