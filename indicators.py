import pandas as pd
import numpy as np
import ta

def apply_turbo_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorized calculation of HFT scalping indicators.
    Assumes df has ['Open', 'High', 'Low', 'Close', 'Volume']
    """
    if df.empty:
        return df

    # 1. EMA Stacks (9 and 200)
    df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()

    # 2. Daily VWAP (Volume Weighted Average Price)
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VP'] = df['Typical_Price'] * df['Volume']
    
    # Extract date for daily VWAP reset
    df['Date'] = df.index.date
    df['Cumulative_VP'] = df.groupby('Date')['VP'].cumsum()
    df['Cumulative_Vol'] = df.groupby('Date')['Volume'].cumsum()
    
    # Handle zero-volume edge cases (common with yfinance indices)
    df['VWAP'] = np.where(
        df['Cumulative_Vol'] == 0,
        df['Typical_Price'], # Fallback if volume is missing
        df['Cumulative_VP'] / df['Cumulative_Vol']
    )

    # 3. RSI (Period 2) - Extreme momentum
    df['RSI_2'] = ta.momentum.RSIIndicator(close=df['Close'], window=2).rsi()

    # 4. ATR (Volatility)
    df['ATR'] = ta.volatility.AverageTrueRange(
        high=df['High'], low=df['Low'], close=df['Close'], window=14
    ).average_true_range()

    return df
