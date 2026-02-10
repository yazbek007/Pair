import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
from config import SYRIA_TZ
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "data/crypto_scanner.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """تهيئة قاعدة البيانات والجداول"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # جدول تحليل العملات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coin_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                symbol TEXT,
                price_usdt REAL,
                price_btc REAL,
                score REAL,
                rank INTEGER,
                recommendation TEXT,
                returns_vs_btc TEXT,
                rsi REAL,
                atr_percent REAL,
                volume_usd REAL,
                spread_percent REAL,
                signals TEXT
            )
        ''')
        
        # جدول أزواج التداول
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trading_pairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                pair TEXT,
                score_difference REAL,
                performance_difference_4h REAL,
                pair_score REAL,
                recommendation TEXT,
                entry_logic TEXT
            )
        ''')
        
        # جدول الإشعارات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                type TEXT,
                title TEXT,
                message TEXT,
                sent INTEGER DEFAULT 0
            )
        ''')
        
        # جدول إعدادات النظام
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_syria_time(self):
        """الحصول على الوقت الحالي بتوقيت سورية"""
        return datetime.now(SYRIA_TZ)
    
    def save_coin_analysis(self, analysis_list: List[Dict]):
        """حفظ تحليل العملات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = self.get_syria_time()
        
        for analysis in analysis_list:
            cursor.execute('''
                INSERT INTO coin_analysis (
                    timestamp, symbol, price_usdt, price_btc, score, rank,
                    recommendation, returns_vs_btc, rsi, atr_percent,
                    volume_usd, spread_percent, signals
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp,
                analysis.get('symbol'),
                analysis.get('price_usdt'),
                analysis.get('price_btc'),
                analysis.get('score'),
                analysis.get('rank'),
                analysis.get('recommendation'),
                json.dumps(analysis.get('returns_vs_btc', {})),
                analysis.get('rsi'),
                analysis.get('atr_percent'),
                analysis.get('volume_usd'),
                analysis.get('spread_percent'),
                json.dumps(analysis.get('signals', []))
            ))
        
        conn.commit()
        conn.close()
    
    def save_trading_pairs(self, pairs: List[Dict]):
        """حفظ أزواج التداول"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = self.get_syria_time()
        
        for pair in pairs:
            cursor.execute('''
                INSERT INTO trading_pairs (
                    timestamp, pair, score_difference, performance_difference_4h,
                    pair_score, recommendation, entry_logic
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp,
                pair.get('pair'),
                pair.get('score_difference'),
                pair.get('performance_difference_4h'),
                pair.get('pair_score'),
                pair.get('recommendation'),
                pair.get('entry_logic')
            ))
        
        conn.commit()
        conn.close()
    
    def get_recent_analysis(self, hours: int = 24, limit: int = 50) -> pd.DataFrame:
        """الحصول على التحليلات الحديثة"""
        conn = sqlite3.connect(self.db_path)
        
        cutoff = self.get_syria_time() - timedelta(hours=hours)
        
        query = '''
            SELECT * FROM coin_analysis 
            WHERE timestamp >= ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        '''
        
        df = pd.read_sql_query(query, conn, params=(cutoff, limit))
        conn.close()
        
        # تحويل الحقول JSON
        if not df.empty and 'returns_vs_btc' in df.columns:
            df['returns_vs_btc'] = df['returns_vs_btc'].apply(json.loads)
        if not df.empty and 'signals' in df.columns:
            df['signals'] = df['signals'].apply(json.loads)
        
        return df
    
    def get_top_pairs_history(self, days: int = 7, limit_per_day: int = 5) -> List[Dict]:
        """الحصول على تاريخ أفضل الأزواج"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = self.get_syria_time() - timedelta(days=days)
        
        cursor.execute('''
            SELECT DATE(timestamp) as date, pair, recommendation, pair_score
            FROM trading_pairs
            WHERE timestamp >= ? 
            AND recommendation != 'NEUTRAL'
            ORDER BY date DESC, pair_score DESC
        ''', (cutoff,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # تنظيم البيانات حسب التاريخ
        result = {}
        for date_str, pair, recommendation, score in rows:
            if date_str not in result:
                result[date_str] = []
            if len(result[date_str]) < limit_per_day:
                result[date_str].append({
                    'pair': pair,
                    'recommendation': recommendation,
                    'score': score
                })
        
        return result
    
    def save_notification(self, notif_type: str, title: str, message: str):
        """حفظ الإشعار في قاعدة البيانات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO notifications (timestamp, type, title, message, sent)
            VALUES (?, ?, ?, ?, 1)
        ''', (self.get_syria_time(), notif_type, title, message))
        
        conn.commit()
        conn.close()
    
    def get_system_setting(self, key: str, default: Any = None) -> Any:
        """الحصول على إعداد النظام"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM system_settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            try:
                return json.loads(result[0])
            except:
                return result[0]
        return default
    
    def set_system_setting(self, key: str, value: Any):
        """تعيين إعداد النظام"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        value_str = json.dumps(value) if not isinstance(value, str) else value
        
        cursor.execute('''
            INSERT OR REPLACE INTO system_settings (key, value, updated_at)
            VALUES (?, ?, ?)
        ''', (key, value_str, self.get_syria_time()))
        
        conn.commit()
        conn.close()
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """تنظيف البيانات القديمة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = self.get_syria_time() - timedelta(days=days_to_keep)
        
        # تنظيف تحليلات العملات
        cursor.execute('DELETE FROM coin_analysis WHERE timestamp < ?', (cutoff,))
        
        # تنظيف أزواج التداول
        cursor.execute('DELETE FROM trading_pairs WHERE timestamp < ?', (cutoff,))
        
        # تنظيف الإشعارات
        cursor.execute('DELETE FROM notifications WHERE timestamp < ?', (cutoff,))
        
        conn.commit()
        conn.close()
        logger.info(f"Cleaned up data older than {days_to_keep} days")

# Singleton instance
db_manager = DatabaseManager()
