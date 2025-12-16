from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
import asyncpg
from typing import List, Dict, Optional

app = FastAPI(
    title="Crypto Gem Finder API",
    description="Real-time cryptocurrency analysis with Telegram alerts",
    version="2.1"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')
db_pool = None

async def init_db():
    global db_pool
    if DATABASE_URL:
        # Fix Render PostgreSQL URL (postgres:// to postgresql://)
        if DATABASE_URL.startswith('postgres://'):
            DATABASE_URL_FIXED = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        else:
            DATABASE_URL_FIXED = DATABASE_URL
            
        try:
            db_pool = await asyncpg.create_pool(DATABASE_URL_FIXED, min_size=1, max_size=10)
            
            # Create tables if not exist
            async with db_pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS crypto_signals (
                        id SERIAL PRIMARY KEY,
                        coin_id VARCHAR(50),
                        symbol VARCHAR(20),
                        signal_type VARCHAR(50),
                        strength FLOAT,
                        price FLOAT,
                        message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS whale_transactions (
                        id SERIAL PRIMARY KEY,
                        tx_hash VARCHAR(100) UNIQUE,
                        blockchain VARCHAR(20),
                        from_address VARCHAR(100),
                        to_address VARCHAR(100),
                        token_symbol VARCHAR(20),
                        amount FLOAT,
                        value_usd FLOAT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS telegram_alerts (
                        id SERIAL PRIMARY KEY,
                        chat_id VARCHAR(50),
                        alert_type VARCHAR(50),
                        message TEXT,
                        sent BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
            print("✅ Database connected and tables created")
        except Exception as e:
            print(f"❌ Database connection error: {e}")
            db_pool = None

@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Crypto Gem Finder API v2.1",
        "status": "online",
        "database": "connected" if db_pool else "not configured",
        "telegram": "ready" if os.getenv('TELEGRAM_BOT_TOKEN') else "not configured",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "signals": "/api/v1/signals",
            "whales": "/api/v1/whales",
            "test_signal": "/api/v1/test-signal"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# Health check
@app.get("/health")
async def health_check():
    db_status = "healthy"
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_status = "healthy"
        except:
            db_status = "error"
    else:
        db_status = "not connected"
        
    return {
        "status": "healthy",
        "database": db_status,
        "telegram_configured": bool(os.getenv('TELEGRAM_BOT_TOKEN')),
        "timestamp": datetime.utcnow().isoformat()
    }

# Get recent signals
@app.get("/api/v1/signals")
async def get_signals(limit: int = 10):
    if not db_pool:
        return {"signals": [], "message": "Database not configured"}
    
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT * FROM crypto_signals 
                ORDER BY created_at DESC 
                LIMIT $1
            ''', limit)
            
            signals = []
            for row in rows:
                signals.append({
                    "id": row['id'],
                    "coin_id": row['coin_id'],
                    "symbol": row['symbol'],
                    "signal_type": row['signal_type'],
                    "strength": row['strength'],
                    "price": row['price'],
                    "message": row['message'],
                    "created_at": row['created_at'].isoformat()
                })
            
            return {"signals": signals, "count": len(signals)}
    except Exception as e:
        return {"error": str(e), "signals": []}

# Create test signal
@app.post("/api/v1/test-signal")
async def create_test_signal():
    """Crea un segnale di test per verificare il sistema"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        async with db_pool.acquire() as conn:
            signal_id = await conn.fetchval('''
                INSERT INTO crypto_signals (coin_id, symbol, signal_type, strength, price, message)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
            ''', 'bitcoin', 'BTC', 'TEST_SIGNAL', 0.85, 42000.0, 
            'Test signal created via API - Sistema funzionante!')
            
            # Se Telegram è configurato, prepara alert
            if os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID'):
                await conn.execute('''
                    INSERT INTO telegram_alerts (chat_id, alert_type, message)
                    VALUES ($1, $2, $3)
                ''', os.getenv('TELEGRAM_CHAT_ID'), 'TEST', 
                '🚀 Test Signal: BTC a $42,000 - Sistema API funzionante!')
            
            return {
                "success": True,
                "signal_id": signal_id,
                "message": "Test signal created successfully!",
                "telegram_ready": bool(os.getenv('TELEGRAM_BOT_TOKEN'))
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get whale transactions
@app.get("/api/v1/whales")
async def get_whale_transactions(limit: int = 10):
    if not db_pool:
        return {"transactions": [], "message": "Database not configured"}
    
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT * FROM whale_transactions 
                ORDER BY created_at DESC 
                LIMIT $1
            ''', limit)
            
            transactions = []
            for row in rows:
                transactions.append({
                    "id": row['id'],
                    "tx_hash": row['tx_hash'],
                    "blockchain": row['blockchain'],
                    "from_address": row['from_address'][:10] + "...",
                    "to_address": row['to_address'][:10] + "...",
                    "token_symbol": row['token_symbol'],
                    "amount": row['amount'],
                    "value_usd": row['value_usd'],
                    "created_at": row['created_at'].isoformat()
                })
            
            return {"transactions": transactions, "count": len(transactions)}
    except Exception as e:
        return {"error": str(e), "transactions": []}
