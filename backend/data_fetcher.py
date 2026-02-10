import ccxt
import pandas as pd
import numpy as np
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from config import COINS_TO_MONITOR, TIME_FRAMES, SYRIA_TZ

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CryptoDataFetcher:
    """فئة لجلب بيانات العملات الرقمية من Binance"""
    
    def __init__(self):
        """تهيئة كائن جلب البيانات"""
        try:
            self.exchange = ccxt.binance({
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',
                    'adjustForTimeDifference': True
                },
                'timeout': 30000,
                'rateLimit': 1200,
                'proxies': {}
            })
            
            # التحقق من اتصال Exchange
            self.exchange.load_markets()
            logger.info(f"Connected to Binance. Total symbols: {len(self.exchange.symbols)}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Binance exchange: {e}")
            raise
        
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = timedelta(minutes=2)
        
    def get_syria_time(self):
        """الحصول على الوقت الحالي بتوقيت سورية"""
        return datetime.now(SYRIA_TZ)
    
    def clear_cache(self):
        """مسح الكاش الموجود"""
        self.cache.clear()
        self.cache_time.clear()
        logger.info("Cache cleared")
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> Optional[pd.DataFrame]:
        """
        جلب بيانات OHLCV (سعر الفتح، الأعلى، الأدنى، الإغلاق، الحجم)
        
        Args:
            symbol: رمز العملة (مثل: BTC/USDT)
            timeframe: الإطار الزمني (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
            limit: عدد الشموع المطلوبة
            
        Returns:
            DataFrame يحتوي على بيانات OHLCV أو None في حالة الخطأ
        """
        cache_key = f"{symbol}_{timeframe}_{limit}"
        
        # التحقق من الكاش أولاً
        if (cache_key in self.cache and 
            cache_key in self.cache_time and 
            datetime.now() - self.cache_time[cache_key] < self.cache_duration):
            logger.debug(f"Returning cached OHLCV data for {cache_key}")
            return self.cache[cache_key].copy()
        
        try:
            # تحويل رمز العملة للتأكد من أنه صحيح
            if "/" in symbol:
                base, quote = symbol.split("/")
                symbol = f"{base}/{quote}"
            
            # التحقق من أن الرمز مدعوم
            if symbol not in self.exchange.symbols:
                logger.warning(f"Symbol {symbol} not supported on Binance")
                # محاولة مع رمز مختلف
                if symbol.endswith("/USDT"):
                    alt_symbol = symbol.replace("/USDT", "/BUSD")
                    if alt_symbol in self.exchange.symbols:
                        logger.info(f"Using alternative symbol: {alt_symbol}")
                        symbol = alt_symbol
            
            # جلب البيانات بشكل متزامن
            logger.debug(f"Fetching OHLCV for {symbol} ({timeframe}, limit: {limit})")
            ohlcv = await asyncio.to_thread(
                self.exchange.fetch_ohlcv,
                symbol,
                timeframe=timeframe,
                limit=limit
            )
            
            if not ohlcv or len(ohlcv) == 0:
                logger.warning(f"No OHLCV data returned for {symbol}")
                return None
            
            # تحويل البيانات إلى DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # تحويل الطوابع الزمنية
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # تطبيع البيانات
            df = df.astype({
                'open': 'float64',
                'high': 'float64',
                'low': 'float64',
                'close': 'float64',
                'volume': 'float64'
            })
            
            # حفظ في الكاش
            self.cache[cache_key] = df.copy()
            self.cache_time[cache_key] = datetime.now()
            
            logger.debug(f"Successfully fetched {len(df)} candles for {symbol}")
            return df
            
        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching OHLCV for {symbol}: {e}")
            return None
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching OHLCV for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching OHLCV for {symbol}: {e}")
            return None
    
    async def fetch_ticker(self, symbol: str) -> Optional[Dict]:
        """
        جلب بيانات التيكر الحالية للعملة
        
        Args:
            symbol: رمز العملة (مثل: BTC/USDT)
            
        Returns:
            قاموس يحتوي على بيانات التيكر أو None في حالة الخطأ
        """
        cache_key = f"ticker_{symbol}"
        
        # التحقق من الكاش
        if (cache_key in self.cache and 
            cache_key in self.cache_time and 
            datetime.now() - self.cache_time[cache_key] < timedelta(seconds=30)):
            logger.debug(f"Returning cached ticker for {symbol}")
            return self.cache[cache_key].copy()
        
        try:
            # تنظيف رمز العملة
            if "/" in symbol:
                base, quote = symbol.split("/")
                symbol = f"{base}/{quote}"
            
            # جلب بيانات التيكر
            logger.debug(f"Fetching ticker for {symbol}")
            ticker = await asyncio.to_thread(self.exchange.fetch_ticker, symbol)
            
            if not ticker:
                logger.warning(f"Empty ticker response for {symbol}")
                return None
            
            # استخراج البيانات مع قيم افتراضية
            last = ticker.get('last')
            bid = ticker.get('bid')
            ask = ticker.get('ask')
            
            # إذا كانت البيانات الأساسية مفقودة
            if last is None or bid is None or ask is None:
                logger.warning(f"Incomplete ticker data for {symbol}: last={last}, bid={bid}, ask={ask}")
                return None
            
            # حساب الـ spread بأمان
            spread = 0.0
            try:
                if ask and bid and ask > 0:
                    spread = ((ask - bid) / ask) * 100
            except (TypeError, ZeroDivisionError):
                pass
            
            # تجميع البيانات
            ticker_data = {
                'symbol': symbol,
                'last': float(last),
                'bid': float(bid),
                'ask': float(ask),
                'volume': float(ticker.get('quoteVolume', ticker.get('baseVolume', 0))),
                'high': float(ticker.get('high', 0)) if ticker.get('high') else None,
                'low': float(ticker.get('low', 0)) if ticker.get('low') else None,
                'change': float(ticker.get('percentage', 0)) if ticker.get('percentage') else 0.0,
                'spread': spread,
                'timestamp': ticker.get('timestamp'),
                'datetime': ticker.get('datetime')
            }
            
            # حفظ في الكاش
            self.cache[cache_key] = ticker_data.copy()
            self.cache_time[cache_key] = datetime.now()
            
            logger.debug(f"Successfully fetched ticker for {symbol}: {ticker_data['last']}")
            return ticker_data
            
        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching ticker for {symbol}: {e}")
            return None
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching ticker for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching ticker for {symbol}: {e}")
            return None
    
    async def fetch_multiple_tickers(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        جلب بيانات تيكر متعددة بشكل متزامن
        
        Args:
            symbols: قائمة برموز العملات
            
        Returns:
            قاموس يحتوي على بيانات التيكر للرموز الناجحة
        """
        if not symbols:
            return {}
        
        logger.info(f"Fetching {len(symbols)} tickers concurrently")
        
        # إنشاء المهام
        tasks = []
        for symbol in symbols:
            if symbol:  # تخطى الرموز الفارغة
                tasks.append(self.fetch_ticker(symbol))
        
        # تنفيذ المهام بشكل متزامن
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # تجميع النتائج الناجحة
        tickers = {}
        for i, result in enumerate(results):
            symbol = symbols[i]
            if isinstance(result, dict):
                tickers[symbol] = result
                logger.debug(f"Successfully fetched ticker for {symbol}")
            elif result is not None:
                logger.warning(f"Failed to fetch ticker for {symbol}: {result}")
            else:
                logger.debug(f"No data returned for {symbol}")
        
        logger.info(f"Successfully fetched {len(tickers)} out of {len(symbols)} tickers")
        return tickers
    
    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """
        جلب كتاب الأوامر (الطلب والعرض)
        
        Args:
            symbol: رمز العملة
            limit: عدد مستويات السعر المطلوبة
            
        Returns:
            قاموس يحتوي على كتاب الأوامر
        """
        try:
            logger.debug(f"Fetching order book for {symbol} (limit: {limit})")
            order_book = await asyncio.to_thread(
                self.exchange.fetch_order_book,
                symbol,
                limit
            )
            
            return order_book
            
        except Exception as e:
            logger.error(f"Error fetching order book for {symbol}: {e}")
            return None
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> Optional[float]:
        """
        حساب Average True Range (ATR) - مؤشر التذبذب
        
        Args:
            df: DataFrame يحتوي على بيانات OHLCV
            period: فترة الحساب
            
        Returns:
            قيمة ATR أو None في حالة الخطأ
        """
        if df is None or len(df) < period + 1:
            logger.warning(f"Insufficient data for ATR calculation (need {period+1} candles, have {len(df) if df else 0})")
            return None
        
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            # حساب True Range
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # حساب ATR باستخدام المتوسط المتحرك
            atr = tr.rolling(window=period).mean()
            
            # إرجاع آخر قيمة
            return float(atr.iloc[-1])
            
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return None
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Optional[float]:
        """
        حساب Relative Strength Index (RSI) - مؤشر القوة النسبية
        
        Args:
            df: DataFrame يحتوي على بيانات OHLCV
            period: فترة الحساب
            
        Returns:
            قيمة RSI (0-100) أو None في حالة الخطأ
        """
        if df is None or len(df) < period + 1:
            logger.warning(f"Insufficient data for RSI calculation (need {period+1} candles, have {len(df) if df else 0})")
            return None
        
        try:
            prices = df['close']
            deltas = prices.diff()
            
            # فصل المكاسب والخسائر
            gains = deltas.where(deltas > 0, 0)
            losses = -deltas.where(deltas < 0, 0)
            
            # حساب المتوسطات
            avg_gain = gains.rolling(window=period).mean()
            avg_loss = losses.rolling(window=period).mean()
            
            # حساب RS وRSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            # إرجاع آخر قيمة
            return float(rsi.iloc[-1])
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return None
    
    def calculate_returns(self, df: pd.DataFrame, periods: List[int] = None) -> Dict[str, float]:
        """
        حساب العوائد على أطر زمنية مختلفة
        
        Args:
            df: DataFrame يحتوي على بيانات OHLCV
            periods: قائمة بالفترات الزمنية (بالساعات)
            
        Returns:
            قاموس يحتوي على العوائد لكل فترة
        """
        if periods is None:
            periods = [1, 4, 24, 168]  # 1h, 4h, 1d, 1w
        
        returns = {}
        
        if df is None or len(df) < max(periods):
            logger.warning(f"Insufficient data for returns calculation")
            for period in periods:
                returns[f"return_{period}"] = 0.0
            return returns
        
        try:
            close_series = df['close']
            
            for period in periods:
                if len(close_series) >= period:
                    start_price = close_series.iloc[-period]
                    end_price = close_series.iloc[-1]
                    
                    if start_price > 0:
                        returns[f"return_{period}"] = ((end_price / start_price) - 1) * 100
                    else:
                        returns[f"return_{period}"] = 0.0
                else:
                    returns[f"return_{period}"] = 0.0
            
            return returns
            
        except Exception as e:
            logger.error(f"Error calculating returns: {e}")
            for period in periods:
                returns[f"return_{period}"] = 0.0
            return returns
    
    def calculate_sma(self, df: pd.DataFrame, period: int = 20) -> Optional[float]:
        """
        حساب Simple Moving Average (SMA)
        
        Args:
            df: DataFrame يحتوي على بيانات OHLCV
            period: فترة الحساب
            
        Returns:
            قيمة SMA أو None في حالة الخطأ
        """
        if df is None or len(df) < period:
            return None
        
        try:
            sma = df['close'].rolling(window=period).mean()
            return float(sma.iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating SMA: {e}")
            return None
    
    def calculate_ema(self, df: pd.DataFrame, period: int = 20) -> Optional[float]:
        """
        حساب Exponential Moving Average (EMA)
        
        Args:
            df: DataFrame يحتوي على بيانات OHLCV
            period: فترة الحساب
            
        Returns:
            قيمة EMA أو None في حالة الخطأ
        """
        if df is None or len(df) < period:
            return None
        
        try:
            ema = df['close'].ewm(span=period, adjust=False).mean()
            return float(ema.iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            return None
    
    async def test_connection(self) -> bool:
        """
        اختبار اتصال Exchange
        
        Returns:
            True إذا كان الاتصال ناجحاً، False خلاف ذلك
        """
        try:
            # محاولة جلب بيانات BTC/USDT كاختبار
            ticker = await self.fetch_ticker("BTC/USDT")
            if ticker and 'last' in ticker:
                logger.info(f"Connection test successful. BTC price: {ticker['last']}")
                return True
            else:
                logger.warning("Connection test failed: No ticker data")
                return False
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def get_available_symbols(self, quote: str = "USDT") -> List[str]:
        """
        الحصول على قائمة الرموز المتاحة لزوج معين
        
        Args:
            quote: العملة المقابلة (مثل: USDT, BTC)
            
        Returns:
            قائمة بالرموز المتاحة
        """
        try:
            symbols = []
            for symbol in self.exchange.symbols:
                if symbol.endswith(f"/{quote}"):
                    symbols.append(symbol)
            
            logger.info(f"Found {len(symbols)} symbols for {quote}")
            return sorted(symbols)
        except Exception as e:
            logger.error(f"Error getting available symbols: {e}")
            return []

# إنشاء كائن مفرد للاستخدام في جميع أنحاء التطبيق
data_fetcher = CryptoDataFetcher()

# دالة مساعدة للاختبار
async def test_data_fetcher():
    """اختبار وظائف جلب البيانات"""
    logger.info("Testing data fetcher...")
    
    # اختبار الاتصال
    connected = await data_fetcher.test_connection()
    if not connected:
        logger.error("Failed to connect to exchange")
        return False
    
    # اختبار جلب التيكر
    btc_ticker = await data_fetcher.fetch_ticker("BTC/USDT")
    if btc_ticker:
        logger.info(f"BTC/USDT ticker: {btc_ticker['last']}")
    else:
        logger.error("Failed to fetch BTC ticker")
        return False
    
    # اختبار جلب OHLCV
    btc_ohlcv = await data_fetcher.fetch_ohlcv("BTC/USDT", "1h", 24)
    if btc_ohlcv is not None:
        logger.info(f"BTC/USDT OHLCV: {len(btc_ohlcv)} candles, last price: {btc_ohlcv['close'].iloc[-1]}")
        
        # اختبار حسابات المؤشرات
        atr = data_fetcher.calculate_atr(btc_ohlcv)
        rsi = data_fetcher.calculate_rsi(btc_ohlcv)
        returns = data_fetcher.calculate_returns(btc_ohlcv)
        
        logger.info(f"BTC ATR: {atr}, RSI: {rsi}, 24h return: {returns.get('return_24', 0)}%")
    else:
        logger.error("Failed to fetch BTC OHLCV")
        return False
    
    logger.info("Data fetcher test completed successfully")
    return True

if __name__ == "__main__":
    # اختبار مباشر إذا تم تشغيل الملف
    async def main():
        success = await test_data_fetcher()
        if success:
            print("✅ Data fetcher working correctly")
        else:
            print("❌ Data fetcher test failed")
    
    asyncio.run(main())
