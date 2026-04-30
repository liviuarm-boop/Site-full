#!/usr/bin/env python3
"""
GhidBursa.ro — weekly_newsletter.py

Rulează în două moduri:
  --preview   Generează newsletter + trimite DOAR la owner pentru aprobare
  --send      Trimite la toți abonații (rulat manual după aprobare)

GitHub Actions:
  Marți 07:00 UTC → rulează automat cu --preview
  Manual dispatch  → rulează cu --send (după ce owner aprobă)

Secrets necesare:
  ANTHROPIC_API_KEY, RESEND_API_KEY,
  NEWSLETTER_WORKER_URL, EXPORT_SECRET,
  OWNER_EMAIL (emailul tău personal pentru preview)
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID (opțional)
"""

import json, os, sys, datetime, subprocess, argparse, time

subprocess.run([sys.executable, "-m", "pip", "install", "requests", "--quiet"], check=True)
import requests

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_KEY    = os.environ["ANTHROPIC_API_KEY"]
RESEND_KEY       = os.environ["RESEND_API_KEY"]
WORKER_URL       = os.environ.get("NEWSLETTER_WORKER_URL", "https://newsletter.ghidbursa.ro")
EXPORT_SECRET    = os.environ.get("EXPORT_SECRET", "")
OWNER_EMAIL      = os.environ.get("OWNER_EMAIL", "liviuarm@gmail.com")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL_ID", "")

TODAY     = datetime.date.today()
MONTHS_RO = ["ianuarie","februarie","martie","aprilie","mai","iunie",
             "iulie","august","septembrie","octombrie","noiembrie","decembrie"]
TODAY_STR = f"{TODAY.day} {MONTHS_RO[TODAY.month-1]} {TODAY.year}"
WEEK_NUM  = TODAY.isocalendar()[1]

DRAFT_PATH = "/tmp/newsletter_draft.json"


# ── 1. Încarcă date ───────────────────────────────────────────────────────────
def load_stocks():
    for path in ["data/stocks.json", "stocks.json"]:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    print("WARN: stocks.json lipsă")
    return {"stocks": {}}

def load_fear_greed():
    for path in ["score.json", "data/score.json"]:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    return None


# ── 2. Context de piață ───────────────────────────────────────────────────────
def build_context(stocks_data, fg_data):
    stocks = stocks_data.get("stocks", {})

    with_ytd = [(t, s) for t, s in stocks.items()
                if s.get("ytd") is not None and s.get("price") is not None]
    with_ytd.sort(key=lambda x: x[1]["ytd"], reverse=True)
    gainers = with_ytd[:5]
    losers  = with_ytd[-5:][::-1] if len(with_ytd) >= 5 else []

    with_div = [(t, s) for t, s in stocks.items()
                if s.get("div_yield") is not None]
    with_div.sort(key=lambda x: x[1]["div_yield"], reverse=True)
    top_div = with_div[:6]

    fg_score = fg_data.get("score") if fg_data else None
    fg_label = fg_data.get("label", "") if fg_data else ""

    return {
        "date": TODAY_STR,
        "week": WEEK_NUM,
        "fg_score": fg_score,
        "fg_label": fg_label,
        "gainers": gainers,
        "losers": losers,
        "top_div": top_div,
        "total_stocks": len(stocks),
    }


# ── 3. Generare Claude ────────────────────────────────────────────────────────
SYSTEM = """Ești redactorul GhidBursa.ro — newsletter financiar serios pentru investitorii BVB.
Scrii în română perfectă cu diacritice corecte (ș ț ă â î).
Ton: profesionist, direct, analitic, fără clickbait, fără superlative goale.
Nu inventezi date. Folosești EXACT cifrele furnizate."""

def generate(ctx):
    gainers_txt = "\n".join(
        f"  {t}: +{s['ytd']:.1f}% YTD, {s['price']:.2f} RON"
        for t, s in ctx["gainers"]
    ) or "  date indisponibile"

    losers_txt = "\n".join(
        f"  {t}: {s['ytd']:.1f}% YTD, {s['price']:.2f} RON"
        for t, s in ctx["losers"]
    ) or "  date indisponibile"

    div_txt = "\n".join(
        f"  {t} ({s[1].get('name', t)}): {s[1]['div_yield']:.1f}% yield"
        for s in ctx["top_div"]
    ) or "  date indisponibile"

    fg_txt = (f"Fear & Greed BVB: {ctx['fg_score']}/100 — {ctx['fg_label']}"
              if ctx["fg_score"] is not None else "Fear & Greed: indisponibil")

    prompt = f"""Generează newsletter-ul săptămânal GhidBursa.ro — Săptămâna {ctx['week']}, {ctx['date']}.

DATE REALE BVB (folosește-le exact, nu inventa altele):
{fg_txt}

Top câștigătoare YTD:
{gainers_txt}

Top perdante YTD:
{losers_txt}

Top dividend yield:
{div_txt}

STRUCTURA:
1. SUBIECT EMAIL — max 55 caractere, specific și informativ (ex: "BVB săptămâna {ctx['week']}: cine a câștigat și de ce")
2. TITLU NEWSLETTER — mai lung, captivant (va apărea în header)
3. INTRO — 2 propoziții despre contextul săptămânii
4. BVB ÎN ACEASTĂ SĂPTĂMÂNĂ — 3-4 paragrafe: sentiment, mișcări notabile, ce a contat. Folosește datele reale.
5. DIVIDENDE — 2 paragrafe: oportunități curente, ce trebuie urmărit. Folosește datele reale.
6. GÂNDUL SĂPTĂMÂNII — un principiu de investiție relevant acum, 3-4 propoziții. Poate fi o lecție, o perspectivă.
7. DE URMĂRIT — 2-3 acțiuni sau sectoare pentru săptămâna viitoare, cu justificare scurtă.

Ton: serios, direct, fără bullet points excesive, în proză naturală. 450-600 cuvinte total.

Returnează DOAR JSON valid, fără text în afara JSON-ului:
{{
  "subject": "...",
  "title": "...",
  "intro": "...",
  "bvb_focus": "...",
  "dividende": "...",
  "gandul": "...",
  "de_urmarit": "..."
}}"""

    print("📡 Apelează Claude API...")
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
            "system": SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    raw = resp.json()["content"][0]["text"].strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw.strip())


# ── 4. HTML email template ────────────────────────────────────────────────────
def build_html(newsletter, unsubscribe_url, is_preview=False):
    preview_banner = """
    <tr>
      <td style="background:#FFB800;color:#080B0F;text-align:center;padding:10px;font-size:13px;font-weight:700">
        ⚠️ PREVIEW — Acesta este un draft. Nu a fost trimis abonaților.
        <a href="https://github.com" style="color:#080B0F;margin-left:16px;font-weight:400">→ Aprobă în GitHub Actions</a>
      </td>
    </tr>""" if is_preview else ""

    sections_html = ""

    if newsletter.get("bvb_focus"):
        sections_html += f"""
        <tr><td style="padding:0 0 28px">
          <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#00D4FF;margin-bottom:8px">BVB ÎN ACEASTĂ SĂPTĂMÂNĂ</div>
          <div style="font-size:15px;color:rgba(232,237,242,.88);line-height:1.8">{newsletter['bvb_focus'].replace(chr(10), '<br>')}</div>
        </td></tr>"""

    if newsletter.get("dividende"):
        sections_html += f"""
        <tr><td style="padding:0 0 28px">
          <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#00FF94;margin-bottom:8px">DIVIDENDE</div>
          <div style="font-size:15px;color:rgba(232,237,242,.88);line-height:1.8">{newsletter['dividende'].replace(chr(10), '<br>')}</div>
        </td></tr>"""

    if newsletter.get("gandul"):
        sections_html += f"""
        <tr><td style="padding:0 0 28px">
          <div style="background:rgba(0,212,255,.06);border-left:3px solid #00D4FF;border-radius:0 8px 8px 0;padding:18px 20px">
            <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#00D4FF;margin-bottom:8px">GÂNDUL SĂPTĂMÂNII</div>
            <div style="font-size:15px;color:rgba(232,237,242,.88);line-height:1.8;font-style:italic">{newsletter['gandul'].replace(chr(10), '<br>')}</div>
          </div>
        </td></tr>"""

    if newsletter.get("de_urmarit"):
        sections_html += f"""
        <tr><td style="padding:0 0 28px">
          <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#FFB800;margin-bottom:8px">DE URMĂRIT SĂPTĂMÂNA VIITOARE</div>
          <div style="font-size:15px;color:rgba(232,237,242,.88);line-height:1.8">{newsletter['de_urmarit'].replace(chr(10), '<br>')}</div>
        </td></tr>"""

    title = newsletter.get("title", f"Newsletter BVB — Săptămâna {WEEK_NUM}")
    intro = newsletter.get("intro", "")

    return f"""<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="dark"/>
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#080B0F;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Plus Jakarta Sans',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#080B0F">
  <tr><td align="center" style="padding:20px 16px">
    <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%">

      {preview_banner}

      <!-- HEADER -->
      <tr>
        <td style="background:#111820;border:1px solid #1E2A38;border-radius:12px 12px 0 0;padding:24px 32px;border-bottom:none">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td>
                <a href="https://www.ghidbursa.ro" style="text-decoration:none;font-size:20px;font-weight:800;color:#E8EDF2;letter-spacing:-.02em">
                  Ghid<span style="color:#00D4FF">Bursa</span>.ro
                </a>
                <div style="font-size:11px;color:#8A9BB0;margin-top:4px;letter-spacing:.05em;text-transform:uppercase">Newsletter BVB · Săptămâna {WEEK_NUM} · {TODAY_STR}</div>
              </td>
              <td align="right" style="vertical-align:top">
                <span style="background:rgba(0,255,148,.1);border:1px solid rgba(0,255,148,.25);color:#00FF94;font-size:10px;font-weight:700;padding:4px 10px;border-radius:20px;letter-spacing:.08em;text-transform:uppercase">
                  ● LIVE BVB
                </span>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- TITLE BAND -->
      <tr>
        <td style="background:linear-gradient(135deg,rgba(0,212,255,.08),rgba(0,255,148,.04));border:1px solid #1E2A38;border-top:none;border-bottom:none;padding:28px 32px">
          <div style="font-size:24px;font-weight:700;color:#E8EDF2;line-height:1.2;letter-spacing:-.01em">{title}</div>
          <div style="font-size:15px;color:rgba(232,237,242,.7);margin-top:10px;line-height:1.6">{intro}</div>
        </td>
      </tr>

      <!-- DIVIDER -->
      <tr>
        <td style="background:#111820;border-left:1px solid #1E2A38;border-right:1px solid #1E2A38;padding:0 32px">
          <div style="height:1px;background:linear-gradient(90deg,transparent,#1E2A38,transparent)"></div>
        </td>
      </tr>

      <!-- CONTENT -->
      <tr>
        <td style="background:#111820;border:1px solid #1E2A38;border-top:none;border-bottom:none;padding:28px 32px">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            {sections_html}
          </table>
        </td>
      </tr>

      <!-- CTA -->
      <tr>
        <td style="background:rgba(0,212,255,.04);border:1px solid #1E2A38;border-top:1px solid rgba(0,212,255,.15);border-bottom:none;padding:24px 32px;text-align:center">
          <div style="font-size:14px;color:#8A9BB0;margin-bottom:16px">Vrei să investești în acțiunile de pe BVB?</div>
          <a href="https://www.ghidbursa.ro/brokeri.html" style="display:inline-block;background:#00D4FF;color:#080B0F;font-weight:700;font-size:14px;padding:13px 28px;border-radius:8px;text-decoration:none;margin:0 6px">
            Compară brokeri BVB →
          </a>
          <a href="https://www.ghidbursa.ro/screener.html" style="display:inline-block;border:1px solid rgba(0,212,255,.3);color:#00D4FF;font-size:13px;padding:12px 20px;border-radius:8px;text-decoration:none;margin:0 6px">
            Screener acțiuni
          </a>
        </td>
      </tr>

      <!-- FOOTER -->
      <tr>
        <td style="background:#0D1117;border:1px solid #1E2A38;border-top:none;border-radius:0 0 12px 12px;padding:20px 32px;text-align:center">
          <div style="font-size:12px;color:#8A9BB0;line-height:1.7">
            Primești acest email pentru că te-ai abonat pe <a href="https://www.ghidbursa.ro" style="color:#00D4FF">ghidbursa.ro</a>.<br>
            Conținut exclusiv informativ — nu constituie consultanță financiară. Investițiile implică riscuri.<br><br>
            <a href="{unsubscribe_url}" style="color:#8A9BB0">Dezabonare</a>
            &nbsp;·&nbsp;
            <a href="https://www.ghidbursa.ro" style="color:#8A9BB0">GhidBursa.ro</a>
            &nbsp;·&nbsp;
            <a href="https://www.ghidbursa.ro/legal.html" style="color:#8A9BB0">Politică confidențialitate</a>
          </div>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


# ── 5. Trimite email ──────────────────────────────────────────────────────────
def send_email(to_email, subject, html, label=""):
    unsub = f"https://newsletter.ghidbursa.ro/unsubscribe?email={to_email}"
    # Replace placeholder in html
    html_final = html.replace("UNSUB_PLACEHOLDER", unsub)

    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json"},
        json={
            "from": "GhidBursa.ro <newsletter@ghidbursa.ro>",
            "to": [to_email],
            "subject": subject,
            "html": html_final,
        },
        timeout=15,
    )
    if resp.ok:
        print(f"  ✅ {label or to_email}")
    else:
        print(f"  ❌ {label or to_email}: {resp.text}")
    return resp.ok


# ── 6. Export abonați din Worker ──────────────────────────────────────────────
def get_subscribers():
    if not WORKER_URL or not EXPORT_SECRET:
        print("WARN: WORKER_URL sau EXPORT_SECRET lipsă — test mode")
        return []
    try:
        url = f"{WORKER_URL}/export?secret={EXPORT_SECRET}"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        lines = resp.text.strip().split("\n")
        # CSV: email,subscribed_at,unsubscribe_url
        subscribers = []
        for line in lines[1:]:  # skip header
            if line.strip():
                email = line.split(",")[0].strip()
                if "@" in email:
                    subscribers.append(email)
        print(f"📋 {len(subscribers)} abonați activi")
        return subscribers
    except Exception as e:
        print(f"ERROR export abonați: {e}")
        return []


# ── 7. Telegram ───────────────────────────────────────────────────────────────
def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHANNEL:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHANNEL, "text": text,
                  "parse_mode": "Markdown", "disable_web_page_preview": True},
            timeout=10,
        )
        print("✅ Telegram trimis")
    except Exception as e:
        print(f"WARN Telegram: {e}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true",
                        help="Generează + trimite preview la owner")
    parser.add_argument("--send", action="store_true",
                        help="Trimite la toți abonații (după aprobare)")
    args = parser.parse_args()

    if not args.preview and not args.send:
        print("Folosire: python weekly_newsletter.py --preview | --send")
        sys.exit(1)

    # ── PREVIEW MODE ──
    if args.preview:
        print(f"\n🔄 GhidBursa Newsletter — PREVIEW — {TODAY_STR}")
        print("=" * 50)

        stocks = load_stocks()
        fg     = load_fear_greed()
        ctx    = build_context(stocks, fg)

        newsletter = generate(ctx)
        print(f"\n📄 Subiect: {newsletter['subject']}")
        print(f"📰 Titlu: {newsletter['title']}")

        # Salvează draft
        with open(DRAFT_PATH, "w", encoding="utf-8") as f:
            json.dump(newsletter, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Draft salvat: {DRAFT_PATH}")

        # Construiește HTML preview
        unsub_preview = f"https://newsletter.ghidbursa.ro/unsubscribe?email={OWNER_EMAIL}"
        html = build_html(newsletter, unsub_preview, is_preview=True)
        html_with_unsub = html.replace("UNSUB_PLACEHOLDER", unsub_preview)

        # Trimite DOAR la owner
        print(f"\n📧 Trimite preview la {OWNER_EMAIL}...")
        subject_preview = f"[PREVIEW] {newsletter['subject']}"
        send_email(OWNER_EMAIL, subject_preview, html_with_unsub, "Owner preview")

        # Notificare Telegram
        tg_text = (
            f"📨 *Newsletter săptămânal generat — Săptămâna {WEEK_NUM}*\n\n"
            f"📌 Subiect: _{newsletter['subject']}_\n\n"
            f"✅ Preview trimis la {OWNER_EMAIL}\n\n"
            f"▶️ *Pentru a trimite la toți abonații:*\n"
            f"GitHub → Actions → Weekly Newsletter → Run workflow → Send"
        )
        send_telegram(tg_text)

        print(f"\n✅ Preview gata! Verifică {OWNER_EMAIL}")
        print("▶️  Pentru a trimite: GitHub Actions → Run workflow → mode: send")

    # ── SEND MODE ──
    elif args.send:
        print(f"\n🚀 GhidBursa Newsletter — SEND — {TODAY_STR}")
        print("=" * 50)

        # Încearcă să citească draft-ul salvat
        newsletter = None
        if os.path.exists(DRAFT_PATH):
            print("📂 Folosesc draft-ul salvat...")
            with open(DRAFT_PATH, encoding="utf-8") as f:
                newsletter = json.load(f)
        else:
            print("📂 Draft lipsă — regenerez newsletter...")
            stocks = load_stocks()
            fg     = load_fear_greed()
            ctx    = build_context(stocks, fg)
            newsletter = generate(ctx)

        print(f"📄 Subiect: {newsletter['subject']}")

        # Export abonați
        subscribers = get_subscribers()
        if not subscribers:
            print("❌ Niciun abonat găsit. Verifică WORKER_URL și EXPORT_SECRET.")
            sys.exit(1)

        # Trimite la fiecare abonat
        print(f"\n📤 Trimitere la {len(subscribers)} abonați...")
        sent = failed = 0
        for email in subscribers:
            unsub = f"https://newsletter.ghidbursa.ro/unsubscribe?email={email}"
            html  = build_html(newsletter, unsub, is_preview=False)
            html  = html.replace("UNSUB_PLACEHOLDER", unsub)
            ok    = send_email(email, newsletter["subject"], html, email)
            if ok:
                sent += 1
            else:
                failed += 1
            time.sleep(0.1)  # evită rate limiting Resend

        # Raport final
        print(f"\n📊 Rezultat: {sent} trimise, {failed} eșuate din {len(subscribers)}")

        # Telegram confirmare
        tg_text = (
            f"✅ *Newsletter trimis — Săptămâna {WEEK_NUM}*\n\n"
            f"📌 _{newsletter['subject']}_\n\n"
            f"📊 {sent}/{len(subscribers)} emailuri trimise cu succes"
        )
        send_telegram(tg_text)


if __name__ == "__main__":
    main()
