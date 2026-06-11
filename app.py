import streamlit as st
import pandas as pd
import yfinance as yf
import time
from datetime import datetime
from indicators import apply_turbo_indicators

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="QuantBengal Turbo-Scanner", page_icon="🐅", layout="wide")

# --- ASSET DICTIONARY ---
AVAILABLE_ASSETS = {
    "NIFTY 50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
    "CRUDE OIL": "CL=F",
    "GOLD": "GC=F"
}

# --- CACHED DATA FETCHING ---
# We cache the data for 60 seconds to prevent hitting Yahoo Finance limits
@st.cache_data(ttl=60)
def fetch_and_analyze(ticker: str) -> dict:
    try:
        df = yf.download(ticker, period="2d", interval="1m", progress=False)
        if df.empty or len(df) < 200:
            return {"error": "Not enough data"}

        # Flatten columns if multi-index (yfinance update)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = apply_turbo_indicators(df)
        latest = df.iloc[-1]

        price = float(latest['Close'])
        vwap = float(latest['VWAP'])
        ema_9 = float(latest['EMA_9'])
        ema_200 = float(latest['EMA_200'])
        rsi_2 = float(latest['RSI_2'])

        # Signal Logic
        signal = "⚪ NEUTRAL"
        color = "white"
        if (price > ema_200) and (price < vwap) and (rsi_2 < 10):
            signal = "🟢 BUY (Deep Pullback)"
            color = "#00FF00"
        elif (price < ema_200) and (price > vwap) and (rsi_2 > 90):
            signal = "🔴 SELL (Dead Cat Bounce)"
            color = "#FF0000"

        return {
            "Price": price, "VWAP": vwap, "EMA_9": ema_9, "EMA_200": ema_200, 
            "RSI_2": rsi_2, "Signal": signal, "Color": color
        }
    except Exception as e:
        return {"error": str(e)}

# --- WEB INTERFACE LAYOUT ---
st.title("🐅 QuantBengal Turbo-Scanner")
st.markdown("### Real-Time HFT Scalping Dashboard")

# Sidebar Controls
st.sidebar.header("⚙️ Dashboard Controls")
selected_assets = st.sidebar.multiselect(
    "Select Assets to Monitor:",
    options=list(AVAILABLE_ASSETS.keys()),
    default=["NIFTY 50", "BANKNIFTY", "SENSEX"]
)

auto_refresh = st.sidebar.checkbox("Enable Auto-Refresh (60s)", value=False)

if not selected_assets:
    st.warning("👈 Please select at least one asset from the sidebar to begin monitoring.")
    st.stop()

# --- DISPLAY METRICS ---
# Create columns dynamically based on how many assets are selected
cols = st.columns(len(selected_assets))

for i, asset_name in enumerate(selected_assets):
    ticker = AVAILABLE_ASSETS[asset_name]
    with cols[i]:
        st.subheader(asset_name)
        
        with st.spinner(f"Analyzing {asset_name}..."):
            data = fetch_and_analyze(ticker)

        if "error" in data:
            st.error(f"Data Error: Market Closed or API limit. ({data['error']})")
        else:
            # Display Signal prominently
            st.markdown(f"<h3 style='text-align: center; color: {data['Color']};'>{data['Signal']}</h3>", unsafe_allow_html=True)
            
            # Display core metrics
            st.metric(label="LTP (Current Price)", value=f"₹{data['Price']:.2f}")
            st.metric(label="VWAP", value=f"₹{data['VWAP']:.2f}")
            st.metric(label="RSI (2)", value=f"{data['RSI_2']:.1f}")
            
            # Target / Status details
            st.markdown("---")
            st.markdown(f"**200 EMA (Trend):** ₹{data['EMA_200']:.2f}")
            st.markdown(f"**9 EMA (Target):** ₹{data['EMA_9']:.2f}")

st.sidebar.markdown("---")
st.sidebar.write(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

# Auto-refresh logic
if auto_refresh:
    time.sleep(60)
    st.rerun()
