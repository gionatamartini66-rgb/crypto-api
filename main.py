"""
Crypto Gem Finder - Main Application v2.2
Sistema completo con Alert Optimizer + Database PostgreSQL
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
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncpg

# Whale Tracking (v2.2)
try:
    from whale_tracker import WhaleAlertAPI, WhaleTracker
    WHALE_ENABLED = True
except ImportError:
    WHALE_ENABLED = False
    logger.warning("⚠️ whale_tracker.py non trovato - whale tracking disabilitato")
# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """Gestione PostgreSQL con graceful fallback"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.database_url = os.getenv("DATABASE_URL", "")
        self.enabled = bool(self.database_url)
        self.connected = False
        
    async def connect(self):
        """Connessione PostgreSQL"""
        if not self.enabled:
            logger.warning("⚠️ Database non configurato - usando in-memory storage")
            return False
        
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            
            async with self.pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
            
            self.connected = True
            logger.info("✅ Database PostgreSQL connesso")
            
            # Auto-create tables
            await self._create_tables()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            self.enabled = False
            self.connected = False
            return False
    
    async def _create_tables(self):
        """Crea tabelle automaticamente se non esistono"""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                # Prices history
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS prices_history (
                        id SERIAL PRIMARY KEY,
                        coin_id VARCHAR(50) NOT NULL,
                        symbol VARCHAR(10) NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        price DECIMAL(20,8) NOT NULL,
                        change_24h DECIMAL(10,4),
                        volume_24h BIGINT,
                        market_cap BIGINT,
                        high_24h DECIMAL(20,8),
                        low_24h DECIMAL(20,8),
                        timestamp TIMESTAMP DEFAULT NOW(),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Alerts history
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS alerts_history (
                        id SERIAL PRIMARY KEY,
                        coin_id VARCHAR(50) NOT NULL,
                        alert_type VARCHAR(20) NOT NULL,
                        priority VARCHAR(10) NOT NULL,
                        price DECIMAL(20,8),
                        change_percent DECIMAL(10,4),
                        volume_24h BIGINT,
                        market_cap BIGINT,
                        message TEXT,
                        sent_at TIMESTAMP DEFAULT NOW(),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Indexes
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_prices_coin_timestamp 
                    ON prices_history(coin_id, timestamp DESC)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_alerts_sent 
                    ON alerts_history(sent_at DESC)
                """)

# Whale transactions table (v2.2)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS whale_transactions (
                        id SERIAL PRIMARY KEY,
                        transaction_hash VARCHAR(100) NOT NULL,
                        blockchain VARCHAR(20) NOT NULL,
                        symbol VARCHAR(10) NOT NULL,
                        amount DECIMAL(30,8) NOT NULL,
                        amount_usd BIGINT NOT NULL,
                        from_owner VARCHAR(50),
                        to_owner VARCHAR(50),
                        transaction_type VARCHAR(20) DEFAULT 'transfer',
                        whale_size VARCHAR(20) NOT NULL,
                        timestamp BIGINT NOT NULL,
                        detected_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(blockchain, transaction_hash)
                    )
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_whale_detected 
                    ON whale_transactions(detected_at DESC)
                """)

                # Whale transactions table (v2.2)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS whale_transactions (
                        id SERIAL PRIMARY KEY,
                        transaction_hash VARCHAR(100) NOT NULL,
                        whale_size VARCHAR(20) NOT NULL,
                        timestamp BIGINT NOT NULL,
                        detected_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(blockchain, transaction_hash)
                    )
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_whale_detected 
                    ON whale_transactions(detected_at DESC)
                """)
                logger.info("✅ Database schema verificato/creato")
                
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
    
    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            logger.info("Database disconnesso")
    
    async def save_price(self, coin_data: Dict):
        """Salva prezzo su database"""
        if not self.connected or not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO prices_history 
                    (coin_id, symbol, name, price, change_24h, volume_24h, market_cap, high_24h, low_24h)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    coin_data['id'],
                    coin_data['symbol'],
                    coin_data['name'],
                    float(coin_data['price']),
                    float(coin_data.get('change24h', 0)),
                    int(coin_data.get('volume24h', 0)),
                    int(coin_data.get('marketCap', 0)),
                    float(coin_data.get('high24h', 0)),
                    float(coin_data.get('low24h', 0))
                )
        except Exception as e:
            logger.error(f"Error save_price: {e}")
    
    async def save_alert(self, alert_data: Dict):
        """Salva alert su database"""
        if not self.connected or not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO alerts_history 
                    (coin_id, alert_type, priority, price, change_percent, volume_24h, market_cap, message)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    alert_data['coin_id'],
                    alert_data['alert_type'],
                    alert_data['priority'],
                    float(alert_data.get('price', 0)),
                    float(alert_data.get('change_percent', 0)),
                    int(alert_data.get('volume_24h', 0)),
                    int(alert_data.get('market_cap', 0)),
                    alert_data.get('message', '')
                )
        except Exception as e:
            logger.error(f"Error save_alert: {e}")

    async def save_whale_transaction(self, whale_data: Dict):
        """Salva whale transaction"""
        if not self.connected or not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO whale_transactions 
                    (transaction_hash, blockchain, symbol, amount, amount_usd, 
                     from_owner, to_owner, transaction_type, whale_size, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (blockchain, transaction_hash) DO NOTHING
                    """,
                    whale_data['transaction_hash'],
                    whale_data['blockchain'],
                    whale_data['symbol'],
                    float(whale_data['amount']),
                    int(whale_data['amount_usd']),
                    whale_data.get('from_owner', 'unknown'),
                    whale_data.get('to_owner', 'unknown'),
                    whale_data.get('transaction_type', 'transfer'),
                    whale_data['whale_size'],
                    int(whale_data['timestamp'])
                )
        except Exception as e:
            logger.error(f"Error save_whale: {e}")
    
    async def get_whale_history(self, limit: int = 50):
        """Recupera whale history"""
        if not self.connected or not self.pool:
            return []
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT transaction_hash, blockchain, symbol, amount,
                           amount_usd, from_owner, to_owner, whale_size,
                           timestamp, detected_at
                    FROM whale_transactions
                    ORDER BY detected_at DESC
                    LIMIT $1
                    """,
                    limit
                )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error get_whale_history: {e}")
            return []
    async def get_price_history(self, coin_id: str, days: int = 7):
        """Recupera storico prezzi"""
        if not self.connected or not self.pool:
            return []
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT coin_id, symbol, name, price, change_24h, 
                           volume_24h, market_cap, timestamp
                    FROM prices_history
                    WHERE coin_id = $1 
                      AND timestamp > NOW() - INTERVAL '1 day' * $2
                    ORDER BY timestamp DESC
                    LIMIT 1000
                    """,
                    coin_id, days
                )
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error get_price_history: {e}")
            return []
    
    async def get_alert_history(self, limit: int = 50, coin_id: Optional[str] = None):
        """Recupera storico alert"""
        if not self.connected or not self.pool:
            return []
        
        try:
            async with self.pool.acquire() as conn:
                if coin_id:
                    rows = await conn.fetch(
                        """
                        SELECT id, coin_id, alert_type, priority, price, 
                               change_percent, message, sent_at
                        FROM alerts_history
                        WHERE coin_id = $1
                        ORDER BY sent_at DESC
                        LIMIT $2
                        """,
                        coin_id, limit
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT id, coin_id, alert_type, priority, price,
                               change_percent, message, sent_at
                        FROM alerts_history
                        ORDER BY sent_at DESC
                        LIMIT $1
                        """,
                        limit
                    )
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error get_alert_history: {e}")
            return []


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
    description="Sistema intelligente monitoraggio cryptocurrency con database",
    version="2.1.0"
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

# Instances
alert_optimizer = AlertOptimizer()
db = DatabaseManager()

# Whale Tracker (v2.2)
if WHALE_ENABLED:
    whale_api = WhaleAlertAPI()
    whale_tracker = WhaleTracker(whale_api)
else:
    whale_tracker = None

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
    
    # Salva prezzo su database
    await db.save_price(coin_data)
    
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
        
        # Salva alert su database
        alert_data = {
            'coin_id': coin_id,
            'alert_type': alert_type.value,
            'priority': priority.value,
            'price': coin_data['price'],
            'change_percent': coin_data.get('change24h', 0),
            'volume_24h': coin_data.get('volume24h', 0),
            'market_cap': coin_data.get('marketCap', 0),
            'message': message
        }
        await db.save_alert(alert_data)
        
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

# Check whale activity (v2.2)
            if whale_tracker:
                whale_txs = whale_tracker.check_whale_activity()
                for whale_tx in whale_txs:
                    # Salva su database
                    whale_data = {
                        'transaction_hash': whale_tx.transaction_hash,
                        'blockchain': whale_tx.blockchain,
                        'symbol': whale_tx.symbol,
                        'amount': whale_tx.amount,
                        'amount_usd': whale_tx.amount_usd,
                        'from_owner': whale_tx.from_owner,
                        'to_owner': whale_tx.to_owner,
                        'transaction_type': whale_tx.transaction_type,
                        'whale_size': whale_tx.whale_size.value,
                        'timestamp': whale_tx.timestamp
                    }
                    await db.save_whale_transaction(whale_data)
                    
                    # Alert Telegram
                    emoji = "🔴" if "MEGA" in whale_tx.whale_size.value else "🐋"
                    message = (
                        f"{emoji} <b>WHALE DETECTED</b>\n\n"
                        f"💰 <b>${whale_tx.amount_usd:,.0f}</b>\n"
                        f"📊 {whale_tx.amount:,.2f} {whale_tx.symbol}\n"
                        f"⛓️ {whale_tx.blockchain.upper()}\n"
                        f"📤 From: {whale_tx.from_owner}\n"
                        f"📥 To: {whale_tx.to_owner}\n"
                        f"⏰ {datetime.fromtimestamp(whale_tx.timestamp).strftime('%H:%M:%S')}"
                    )
                    
                    if telegram_bot.send_message(message):
                        logger.info(f"🐋 Whale alert: {whale_tx.symbol} ${whale_tx.amount_usd:,.0f}")
            
            await asyncio.sleep(check_interval)
        except Exception as e:
            logger.error(f"❌ Errore monitoring: {e}")
            await asyncio.sleep(30)
    
    logger.info("⏸️ Monitoring fermato")


async def start_monitoring_internal():
    """Avvia monitoring interno"""
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
        "version": "2.2.0",
        "monitoring_active": monitoring_active,
        "auto_start_enabled": AUTO_START_MONITORING,
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "database_configured": db.enabled,
        "database_connected": db.connected,
        "whale_tracking_enabled": WHALE_ENABLED,
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


@app.get("/api/alerts/stats")
async def get_alert_stats():
    return alert_optimizer.get_stats()


@app.get("/api/alerts/history")
async def get_alert_history_api(limit: int = Query(default=50, le=200)):
    """Storico alert - in-memory o database"""
    if db.connected:
        db_alerts = await db.get_alert_history(limit=limit)
        if db_alerts:
            return {"alerts": db_alerts, "total": len(db_alerts), "source": "database"}
    
    return {"alerts": alert_history[-limit:], "total": len(alert_history), "source": "memory"}


@app.get("/api/history/prices")
async def get_price_history_api(
    coin: str = Query(..., description="Coin ID (es: bitcoin)"),
    days: int = Query(default=7, le=30, description="Giorni di storico")
):
    """Storico prezzi da database"""
    if not db.connected:
        raise HTTPException(status_code=503, detail="Database non disponibile")
    
    history = await db.get_price_history(coin_id=coin, days=days)
    
    return {
        "coin_id": coin,
        "days": days,
        "data_points": len(history),
        "history": history
    }


@app.get("/api/history/alerts")
async def get_alert_history_db(
    limit: int = Query(default=100, le=500),
    coin: Optional[str] = Query(default=None, description="Filtra per coin")
):
    """Storico alert completo da database"""
    if not db.connected:
        raise HTTPException(status_code=503, detail="Database non disponibile")
    
    alerts = await db.get_alert_history(limit=limit, coin_id=coin)
    
    return {
        "total": len(alerts),
        "coin_filter": coin,
        "alerts": alerts
    }


@app.post("/api/test-telegram")
async def test_telegram():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise HTTPException(status_code=400, detail="Telegram non configurato")
    
    message = (
        "🧪 <b>Test Crypto Gem Finder v2.1</b>\n\n"
        "✅ Bot Telegram operativo\n"
        "✅ Database persistence attivo\n"
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

@app.get("/api/whales/recent")
async def get_recent_whales(limit: int = Query(default=20, le=100)):
    """Ultimi movimenti whale"""
    if not db.connected:
        raise HTTPException(status_code=503, detail="Database non disponibile")
    
    whales = await db.get_whale_history(limit=limit)
    
    whale_stats = {}
    if whale_tracker:
        whale_stats = whale_tracker.get_stats()
    
    return {
        "whales": whales,
        "total": len(whales),
        "tracker_stats": whale_stats
    }

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("🚀 CRYPTO GEM FINDER v2.2 - AVVIO (Whale Tracking)")
    logger.info("=" * 60)
    logger.info(f"Telegram: {bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)}")
    logger.info(f"CoinGecko API: {bool(COINGECKO_API_KEY)}")
    logger.info(f"Crypto monitorate: {len(TRACKED_COINS)}")
    logger.info(f"Auto-start: {AUTO_START_MONITORING}")
    
    # Connessione database
    await db.connect()
    if db.connected:
        logger.info("💾 Database persistence: ATTIVO")
    else:
        logger.info("💾 Database persistence: DISABILITATO (in-memory mode)")
    
    logger.info("=" * 60)
    
    # AUTO-START monitoring
    if AUTO_START_MONITORING:
        await start_monitoring_internal()


@app.on_event("shutdown")
async def shutdown_event():
    global monitoring_active, monitoring_task
    
    if monitoring_active:
        monitoring_active = False
        if monitoring_task:
            monitoring_task.cancel()
    
    await db.disconnect()
    logger.info("👋 Shutdown")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
