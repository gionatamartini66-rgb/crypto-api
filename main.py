from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os

app = FastAPI(
    title="Crypto Gem Finder API",
    description="Real-time cryptocurrency analysis and whale tracking",
    version="2.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Crypto Gem Finder API v2.0",
        "status": "online",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "api": "/api/v1/"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "crypto-gem-finder",
        "version": "2.0",
        "timestamp": datetime.utcnow().isoformat()
    }

# API info
@app.get("/api/v1/")
async def api_info():
    return {
        "name": "Crypto Gem Finder API",
        "version": "1.0",
        "endpoints": [
            "/api/v1/cryptos",
            "/api/v1/signals",
            "/api/v1/whales"
        ]
    }

# Mock endpoint per test
@app.get("/api/v1/cryptos")
async def get_cryptos():
    return {
        "cryptos": [
            {"symbol": "BTC", "name": "Bitcoin", "price": 42000},
            {"symbol": "ETH", "name": "Ethereum", "price": 2200}
        ],
        "count": 2
    }
