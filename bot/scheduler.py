from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, time
import asyncio
import logging
from typing import Dict, Any
import traceback

from backend.data_fetcher import data_fetcher
from backend.analyzer import analyzer, CoinAnalysis
from backend.notifier import notifier
from backend.database import db_manager
from config import COINS_TO_MONITOR, API_UPDATE_INTERVAL, SYRIA_TZ

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CryptoScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=SYRIA_TZ)
        self.is_running = False
        
    def get_syria_time(self):
        """الحصول على الوقت الحالي بتوقيت سورية"""
        return datetime.now(SYRIA_TZ)
    
    async def fetch_all_data(self) -> Dict[str, Any]:
        """جلب جميع البيانات المطلوبة"""
        logger.info("Starting data fetch...")
        
        try:
            # جلب بيانات BTC أولاً
            btc_data = await data_fetcher.fetch_ticker("BTC/USDT")
            btc_ohlcv = await data_fetcher.fetch_ohlcv("BTC/USDT", "1h", 200)
            
            if not btc_data or btc_ohlcv is None:
                raise Exception("Failed to fetch BTC data")
            
            # حساب مؤشرات BTC
            btc_atr = data_fetcher.calculate_atr(btc_ohlcv)
            btc_rsi = data_fetcher.calculate_rsi(btc_ohlcv)
            btc_returns = data_fetcher.calculate_returns(btc_ohlcv, [1, 4, 24, 168])
            
            btc_analysis = CoinAnalysis(
                symbol="BTC/USDT",
                price_usdt=btc_data['last'],
                price_btc=1.0,
                returns_vs_btc={},  # BTC مقابل نفسه
                rsi=btc_rsi,
                atr_percent=(btc_atr / btc_data['last'] * 100) if btc_atr else None,
                volume_usd=btc_data['volume'],
                spread_percent=btc_data['spread']
            )
            
            # جلب بيانات العملات الأخرى
            all_analysis = []
            
            for coin in COINS_TO_MONITOR:
                if coin == "BTC":
                    continue
                    
                symbol_usdt = f"{coin}/USDT"
                symbol_btc = f"{coin}/BTC"
                
                # جلب البيانات
                ticker_usdt = await data_fetcher.fetch_ticker(symbol_usdt)
                ticker_btc = await data_fetcher.fetch_ticker(symbol_btc)
                ohlcv = await data_fetcher.fetch_ohlcv(symbol_usdt, "1h", 200)
                
                if not ticker_usdt or ohlcv is None:
                    continue
                
                # حساب المؤشرات
                atr = data_fetcher.calculate_atr(ohlcv)
                rsi = data_fetcher.calculate_rsi(ohlcv)
                returns = data_fetcher.calculate_returns(ohlcv, [1, 4, 24, 168])
                
                # حساب العوائد مقابل BTC
                returns_vs_btc = {
                    '1h': returns.get('return_1', 0) - btc_returns.get('return_1', 0),
                    '4h': returns.get('return_4', 0) - btc_returns.get('return_4', 0),
                    '1d': returns.get('return_24', 0) - btc_returns.get('return_24', 0),
                    '1w': returns.get('return_168', 0) - btc_returns.get('return_168', 0)
                }
                
                # إنشاء تحليل العملة
                coin_analysis = CoinAnalysis(
                    symbol=symbol_usdt,
                    price_usdt=ticker_usdt['last'],
                    price_btc=ticker_btc['last'] if ticker_btc else None,
                    returns_vs_btc=returns_vs_btc,
                    rsi=rsi,
                    atr_percent=(atr / ticker_usdt['last'] * 100) if atr else None,
                    volume_usd=ticker_usdt['volume'],
                    spread_percent=ticker_usdt['spread']
                )
                
                # تقييم العملة
                coin_analysis.score = analyzer.score_coin(coin_analysis)
                coin_analysis.signals = analyzer.detect_signals(coin_analysis, btc_analysis)
                coin_analysis.recommendation = analyzer.generate_recommendation(
                    coin_analysis.score, coin_analysis.signals
                )
                
                all_analysis.append(coin_analysis)
            
            # فرز العملات حسب النتيجة
            all_analysis.sort(key=lambda x: x.score, reverse=True)
            
            # تعيين الترتيب
            for i, coin in enumerate(all_analysis, 1):
                coin.rank = i
            
            # إيجاد أفضل أزواج التداول
            top_pairs = analyzer.find_best_pairs(all_analysis, top_n=5)
            
            return {
                'timestamp': self.get_syria_time(),
                'btc_analysis': btc_analysis,
                'coins_analysis': all_analysis,
                'top_pairs': top_pairs,
                'market_status': {
                    'total_coins': len(all_analysis),
                    'strong_signals': sum(1 for c in all_analysis if c.score >= 70),
                    'avg_score': sum(c.score for c in all_analysis) / len(all_analysis) if all_analysis else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error in fetch_all_data: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def analyze_and_notify(self):
        """المهمة الرئيسية: التحليل والإشعارات"""
        logger.info(f"Starting analysis at {self.get_syria_time()}")
        
        try:
            # جلب البيانات
            analysis_data = await self.fetch_all_data()
            
            # حفظ في قاعدة البيانات
            coins_dict = []
            for coin in analysis_data['coins_analysis']:
                coins_dict.append({
                    'symbol': coin.symbol,
                    'price_usdt': coin.price_usdt,
                    'price_btc': coin.price_btc,
                    'score': coin.score,
                    'rank': coin.rank,
                    'recommendation': coin.recommendation,
                    'returns_vs_btc': coin.returns_vs_btc,
                    'rsi': coin.rsi,
                    'atr_percent': coin.atr_percent,
                    'volume_usd': coin.volume_usd,
                    'spread_percent': coin.spread_percent,
                    'signals': coin.signals
                })
            
            db_manager.save_coin_analysis(coins_dict)
            db_manager.save_trading_pairs(analysis_data['top_pairs'])
            
            # التحقق من الإشارات القوية وإرسال إشعارات
            strong_signals = []
            for coin in analysis_data['coins_analysis']:
                if coin.score >= 80 or "STRONG_" in coin.recommendation:
                    strong_signals.append(coin)
            
            if strong_signals:
                for coin in strong_signals[:3]:  # إرسال أول 3 إشارات قوية فقط
                    notifier.send_notification(
                        title=f"🚀 Strong Signal: {coin.symbol}",
                        message=f"Score: {coin.score} | Recommendation: {coin.recommendation}",
                        tags=["rocket", "chart_increasing"]
                    )
            
            # إرسال أفضل أزواج التداول
            if analysis_data['top_pairs']:
                best_pair = analysis_data['top_pairs'][0]
                if best_pair['pair_score'] > 60:    # إرسال فقط إذا كانت النقطة > 60
                    notifier.send_trading_signal(
                        pair=best_pair['pair'],
                        signal=best_pair['recommendation'],
                        confidence=best_pair['pair_score'],
                        details={
                            'score_diff': best_pair['score_difference'],
                            'perf_diff': best_pair['performance_difference_4h'],
                            'logic': best_pair['entry_logic'],
                            'timeframe': '4H'
                        }
                    )
            
            # تنظيف البيانات القديمة (مرة يومياً في 2 صباحاً)
            syria_time = self.get_syria_time()
            if syria_time.hour == 2 and syria_time.minute < 5:
                db_manager.cleanup_old_data()
                
                # إرسال ملخص يومي في 8 صباحاً
                if syria_time.hour == 8 and syria_time.minute < 5:
                    await self.send_daily_summary(analysis_data)
            
            logger.info(f"Analysis completed at {self.get_syria_time()}")
            
        except Exception as e:
            error_msg = f"Analysis job failed: {str(e)}"
            logger.error(error_msg)
            notifier.send_notification(
                title="❌ System Error",
                message=error_msg,
                tags=["warning", "x"],
                priority="max"
            )
    
    async def send_daily_summary(self, analysis_data: Dict[str, Any]):
        """إرسال ملخص يومي"""
        try:
            market_status = analysis_data['market_status']
            
            # حساب حالة السوق
            if market_status['avg_score'] > 60:
                status = "BULLISH"
            elif market_status['avg_score'] < 40:
                status = "BEARISH"
            else:
                status = "NEUTRAL"
            
            market_status['status'] = status
            market_status['condition'] = "Volatile" if market_status['avg_score'] > 70 else "Stable"
            
            # إرسال الملخص
            notifier.send_daily_summary(
                top_pairs=analysis_data['top_pairs'][:5],
                market_status=market_status
            )
            
        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")
    
    def start(self):
        """بدء البوت المجدول"""
        if self.is_running:
            return
        
        logger.info("Starting Crypto Scanner Scheduler...")
        
        # جدولة التحليل كل 15 دقيقة
        self.scheduler.add_job(
            self.analyze_and_notify,
            'interval',
            minutes=API_UPDATE_INTERVAL,
            id='main_analysis',
            next_run_time=datetime.now(SYRIA_TZ)
        )
        
        # جدولة مهمة الصيانة اليومية الساعة 3 صباحاً بتوقيت سورية
        self.scheduler.add_job(
            db_manager.cleanup_old_data,
            'cron',
            hour=3,
            minute=0,
            id='daily_cleanup'
        )
        
        # بدء المجدول
        self.scheduler.start()
        self.is_running = True
        
        logger.info(f"Scheduler started. Next analysis in {API_UPDATE_INTERVAL} minutes.")
    
    def stop(self):
        """إيقاف البوت المجدول"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Scheduler stopped.")

# Singleton instance
scheduler = CryptoScheduler()
