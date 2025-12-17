from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional

app = FastAPI(
    title="Crypto Gem Finder API",
    description="Real-time cryptocurrency analysis with Telegram alerts",
    version="2.2"
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
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

def get_db_connection():
    """Get database connection"""
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        except Exception as e:
            print(f"Database connection error: {e}")
            return None
    return None

def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            
            # Create tables
            cur.execute('''
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
            
            cur.execute('''
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
            
            conn.commit()
            print("✅ Database tables created/verified")
            
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
        finally:
            cur.close()
            conn.close()

# Initialize DB on startup
init_db()

# Root endpoint
@app.get("/")
async def root():
    db_status = "not configured"
    conn = get_db_connection()
    if conn:
        db_status = "connected"
        conn.close()
        
    return {
        "message": "Crypto Gem Finder API v2.2",
        "status": "online",
        "database": db_status,
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
    db_status = "not connected"
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            db_status = "healthy"
        except:
            db_status = "error"
        finally:
            conn.close()
            
    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }

# Get signals
@app.get("/api/v1/signals")
async def get_signals(limit: int = 10):
    conn = get_db_connection()
    if not conn:
        return {"signals": [], "message": "Database not configured"}
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('''
            SELECT * FROM crypto_signals 
            ORDER BY created_at DESC 
            LIMIT %s
        ''', (limit,))
        
        signals = cur.fetchall()
        cur.close()
        
        # Convert datetime to string
        for signal in signals:
            if signal.get('created_at'):
                signal['created_at'] = signal['created_at'].isoformat()
        
        return {"signals": signals, "count": len(signals)}
        
    except Exception as e:
        return {"error": str(e), "signals": []}
    finally:
        conn.close()

# Create test signal
@app.post("/api/v1/test-signal")
async def create_test_signal():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO crypto_signals (coin_id, symbol, signal_type, strength, price, message)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', ('bitcoin', 'BTC', 'TEST_SIGNAL', 0.85, 42000.0, 
        'Test signal created via API - Sistema funzionante!'))
        
        signal_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        
        return {
            "success": True,
            "signal_id": signal_id,
            "message": "Test signal created successfully!"
        }
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
