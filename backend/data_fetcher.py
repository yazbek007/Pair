import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import asyncio
from typing import Dict, List, Optional
import logging
from config import COINS_TO_MONITOR, TIME_FRAMES, SYRIA_TZ

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CryptoDataFetcher:
    def __init__(self):
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = timedelta(minutes=5)
        
    def get_syria_time(self):
        """الحصول على الوقت الحالي بتوقيت سورية"""
        return datetime.now(SYRIA_TZ)
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100):
        """جلب بيانات OHLCV"""
        cache_key = f"{symbol}_{timeframe}"
        
        # التحقق من الكاش
        if (cache_key in self.cache and 
            self.cache_time.get(cache_key) and 
            datetime.now() - self.cache_time[cache_key] < self.cache_duration):
            return self.cache[cache_key]
        
        try:
            ohlcv = await asyncio.to_thread(
                self.exchange.fetch_ohlcv,
                symbol,
                timeframe=timeframe,
                limit=limit
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # التخزين في الكاش
            self.cache[cache_key] = df
            self.cache_time[cache_key] = datetime.now()
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching {symbol} {timeframe}: {e}")
            return None
    
    async def fetch_ticker(self, symbol: str):
        """جلب بيانات التيكر الحالية"""
        try:
            ticker = await asyncio.to_thread(self.exchange.fetch_ticker, symbol)
            return {
                'symbol': symbol,
                'last': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'volume': ticker['quoteVolume'],
                'high': ticker['high'],
                'low': ticker['low'],
                'change': ticker['percentage'],
                'spread': (ticker['ask'] - ticker['bid']) / ticker['ask'] * 100
            }
        except Exception as e:
            logger.error(f"Error fetching ticker {symbol}: {e}")
            return None
    
    async def fetch_multiple_tickers(self, symbols: List[str]):
        """جلب بيانات متعددة بشكل متزامن"""
        tasks = [self.fetch_ticker(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        tickers = {}
        for i, result in enumerate(results):
            if isinstance(result, dict):
                tickers[symbols[i]] = result
            elif result is not None:
                logger.warning(f"Failed to fetch {symbols[i]}: {result}")
        
        return tickers
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14):
        """حساب Average True Range"""
        if df is None or len(df) < period:
            return None
            
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr.iloc[-1]
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14):
        """حساب Relative Strength Index"""
        if df is None or len(df) < period:
            return None
            
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1]
    
    def calculate_returns(self, df: pd.DataFrame, periods: List[int] = [1, 4, 24, 168]):
        """حساب العوائد على أطر زمنية مختلفة"""
        if df is None or len(df) < max(periods):
            return {f"return_{p}": 0 for p in periods}
            
        returns = {}
        close_series = df['close']
        
        for period in periods:
            if len(close_series) >= period:
                returns[f"return_{period}"] = (
                    (close_series.iloc[-1] / close_series.iloc[-period]) - 1
                ) * 100
            else:
                returns[f"return_{period}"] = 0
        
        return returns

# Singleton instance
data_fetcher = CryptoDataFetcher()
