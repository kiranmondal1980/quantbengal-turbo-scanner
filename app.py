import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from indicators import apply_turbo_indicators

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Institutional Algo Terminal", page_icon="🛡️", layout="wide")

AVAILABLE_ASSETS = {
    "BANKNIFTY": "^NSEBANK",
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "CRUDE OIL": "CL=F",
    "GOLD": "GC=F"
}

@st.cache_data(ttl=60)
def fetch_and_calculate(ticker: str):
    # Pulling 30 days of 5-minute data to have enough sample size for backtesting
    df = yf.download(ticker, period="30d", interval="5m", progress=False)
    if df.empty or len(df) < 200:
        return None
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = apply_turbo_indicators(df)
    
    df['Signal'] = 0 
    
    # 🟢 BUY: Above 200 EMA, Above VWAP, and 9 EMA crosses UP over 21 EMA
    buy_condition = (
        (df['Close'] > df['EMA_200']) & 
        (df['Close'] > df['VWAP']) & 
        (df['EMA_9'] > df['EMA_21']) & 
        (df['EMA_9'].shift(1) <= df['EMA_21'].shift(1))
    )
    
    # 🔴 SELL: Below 200 EMA, Below VWAP, and 9 EMA crosses DOWN under 21 EMA
    sell_condition = (
        (df['Close'] < df['EMA_200']) & 
        (df['Close'] < df['VWAP']) & 
        (df['EMA_9'] < df['EMA_21']) & 
        (df['EMA_9'].shift(1) >= df['EMA_21'].shift(1))
    )
    
    df.loc[buy_condition, 'Signal'] = 1
    df.loc[sell_condition, 'Signal'] = -1
    
    return df

def run_backtest(df, target_pts, sl_pts):
    """Simulates trading performance based on historical bars."""
    trades = []
    active_trade = None
    
    for i in range(len(df)):
        row = df.iloc[i]
        timestamp = df.index[i]
        
        # Check if active trade exit conditions are met
        if active_trade:
            entry_price = active_trade['entry_price']
            trade_type = active_trade['type']
            
            if trade_type == 'BUY':
                if row['Low'] <= active_trade['sl']:
                    trades.append({
                        'Entry Time': active_trade['time'], 'Exit Time': timestamp,
                        'Type': 'BUY', 'Entry': entry_price, 'Exit': active_trade['sl'],
                        'P&L (Pts)': -sl_pts, 'Result': 'Loss'
                    })
                    active_trade = None
                elif row['High'] >= active_trade['target']:
                    trades.append({
                        'Entry Time': active_trade['time'], 'Exit Time': timestamp,
                        'Type': 'BUY', 'Entry': entry_price, 'Exit': active_trade['target'],
                        'P&L (Pts)': target_pts, 'Result': 'Win'
                    })
                    active_trade = None
            
            elif trade_type == 'SELL':
                if row['High'] >= active_trade['sl']:
                    trades.append({
                        'Entry Time': active_trade['time'], 'Exit Time': timestamp,
                        'Type': 'SELL', 'Entry': entry_price, 'Exit': active_trade['sl'],
                        'P&L (Pts)': -sl_pts, 'Result': 'Loss'
                    })
                    active_trade = None
                elif row['Low'] <= active_trade['target']:
                    trades.append({
                        'Entry Time': active_trade['time'], 'Exit Time': timestamp,
                        'Type': 'SELL', 'Entry': entry_price, 'Exit': active_trade['target'],
                        'P&L (Pts)': target_pts, 'Result': 'Win'
                    })
                    active_trade = None
        
        # Only enter new trades if no trade is active
        if not active_trade:
            if row['Signal'] == 1:
                active_trade = {
                    'time': timestamp, 'type': 'BUY', 'entry_price': row['Close'],
                    'target': row['Close'] + target_pts, 'sl': row['Close'] - sl_pts
                }
            elif row['Signal'] == -1:
                active_trade = {
                    'time': timestamp, 'type': 'SELL', 'entry_price': row['Close'],
                    'target': row['Close'] - target_pts, 'sl': row['Close'] + sl_pts
                }
                
    return pd.DataFrame(trades)

def plot_professional_chart(df, asset_name):
    df_plot = df.tail(100) # Show last 100 candles for clean UI
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], 
        low=df_plot['Low'], close=df_plot['Close'], name='Price'
    ))

    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['VWAP'], line=dict(color='orange', width=2), name='VWAP'))
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['EMA_200'], line=dict(color='white', width=2), name='200 EMA'))
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['EMA_9'], line=dict(color='cyan', width=1), name='9 EMA'))
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['EMA_21'], line=dict(color='magenta', width=1), name='21 EMA'))

    buy_signals = df_plot[df_plot['Signal'] == 1]
    sell_signals = df_plot[df_plot['Signal'] == -1]

    if not buy_signals.empty:
        fig.add_trace(go.Scatter(
            x=buy_signals.index, y=buy_signals['Low'] - 10,
            mode='markers', marker=dict(symbol='triangle-up', color='lime', size=16), name='BUY Entry'
        ))
    if not sell_signals.empty:
        fig.add_trace(go.Scatter(
            x=sell_signals.index, y=sell_signals['High'] + 10,
            mode='markers', marker=dict(symbol='triangle-down', color='red', size=16), name='SELL Entry'
        ))

    fig.update_layout(
        title=f"Live 5m Terminal Chart: {asset_name}",
        template="plotly_dark", xaxis_rangeslider_visible=False, height=500, margin=dict(l=0, r=0, t=40, b=0)
    )
    return fig

# --- UI CONTROLS ---
st.sidebar.title("🛡️ Algo Controls")
selected_asset = st.sidebar.selectbox("Select Asset:", list(AVAILABLE_ASSETS.keys()))
ticker = AVAILABLE_ASSETS[selected_asset]

# Fixed dynamic points setup
TARGET_POINTS = 50.0 if "NIFTY" in selected_asset or "SENSEX" in selected_asset else 0.5
STOP_LOSS_POINTS = TARGET_POINTS / 2  # Strict 1:2 R:R ratio

if st.sidebar.button("🔄 Force Refresh All Data"):
    st.cache_data.clear()

with st.spinner("Analyzing Market and Backtesting 30 Days of History..."):
    df = fetch_and_calculate(ticker)

if df is None:
    st.error("Not enough historical data or markets closed.")
    st.stop()

# --- STREAMLIT TABS ---
tab1, tab2 = st.tabs(["🔴 Live Trading Terminal", "📊 Backtest & Performance Report"])

# --- TAB 1: LIVE TERMINAL ---
with tab1:
    latest = df.iloc[-1]
    current_price = latest['Close']
    
    signal_status = "⚪ NEUTRAL - Searching for Golden Cross setup..."
    signal_color = "gray"
    target_price, stop_loss = 0.0, 0.0
    action = "None"
    
    if latest['Signal'] == 1:
        signal_status = "🟢 CONFIRMED BUY SIGNAL"
        signal_color = "#00FF00"
        action = "BUY"
        target_price = current_price + TARGET_POINTS
        stop_loss = current_price - STOP_LOSS_POINTS
    elif latest['Signal'] == -1:
        signal_status = "🔴 CONFIRMED SELL SIGNAL"
        signal_color = "#FF0000"
        action = "SELL"
        target_price = current_price - TARGET_POINTS
        stop_loss = current_price + STOP_LOSS_POINTS

    st.markdown(f"""
        <div style="background-color: #1E1E1E; padding: 15px; border-radius: 8px; border: 1px solid {signal_color}; margin-bottom: 20px;">
            <h3 style="margin-top:0px; color:{signal_color}; text-align:center;">{signal_status}</h3>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Market Price", f"₹{current_price:.2f}")
    
    if action != "None":
        col2.metric("Target (Take Profit)", f"₹{target_price:.2f}", f"+{TARGET_POINTS} pts")
        col3.metric("Stop Loss", f"₹{stop_loss:.2f}", f"-{STOP_LOSS_POINTS} pts", delta_color="inverse")
        col4.metric("Risk Reward Ratio", "1 : 2")
    else:
        col2.metric("Target", "Waiting...")
        col3.metric("Stop Loss", "Waiting...")
        col4.metric("R:R Setup", f"1:2 Risk Reward (Target: {TARGET_POINTS}pts)")

    st.markdown("---")
    fig = plot_professional_chart(df, selected_asset)
    st.plotly_chart(fig, use_container_width=True)

# --- TAB 2: BACKTEST REPORT ---
with tab2:
    st.header(f"📈 30-Day Simulation Performance Report: {selected_asset}")
    st.markdown(f"**Parameters:** Target: `+{TARGET_POINTS} pts` | Stop Loss: `-{STOP_LOSS_POINTS} pts` | Timeframe: `5 Minutes`")
    
    # Run the backtest engine
    trades = run_backtest(df, TARGET_POINTS, STOP_LOSS_POINTS)
    
    if trades.empty:
        st.warning("No historical trades were triggered in the last 30 days under current parameters.")
    else:
        # Calculate statistics
        total_trades = len(trades)
        wins = len(trades[trades['Result'] == 'Win'])
        losses = len(trades[trades['Result'] == 'Loss'])
        win_rate = (wins / total_trades) * 100
        total_pnl = trades['P&L (Pts)'].sum()
        
        # Calculate Profit Factor
        gross_profit = trades[trades['P&L (Pts)'] > 0]['P&L (Pts)'].sum()
        gross_loss = abs(trades[trades['P&L (Pts)'] < 0]['P&L (Pts)'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else gross_profit
        
        # Display Metrics Bar
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Trades Executed", f"{total_trades}")
        m2.metric("Win Rate", f"{win_rate:.1f}%", f"{wins} Wins / {losses} Losses")
        
        pnl_color = "normal" if total_pnl > 0 else "inverse"
        m3.metric("Net Point Accrual", f"{total_pnl:+.1f} Points", delta_color=pnl_color)
        m4.metric("Profit Factor", f"{profit_factor:.2f}")

        st.markdown("---")
        
        # Plot Equity Curve
        trades['Cumulative_PnL'] = trades['P&L (Pts)'].cumsum()
        
        st.subheader("Point Equity Curve (Accumulated Points over 30 Days)")
        fig_equity = go.Figure()
        fig_equity.add_trace(go.Scatter(
            x=trades['Exit Time'], y=trades['Cumulative_PnL'],
            line=dict(color='lime', width=3),
            fill='tozeroy', fillcolor='rgba(0,255,0,0.1)', name='Equity'
        ))
        fig_equity.update_layout(
            template="plotly_dark", height=350, margin=dict(l=0, r=0, t=10, b=0),
            xaxis_title="Time of Trade Exit", yaxis_title="Total Points"
        )
        st.plotly_chart(fig_equity, use_container_width=True)
        
        st.markdown("---")
        
        # Detailed Trade Log
        st.subheader("📜 Detailed Historical Trade Log")
        st.dataframe(trades.sort_values(by="Entry Time", ascending=False), use_container_width=True)
