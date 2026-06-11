import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import ta
import plotly.graph_objects as go

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="SMC Liquidity Terminal", page_icon="🏦", layout="wide")

AVAILABLE_ASSETS = {
    "BANKNIFTY": "^NSEBANK",
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "CRUDE OIL": "CL=F",
    "GOLD": "GC=F"
}

# --- MERGED INDICATORS LOGIC (Directly inside app.py) ---
def calculate_smc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    # 1. Identify local Support and Resistance (Swing Highs/Lows over 20 periods)
    df['Prev_Support'] = df['Low'].rolling(window=20).min().shift(1)
    df['Prev_Resistance'] = df['High'].rolling(window=20).max().shift(1)

    # 2. Institutional Volume Filter (Moving Average of Volume)
    df['Vol_SMA'] = df['Volume'].rolling(window=20).mean()

    # 3. Volatility metric (ATR)
    df['ATR'] = ta.volatility.AverageTrueRange(
        high=df['High'], low=df['Low'], close=df['Close'], window=14
    ).average_true_range()

    return df

# --- NO CACHE FORCING RAW RE-CALCULATION ---
def fetch_and_calculate_fresh(ticker: str):
    # Pulling 30 days of 15-minute data
    df = yf.download(ticker, period="30d", interval="15m", progress=False)
    if df.empty or len(df) < 50:
        return None
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Run indicators locally
    df = calculate_smc_indicators(df)
    
    df['Signal'] = 0 
    
    # 🏦 BULLISH LIQUIDITY SWEEP
    bullish_sweep = (
        (df['Low'] < df['Prev_Support']) & 
        (df['Close'] > df['Prev_Support']) &
        (df['Volume'] > (df['Vol_SMA'] * 1.2))
    )
    
    # 🏦 BEARISH LIQUIDITY SWEEP
    bearish_sweep = (
        (df['High'] > df['Prev_Resistance']) & 
        (df['Close'] < df['Prev_Resistance']) &
        (df['Volume'] > (df['Vol_SMA'] * 1.2))
    )
    
    df.loc[bullish_sweep, 'Signal'] = 1
    df.loc[bearish_sweep, 'Signal'] = -1
    
    return df

def run_backtest(df, target_pts, sl_pts):
    trades = []
    active_trade = None
    
    for i in range(len(df)):
        row = df.iloc[i]
        timestamp = df.index[i]
        
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
    df_plot = df.tail(100)
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], 
        low=df_plot['Low'], close=df_plot['Close'], name='Price'
    ))

    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Prev_Support'], line=dict(color='red', width=1, dash='dash'), name='Retail Stops Low'))
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Prev_Resistance'], line=dict(color='green', width=1, dash='dash'), name='Retail Stops High'))

    buy_signals = df_plot[df_plot['Signal'] == 1]
    sell_signals = df_plot[df_plot['Signal'] == -1]

    if not buy_signals.empty:
        fig.add_trace(go.Scatter(
            x=buy_signals.index, y=buy_signals['Low'] - 10,
            mode='markers', marker=dict(symbol='triangle-up', color='lime', size=18, line=dict(color='black', width=1.5)), name='INSTITUTIONAL BUY'
        ))
    if not sell_signals.empty:
        fig.add_trace(go.Scatter(
            x=sell_signals.index, y=sell_signals['High'] + 10,
            mode='markers', marker=dict(symbol='triangle-down', color='red', size=18, line=dict(color='black', width=1.5)), name='INSTITUTIONAL SELL'
        ))

    fig.update_layout(
        title=f"15m SMC Order Flow Terminal: {asset_name}",
        template="plotly_dark", xaxis_rangeslider_visible=False, height=500, margin=dict(l=0, r=0, t=40, b=0)
    )
    return fig

# --- UI CONTROLS ---
st.sidebar.title("🏦 Institutional Settings")
selected_asset = st.sidebar.selectbox("Select Asset:", list(AVAILABLE_ASSETS.keys()))
ticker = AVAILABLE_ASSETS[selected_asset]

TARGET_POINTS = 100.0 if "NIFTY" in selected_asset or "SENSEX" in selected_asset else 1.0
STOP_LOSS_POINTS = TARGET_POINTS / 2.5 

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Force Refresh All Data"):
    st.cache_data.clear()

with st.spinner("Scanning Order Flow for Stop Hunts..."):
    # Running fresh calculation, bypassing previous caching bugs
    df = fetch_and_calculate_fresh(ticker)

if df is None:
    st.error("Not enough historical data or markets closed.")
    st.stop()

tab1, tab2 = st.tabs(["🏛️ Institutional Live Radar", "📊 SMC Performance Backtest"])

# --- TAB 1: LIVE RADAR ---
with tab1:
    latest = df.iloc[-1]
    current_price = latest['Close']
    
    signal_status = "⚪ MONITORING ORDER FLOW - Waiting for Retail Liquidity Sweeps..."
    signal_color = "gray"
    target_price, stop_loss = 0.0, 0.0
    action = "None"
    
    if latest['Signal'] == 1:
        signal_status = "🟢 INSTITUTIONAL ABSORPTION (Retail Sellers Hunted)"
        signal_color = "#00FF00"
        action = "BUY"
        target_price = current_price + TARGET_POINTS
        stop_loss = current_price - STOP_LOSS_POINTS
    elif latest['Signal'] == -1:
        signal_status = "🔴 INSTITUTIONAL SELLING (Breakout Buyers Hunted)"
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
        col2.metric("Target (Swing Target)", f"₹{target_price:.2f}", f"+{TARGET_POINTS} pts")
        col3.metric("Stop Loss (Invalidation)", f"₹{stop_loss:.2f}", f"-{STOP_LOSS_POINTS} pts", delta_color="inverse")
        col4.metric("Risk Reward Ratio", "1 : 2.5")
    else:
        col2.metric("Target", "Waiting...")
        col3.metric("Stop Loss", "Waiting...")
        col4.metric("R:R Setup", "1:2.5 (Tight SL / Big Range Moves)")

    st.markdown("---")
    fig = plot_professional_chart(df, selected_asset)
    st.plotly_chart(fig, use_container_width=True)

# --- TAB 2: SMC BACKTEST REPORT ---
with tab2:
    st.header(f"📈 30-Day SMC Simulation Report: {selected_asset}")
    st.markdown(f"**Strategy:** Stop Hunt & Reversal | **Timeframe:** `15 Minutes`")
    
    trades = run_backtest(df, TARGET_POINTS, STOP_LOSS_POINTS)
    
    if trades.empty:
        st.warning("No liquidity sweeps detected under these exact parameters in the last 30 days.")
    else:
        total_trades = len(trades)
        wins = len(trades[trades['Result'] == 'Win'])
        losses = len(trades[trades['Result'] == 'Loss'])
        win_rate = (wins / total_trades) * 100
        total_pnl = trades['P&L (Pts)'].sum()
        
        gross_profit = trades[trades['P&L (Pts)'] > 0]['P&L (Pts)'].sum()
        gross_loss = abs(trades[trades['P&L (Pts)'] < 0]['P&L (Pts)'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else gross_profit
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Sweeps Exploited", f"{total_trades}")
        m2.metric("Execution Win Rate", f"{win_rate:.1f}%", f"{wins} Wins / {losses} Losses")
        
        pnl_color = "normal" if total_pnl > 0 else "inverse"
        m3.metric("Net Points Accrued", f"{total_pnl:+.1f} Points", delta_color=pnl_color)
        m4.metric("Profit Factor", f"{profit_factor:.2f}")

        st.markdown("---")
        
        trades['Cumulative_PnL'] = trades['P&L (Pts)'].cumsum()
        
        st.subheader("Point Equity Curve")
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
        st.subheader("📜 Detailed Order Flow Log")
        st.dataframe(trades.sort_values(by="Entry Time", ascending=False), use_container_width=True)
