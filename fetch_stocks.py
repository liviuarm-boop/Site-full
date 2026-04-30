#!/usr/bin/env python3
"""
GhidBursa.ro — fetch_stocks.py v3
Trage date din Yahoo Finance pentru toate acțiunile BVB.
Include: P/E, dividend yield, capitalizare, EPS, YTD, preț
         + ISTORIC DIVIDENDE (ultimii 5 ani): ex-date, suma/acțiune, randament la plată
"""

import json, datetime, math, os, subprocess, sys

subprocess.run([sys.executable, "-m", "pip", "install", "yfinance", "--quiet"], check=True)
import yfinance as yf

STOCKS = {
    "TLV":  "TLV.RO",  "SNP":  "SNP.RO",  "H2O":  "H2O.RO",
    "SNG":  "SNG.RO",  "TGN":  "TGN.RO",  "TEL":  "TEL.RO",
    "BRD":  "BRD.RO",  "FP":   "FP.RO",   "DIGI": "DIGI.RO",
    "ONE":  "ONE.RO",  "EL":   "EL.RO",   "M":    "M.RO",
    "SFG":  "SFG.RO",  "TTS":  "TTS.RO",  "COTE": "COTE.RO",
    "AQ":   "AQ.RO",   "WINE": "WINE.RO", "TRP":  "TRP.RO",
    "BVB":  "BVB.RO",  "ALR":  "ALR.RO",
}

def safe_round(val, dec=2):
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, dec)
    except Exception:
        return None

def calc_ytd(hist):
    try:
        jan1 = datetime.date(datetime.date.today().year, 1, 1)
        h = hist[hist.index.date >= jan1]
        if len(h) < 2:
            return None
        first = float(h["Close"].iloc[0])
        last  = float(h["Close"].iloc[-1])
        if first <= 0:
            return None
        ytd = round(((last - first) / first) * 100, 1)
        if abs(ytd) > 200:
            return None
        return ytd
    except Exception:
        return None

def fix_div_yield(raw_yield):
    val = safe_round(raw_yield, 2)
    if val is None:
        return None
    if val < 1.0:
        val = round(val * 100, 1)
    if val > 30.0:
        return None
    return val

def get_div_history(ticker_obj, hist_5y):
    try:
        divs = ticker_obj.dividends
        if divs is None or len(divs) == 0:
            return []

        cutoff = datetime.date.today() - datetime.timedelta(days=5 * 365)
        result = []

        for ex_dt, amount in divs.items():
            try:
                ex_date = ex_dt.date() if hasattr(ex_dt, 'date') else ex_dt
            except Exception:
                continue

            if ex_date < cutoff:
                continue

            amt = safe_round(float(amount), 4)
            if amt is None or amt <= 0:
                continue

            yield_pct = None
            try:
                hist_slice = hist_5y[hist_5y.index.date <= ex_date]
                if len(hist_slice) > 0:
                    price = float(hist_slice["Close"].iloc[-1])
                    if price > 0:
                        yp = round((amt / price) * 100, 2)
                        if yp <= 50.0:
                            yield_pct = yp
            except Exception:
                pass

            result.append({
                "ex_date":   ex_date.isoformat(),
                "amount":    amt,
                "yield_pct": yield_pct,
            })

        result.sort(key=lambda x: x["ex_date"], reverse=True)
        return result

    except Exception as e:
        print(f"  [div_history error: {e}]")
        return []


def generate_screener_schema(results, today):
    """Generează ItemList schema pentru screener cu date reale din Yahoo Finance."""
    import json as _json

    # Sort by market cap descending for ranking
    ranked = sorted(
        [(t, s) for t, s in results.items() if s.get("market_cap_bln")],
        key=lambda x: x[1]["market_cap_bln"] or 0,
        reverse=True
    )

    NAMES = {
        "TLV": "Banca Transilvania", "SNP": "OMV Petrom", "H2O": "Hidroelectrica",
        "SNG": "Romgaz", "TGN": "Transgaz", "TEL": "Transelectrica",
        "BRD": "BRD Groupe SG", "FP": "Fondul Proprietatea", "DIGI": "Digi Communications",
        "ONE": "One United Properties", "EL": "Electrica", "M": "MedLife",
        "SFG": "Sphera Franchise Group", "TTS": "Transport Trade Services",
        "COTE": "Conpet", "AQ": "Aquila", "WINE": "Purcari Wineries",
        "TRP": "TeraPlast", "BVB": "Bursa de Valori București", "ALR": "Alro",
    }

    items = []
    for i, (ticker, s) in enumerate(ranked[:20], 1):
        desc_parts = [f"Capitalizare {s['market_cap_bln']:.1f} mld RON."]
        if s.get("pe"):
            desc_parts.append(f"P/E {s['pe']:.1f}x.")
        if s.get("div_yield"):
            desc_parts.append(f"Randament dividend {s['div_yield']:.1f}%.")
        if s.get("ytd") is not None:
            sign = "+" if s["ytd"] >= 0 else ""
            desc_parts.append(f"YTD {sign}{s['ytd']:.1f}%.")
        desc_parts.append(f"Date reale Yahoo Finance, actualizate {today}.")

        items.append({
            "@type": "ListItem",
            "position": i,
            "name": f"{NAMES.get(ticker, ticker)} ({ticker})",
            "url": f"https://www.ghidbursa.ro/actiune-{ticker.lower()}.html",
            "description": " ".join(desc_parts)
        })

    schema = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"Top acțiuni BVB după capitalizare bursieră — {today}",
        "description": "Lista principalelor companii listate la Bursa de Valori București, cu date fundamentale reale actualizate zilnic din Yahoo Finance.",
        "url": "https://www.ghidbursa.ro/screener.html",
        "numberOfItems": len(items),
        "itemListElement": items
    }

    os.makedirs("data", exist_ok=True)
    with open("data/screener_schema.json", "w", encoding="utf-8") as f:
        _json.dump(schema, f, ensure_ascii=False, indent=2)
    print(f"Salvat data/screener_schema.json — {len(items)} items cu date reale")


def main():
    results = {}
    today = datetime.date.today().isoformat()
    print(f"Fetching {len(STOCKS)} stocks — {today}\n")

    for ticker, symbol in STOCKS.items():
        print(f"  {ticker}...", end=" ", flush=True)
        try:
            t       = yf.Ticker(symbol)
            info    = t.info
            hist_5y = t.history(period="5y")

            div_yield   = fix_div_yield(info.get("dividendYield"))
            cap_raw     = info.get("marketCap")
            div_history = get_div_history(t, hist_5y)

            # Extract last dividend from history for schema use
            last_div = div_history[0] if div_history else {}

            results[ticker] = {
                "ticker":           ticker,
                "pe":               safe_round(info.get("trailingPE"), 1),
                "div_yield":        div_yield,
                "div_per_share":    safe_round(info.get("lastDividendValue") or info.get("dividendRate"), 4),
                "market_cap_bln":   round(cap_raw / 1e9, 1) if cap_raw else None,
                "eps":              safe_round(info.get("trailingEps"), 2),
                "ytd":              calc_ytd(hist_5y),
                "price":            safe_round(info.get("regularMarketPrice") or info.get("currentPrice"), 2),
                "div_history":      div_history,
                "last_div_amount":  last_div.get("amount"),
                "last_div_ex_date": last_div.get("ex_date"),
                "last_div_yield":   last_div.get("yield_pct"),
                "updated":          today,
            }
            s = results[ticker]
            print(f"P/E={s['pe']} Div={s['div_yield']}% Cap={s['market_cap_bln']}mld YTD={s['ytd']}% DivHist={len(div_history)}")

        except Exception as e:
            print(f"ERROR: {e}")
            results[ticker] = {
                "ticker": ticker, "pe": None, "div_yield": None,
                "div_per_share": None, "market_cap_bln": None,
                "eps": None, "ytd": None, "price": None,
                "div_history": [], "updated": today
            }

    os.makedirs("data", exist_ok=True)
    with open("data/stocks.json", "w", encoding="utf-8") as f:
        json.dump({"updated": today, "stocks": results}, f, ensure_ascii=False, indent=2)

    ok     = sum(1 for s in results.values() if s.get("pe") or s.get("div_yield"))
    div_ok = sum(1 for s in results.values() if s.get("div_history"))
    print(f"\nSalvat data/stocks.json — {ok}/{len(results)} fundamentale, {div_ok}/{len(results)} cu istoric dividende")

if __name__ == "__main__":
    main()
