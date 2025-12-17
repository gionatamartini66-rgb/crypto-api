from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
import json
from typing import List, Dict, Optional

app = FastAPI(
    title="Crypto Gem Finder API",
    description="Real-time cryptocurrency analysis with Telegram alerts",
    version="2.3"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (temporary solution)
signals_storage = []
test_signal_id = 0

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Crypto Gem Finder API v2.3",
        "status": "online",
        "database": "in-memory" if not os.getenv('DATABASE_URL') else "postgresql",
        "telegram": "ready" if os.getenv('TELEGRAM_BOT_TOKEN') else "not configured",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "signals": "/api/v1/signals",
            "test_signal": "/api/v1/test-signal"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "in-memory",
        "telegram_configured": bool(os.getenv('TELEGRAM_BOT_TOKEN')),
        "timestamp": datetime.utcnow().isoformat()
    }

# Get signals
@app.get("/api/v1/signals")
async def get_signals(limit: int = 10):
    # Return last N signals
    return {
        "signals": signals_storage[-limit:] if signals_storage else [],
        "count": len(signals_storage[-limit:]) if signals_storage else 0,
        "total_signals": len(signals_storage)
    }

# Create test signal
@app.post("/api/v1/test-signal")
async def create_test_signal():
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
    
    # Keep only last 100 signals in memory
    if len(signals_storage) > 100:
        signals_storage.pop(0)
    
    return {
        "success": True,
        "signal_id": test_signal_id,
        "message": "Test signal created successfully!",
        "telegram_ready": bool(os.getenv('TELEGRAM_BOT_TOKEN'))
    }

# Get crypto data (mock)
@app.get("/api/v1/cryptos")
async def get_cryptos():
    return {
        "cryptos": [
            {
                "id": "bitcoin",
                "symbol": "BTC",
                "name": "Bitcoin",
                "price": 42000.50,
                "change_24h": 2.5
            },
            {
                "id": "ethereum", 
                "symbol": "ETH",
                "name": "Ethereum",
                "price": 2200.30,
                "change_24h": 3.2
            }
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
