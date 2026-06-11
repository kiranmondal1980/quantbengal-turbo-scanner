import pandas as pd
import numpy as np
import ta

def apply_turbo_indicators(df: pd.DataFrame) -> pd.DataFrame:
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
