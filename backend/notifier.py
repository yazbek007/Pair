import requests
import json
from datetime import datetime
from typing import Dict, List, Optional
import logging
from config import NTFY_SERVER, NTFY_TOPIC, NTFY_PRIORITY, SYRIA_TZ

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NTFYNotifier:
    def __init__(self):
        self.server = NTFY_SERVER
        self.topic = NTFY_TOPIC
        self.priority = NTFY_PRIORITY
        
    def get_syria_time_str(self):
        """الحصول على وقت سورية كسلسلة نصية"""
        return datetime.now(SYRIA_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    
    def send_notification(self, title: str, message: str, tags: List[str] = None, 
                         priority: str = None, click_url: str = None):
        """إرسال إشعار إلى NTFY"""
        if priority is None:
            priority = self.priority
            
        headers = {
            "Title": title.encode('utf-8'),
            "Priority": priority,
            "Tags": ",".join(tags) if tags else "",
            "Click": click_url if click_url else ""
        }
        
        # إضافة وقت سورية للرسالة
        syria_time = self.get_syria_time_str()
        full_message = f"{message}\n\n📍 Syria Time: {syria_time}"
        
        try:
            response = requests.post(
                f"{self.server}/{self.topic}",
                data=full_message.encode('utf-8'),
                headers=headers
            )
            
            if response.status_code == 200:
                logger.info(f"Notification sent: {title}")
                return True
            else:
                logger.error(f"Failed to send notification: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False
    
    def send_trading_signal(self, pair: str, signal: str, confidence: float, 
                           details: Dict[str, any]):
        """إرسال إشعار إشارة تداول"""
        emoji = "📈" if "LONG" in signal else "📉" if "SHORT" in signal else "⚡"
        tags = ["chart_increasing" if "LONG" in signal else "chart_decreasing", "moneybag"]
        
        title = f"{emoji} Crypto Signal: {pair}"
        
        message_lines = [
            f"Signal: {signal}",
            f"Confidence: {confidence}%",
            f"Timeframe: {details.get('timeframe', '4H')}",
            f"Score Diff: {details.get('score_diff', 'N/A')}",
            f"Perf Diff: {details.get('perf_diff', 'N/A')}%",
            f"Entry Logic: {details.get('logic', 'N/A')}"
        ]
        
        message = "\n".join(message_lines)
        
        return self.send_notification(title, message, tags)
    
    def send_market_alert(self, alert_type: str, coins: List[str], 
                         metric: str, value: float, threshold: float):
        """إرسال إنذار سوقي"""
        emoji_map = {
            "HIGH_VOLATILITY": "🌪️",
            "LOW_LIQUIDITY": "⚠️",
            "EXTREME_MOVE": "🚨",
            "BTC_DOMINANCE_CHANGE": "👑",
            "MARKET_CRASH": "💥"
        }
        
        emoji = emoji_map.get(alert_type, "🔔")
        tags = ["warning", "exclamation"]
        
        title = f"{emoji} Market Alert: {alert_type.replace('_', ' ').title()}"
        
        message_lines = [
            f"Coins affected: {', '.join(coins[:3])}" + ("..." if len(coins) > 3 else ""),
            f"Metric: {metric}",
            f"Current Value: {value:.2f}",
            f"Threshold: {threshold:.2f}",
            f"Status: {'ABOVE' if value > threshold else 'BELOW'} threshold"
        ]
        
        message = "\n".join(message_lines)
        
        return self.send_notification(title, message, tags, priority="high")
    
    def send_daily_summary(self, top_pairs: List[Dict], market_status: Dict):
        """إرسال ملخص يومي"""
        title = "📊 Daily Crypto Market Summary"
        tags = ["bar_chart", "calendar"]
        
        syria_time = self.get_syria_time_str()
        
        message_lines = [
            f"📅 Report Time: {syria_time}",
            f"Market Status: {market_status.get('status', 'N/A')}",
            f"BTC Dominance: {market_status.get('btc_dominance', 'N/A')}%",
            "",
            "🏆 Top Trading Pairs:"
        ]
        
        for i, pair in enumerate(top_pairs[:3], 1):
            message_lines.append(
                f"{i}. {pair['pair']} - {pair['recommendation']} "
                f"(Score: {pair['pair_score']:.1f})"
            )
        
        message_lines.extend([
            "",
            "⚡ Market Stats:",
            f"Total Coins Analyzed: {market_status.get('total_coins', 0)}",
            f"Strong Signals: {market_status.get('strong_signals', 0)}",
            f"Market Condition: {market_status.get('condition', 'N/A')}"
        ])
        
        message = "\n".join(message_lines)
        
        return self.send_notification(title, message, tags, priority="default")

# Singleton instance
notifier = NTFYNotifier()
