"""
Technical indicator calculations.

Uses the `ta` library for standard indicators. All functions accept a
pandas DataFrame with columns [open, high, low, close, volume] and return
a float (latest value) or a Series.
"""

import pandas as pd


def sma(df: pd.DataFrame, period: int = 20) -> float:
    """Simple Moving Average of close price (latest value)."""
    return float(df["close"].rolling(period).mean().iloc[-1])


def ema(df: pd.DataFrame, period: int = 20) -> float:
    """Exponential Moving Average of close price (latest value)."""
    return float(df["close"].ewm(span=period, adjust=False).mean().iloc[-1])


def rsi(df: pd.DataFrame, period: int = 14) -> float:
    """Relative Strength Index (latest value, 0-100)."""
    import ta
    series = ta.momentum.RSIIndicator(close=df["close"], window=period).rsi()
    return float(series.iloc[-1])


def macd(df: pd.DataFrame) -> dict:
    """
    MACD indicator.
    Returns {'macd': float, 'signal': float, 'histogram': float}.
    """
    import ta
    indicator = ta.trend.MACD(close=df["close"])
    return {
        "macd": float(indicator.macd().iloc[-1]),
        "signal": float(indicator.macd_signal().iloc[-1]),
        "histogram": float(indicator.macd_diff().iloc[-1]),
    }


def bollinger_bands(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> dict:
    """
    Bollinger Bands.
    Returns {'upper': float, 'middle': float, 'lower': float}.
    """
    import ta
    bb = ta.volatility.BollingerBands(close=df["close"], window=period, window_dev=std)
    return {
        "upper": float(bb.bollinger_hband().iloc[-1]),
        "middle": float(bb.bollinger_mavg().iloc[-1]),
        "lower": float(bb.bollinger_lband().iloc[-1]),
    }


def check_condition(condition_type: str, threshold: float, df: pd.DataFrame) -> bool:
    """
    Evaluate an alert condition against the latest bar.

    Supported condition_type values:
      'price_below', 'price_above',
      'rsi_below',   'rsi_above',
      'sma20_below', 'sma20_above'
    """
    latest_close = float(df["close"].iloc[-1])

    if condition_type == "price_below":
        return latest_close < threshold
    if condition_type == "price_above":
        return latest_close > threshold

    if condition_type in ("rsi_below", "rsi_above"):
        if len(df) < 15:
            return False
        value = rsi(df)
        return value < threshold if condition_type == "rsi_below" else value > threshold

    if condition_type in ("sma20_below", "sma20_above"):
        if len(df) < 20:
            return False
        value = sma(df, 20)
        return latest_close < value if condition_type == "sma20_below" else latest_close > value

    return False
