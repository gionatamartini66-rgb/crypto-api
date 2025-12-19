from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
import json
import requests
import asyncio
from typing import List, Dict, Optional

# Import crypto monitor
import sys
sys.path.append('.')
from crypto_monitor import crypto_monitor

app = FastAPI(
    title="Crypto Gem Finder API",
    description="Real-time cryptocurrency analysis with Telegram alerts",
    version="2.5"
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
monitoring_active = False

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

# Background task for price monitoring
async def monitor_prices_task():
    """Monitor crypto prices every 5 minutes"""
    global monitoring_active
    while monitoring_active:
        try:
            # Get current prices
            prices = crypto_monitor.get_prices()
            if prices:
                # Check for alerts
                alerts = crypto_monitor.check_price_changes(prices)
                
                # Send alerts to Telegram
                for alert in alerts:
                    message = crypto_monitor.format_alert_message(alert)
                    send_telegram_message(message)
                    
                    # Store signal
                    signals_storage.append({
                        "type": "price_alert",
                        "data": alert,
                        "created_at": datetime.utcnow().isoformat()
                    })
            
            # Wait 5 minutes
            await asyncio.sleep(300)
            
        except Exception as e:
            print(f"Monitor error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error

# Startup event
@app.on_event("startup")
async def startup_event():
    global monitoring_active
    monitoring_active = True
    # Start background monitoring
    asyncio.create_task(monitor_prices_task())

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    global monitoring_active
    monitoring_active = False

# Root endpoint
@app.get("/")
async def root():
    telegram_status = "not configured"
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        telegram_status = "configured"
    
    return {
        "message": "Crypto Gem Finder API v2.5",
        "status": "online",
        "database": "in-memory",
        "telegram": telegram_status,
        "monitoring": "active" if monitoring_active else "inactive",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "signals": "/api/v1/signals",
            "prices": "/api/v1/prices",
            "monitoring": "/api/v1/monitoring"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# Get current prices
@app.get("/api/v1/prices")
async def get_current_prices():
    """Get current crypto prices"""
    prices = crypto_monitor.get_prices()
    return {
        "prices": prices,
        "tracked_coins": crypto_monitor.tracked_coins,
        "timestamp": datetime.utcnow().isoformat()
    }

# Get/Set monitoring status
@app.get("/api/v1/monitoring")
async def get_monitoring_status():
    """Get monitoring status"""
    return {
        "active": monitoring_active,
        "tracked_coins": crypto_monitor.tracked_coins,
        "thresholds": crypto_monitor.alert_thresholds,
        "last_prices": crypto_monitor.last_prices
    }

@app.post("/api/v1/monitoring/{action}")
async def control_monitoring(action: str):
    """Start or stop monitoring"""
    global monitoring_active
    
    if action == "start":
        monitoring_active = True
        asyncio.create_task(monitor_prices_task())
        
        if TELEGRAM_BOT_TOKEN:
            send_telegram_message("🟢 Monitoraggio prezzi ATTIVATO\n\nRiceverai alert per variazioni significative.")
        
        return {"status": "started", "monitoring": monitoring_active}
    
    elif action == "stop":
        monitoring_active = False
        
        if TELEGRAM_BOT_TOKEN:
            send_telegram_message("🔴 Monitoraggio prezzi DISATTIVATO")
            
        return {"status": "stopped", "monitoring": monitoring_active}
    
    else:
        raise HTTPException(status_code=400, detail="Action must be 'start' or 'stop'")

# ADD ALL OTHER EXISTING ENDPOINTS BELOW (health, signals, telegram-test, etc.)

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "in-memory",
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "monitoring_active": monitoring_active,
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

# Create test signal
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
