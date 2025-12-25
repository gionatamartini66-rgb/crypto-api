"""
Crypto Gem Finder - Main Application v2.0.1
Sistema completo con Alert Optimizer + AUTO-START
"""
import os
import time
import asyncio
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# ALERT OPTIMIZER CLASSES
# ============================================================================

class AlertPriority(Enum):
    """Priorità degli alert"""
    HIGH = "🔴 HIGH"
    MEDIUM = "🟡 MEDIUM"
    LOW = "🟢 LOW"


class AlertType(Enum):
    """Tipi di alert supportati"""
    STRONG_BUY = "STRONG_BUY"
    WHALE = "WHALE"
    PUMP = "PUMP"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    PRICE_DROP = "PRICE_DROP"


@dataclass
class AlertRecord:
    """Record di un alert inviato"""
    coin_id: str
    alert_type: AlertType
    timestamp: float
    price: float
    priority: AlertPriority


class AlertOptimizer:
    """Sistema di ottimizzazione alert"""
    
    def __init__(self):
        self.alert_history: Dict[str, AlertRecord] = {}
        
        self.cooldown_config = {
            AlertPriority.HIGH: 1800,
            AlertPriority.MEDIUM: 3600,
            AlertPriority.LOW: 7200
        }
        
        self.min_volume_24h = 1_000_000
        self.min_market_cap = 10_000_000
        self.max_alerts_per_minute = 5
        self.alerts_sent_minute: list = []
        
        self.stats = {
            "total_checks": 0,
            "alerts_sent": 0,
            "alerts_blocked_cooldown": 0,
            "alerts_blocked_filters": 0,
            "alerts_blocked_rate_limit": 0
        }
    
    def should_send_alert(self, coin_id: str, alert_type: AlertType, crypto_data: Dict, priority: AlertPriority = None):
        """Determina se un alert deve essere inviato"""
        if priority is None:
            priority = AlertPriority.MEDIUM
            
        self.stats["total_checks"] += 1
        
        if not self._check_rate_limit():
            self.stats["alerts_blocked_rate_limit"] += 1
            return False, "Rate limit raggiunto"
        
        passes_filters, filter_reason = self._check_filters(crypto_data)
        if not passes_filters:
            self.stats["alerts_blocked_filters"] += 1
            return False, filter_reason
        
        alert_key = f"{coin_id}_{alert_type.value}"
        
        if alert_key in self.alert_history:
            last_alert = self.alert_history[alert_key]
            cooldown_seconds = self.cooldown_config[last_alert.priority]
            time_since_last = time.time() - last_alert.timestamp
            
            if time_since_last < cooldown_seconds:
                remaining = cooldown_seconds - time_since_last
                self.stats["alerts_blocked_cooldown"] += 1
                return False, f"Cooldown attivo ({remaining/60:.1f} min)"
        
        return True, "Alert approvato"
    
    def record_alert(self, coin_id: str, alert_type: AlertType, price: float, priority: AlertPriority):
        """Registra alert inviato"""
        alert_key = f"{coin_id}_{alert_type.value}"
        
        self.alert_history[alert_key] = AlertRecord(
            coin_id=coin_id,
            alert_type=alert_type,
            timestamp=time.time(),
            price=price,
            priority=priority
        )
        
        self.stats["alerts_sent"] += 1
        self._track_rate_limit()
    
    def _check_rate_limit(self):
        now = time.time()
        self.alerts_sent_minute = [t for t in self.alerts_sent_minute if now - t < 60]
        return len(self.alerts_sent_minute) < self.max_alerts_per_minute
    
    def _track_rate_limit(self):
        self.alerts_sent_minute.append(time.time())
    
    def _check_filters(self, crypto_data: Dict):
        volume = crypto_data.get('volume24h', 0)
        if volume < self.min_volume_24h:
            return False, f"Volume basso"
        
        market_cap = crypto_data.get('marketCap', 0)
        if market_cap < self.min_market_cap:
            return False, f"Market cap basso"
        
        price = crypto_data.get('price', 0)
        if price <= 0:
            return False, "Prezzo non valido"
        
        return True, None
    
    def get_priority(self, alert_type: AlertType, crypto_data: Dict):
        change_24h = abs(crypto_data.get('change24h', 0))
        market_cap = crypto_data.get('marketCap', 0)
        
        if alert_type == AlertType.WHALE:
            return AlertPriority.HIGH
        
        if alert_type == AlertType.PUMP and change_24h > 100:
            return AlertPriority.HIGH
        
        if alert_type == AlertType.STRONG_BUY and market_cap > 1_000_000_000:
            return AlertPriority.HIGH
        
        if alert_type == AlertType.STRONG_BUY:
            return AlertPriority.MEDIUM
        
        if alert_type == AlertType.PUMP and change_24h > 50:
            return AlertPriority.MEDIUM
        
        if alert_type == AlertType.VOLUME_SPIKE:
            return AlertPriority.MEDIUM
        
        return AlertPriority.LOW
    
    def cleanup_old_alerts(self, max_age_hours: int = 24):
        cutoff_time = time.time() - (max_age_hours * 3600)
        self.alert_history = {
            k: v for k, v in self.alert_history.items()
            if v.timestamp > cutoff_time
        }
    
    def get_stats(self):
        return {
            **self.stats,
            "active_cooldowns": len(self.alert_history),
            "success_rate": (
                self.stats["alerts_sent"] / self.stats["total_checks"] * 100
                if self.stats["total_checks"] > 0 else 0
            )
        }
    
    def reset_stats(self):
        self.stats = {
            "total_checks": 0,
            "alerts_sent": 0,
            "alerts_blocked_cooldown": 0,
            "alerts_blocked_filters": 0,
            "alerts_blocked_rate_limit": 0
        }


class MessageTemplate:
    """Template messaggi Telegram"""
    
    @staticmethod
    def format_alert(alert_type: AlertType, priority: AlertPriority, crypto_data: Dict):
        name = crypto_data['name']
        symbol = crypto_data['symbol']
        price = crypto_data['price']
        change = crypto_data.get('change24h', 0)
        
        header = f"{priority.value}\n"
        
        if alert_type == AlertType.STRONG_BUY:
            emoji = "🚀"
            title = "STRONG BUY SIGNAL"
            extra = ""
        elif alert_type == AlertType.WHALE:
            emoji = "🐋"
            title = "WHALE ACTIVITY"
            extra = "📊 Activity: HIGH"
        elif alert_type == AlertType.PUMP:
            emoji = "⚡"
            title = "PUMP DETECTED"
            extra = f"📈 +{change:.1f}% in 24h"
        elif alert_type == AlertType.VOLUME_SPIKE:
            emoji = "📊"
            title = "VOLUME SPIKE"
            volume = crypto_data.get('volume24h', 0)
            extra = f"💰 Volume: ${volume:,.0f}"
        elif alert_type == AlertType.PRICE_DROP:
            emoji = "📉"
            title = "SIGNIFICANT DROP"
            extra = f"📉 {change:.1f}% in 24h"
        else:
            emoji = "💎"
            title = "CRYPTO ALERT"
            extra = ""
        
        message = f"{header}{emoji} <b>{title}</b>\n\n"
        message += f"💎 {name} ({symbol})\n"
        message += f"💰 ${price:.8f}\n"
        
        if change != 0:
            direction = "📈" if change > 0 else "📉"
            message += f"{direction} {change:+.2f}% (24h)\n"
        
        if extra:
            message += f"\n{extra}"
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        message += f"\n\n⏰ {timestamp}"
        
        return message


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Crypto Gem Finder",
    description="Sistema intelligente monitoraggio cryptocurrency",
    version="2.0.1"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
AUTO_START_MONITORING = os.getenv("AUTO_START_MONITORING", "true").lower() == "true"

# State
monitoring_active = False
monitoring_task: Optional[asyncio.Task] = None
price_cache: Dict[str, Dict] = {}
alert_history: List[Dict] = []

# CoinGecko
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
TRACKED_COINS = ["bitcoin", "ethereum", "binancecoin", "cardano", "solana"]

# Alert optimizer instance
alert_optimizer = AlertOptimizer()


class TelegramBot:
    """Client Telegram Bot"""
    
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    def send_message(self, text: str):
        if not self.token or not self.chat_id:
            logger.warning("Telegram non configurato")
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            data = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ Messaggio Telegram inviato")
                return True
            else:
                logger.error(f"❌ Telegram error: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Errore Telegram: {e}")
            return False


telegram_bot = TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)


def get_coingecko_headers():
    headers = {"accept": "application/json"}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY
    return headers


async def fetch_coin_data(coin_id: str):
    try:
        url = f"{COINGECKO_BASE_URL}/coins/{coin_id}"
        params = {
            "localization": "false",
            "tickers": "false",
            "community_data": "true",
            "developer_data": "false",
            "sparkline": "false"
        }
        
        response = requests.get(url, params=params, headers=get_coingecko_headers(), timeout=10)
        
        if response.status_code != 200:
            logger.error(f"CoinGecko error {response.status_code} per {coin_id}")
            return None
        
        data = response.json()
        market_data = data.get('market_data', {})
        
        return {
            'id': coin_id,
            'symbol': data.get('symbol', '').upper(),
            'name': data.get('name', ''),
            'price': market_data.get('current_price', {}).get('usd', 0),
            'change24h': market_data.get('price_change_percentage_24h', 0),
            'volume24h': market_data.get('total_volume', {}).get('usd', 0),
            'marketCap': market_data.get('market_cap', {}).get('usd', 0),
            'high24h': market_data.get('high_24h', {}).get('usd', 0),
            'low24h': market_data.get('low_24h', {}).get('usd', 0),
        }
    except Exception as e:
        logger.error(f"Errore fetch {coin_id}: {e}")
        return None


def analyze_crypto(coin_data: Dict):
    change_24h = coin_data.get('change24h', 0)
    volume = coin_data.get('volume24h', 0)
    market_cap = coin_data.get('marketCap', 0)
    
    if change_24h > 50:
        priority = alert_optimizer.get_priority(AlertType.PUMP, coin_data)
        return AlertType.PUMP, priority, True
    
    if volume > market_cap * 0.5:
        priority = alert_optimizer.get_priority(AlertType.VOLUME_SPIKE, coin_data)
        return AlertType.VOLUME_SPIKE, priority, True
    
    if change_24h < -20:
        priority = alert_optimizer.get_priority(AlertType.PRICE_DROP, coin_data)
        return AlertType.PRICE_DROP, priority, True
    
    if change_24h > 10 and volume > 100_000_000:
        priority = alert_optimizer.get_priority(AlertType.STRONG_BUY, coin_data)
        return AlertType.STRONG_BUY, priority, True
    
    return AlertType.STRONG_BUY, AlertPriority.LOW, False


async def check_and_alert(coin_id: str):
    coin_data = await fetch_coin_data(coin_id)
    if not coin_data:
        return
    
    price_cache[coin_id] = {**coin_data, 'timestamp': time.time()}
    
    alert_type, priority, should_check = analyze_crypto(coin_data)
    
    if not should_check:
        return
    
    should_send, reason = alert_optimizer.should_send_alert(
        coin_id=coin_id,
        alert_type=alert_type,
        crypto_data=coin_data,
        priority=priority
    )
    
    if not should_send:
        logger.debug(f"Alert bloccato per {coin_id}: {reason}")
        return
    
    message = MessageTemplate.format_alert(alert_type, priority, coin_data)
    
    if telegram_bot.send_message(message):
        alert_optimizer.record_alert(coin_id, alert_type, coin_data['price'], priority)
        alert_history.append({
            'coin_id': coin_id,
            'alert_type': alert_type.value,
            'priority': priority.value,
            'price': coin_data['price'],
            'timestamp': datetime.now().isoformat()
        })
        logger.info(f"✅ Alert inviato: {coin_id} - {alert_type.value}")


async def monitoring_loop():
    logger.info("🚀 Monitoring loop avviato")
    
    check_interval = 300
    cleanup_interval = 3600
    last_cleanup = time.time()
    
    while monitoring_active:
        try:
            logger.info("🔍 Scanning crypto...")
            
            for coin_id in TRACKED_COINS:
                await check_and_alert(coin_id)
                await asyncio.sleep(2)
            
            if time.time() - last_cleanup > cleanup_interval:
                alert_optimizer.cleanup_old_alerts()
                last_cleanup = time.time()
                logger.info("🧹 Cleanup completato")
            
            stats = alert_optimizer.get_stats()
            logger.info(f"📊 Stats: {stats['alerts_sent']} sent, "
                       f"{stats['alerts_blocked_cooldown']} cooldown, "
                       f"{stats['alerts_blocked_filters']} filtered")
            
            await asyncio.sleep(check_interval)
        except Exception as e:
            logger.error(f"❌ Errore monitoring: {e}")
            await asyncio.sleep(30)
    
    logger.info("⏸️ Monitoring fermato")


async def start_monitoring_internal():
    """Avvia monitoring interno (chiamato da startup)"""
    global monitoring_active, monitoring_task
    
    if monitoring_active:
        return
    
    monitoring_active = True
    monitoring_task = asyncio.create_task(monitoring_loop())
    logger.info("▶️ Monitoring AUTO-STARTED")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.1",
        "monitoring_active": monitoring_active,
        "auto_start_enabled": AUTO_START_MONITORING,
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "tracked_coins": len(TRACKED_COINS),
        "cache_size": len(price_cache),
        "alert_history_size": len(alert_history),
        "optimizer_stats": alert_optimizer.get_stats()
    }


@app.get("/api/prices")
async def get_prices():
    return {
        "prices": price_cache,
        "count": len(price_cache),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/alerts/history")
async def get_alert_history_api(limit: int = 50):
    return {"alerts": alert_history[-limit:], "total": len(alert_history)}


@app.get("/api/alerts/stats")
async def get_alert_stats():
    return alert_optimizer.get_stats()


@app.post("/api/test-telegram")
async def test_telegram():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise HTTPException(status_code=400, detail="Telegram non configurato")
    
    message = (
        "🧪 <b>Test Crypto Gem Finder v2.0.1</b>\n\n"
        "✅ Bot Telegram operativo\n"
        "✅ AUTO-START attivo\n"
        "🔔 Sistema alert attivo\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    success = telegram_bot.send_message(message)
    
    if success:
        return {"status": "success", "message": "Test inviato"}
    else:
        raise HTTPException(status_code=500, detail="Errore invio")


@app.post("/api/start-monitoring")
async def start_monitoring():
    global monitoring_active, monitoring_task
    
    if monitoring_active:
        return {"status": "already_running"}
    
    await start_monitoring_internal()
    
    return {"status": "started", "tracked_coins": TRACKED_COINS}


@app.post("/api/stop-monitoring")
async def stop_monitoring():
    global monitoring_active, monitoring_task
    
    if not monitoring_active:
        return {"status": "not_running"}
    
    monitoring_active = False
    if monitoring_task:
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass
    
    logger.info("⏸️ Monitoring fermato")
    return {"status": "stopped"}


@app.post("/api/alerts/reset-stats")
async def reset_alert_stats():
    alert_optimizer.reset_stats()
    return {"status": "success"}


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("🚀 CRYPTO GEM FINDER v2.0.1 - AVVIO")
    logger.info("=" * 60)
    logger.info(f"Telegram: {bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)}")
    logger.info(f"CoinGecko API: {bool(COINGECKO_API_KEY)}")
    logger.info(f"Crypto monitorate: {len(TRACKED_COINS)}")
    logger.info(f"Auto-start: {AUTO_START_MONITORING}")
    logger.info("=" * 60)
    
    # AUTO-START monitoring se abilitato
    if AUTO_START_MONITORING:
        await start_monitoring_internal()


@app.on_event("shutdown")
async def shutdown_event():
    global monitoring_active, monitoring_task
    
    if monitoring_active:
        monitoring_active = False
        if monitoring_task:
            monitoring_task.cancel()
    
    logger.info("👋 Shutdown")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
