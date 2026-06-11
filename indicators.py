import pandas as pd
import numpy as np
import ta

def apply_turbo_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    # EMA Stacks (9, 21, and 200)
    df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean() # THIS IS THE MISSING LINE!
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()

    # Daily VWAP
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VP'] = df['Typical_Price'] * df['Volume']
    df['Date'] = df.index.date
    df['Cumulative_VP'] = df.groupby('Date')['VP'].cumsum()
    df['Cumulative_Vol'] = df.groupby('Date')['Volume'].cumsum()
    
    df['VWAP'] = np.where(
        df['Cumulative_Vol'] == 0,
        df['Typical_Price'],
        df['Cumulative_VP'] / df['Cumulative_Vol']
    )

    # ATR (Volatility)
    df['ATR'] = ta.volatility.AverageTrueRange(
        high=df['High'], low=df['Low'], close=df['Close'], window=14
    ).average_true_range()

    return df
