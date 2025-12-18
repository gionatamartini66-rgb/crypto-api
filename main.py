from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
import json
import requests
from typing import List, Dict, Optional

app = FastAPI(
    title="Crypto Gem Finder API",
    description="Real-time cryptocurrency analysis with Telegram alerts",
    version="2.4"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
signals_storage = []
test_signal_id = 0

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_message(message: str):
    """Send message to Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.json().get("ok", False)
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

# Root endpoint
@app.get("/")
async def root():
    telegram_status = "not configured"
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        telegram_status = "configured"
    
    return {
        "message": "Crypto Gem Finder API v2.4",
        "status": "online",
        "database": "in-memory",
        "telegram": telegram_status,
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "signals": "/api/v1/signals",
            "test_signal": "/api/v1/test-signal",
            "telegram_test": "/api/v1/telegram-test"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "in-memory",
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "timestamp": datetime.utcnow().isoformat()
    }

# Test Telegram
@app.post("/api/v1/telegram-test")
async def test_telegram():
    """Test Telegram integration"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise HTTPException(status_code=503, detail="Telegram not configured")
    
    message = "🔔 <b>Test Alert</b>\n\n✅ Telegram integration working!\n\nCrypto Gem Finder is ready to send alerts."
    success = send_telegram_message(message)
    
    if success:
        return {"success": True, "message": "Telegram test message sent!"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send Telegram message")

# Get signals
@app.get("/api/v1/signals")
async def get_signals(limit: int = 10):
    return {
        "signals": signals_storage[-limit:] if signals_storage else [],
        "count": len(signals_storage[-limit:]) if signals_storage else 0,
        "total_signals": len(signals_storage)
    }

# Create test signal with Telegram notification
@app.post("/api/v1/test-signal")
async def create_test_signal(background_tasks: BackgroundTasks):
    global test_signal_id
    test_signal_id += 1
    
    signal = {
        "id": test_signal_id,
        "coin_id": "bitcoin",
        "symbol": "BTC",
        "signal_type": "TEST_SIGNAL",
        "strength": 0.85,
        "price": 42000.0,
        "message": f"Test signal #{test_signal_id} - Sistema funzionante!",
        "created_at": datetime.utcnow().isoformat()
    }
    
    signals_storage.append(signal)
    
    # Keep only last 100 signals
    if len(signals_storage) > 100:
        signals_storage.pop(0)
    
    # Send Telegram notification
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        telegram_message = f"""
🚨 <b>NUOVO SEGNALE CRYPTO</b>

💰 <b>Coin:</b> {signal['symbol']}
📊 <b>Tipo:</b> {signal['signal_type']}
💪 <b>Forza:</b> {signal['strength'] * 100:.0f}%
💵 <b>Prezzo:</b> ${signal['price']:,.2f}
📝 <b>Messaggio:</b> {signal['message']}
⏰ <b>Ora:</b> {datetime.utcnow().strftime('%H:%M:%S')}
"""
        background_tasks.add_task(send_telegram_message, telegram_message)
    
    return {
        "success": True,
        "signal_id": test_signal_id,
        "message": "Test signal created!",
        "telegram_sent": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    }

# Crypto price alert example
@app.post("/api/v1/alerts/price")
async def create_price_alert(
    symbol: str, 
    target_price: float, 
    alert_type: str,
    background_tasks: BackgroundTasks
):
    """Create a price alert (example endpoint)"""
    alert = {
        "symbol": symbol.upper(),
        "target_price": target_price,
        "type": alert_type,  # "above" or "below"
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Send Telegram notification
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        emoji = "📈" if alert_type == "above" else "📉"
        message = f"""
{emoji} <b>PRICE ALERT IMPOSTATO</b>

🪙 <b>Coin:</b> {symbol.upper()}
🎯 <b>Target:</b> ${target_price:,.2f}
📊 <b>Tipo:</b> Avvisa quando il prezzo è {alert_type} il target

Riceverai una notifica quando si verifica questa condizione!
"""
        background_tasks.add_task(send_telegram_message, message)
    
    return {
        "success": True,
        "alert": alert,
        "telegram_notification": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    }

# Get crypto data (mock)
@app.get("/api/v1/cryptos")
async def get_cryptos():
    return {
        "cryptos": [
            {"id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "price": 42000.50, "change_24h": 2.5},
            {"id": "ethereum", "symbol": "ETH", "name": "Ethereum", "price": 2200.30, "change_24h": 3.2}
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
