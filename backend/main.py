from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import json
import asyncio
from typing import Dict, List, Optional
import logging

from backend.data_fetcher import data_fetcher
from backend.analyzer import analyzer
from backend.notifier import notifier
from backend.database import db_manager
from bot.scheduler import scheduler
from config import SYRIA_TZ

# إعداد التطبيق
app = FastAPI(
    title="Crypto Relative Strength Scanner",
    description="Advanced cryptocurrency pair trading scanner with real-time analysis",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# إعداد CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# إعداد المجلدات الثابتة
import os
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# حالة النظام
system_status = {
    "started": False,
    "last_analysis": None,
    "next_analysis": None,
    "total_analyses": 0,
    "last_error": None
}

@app.on_event("startup")
async def startup_event():
    """بدء النظام عند التشغيل"""
    logger = logging.getLogger(__name__)
    logger.info("Starting Crypto Scanner System...")
    
    # بدء البوت المجدول
    scheduler.start()
    system_status["started"] = True
    system_status["start_time"] = datetime.now(SYRIA_TZ)
    
    # إرسال إشعار بدء التشغيل
    notifier.send_notification(
        title="🚀 Crypto Scanner Started",
        message="System is now online and analyzing the market",
        tags=["white_check_mark", "rocket"]
    )
    
    logger.info("System started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """إيقاف النظام عند الإغلاق"""
    scheduler.stop()
    
    notifier.send_notification(
        title="🛑 Crypto Scanner Stopped",
        message="System has been shut down",
        tags=["stop_sign", "warning"]
    )

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """الصفحة الرئيسية"""
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@app.get("/api/health")
async def health_check():
    """فحص صحة النظام"""
    return {
        "status": "healthy" if system_status["started"] else "starting",
        "timestamp": datetime.now(SYRIA_TZ).isoformat(),
        "system_time_syria": datetime.now(SYRIA_TZ).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "uptime": str(datetime.now(SYRIA_TZ) - system_status.get("start_time", datetime.now(SYRIA_TZ))) 
        if system_status.get("start_time") else "0:00:00"
    }

@app.get("/api/analysis/current")
async def get_current_analysis():
    """الحصول على التحليل الحالي"""
    try:
        # الحصول على أحدث البيانات من قاعدة البيانات
        df = db_manager.get_recent_analysis(hours=1, limit=20)
        
        if df.empty:
            return {"error": "No analysis data available yet"}
        
        # تحويل البيانات
        coins_data = []
        for _, row in df.iterrows():
            coin_data = {
                "symbol": row["symbol"],
                "price_usdt": row["price_usdt"],
                "score": row["score"],
                "rank": row["rank"],
                "recommendation": row["recommendation"],
                "rsi": row["rsi"],
                "atr_percent": row["atr_percent"],
                "volume_usd": row["volume_usdt"],
                "signals": row["signals"],
                "timestamp": row["timestamp"]
            }
            coins_data.append(coin_data)
        
        # الحصول على أفضل الأزواج
        pairs_data = []
        pairs_df = db_manager.get_recent_analysis(hours=1, limit=10)
        
        return {
            "timestamp": datetime.now(SYRIA_TZ).isoformat(),
            "total_coins": len(coins_data),
            "coins": coins_data,
            "top_pairs": pairs_data[:5],
            "market_summary": {
                "average_score": df["score"].mean() if not df.empty else 0,
                "bullish_count": len(df[df["score"] >= 60]) if not df.empty else 0,
                "bearish_count": len(df[df["score"] <= 40]) if not df.empty else 0,
                "strong_signals": len(df[df["score"] >= 80]) if not df.empty else 0
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pairs/top")
async def get_top_pairs(days: int = 1, limit: int = 10):
    """الحصول على أفضل أزواج التداول"""
    try:
        pairs_history = db_manager.get_top_pairs_history(days=days, limit_per_day=limit)
        
        return {
            "days": days,
            "limit": limit,
            "data": pairs_history,
            "summary": {
                "total_days": len(pairs_history),
                "total_pairs": sum(len(pairs) for pairs in pairs_history.values())
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/coins/ranking")
async def get_coins_ranking(limit: int = 20):
    """الحصول على ترتيب العملات"""
    try:
        df = db_manager.get_recent_analysis(hours=24, limit=limit)
        
        if df.empty:
            return {"error": "No data available"}
        
        ranking = []
        for _, row in df.iterrows():
            ranking.append({
                "symbol": row["symbol"],
                "score": row["score"],
                "rank": row["rank"],
                "recommendation": row["recommendation"],
                "price": row["price_usdt"],
                "change_24h": 0,  # تحتاج بيانات إضافية
                "volume": row["volume_usdt"],
                "signals": row["signals"][:3] if row["signals"] else []
            })
        
        return {
            "timestamp": datetime.now(SYRIA_TZ).isoformat(),
            "ranking": sorted(ranking, key=lambda x: x["rank"]),
            "statistics": {
                "top_score": max([r["score"] for r in ranking]) if ranking else 0,
                "avg_score": sum([r["score"] for r in ranking]) / len(ranking) if ranking else 0,
                "strong_buy": len([r for r in ranking if "STRONG_BUY" in r["recommendation"]]),
                "strong_sell": len([r for r in ranking if "STRONG_SELL" in r["recommendation"]])
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze/now")
async def trigger_analysis_now(background_tasks: BackgroundTasks):
    """تفعيل التحليل فوراً"""
    background_tasks.add_task(scheduler.analyze_and_notify)
    
    return {
        "message": "Analysis triggered",
        "timestamp": datetime.now(SYRIA_TZ).isoformat(),
        "expected_completion": "1-2 minutes"
    }

@app.get("/api/system/status")
async def get_system_status():
    """الحصول على حالة النظام"""
    return {
        **system_status,
        "current_time_syria": datetime.now(SYRIA_TZ).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "scheduler_running": scheduler.is_running,
        "database_path": db_manager.db_path,
        "coins_monitored": len(db_manager.get_recent_analysis(hours=1, limit=1)) if system_status["total_analyses"] > 0 else 0
    }

@app.get("/api/settings")
async def get_settings():
    """الحصول على إعدادات النظام"""
    settings = {
        "update_interval": db_manager.get_system_setting("update_interval", 15),
        "min_liquidity": db_manager.get_system_setting("min_liquidity", 10000000),
        "volatility_threshold": db_manager.get_system_setting("volatility_threshold", 5.0),
        "notification_enabled": db_manager.get_system_setting("notification_enabled", True),
        "timezone": str(SYRIA_TZ),
        "server_time": datetime.now(SYRIA_TZ).isoformat(),
        "local_time": datetime.now().isoformat()
    }
    return settings

@app.post("/api/test/notification")
async def test_notification(message: str = "Test notification from Crypto Scanner"):
    """اختبار نظام الإشعارات"""
    success = notifier.send_notification(
        title="🔔 Test Notification",
        message=message,
        tags=["test_tube", "bell"]
    )
    
    return {
        "success": success,
        "message": message,
        "timestamp": datetime.now(SYRIA_TZ).isoformat()
    }

@app.get("/api/history/summary")
async def get_history_summary(days: int = 7):
    """الحصول على ملخص تاريخي"""
    try:
        df = db_manager.get_recent_analysis(hours=days*24, limit=1000)
        
        if df.empty:
            return {"error": "No historical data available"}
        
        # تحليل البيانات التاريخية
        summary = {
            "days": days,
            "total_analyses": len(df),
            "average_scores": {},
            "top_performers": [],
            "signal_distribution": {}
        }
        
        # حساب المتوسطات
        if 'score' in df.columns:
            summary["average_scores"]["overall"] = df["score"].mean()
        
        # أفضل 5 عملات
        top_coins = df.groupby("symbol")["score"].mean().nlargest(5)
        summary["top_performers"] = [
            {"symbol": symbol, "avg_score": score}
            for symbol, score in top_coins.items()
        ]
        
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# نقطة النهاية للملفات الثابتة
@app.get("/dashboard")
async def get_dashboard():
    """لوحة التحكم"""
    return FileResponse("frontend/dashboard.html")

@app.get("/charts")
async def get_charts():
    """صفحة الرسوم البيانية"""
    return FileResponse("frontend/charts.html")

@app.get("/api/chart/data/{symbol}")
async def get_chart_data(symbol: str, timeframe: str = "1h", limit: int = 100):
    """الحصول على بيانات الرسم البياني"""
    try:
        # تنظيف الرمز
        if "/" not in symbol:
            symbol = f"{symbol}/USDT"
        
        ohlcv = await data_fetcher.fetch_ohlcv(symbol, timeframe, limit)
        
        if ohlcv is None:
            raise HTTPException(status_code=404, detail="Symbol not found")
        
        # تحويل البيانات لـ Chart.js
        labels = ohlcv.index.strftime("%Y-%m-%d %H:%M").tolist()
        closes = ohlcv['close'].tolist()
        volumes = ohlcv['volume'].tolist()
        highs = ohlcv['high'].tolist()
        lows = ohlcv['low'].tolist()
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "labels": labels,
            "datasets": [
                {
                    "label": "Price",
                    "data": closes,
                    "borderColor": "rgb(75, 192, 192)",
                    "backgroundColor": "rgba(75, 192, 192, 0.2)"
                },
                {
                    "label": "High",
                    "data": highs,
                    "borderColor": "rgb(75, 255, 192)",
                    "borderDash": [5, 5],
                    "fill": False
                },
                {
                    "label": "Low",
                    "data": lows,
                    "borderColor": "rgb(255, 75, 192)",
                    "borderDash": [5, 5],
                    "fill": False
                }
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
