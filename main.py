"""
Crypto Gem Finder - Main Application
Sistema di monitoraggio cryptocurrency con alert intelligenti
"""
import os
import time
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import custom modules
from alert_optimizer import (
    AlertOptimizer, 
    AlertType, 
    AlertPriority, 
    MessageTemplate,
    alert_optimizer
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Crypto Gem Finder",
    description="Sistema intelligente monitoraggio cryptocurrency",
    version="2.0.0"
)

# CORS
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

# Monitoring state
monitoring_active = False
monitoring_task: Optional[asyncio.Task] = None

# In-memory storage (da migrare a PostgreSQL)
price_cache: Dict[str, Dict] = {}
alert_history: List[Dict] = []

# CoinGecko configuration
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
TRACKED_COINS = ["bitcoin", "ethereum", "binancecoin", "cardano", "solana"]


class TelegramBot:
    """Client Telegram Bot semplificato"""
    
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    def send_message(self, text: str) -> bool:
        """Invia messaggio Telegram"""
        if not self.token or not self.chat_id:
            logger.warning("Telegram non configurato")
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ Messaggio Telegram inviato")
                return True
            else:
                logger.error(f"❌ Telegram error: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Errore invio Telegram: {e}")
            return False


# Initialize Telegram bot
telegram_bot = TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)


def get_coingecko_headers() -> Dict[str, str]:
    """Headers per richieste CoinGecko"""
    headers = {"accept": "application/json"}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY
    return headers


async def fetch_coin_data(coin_id: str) -> Optional[Dict]:
    """Recupera dati coin da CoinGecko"""
    try:
        url = f"{COINGECKO_BASE_URL}/coins/{coin_id}"
        params = {
            "localization": "false",
            "tickers": "false",
            "community_data": "true",
            "developer_data": "false",
            "sparkline": "false"
        }
        
        response = requests.get(
            url, 
            params=params,
            headers=get_coingecko_headers(),
            timeout=10
        )
        
        if response.status_code != 200:
            logger.error(f"CoinGecko error {response.status_code} per {coin_id}")
            return None
        
        data = response.json()
        
        # Estrai dati rilevanti
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


def analyze_crypto(coin_data: Dict) -> tuple[AlertType, AlertPriority, bool]:
    """
    Analizza crypto e determina se inviare alert
    
    Returns:
        (alert_type, priority, should_alert)
    """
    change_24h = coin_data.get('change24h', 0)
    volume = coin_data.get('volume24h', 0)
    market_cap = coin_data.get('marketCap', 0)
    
    # PUMP Detection (>50% in 24h)
    if change_24h > 50:
        priority = alert_optimizer.get_priority(AlertType.PUMP, coin_data)
        return AlertType.PUMP, priority, True
    
    # VOLUME SPIKE Detection (sopra media)
    if volume > market_cap * 0.5:  # Volume > 50% market cap
        priority = alert_optimizer.get_priority(AlertType.VOLUME_SPIKE, coin_data)
        return AlertType.VOLUME_SPIKE, priority, True
    
    # PRICE DROP Detection (<-20% in 24h)
    if change_24h < -20:
        priority = alert_optimizer.get_priority(AlertType.PRICE_DROP, coin_data)
        return AlertType.PRICE_DROP, priority, True
    
    # STRONG BUY (variazione positiva + volume alto)
    if change_24h > 10 and volume > 100_000_000:
        priority = alert_optimizer.get_priority(AlertType.STRONG_BUY, coin_data)
        return AlertType.STRONG_BUY, priority, True
    
    return AlertType.STRONG_BUY, AlertPriority.LOW, False


async def check_and_alert(coin_id: str):
    """Controlla coin e invia alert se necessario"""
    
    # Fetch dati
    coin_data = await fetch_coin_data(coin_id)
    if not coin_data:
        return
    
    # Salva in cache
    price_cache[coin_id] = {
        **coin_data,
        'timestamp': time.time()
    }
    
    # Analizza
    alert_type, priority, should_check = analyze_crypto(coin_data)
    
    if not should_check:
        return
    
    # Verifica con optimizer
    should_send, reason = alert_optimizer.should_send_alert(
        coin_id=coin_id,
        alert_type=alert_type,
        crypto_data=coin_data,
        priority=priority
    )
    
    if not should_send:
        logger.debug(f"Alert bloccato per {coin_id}: {reason}")
        return
    
    # Prepara e invia messaggio
    message = MessageTemplate.format_alert(alert_type, priority, coin_data)
    
    if telegram_bot.send_message(message):
        # Registra alert inviato
        alert_optimizer.record_alert(
            coin_id=coin_id,
            alert_type=alert_type,
            price=coin_data['price'],
            priority=priority
        )
        
        # Salva in history
        alert_history.append({
            'coin_id': coin_id,
            'alert_type': alert_type.value,
            'priority': priority.value,
            'price': coin_data['price'],
            'timestamp': datetime.now().isoformat()
        })
        
        logger.info(f"✅ Alert inviato: {coin_id} - {alert_type.value}")


async def monitoring_loop():
    """Loop principale monitoring"""
    logger.info("🚀 Monitoring loop avviato")
    
    check_interval = 300  # 5 minuti
    cleanup_interval = 3600  # 1 ora
    last_cleanup = time.time()
    
    while monitoring_active:
        try:
            logger.info("🔍 Scanning crypto...")
            
            # Check ogni coin
            for coin_id in TRACKED_COINS:
                await check_and_alert(coin_id)
                await asyncio.sleep(2)  # Rate limiting CoinGecko
            
            # Cleanup periodico
            if time.time() - last_cleanup > cleanup_interval:
                alert_optimizer.cleanup_old_alerts()
                last_cleanup = time.time()
                logger.info("🧹 Cleanup completato")
            
            # Stats
            stats = alert_optimizer.get_stats()
            logger.info(f"📊 Stats: {stats['alerts_sent']} sent, "
                       f"{stats['alerts_blocked_cooldown']} cooldown, "
                       f"{stats['alerts_blocked_filters']} filtered")
            
            # Attendi prossimo check
            await asyncio.sleep(check_interval)
            
        except Exception as e:
            logger.error(f"❌ Errore monitoring: {e}")
            await asyncio.sleep(30)
    
    logger.info("⏸️ Monitoring loop fermato")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "monitoring_active": monitoring_active,
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "tracked_coins": len(TRACKED_COINS),
        "cache_size": len(price_cache),
        "alert_history_size": len(alert_history),
        "optimizer_stats": alert_optimizer.get_stats()
    }


@app.get("/api/prices")
async def get_prices():
    """Ottieni prezzi attuali delle crypto monitorate"""
    return {
        "prices": price_cache,
        "count": len(price_cache),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/alerts/history")
async def get_alert_history(limit: int = 50):
    """Storico alert inviati"""
    return {
        "alerts": alert_history[-limit:],
        "total": len(alert_history)
    }


@app.get("/api/alerts/stats")
async def get_alert_stats():
    """Statistiche sistema alert"""
    return alert_optimizer.get_stats()


@app.post("/api/test-telegram")
async def test_telegram():
    """Test invio messaggio Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise HTTPException(status_code=400, detail="Telegram non configurato")
    
    message = (
        "🧪 <b>Test Crypto Gem Finder</b>\n\n"
        "✅ Bot Telegram operativo\n"
        "🔔 Sistema alert attivo\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    success = telegram_bot.send_message(message)
    
    if success:
        return {"status": "success", "message": "Test inviato"}
    else:
        raise HTTPException(status_code=500, detail="Errore invio messaggio")


@app.post("/api/start-monitoring")
async def start_monitoring():
    """Avvia monitoring crypto"""
    global monitoring_active, monitoring_task
    
    if monitoring_active:
        return {"status": "already_running", "message": "Monitoring già attivo"}
    
    monitoring_active = True
    monitoring_task = asyncio.create_task(monitoring_loop())
    
    logger.info("▶️ Monitoring avviato")
    
    return {
        "status": "started",
        "message": "Monitoring avviato con successo",
        "tracked_coins": TRACKED_COINS
    }


@app.post("/api/stop-monitoring")
async def stop_monitoring():
    """Ferma monitoring crypto"""
    global monitoring_active, monitoring_task
    
    if not monitoring_active:
        return {"status": "not_running", "message": "Monitoring non attivo"}
    
    monitoring_active = False
    
    if monitoring_task:
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass
    
    logger.info("⏸️ Monitoring fermato")
    
    return {"status": "stopped", "message": "Monitoring fermato"}


@app.post("/api/alerts/reset-stats")
async def reset_alert_stats():
    """Reset statistiche alert"""
    alert_optimizer.reset_stats()
    return {"status": "success", "message": "Statistiche resettate"}


@app.on_event("startup")
async def startup_event():
    """Evento startup applicazione"""
    logger.info("=" * 60)
    logger.info("🚀 CRYPTO GEM FINDER v2.0 - AVVIO")
    logger.info("=" * 60)
    logger.info(f"Telegram configurato: {bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)}")
    logger.info(f"CoinGecko API key: {bool(COINGECKO_API_KEY)}")
    logger.info(f"Crypto monitorate: {len(TRACKED_COINS)}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Evento shutdown applicazione"""
    global monitoring_active, monitoring_task
    
    if monitoring_active:
        monitoring_active = False
        if monitoring_task:
            monitoring_task.cancel()
    
    logger.info("👋 Crypto Gem Finder shutdown")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
