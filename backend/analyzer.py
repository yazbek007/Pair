import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Any
import logging
from dataclasses import dataclass
from config import SCORE_WEIGHTS, VOLATILITY_THRESHOLD, MIN_LIQUIDITY_USD, SYRIA_TZ

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CoinAnalysis:
    symbol: str
    price_usdt: float
    price_btc: float
    returns_vs_btc: Dict[str, float]  # على أطر زمنية مختلفة
    rsi: float
    atr_percent: float
    volume_usd: float
    spread_percent: float
    score: float = 0.0
    rank: int = 0
    recommendation: str = ""
    signals: List[str] = None
    
    def __post_init__(self):
        if self.signals is None:
            self.signals = []

class CryptoAnalyzer:
    def __init__(self):
        self.btc_symbol = "BTC/USDT"
        
    def calculate_relative_strength(self, coin_data: Dict, btc_data: Dict) -> Dict[str, float]:
        """حساب القوة النسبية مقابل البتكوين"""
        returns = {}
        
        # العوائد المطلقة
        for timeframe in ['1h', '4h', '1d', '1w']:
            coin_key = f"return_{timeframe}"
            btc_key = f"return_{timeframe}"
            
            if coin_key in coin_data and btc_key in btc_data:
                returns[timeframe] = coin_data[coin_key] - btc_data[btc_key]
        
        return returns
    
    def score_coin(self, coin: CoinAnalysis) -> float:
        """تقييم العملة بناءً على معايير متعددة"""
        score = 0.0
        
        # 1. الأداء مقابل BTC (35%)
        perf_score = 0
        weights = {'1h': 0.15, '4h': 0.30, '1d': 0.40, '1w': 0.15}
        
        for tf, weight in weights.items():
            if tf in coin.returns_vs_btc:
                perf_score += coin.returns_vs_btc[tf] * weight
        
        perf_score = np.clip(perf_score, -20, 20) / 20  # تطبيع بين -1 و 1
        score += (perf_score + 1) * 0.5 * SCORE_WEIGHTS["performance_vs_btc"] * 100
        
        # 2. الزخم (25%)
        momentum_score = 0
        if coin.rsi is not None:
            # RSI بين 30-70 يعتبر صحي
            if 30 < coin.rsi < 70:
                momentum_score = 1.0
            elif coin.rsi >= 70:
                momentum_score = 0.7  |  # ارتفاع شديد - قد يكون ذروة شراء
            elif coin.rsi <= 30:
                momentum_score = 0.7  # انخفاض شديد - قد يكون ذروة بيع
        score += momentum_score * SCORE_WEIGHTS["momentum"] * 100
        
        # 3. التذبذب (20%)
        volatility_score = 0
        if coin.atr_percent is not None:
            if 1.0 <= coin.atr_percent <= VOLATILITY_THRESHOLD:
                volatility_score = 1.0
            elif coin.atr_percent < 1.0:
                volatility_score = 0.5  |  # سوق هادئ جداً
            else:
                volatility_score = 0.3  # سوق فوضوي
        score += volatility_score * SCORE_WEIGHTS["volatility_score"] * 100
        
        # 4. السيولة (10%)
        liquidity_score = 0
        if coin.volume_usd >= MIN_LIQUIDITY_USD * 2:
            liquidity_score = 1.0
        elif coin.volume_usd >= MIN_LIQUIDITY_USD:
            liquidity_score = 0.7
        else:
            liquidity_score = 0.3
        score += liquidity_score * SCORE_WEIGHTS["liquidity_score"] * 100
        
        # 5. اتجاه الحجم (10%)
        volume_trend_score = 0.5  # قيمة افتراضية - تحتاج بيانات تاريخية
        score += volume_trend_score * SCORE_WEIGHTS["volume_trend"] * 100
        
        return round(score, 2)
    
    def detect_signals(self, coin: CoinAnalysis, btc_analysis: CoinAnalysis) -> List[str]:
        """اكتشاف الإشارات الفنية"""
        signals = []
        
        # إشارات القوة النسبية
        if '1h' in coin.returns_vs_btc and coin.returns_vs_btc['1h'] > 2:
            signals.append("STRONG_VS_BTC_1H")
        if '4h' in coin.returns_vs_btc and coin.returns_vs_btc['4h'] > 5:
            signals.append("STRONG_VS_BTC_4H")
            
        # إشارات RSI
        if coin.rsi < 30:
            signals.append("RSI_OVERSOLD")
        elif coin.rsi > 70:
            signals.append("RSI_OVERBOUGHT")
            
        # إشارات التذبذب
        if coin.atr_percent and coin.atr_percent < 1.0:
            signals.append("LOW_VOLATILITY")
        elif coin.atr_percent and coin.atr_percent > 8.0:
            signals.append("HIGH_VOLATILITY")
            
        # إشارات السيولة
        if coin.volume_usd < MIN_LIQUIDITY_USD:
            signals.append("LOW_LIQUIDITY")
            
        return signals
    
    def generate_recommendation(self, score: float, signals: List[str]) -> str:
        """توليد توصية بناءً على النتيجة والإشارات"""
        if score >= 80:
            return "STRONG_BUY"
        elif score >= 70:
            return "BUY"
        elif score >= 60:
            return "MILD_BUY"
        elif score >= 40:
            return "NEUTRAL"
        elif score >= 30:
            return "MILD_SELL"
        elif score >= 20:
            return "SELL"
        else:
            return "STRONG_SELL"
    
    def analyze_pair(self, coin1: CoinAnalysis, coin2: CoinAnalysis) -> Dict[str, Any]:
        """تحليل زوج تداول بين عملتين"""
        pair_score = abs(coin1.score - coin2.score) / 100
        
        # إيجاد الفروقات
        score_diff = coin1.score - coin2.score
        perf_diff_4h = coin1.returns_vs_btc.get('4h', 0) - coin2.returns_vs_btc.get('4h', 0)
        
        analysis = {
            'pair': f"{coin1.symbol.split('/')[0]}/{coin2.symbol.split('/')[0]}",
            'score_difference': score_diff,
            'performance_difference_4h': perf_diff_4h,
            'pair_score': pair_score * 100,
            'recommendation': "",
            'entry_logic': ""
        }
        
        # توليد توصية الزوج
        if score_diff > 20 and perf_diff_4h > 3:
            analysis['recommendation'] = f"LONG_{coin1.symbol.split('/')[0]}_SHORT_{coin2.symbol.split('/')[0]}"
            analysis['entry_logic'] = "Strong vs Weak momentum"
        elif score_diff < -20 and perf_diff_4h < -3:
            analysis['recommendation'] = f"LONG_{coin2.symbol.split('/')[0]}_SHORT_{coin1.symbol.split('/')[0]}"
            analysis['entry_logic'] = "Weak vs Strong mean reversion"
        else:
            analysis['recommendation'] = "NEUTRAL"
            analysis['entry_logic'] = "No clear edge"
        
        return analysis
    
    def find_best_pairs(self, coins_analysis: List[CoinAnalysis], top_n: int = 5) -> List[Dict]:
        """إيجاد أفضل أزواج التداول"""
        pairs = []
        
        # فرز العملات حسب النتيجة
        sorted_coins = sorted(coins_analysis, key=lambda x: x.score, reverse=True)
        
        # إنشاء أزواج من الأعلى والأسفل
        top_coins = sorted_coins[:top_n]
        bottom_coins = sorted_coins[-top_n:]
        
        for strong_coin in top_coins:
            for weak_coin in bottom_coins:
                if strong_coin.symbol != weak_coin.symbol:
                    pair_analysis = self.analyze_pair(strong_coin, weak_coin)
                    if pair_analysis['recommendation'] != "NEUTRAL":
                        pairs.append(pair_analysis)
        
        # فرز الأزواج حسب قوة الإشارة
        return sorted(pairs, key=lambda x: abs(x['score_difference']), reverse=True)[:top_n]

# Singleton instance
analyzer = CryptoAnalyzer()
