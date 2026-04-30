#!/usr/bin/env python3
"""
GhidBursa.ro — daily_briefing.py
Rulează zilnic luni-vineri la 09:30 via GitHub Actions.

Flux:
1. Citește stocks.json și score.json din repo
2. Calculează mișcări mari de preț (YTD), top dividend yield
3. Trimite datele la Claude API → generează briefing în română
4. Postează pe Telegram
5. Trimite email prin Resend la toți abonații activi din D1

Variabile de mediu necesare în GitHub Secrets:
  ANTHROPIC_API_KEY   — cheia Claude API
  TELEGRAM_BOT_TOKEN  — tokenul botului Telegram
  TELEGRAM_CHANNEL_ID — ex: @GhidBursa sau -100xxxxxxxxx
  RESEND_API_KEY      — cheia Resend pentru email
  NEWSLETTER_WORKER_URL — URL-ul worker-ului de newsletter (pentru export abonați)
  EXPORT_SECRET       — secretul pentru endpoint-ul /export din worker
"""

import json, os, sys, datetime, urllib.request, urllib.error, subprocess

# ── Instalare dependențe ──────────────────────────────────────────────────────
subprocess.run([sys.executable, "-m", "pip", "install", "requests", "--quiet"], check=True)
import requests

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_KEY       = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_TOKEN      = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL    = os.environ["TELEGRAM_CHANNEL_ID"]
RESEND_KEY          = os.environ["RESEND_API_KEY"]
WORKER_URL          = os.environ.get("NEWSLETTER_WORKER_URL", "")
EXPORT_SECRET       = os.environ.get("EXPORT_SECRET", "")

TODAY = datetime.date.today()
TODAY_STR = TODAY.strftime("%-d %B %Y").replace(
    "January","ianuarie").replace("February","februarie").replace(
    "March","martie").replace("April","aprilie").replace(
    "May","mai").replace("June","iunie").replace(
    "July","iulie").replace("August","august").replace(
    "September","septembrie").replace("October","octombrie").replace(
    "November","noiembrie").replace("December","decembrie")

DAY_RO = ["Luni","Marți","Miercuri","Joi","Vineri","Sâmbătă","Duminică"][TODAY.weekday()]


# ── 1. Citește stocks.json ────────────────────────────────────────────────────
def load_stocks():
    path = "data/stocks.json"
    if not os.path.exists(path):
        print("ERROR: data/stocks.json not found")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── 2. Citește score.json (Fear & Greed) ─────────────────────────────────────
def load_fear_greed():
    path = "score.json"
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── 3. Calculează date pentru briefing ───────────────────────────────────────
def build_market_data(stocks_data, fg_data):
    stocks = stocks_data.get("stocks", {})

    # Mișcări mari YTD (top 3 câștigătoare, top 3 perdante)
    with_ytd = [
        (t, s) for t, s in stocks.items()
        if s.get("ytd") is not None and s.get("price") is not None
    ]
    with_ytd.sort(key=lambda x: x[1]["ytd"], reverse=True)

    top_gainers = with_ytd[:3]
    top_losers  = with_ytd[-3:][::-1]

    # Top dividend yield
    with_div = [
        (t, s) for t, s in stocks.items()
        if s.get("div_yield") is not None
    ]
    with_div.sort(key=lambda x: x[1]["div_yield"], reverse=True)
    top_div = with_div[:5]

    # Fear & Greed
    fg_score = None
    fg_label = None
    if fg_data and fg_data.get("score") is not None:
        fg_score = fg_data["score"]
        fg_label = fg_data.get("label", "")

    return {
        "date": TODAY_STR,
        "day": DAY_RO,
        "top_gainers": [
            {"ticker": t, "ytd": s["ytd"], "price": s["price"]}
            for t, s in top_gainers
        ],
        "top_losers": [
            {"ticker": t, "ytd": s["ytd"], "price": s["price"]}
            for t, s in top_losers
        ],
        "top_dividend": [
            {"ticker": t, "yield": s["div_yield"], "div_per_share": s.get("div_per_share")}
            for t, s in top_div
        ],
        "fg_score": fg_score,
        "fg_label": fg_label,
        "total_stocks": len(stocks),
        "stocks_updated": stocks_data.get("updated", ""),
    }


# ── 4. Generează briefing cu Claude ──────────────────────────────────────────
def generate_briefing(market_data):
    prompt = f"""Ești analistul de piață al GhidBursa.ro — ghidul independent pentru investitorii la Bursa de Valori București.

Datele de astăzi ({market_data['day']}, {market_data['date']}):

TOP CÂȘTIGĂTOARE YTD:
{chr(10).join(f"  {g['ticker']}: +{g['ytd']}% YTD, preț curent {g['price']} RON" for g in market_data['top_gainers'])}

TOP PERDANTE YTD:
{chr(10).join(f"  {l['ticker']}: {l['ytd']}% YTD, preț curent {l['price']} RON" for l in market_data['top_losers'])}

TOP RANDAMENT DIVIDEND:
{chr(10).join(f"  {d['ticker']}: {d['yield']}% yield" + (f", {d['div_per_share']} RON/acțiune" if d['div_per_share'] else "") for d in market_data['top_dividend'])}

FEAR & GREED BVB: {market_data['fg_score']}/100 — {market_data['fg_label'] or 'N/A'}

INSTRUCȚIUNI:
- Scrie un briefing de piață în ROMÂNĂ pentru investitorii retail români
- Judecă TU lungimea: dacă mișcările sunt semnificative (>5% YTD diferență între câștigătoare și perdante, sau Fear & Greed extrem <20 sau >80) → scrie mai detaliat (5-7 paragrafe). Dacă piața e liniștită → scrie scurt (3-4 paragrafe)
- Stilul: direct, fără jargon inutil, fără fraze goale gen "este important să menționăm"
- Structura TELEGRAM (cu emoji, maxim 800 caractere, folosește formatarea Telegram: **bold**, _italic_):
  → Titlu cu data
  → 2-3 bullet points cu datele cheie
  → O frază de context/analiză
  → Fear & Greed cu interpretare scurtă
  → Link: ghidbursa.ro

- Structura EMAIL (HTML, mai detaliat, fără limită strictă de caractere):
  → Salut
  → Secțiune mișcări piață cu tabel simplu
  → Secțiune dividend top 5
  → Fear & Greed cu explicație
  → Call to action spre screener
  → Footer dezabonare

IMPORTANT: Returnează un JSON cu exact două câmpuri:
{{
  "telegram": "mesajul pentru Telegram (text cu formatare Telegram)",
  "email_subject": "subiectul emailului",
  "email_html": "HTML-ul complet al emailului (body content, fără <html>/<head>)"
}}

Returnează DOAR JSON-ul, fără explicații, fără markdown în jur."""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=60
    )
    resp.raise_for_status()
    data = resp.json()
    raw = data["content"][0]["text"].strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


# ── 5. Postează pe Telegram ───────────────────────────────────────────────────
def post_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHANNEL,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }, timeout=30)

    if not resp.ok:
        print(f"Telegram error: {resp.status_code} — {resp.text}")
        return False
    print(f"✓ Telegram posted — message_id: {resp.json().get('result', {}).get('message_id')}")
    return True


# ── 6. Exportă abonați din D1 ────────────────────────────────────────────────
def get_subscribers():
    if not WORKER_URL or not EXPORT_SECRET:
        print("⚠️  NEWSLETTER_WORKER_URL sau EXPORT_SECRET lipsesc — sar email")
        return []

    url = f"{WORKER_URL}/export?secret={EXPORT_SECRET}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # Worker returnează CSV sau JSON — adaptăm
        if isinstance(data, list):
            return [row["email"] for row in data if row.get("active", 1)]
        return []
    except Exception as e:
        print(f"⚠️  Export abonați eșuat: {e}")
        return []


# ── 7. Trimite email prin Resend ──────────────────────────────────────────────
def send_emails(subscribers, subject, html_body, unsubscribe_base_url=""):
    if not subscribers:
        print("ℹ️  Niciun abonat activ — sar trimiterea emailurilor")
        return

    EMAIL_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #080B0F; color: #E8EDF2; margin: 0; padding: 0; }}
  .wrap {{ max-width: 600px; margin: 0 auto; padding: 32px 20px; }}
  .header {{ border-bottom: 1px solid #1E2A38; padding-bottom: 20px; margin-bottom: 24px; }}
  .logo {{ font-size: 20px; font-weight: 700; color: #E8EDF2; text-decoration: none; }}
  .logo span {{ color: #00D4FF; }}
  .content {{ line-height: 1.7; font-size: 15px; color: rgba(232,237,242,.88); }}
  .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #1E2A38; font-size: 12px; color: #6B7A8D; }}
  a {{ color: #00D4FF; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <a class="logo" href="https://www.ghidbursa.ro">Ghid<span>Bursa</span>.ro</a>
  </div>
  <div class="content">
    {body}
  </div>
  <div class="footer">
    <p>Primești acest email pentru că te-ai abonat pe ghidbursa.ro.</p>
    <p>Conținutul are scop exclusiv informativ și nu constituie consultanță financiară. Nu investiți bani pe care nu vă permiteți să îi pierdeți.</p>
    <p><a href="{unsubscribe_url}">Dezabonare</a> · <a href="https://www.ghidbursa.ro">GhidBursa.ro</a></p>
  </div>
</div>
</body>
</html>"""

    sent = 0
    failed = 0

    for email in subscribers:
        # Build unsubscribe URL (worker handles token lookup by email)
        unsub_url = f"{unsubscribe_base_url}?email={email}" if unsubscribe_base_url else "https://www.ghidbursa.ro/unsubscribe.html"

        full_html = EMAIL_HTML_TEMPLATE.format(
            body=html_body,
            unsubscribe_url=unsub_url
        )

        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": "GhidBursa.ro <newsletter@ghidbursa.ro>",
                    "to": [email],
                    "subject": subject,
                    "html": full_html,
                },
                timeout=15
            )
            if resp.ok:
                sent += 1
            else:
                print(f"  Email fail {email}: {resp.status_code}")
                failed += 1
        except Exception as e:
            print(f"  Email error {email}: {e}")
            failed += 1

    print(f"✓ Email — trimise: {sent}, eșuate: {failed}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*50}")
    print(f"GhidBursa Daily Briefing — {TODAY_STR}")
    print(f"{'='*50}\n")

    # 1. Încarcă date
    print("1. Încărcare date...")
    stocks_data = load_stocks()
    fg_data     = load_fear_greed()
    print(f"   Stocuri: {len(stocks_data.get('stocks', {}))} | F&G: {fg_data.get('score') if fg_data else 'N/A'}")

    # 2. Pregătește datele de piață
    print("2. Calculare date piață...")
    market_data = build_market_data(stocks_data, fg_data)
    print(f"   Top gainer: {market_data['top_gainers'][0]['ticker']} +{market_data['top_gainers'][0]['ytd']}%")
    print(f"   Top loser:  {market_data['top_losers'][0]['ticker']} {market_data['top_losers'][0]['ytd']}%")

    # 3. Generează briefing cu Claude
    print("3. Generare briefing cu Claude API...")
    briefing = generate_briefing(market_data)
    print(f"   Telegram: {len(briefing['telegram'])} caractere")
    print(f"   Email subject: {briefing['email_subject']}")

    # 4. Postează pe Telegram
    print("4. Postare Telegram...")
    post_telegram(briefing["telegram"])

    # 5. Emailuri
    print("5. Trimitere emailuri...")
    subscribers = get_subscribers()
    print(f"   Abonați activi: {len(subscribers)}")
    send_emails(
        subscribers,
        briefing["email_subject"],
        briefing["email_html"],
        unsubscribe_base_url=f"{WORKER_URL}/unsubscribe-by-email" if WORKER_URL else ""
    )

    print(f"\n✅ Briefing complet — {TODAY_STR}")


if __name__ == "__main__":
    main()
