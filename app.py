import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from indicators import apply_turbo_indicators

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Pro Algo Terminal", page_icon="📈", layout="wide")

AVAILABLE_ASSETS = {
    "NIFTY 50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
    "CRUDE OIL": "CL=F",
    "GOLD": "GC=F"
}

@st.cache_data(ttl=60)
def fetch_and_calculate(ticker: str):
    df = yf.download(ticker, period="2d", interval="1m", progress=False)
    if df.empty or len(df) < 200:
        return None
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Calculate Indicators
    df = apply_turbo_indicators(df)
    
    # Generate Historical Signals for the Chart
    df['Signal'] = 0 # 0=Neutral, 1=Buy, -1=Sell
    buy_condition = (df['Close'] > df['EMA_200']) & (df['Close'] < df['VWAP']) & (df['RSI_2'] < 10)
    sell_condition = (df['Close'] < df['EMA_200']) & (df['Close'] > df['VWAP']) & (df['RSI_2'] > 90)
    
    df.loc[buy_condition, 'Signal'] = 1
    df.loc[sell_condition, 'Signal'] = -1
    
    return df

def plot_professional_chart(df, asset_name):
    """Generates a high-performance Plotly financial chart."""
    # Zoom in on the last 120 minutes (2 hours) for clear scalping view
    df_plot = df.tail(120)

    fig = go.Figure()

    # 1. Candlesticks
    fig.add_trace(go.Candlestick(
        x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], 
        low=df_plot['Low'], close=df_plot['Close'], name='Price'
    ))

    # 2. Moving Averages & VWAP
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['VWAP'], line=dict(color='orange', width=2), name='VWAP'))
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['EMA_200'], line=dict(color='white', width=2), name='200 EMA (Trend)'))
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['EMA_9'], line=dict(color='cyan', width=1, dash='dot'), name='9 EMA (Target)'))

    # 3. Buy/Sell Signal Markers
    buy_signals = df_plot[df_plot['Signal'] == 1]
    sell_signals = df_plot[df_plot['Signal'] == -1]

    if not buy_signals.empty:
        fig.add_trace(go.Scatter(
            x=buy_signals.index, y=buy_signals['Low'] * 0.999,
            mode='markers', marker=dict(symbol='triangle-up', color='lime', size=15), name='BUY Signal'
        ))
    if not sell_signals.empty:
        fig.add_trace(go.Scatter(
            x=sell_signals.index, y=sell_signals['High'] * 1.001,
            mode='markers', marker=dict(symbol='triangle-down', color='red', size=15), name='SELL Signal'
        ))

    # Clean UI formatting
    fig.update_layout(
        title=f"Live 1m Scalp Chart: {asset_name}",
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        height=600,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    return fig

# --- UI LAYOUT ---
st.sidebar.title("⚙️ Algo Settings")
selected_asset = st.sidebar.selectbox("Select Asset to Trade:", list(AVAILABLE_ASSETS.keys()))
ticker = AVAILABLE_ASSETS[selected_asset]

if st.sidebar.button("🔄 Refresh Data Now"):
    st.cache_data.clear()

st.title(f"📊 Pro Terminal: {selected_asset}")

with st.spinner("Fetching Live Market Data & Calculating Algorithms..."):
    df = fetch_and_calculate(ticker)

if df is None:
    st.error("Market is closed or not enough data to calculate 200 EMA.")
    st.stop()

# Get the absolute latest candle
latest = df.iloc[-1]
current_price = latest['Close']
target_price = latest['EMA_9']
atr = latest['ATR']

# Calculate Live Signals & Risk Parameters
signal_status = "⚪ NEUTRAL - Waiting for setup..."
signal_color = "gray"
stop_loss = 0.0
action = "None"

if latest['Signal'] == 1:
    signal_status = "🟢 ACTIVE BUY SIGNAL (Deep Pullback)"
    signal_color = "#00FF00"
    action = "BUY"
    stop_loss = current_price - (1.5 * atr) # Volatility-based SL
elif latest['Signal'] == -1:
    signal_status = "🔴 ACTIVE SELL SIGNAL (Dead Cat Bounce)"
    signal_color = "#FF0000"
    action = "SELL"
    stop_loss = current_price + (1.5 * atr)

# --- TRADE EXECUTION DASHBOARD ---
st.markdown(f"""
    <div style="background-color: #1E1E1E; padding: 20px; border-radius: 10px; border: 1px solid {signal_color};">
        <h3 style="margin-top:0px; color:{signal_color}; text-align:center;">{signal_status}</h3>
    </div>
""", unsafe_allow_html=True)

# Risk & Reward Metrics (Only highlight if there is an active trade)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Current Price", f"₹{current_price:.2f}")

if action == "BUY":
    col2.metric("Target (9 EMA)", f"₹{target_price:.2f}", delta=f"+₹{(target_price - current_price):.2f}")
    col3.metric("Stop Loss (1.5 ATR)", f"₹{stop_loss:.2f}", delta=f"-₹{(current_price - stop_loss):.2f}", delta_color="inverse")
    col4.metric("RSI (2)", f"{latest['RSI_2']:.1f}", "Oversold")
elif action == "SELL":
    col2.metric("Target (9 EMA)", f"₹{target_price:.2f}", delta=f"-₹{(current_price - target_price):.2f}")
    col3.metric("Stop Loss (1.5 ATR)", f"₹{stop_loss:.2f}", delta=f"+₹{(stop_loss - current_price):.2f}", delta_color="inverse")
    col4.metric("RSI (2)", f"{latest['RSI_2']:.1f}", "Overbought")
else:
    col2.metric("Target (9 EMA)", f"₹{target_price:.2f}")
    col3.metric("Stop Loss", "Waiting...")
    col4.metric("RSI (2)", f"{latest['RSI_2']:.1f}")

st.markdown("---")

# Render the Interactive Chart
fig = plot_professional_chart(df, selected_asset)
st.plotly_chart(fig, use_container_width=True)

st.caption("Auto-refreshes every 60 seconds based on cache. Click 'Refresh Data Now' in sidebar to force pull.")
