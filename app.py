import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from indicators import apply_turbo_indicators

st.set_page_config(page_title="Pro Algo Terminal | Low Risk", page_icon="🛡️", layout="wide")

AVAILABLE_ASSETS = {
    "BANKNIFTY": "^NSEBANK",
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "CRUDE OIL": "CL=F",
    "GOLD": "GC=F"
}

@st.cache_data(ttl=60)
def fetch_and_calculate(ticker: str):
    # CHANGED: Now pulling 5-minute data for stability and larger targets
    df = yf.download(ticker, period="5d", interval="5m", progress=False)
    if df.empty or len(df) < 200:
        return None
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = apply_turbo_indicators(df)
    
    df['Signal'] = 0 
    
    # 🟢 LOW RISK BUY: Above 200 EMA, Above VWAP, and 9 EMA crosses UP over 21 EMA
    buy_condition = (
        (df['Close'] > df['EMA_200']) & 
        (df['Close'] > df['VWAP']) & 
        (df['EMA_9'] > df['EMA_21']) & 
        (df['EMA_9'].shift(1) <= df['EMA_21'].shift(1)) # Exact moment of crossover
    )
    
    # 🔴 LOW RISK SELL: Below 200 EMA, Below VWAP, and 9 EMA crosses DOWN under 21 EMA
    sell_condition = (
        (df['Close'] < df['EMA_200']) & 
        (df['Close'] < df['VWAP']) & 
        (df['EMA_9'] < df['EMA_21']) & 
        (df['EMA_9'].shift(1) >= df['EMA_21'].shift(1)) # Exact moment of crossover
    )
    
    df.loc[buy_condition, 'Signal'] = 1
    df.loc[sell_condition, 'Signal'] = -1
    
    return df

def plot_professional_chart(df, asset_name):
    # Zoom in on the last 75 candles (roughly 1 trading day on 5m chart)
    df_plot = df.tail(75)
    fig = go.Figure()

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], 
        low=df_plot['Low'], close=df_plot['Close'], name='Price'
    ))

    # Safe Trend Indicators
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['VWAP'], line=dict(color='orange', width=2), name='VWAP'))
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['EMA_200'], line=dict(color='white', width=2), name='200 EMA'))
    
    # Crossover Indicators
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['EMA_9'], line=dict(color='cyan', width=1), name='9 EMA'))
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['EMA_21'], line=dict(color='magenta', width=1), name='21 EMA'))

    buy_signals = df_plot[df_plot['Signal'] == 1]
    sell_signals = df_plot[df_plot['Signal'] == -1]

    if not buy_signals.empty:
        fig.add_trace(go.Scatter(
            x=buy_signals.index, y=buy_signals['Low'] - 10,
            mode='markers', marker=dict(symbol='triangle-up', color='lime', size=16, line=dict(color='black', width=1)), name='BUY Entry'
        ))
    if not sell_signals.empty:
        fig.add_trace(go.Scatter(
            x=sell_signals.index, y=sell_signals['High'] + 10,
            mode='markers', marker=dict(symbol='triangle-down', color='red', size=16, line=dict(color='black', width=1)), name='SELL Entry'
        ))

    fig.update_layout(
        title=f"5-Minute Trend Strategy: {asset_name}",
        template="plotly_dark", xaxis_rangeslider_visible=False, height=600, margin=dict(l=0, r=0, t=40, b=0)
    )
    return fig

# --- UI LAYOUT ---
st.sidebar.title("🛡️ Risk Managed Algo")
selected_asset = st.sidebar.selectbox("Select Asset to Trade:", list(AVAILABLE_ASSETS.keys()))
ticker = AVAILABLE_ASSETS[selected_asset]

# Dynamic Point System (Indices use 50pts, Commodities use ATR based math)
TARGET_POINTS = 50.0 if "NIFTY" in selected_asset or "SENSEX" in selected_asset else 0.5
STOP_LOSS_POINTS = TARGET_POINTS / 2  # Strict 1:2 Risk Reward

if st.sidebar.button("🔄 Refresh Data Now"):
    st.cache_data.clear()

st.title(f"📊 Low-Risk Terminal: {selected_asset}")
st.markdown(f"**Strategy:** 5-Min Trend Confirmation | **Target:** +{TARGET_POINTS} pts | **Stop Loss:** -{STOP_LOSS_POINTS} pts")

with st.spinner("Fetching 5m Data & Scanning for Golden Crosses..."):
    df = fetch_and_calculate(ticker)

if df is None:
    st.error("Market is closed or not enough data.")
    st.stop()

latest = df.iloc[-1]
current_price = latest['Close']

signal_status = "⚪ NEUTRAL - Waiting for EMA Crossover..."
signal_color = "gray"
target_price = 0.0
stop_loss = 0.0
action = "None"

if latest['Signal'] == 1:
    signal_status = "🟢 CONFIRMED BUY (Trend Breakout UP)"
    signal_color = "#00FF00"
    action = "BUY"
    target_price = current_price + TARGET_POINTS
    stop_loss = current_price - STOP_LOSS_POINTS
elif latest['Signal'] == -1:
    signal_status = "🔴 CONFIRMED SELL (Trend Breakdown DOWN)"
    signal_color = "#FF0000"
    action = "SELL"
    target_price = current_price - TARGET_POINTS
    stop_loss = current_price + STOP_LOSS_POINTS

# Dashboard
st.markdown(f"""
    <div style="background-color: #1E1E1E; padding: 20px; border-radius: 10px; border: 1px solid {signal_color};">
        <h3 style="margin-top:0px; color:{signal_color}; text-align:center;">{signal_status}</h3>
    </div>
""", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Live Price", f"₹{current_price:.2f}")

if action in ["BUY", "SELL"]:
    col2.metric("🎯 Strict Target", f"₹{target_price:.2f}", f"{'+' if action=='BUY' else '-'}{TARGET_POINTS} pts")
    col3.metric("🛡️ Stop Loss", f"₹{stop_loss:.2f}", f"{'-' if action=='BUY' else '+'}{STOP_LOSS_POINTS} pts", delta_color="inverse")
    col4.metric("Risk/Reward Ratio", "1 : 2")
else:
    col2.metric("🎯 Target", "Waiting...")
    col3.metric("🛡️ Stop Loss", "Waiting...")
    col4.metric("Trend Status", "Safe" if current_price > latest['EMA_200'] else "Bearish")

st.markdown("---")
fig = plot_professional_chart(df, selected_asset)
st.plotly_chart(fig, use_container_width=True)
