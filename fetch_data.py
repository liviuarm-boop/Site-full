#!/usr/bin/env python3
"""
BVB Fear & Greed Index Calculator v3
- BET index: Stooq.com (bet.xb)
- Components: Yahoo Finance (.RO)
- Fallback: reconstruct BET from weighted components
"""
import json, datetime, sys, io, os, urllib.request
import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance not installed", file=sys.stderr)
    sys.exit(1)

STOOQ_BET = "https://stooq.com/q/d/l/?s=bet.xb&i=d"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

COMPONENTS = {
    "H2O.RO": 0.22, "TLV.RO": 0.18, "SNP.RO": 0.12, "SNG.RO": 0.10,
    "SNN.RO": 0.08, "BRD.RO": 0.07, "EL.RO":  0.06, "TGN.RO": 0.04,
    "TEL.RO": 0.03, "DIGI.RO":0.03, "M.RO":   0.02, "ONE.RO": 0.02,
    "TTS.RO": 0.02, "FP.RO":  0.01,
}

# Output path — always write to repo root regardless of where script lives
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "scripts" else SCRIPT_DIR
OUTPUT_PATH = os.path.join(REPO_ROOT, "score.json")

def dl_stooq():
    try:
        req = urllib.request.Request(STOOQ_BET, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8")
        df = pd.read_csv(io.StringIO(raw), parse_dates=["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        if len(df) < 10:
            return None
        close = df.set_index("Date")["Close"]
        print(f"  + Stooq BET: {len(close)} zile, last={close.iloc[-1]:.2f}")
        return close
    except Exception as e:
        print(f"  - Stooq failed: {e}", file=sys.stderr)
        return None

def dl_yf(ticker, period="9mo"):
    try:
        df = yf.download(ticker, period=period, progress=False, timeout=30, auto_adjust=True)
        if df is None or len(df) < 10:
            return None
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"  - {ticker}: {e}", file=sys.stderr)
        return None

def reconstruct_bet(stocks):
    series_list, weights_list = [], []
    for ticker, weight in COMPONENTS.items():
        df = stocks.get(ticker)
        if df is None or len(df) < 50:
            continue
        norm = df["Close"] / df["Close"].iloc[0]
        series_list.append(norm)
        weights_list.append(weight)
    if not series_list:
        return None
    combined = pd.concat(series_list, axis=1).dropna()
    if len(combined) < 50:
        return None
    w = np.array(weights_list[:len(series_list)])
    w = w / w.sum()
    result = pd.Series(combined.values @ w, index=combined.index) * 100
    print(f"  + BET reconstructed from {len(series_list)} components: {len(result)} days")
    return result

def momentum(close, n=125):
    if close is None or len(close) < n:
        return None, {}
    p   = float(close.iloc[-1])
    sma = float(close.iloc[-n:].mean())
    pct = (p - sma) / sma * 100
    score = round(float(np.clip((pct + 30) / 60 * 100, 0, 100)), 1)
    return score, {"price": round(p, 2), "sma_125": round(sma, 2), "pct_vs_sma": round(pct, 2)}

def volatility(close, n=20):
    if close is None or len(close) < n + 1:
        return None, {}
    ann = float(close.pct_change().dropna().iloc[-n:].std()) * (252 ** 0.5) * 100
    score = round(float(np.clip((40 - ann) / 35 * 100, 0, 100)), 1)
    return score, {"annualized_vol_pct": round(ann, 2)}

def breadth(stocks, n=50):
    above = total = 0
    for df in stocks.values():
        if df is None or len(df) < n:
            continue
        c = df["Close"]
        if float(c.iloc[-1]) > float(c.iloc[-n:].mean()):
            above += 1
        total += 1
    if not total:
        return None, {}
    return round(above / total * 100, 1), {"above_sma50": above, "total_stocks": total}

def label_ro(s):
    if s is None: return "N/A"
    if s <= 20:   return "Frica extrema"
    if s <= 40:   return "Frica"
    if s <= 60:   return "Neutru"
    if s <= 80:   return "Lacomie"
    return "Lacomie extrema"

def label_en(s):
    if s is None: return "N/A"
    if s <= 20:   return "Extreme Fear"
    if s <= 40:   return "Fear"
    if s <= 60:   return "Neutral"
    if s <= 80:   return "Greed"
    return "Extreme Greed"

def main():
    print("=" * 55)
    print("BVB Fear & Greed v3")
    print(f"Output: {OUTPUT_PATH}")
    print("=" * 55)

    # Step 1: Download component stocks
    print("\n[1] Downloading BET components from Yahoo Finance...")
    stocks = {}
    for t in COMPONENTS:
        df = dl_yf(t)
        stocks[t] = df
        status = f"{len(df)} rows" if df is not None else "FAILED"
        print(f"  {'OK' if df is not None else 'FAIL'} {t}: {status}")
    ok = sum(1 for v in stocks.values() if v is not None)
    print(f"  Downloaded: {ok}/{len(COMPONENTS)}")

    # Step 2: Get BET index
    print("\n[2] Downloading BET index from Stooq...")
    bet = dl_stooq()
    bet_source = "stooq"
    if bet is None:
        print("  Stooq failed, reconstructing from components...")
        bet = reconstruct_bet(stocks)
        bet_source = "reconstructed"
    if bet is None:
        bet_source = "unavailable"

    # Step 3: Calculate indicators
    print("\n[3] Calculating indicators...")
    ms, md = momentum(bet)
    vs, vd = volatility(bet)
    bs, bd = breadth(stocks)
    print(f"  Momentum:    {ms} ({label_ro(ms)})")
    print(f"  Volatility:  {vs} ({label_ro(vs)})")
    print(f"  Breadth:     {bs} ({label_ro(bs)})")

    # Step 4: Composite score
    if ms is not None and vs is not None and bs is not None:
        method = "3 indicators"
        valid = [(ms, 0.40), (vs, 0.30), (bs, 0.30)]
    elif ok >= 5:
        # Fallback: use only breadth if BET unavailable
        method = "breadth only (BET unavailable)"
        valid = [(bs, 1.0)] if bs is not None else []
    else:
        method = "insufficient data"
        valid = []

    if valid:
        total_w = sum(wt for _, wt in valid)
        comp = round(sum(s * wt for s, wt in valid) / total_w, 1)
    else:
        comp = None

    print(f"\n  SCORE: {comp} ({label_ro(comp)}) [{method}]")

    # Step 5: Write output
    out = {
        "score":      comp,
        "label_ro":   label_ro(comp),
        "label_en":   label_en(comp),
        "updated":    datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_ro": datetime.datetime.now().strftime("%d %b %Y"),
        "method":     method,
        "indicators": {
            "momentum":   {"score": ms, "label": label_ro(ms), "weight": "40%",
                           "description": "BET price vs 125-day SMA", **md},
            "volatility": {"score": vs, "label": label_ro(vs), "weight": "30%",
                           "description": "Annualized 20-day volatility", **vd},
            "breadth":    {"score": bs, "label": label_ro(bs), "weight": "30%",
                           "description": "% BET stocks above 50-day SMA", **bd},
        },
        "data_quality": {
            "bet_source":       bet_source,
            "bet_days":         len(bet) if bet is not None else 0,
            "components_ok":    ok,
            "components_total": len(COMPONENTS),
        },
        "disclaimer": "Orientativ. Nu constituie consultanta financiara.",
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\nWritten: {OUTPUT_PATH}")

    if comp is None:
        print("ERROR: score is null - not enough data", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
