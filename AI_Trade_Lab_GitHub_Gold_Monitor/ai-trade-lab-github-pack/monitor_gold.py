import csv
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CSV_PATH = DATA_DIR / "gold_15m.csv"
JSON_PATH = DATA_DIR / "latest_analysis.json"
SYMBOL = "XAUUSD=X"  # Yahoo Finance indicative spot-gold ticker; may be unavailable or delayed.
INTERVAL = "15m"
RANGE = "5d"
FIELDS = ["timestamp", "open", "high", "low", "close", "volume"]


def fetch_candles():
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}"
    response = requests.get(
        url,
        params={"range": RANGE, "interval": INTERVAL, "events": "history"},
        headers={"User-Agent": "Mozilla/5.0 AI-Trade-Lab/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        error = payload.get("chart", {}).get("error")
        raise RuntimeError(f"Yahoo Finance returned no chart data: {error}")
    timestamps = result.get("timestamp") or []
    quote_list = result.get("indicators", {}).get("quote") or [{}]
    quote = quote_list[0]
    rows = []
    for i, ts in enumerate(timestamps):
        values = {k: (quote.get(k) or [None] * len(timestamps))[i] for k in ("open", "high", "low", "close", "volume")}
        if any(values[k] is None for k in ("open", "high", "low", "close")):
            continue
        rows.append({
            "timestamp": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
            "open": float(values["open"]), "high": float(values["high"]),
            "low": float(values["low"]), "close": float(values["close"]),
            "volume": int(values["volume"] or 0),
        })
    if len(rows) < 55:
        raise RuntimeError(f"Not enough candles returned ({len(rows)}); need at least 55. Source may be unavailable.")
    return rows


def ema(values, period):
    alpha = 2 / (period + 1)
    current = values[0]
    out = []
    for value in values:
        current = alpha * value + (1 - alpha) * current
        out.append(current)
    return out


def rsi(values, period=14):
    if len(values) <= period:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))


def atr(rows, period=14):
    trs = []
    for i, row in enumerate(rows):
        if i == 0:
            trs.append(row["high"] - row["low"])
        else:
            prev_close = rows[i - 1]["close"]
            trs.append(max(row["high"] - row["low"], abs(row["high"] - prev_close), abs(row["low"] - prev_close)))
    if len(trs) < period:
        return None
    current = sum(trs[:period]) / period
    for tr in trs[period:]:
        current = (current * (period - 1) + tr) / period
    return current


def read_existing():
    if not CSV_PATH.exists():
        return {}
    with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
        return {row["timestamp"]: row for row in csv.DictReader(f)}


def save_rows(rows):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = read_existing()
    for row in rows:
        existing[row["timestamp"]] = {k: str(row[k]) for k in FIELDS}
    ordered = sorted(existing.values(), key=lambda r: r["timestamp"])
    # Keep the last 10,000 candles to prevent the repository file growing without bound.
    ordered = ordered[-10000:]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(ordered)
    return ordered


def send_telegram(text):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("Telegram secrets not configured; skipping notification.")
        return False
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(f"Telegram API error {response.status_code}: {response.text[:300]}")
    return True


def main():
    rows = fetch_candles()
    existing = read_existing()
    latest = rows[-1]
    is_new = latest["timestamp"] not in existing
    saved = save_rows(rows)
    closes = [r["close"] for r in rows]
    ema20 = ema(closes, 20)[-1]
    ema50 = ema(closes, 50)[-1]
    rsi14 = rsi(closes, 14)
    atr14 = atr(rows, 14)
    previous_close = rows[-2]["close"]
    change_pct = ((latest["close"] / previous_close) - 1) * 100 if previous_close else 0
    bias = "BULLISH" if latest["close"] > ema20 > ema50 else ("BEARISH" if latest["close"] < ema20 < ema50 else "MIXED")
    analysis = {
        "source": "Yahoo Finance chart endpoint",
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "note": "Indicative data only; not guaranteed to match your broker's XAUUSD quote. This is technical monitoring, not a trade instruction.",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "latest_candle": latest,
        "candle_is_new_since_last_run": is_new,
        "candles_stored": len(saved),
        "indicators": {
            "ema20": round(ema20, 5), "ema50": round(ema50, 5),
            "rsi14": round(rsi14, 2) if rsi14 is not None else None,
            "atr14": round(atr14, 5) if atr14 is not None else None,
            "change_from_previous_candle_pct": round(change_pct, 4),
            "trend_bias": bias,
        },
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    print(json.dumps(analysis, indent=2))
    # Send only when a new 15-minute candle appears, to avoid repeated messages on every run.
    if is_new:
        msg = (
            f"AI Trade Lab | Gold monitor\n"
            f"Symbol: {SYMBOL} (indicative)\n"
            f"Close: {latest['close']:.3f}\n"
            f"Trend: {bias}\n"
            f"RSI(14): {rsi14:.1f}\n"
            f"EMA20 / EMA50: {ema20:.3f} / {ema50:.3f}\n"
            f"ATR(14): {atr14:.3f}\n"
            f"15m change: {change_pct:+.3f}%\n"
            f"Candle time: {latest['timestamp']}\n"
            "Monitoring only; not a buy/sell instruction."
        )
        send_telegram(msg)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        # Try to notify about failures if Telegram is configured; don't mask the original failure.
        try:
            send_telegram(f"AI Trade Lab gold monitor failed: {exc}")
        except Exception as notify_exc:
            print(f"Telegram error notification failed: {notify_exc}", file=sys.stderr)
        raise
