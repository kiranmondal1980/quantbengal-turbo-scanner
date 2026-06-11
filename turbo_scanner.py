import os
import sys
import time
import logging
import requests
import yfinance as yf
import pandas as pd       # <--- ADD THIS LINE HERE
from indicators import apply_turbo_indicators

# Configure Professional Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("TurboScanner")

# Constants & Configuration
SYMBOLS = {
    "BANKNIFTY": "^NSEBANK",
    "NIFTY": "^NSEI",
    "CRUDE_OIL": "CL=F",
    "GOLD": "GC=F"
}
MAX_RUNTIME_SEC = (5 * 3600) + (50 * 60)  # 5 hours 50 mins
POLL_INTERVAL_SEC = 60
COOLDOWN_SEC = 300  # 5 minutes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# State Management
last_alert_time = {ticker: 0.0 for ticker in SYMBOLS.values()}

def send_telegram_alert(message: str):
    """Asynchronously deliver alerts via Telegram Bot API."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials missing. Printing to console instead.")
        print(message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Telegram API Error: {e}")

def fetch_data_with_retry(ticker: str, retries=3) -> pd.DataFrame:
    """Robust yfinance fetching with exponential backoff."""
    for attempt in range(retries):
        try:
            df = yf.download(ticker, period="2d", interval="1m", progress=False)
            if not df.empty:
                return df
        except Exception as e:
            logger.warning(f"[{ticker}] YFinance fetch error: {e}. Retrying...")
        time.sleep(5 * (attempt + 1))
    return pd.DataFrame()

def process_symbol(name: str, ticker: str, current_time: float):
    """Fetches data, calculates indicators, and evaluates the Turbo Scalp strategy."""
    df = fetch_data_with_retry(ticker)
    if df.empty or len(df) < 200:
        return # Not enough data for 200 EMA

    # Flatten yfinance MultiIndex columns if present (yfinance >= 0.2.31 behavior)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = apply_turbo_indicators(df)
    latest = df.iloc[-1]
    
    price = latest['Close']
    vwap = latest['VWAP']
    ema_9 = latest['EMA_9']
    ema_200 = latest['EMA_200']
    rsi_2 = latest['RSI_2']
    
    # Ensure no NaN values in our logic checks
    if pd.isna(price) or pd.isna(ema_200) or pd.isna(vwap) or pd.isna(rsi_2):
        return

    signal = None
    # BULLISH: Deep pullback in strong uptrend
    if (price > ema_200) and (price < vwap) and (rsi_2 < 10):
        signal = "🟢 <b>BULLISH SCALP</b>"
    
    # BEARISH: Dead cat bounce in strong downtrend
    elif (price < ema_200) and (price > vwap) and (rsi_2 > 90):
        signal = "🔴 <b>BEARISH SCALP</b>"

    # Alert generation and anti-spam check
    if signal and (current_time - last_alert_time[ticker] >= COOLDOWN_SEC):
        msg = (
            f"{signal} | <b>{name}</b>\n\n"
            f"<b>Price:</b> {price:.2f}\n"
            f"<b>VWAP:</b> {vwap:.2f}\n"
            f"<b>200 EMA:</b> {ema_200:.2f}\n"
            f"<b>RSI(2):</b> {rsi_2:.2f}\n\n"
            f"🎯 <b>Target/Exit:</b> Touch of 9 EMA ({ema_9:.2f})"
        )
        send_telegram_alert(msg)
        logger.info(f"ALERT TRIGGERED for {name}: {signal.replace('<b>','').replace('</b>','')}")
        last_alert_time[ticker] = current_time

def main():
    logger.info("Initializing QuantBengal Turbo-Scanner...")
    start_time = time.monotonic()

    while True:
        loop_start = time.monotonic()
        
        # 1. Check max runtime constraint
        elapsed = loop_start - start_time
        if elapsed >= MAX_RUNTIME_SEC:
            logger.info(f"Graceful exit limit reached ({MAX_RUNTIME_SEC}s). Shutting down.")
            sys.exit(0)

        # 2. Process all symbols
        for name, ticker in SYMBOLS.items():
            process_symbol(name, ticker, loop_start)

        # 3. Synchronize loop execution to exactly 60 seconds
        execution_time = time.monotonic() - loop_start
        sleep_time = max(0.0, POLL_INTERVAL_SEC - execution_time)
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()
