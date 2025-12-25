"""
Whale Tracker - Monitoraggio transazioni whale cryptocurrency
Integrazione Whale Alert API
"""
import os
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

import requests

logger = logging.getLogger(__name__)


class WhaleSize(Enum):
    """Classificazione dimensione whale"""
    MEGA = "🔴 MEGA WHALE"      # >$50M
    LARGE = "🟠 LARGE WHALE"    # $10M-$50M
    MEDIUM = "🟡 MEDIUM WHALE"  # $1M-$10M
    SMALL = "🟢 SMALL WHALE"    # $500K-$1M


@dataclass
class WhaleTransaction:
    """Transazione whale"""
    transaction_hash: str
    blockchain: str
    symbol: str
    amount: float
    amount_usd: float
    from_owner: str
    to_owner: str
    timestamp: int
    transaction_type: str  # transfer, mint, burn
    whale_size: WhaleSize


class WhaleAlertAPI:
    """Client Whale Alert API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("WHALE_ALERT_API_KEY", "")
        self.base_url = "https://api.whale-alert.io/v1"
        self.enabled = bool(self.api_key)
        
        if not self.enabled:
            logger.warning("⚠️ Whale Alert API non configurato - feature disabilitata")
    
    def get_recent_transactions(
        self,
        min_value: int = 1000000,  # $1M default
        start_time: Optional[int] = None,
        limit: int = 10
    ) -> List[WhaleTransaction]:
        """
        Recupera transazioni whale recenti
        
        Args:
            min_value: Valore minimo USD (default $1M)
            start_time: Unix timestamp start (default: last 10 min)
            limit: Max risultati (max 100)
        """
        if not self.enabled:
            return []
        
        if not start_time:
            start_time = int(time.time()) - 600  # Last 10 minutes
        
        end_time = int(time.time())
        
        try:
            url = f"{self.base_url}/transactions"
            params = {
                "api_key": self.api_key,
                "min_value": min_value,
                "start": start_time,
                "end": end_time,
                "limit": limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Whale Alert API error: {response.status_code}")
                return []
            
            data = response.json()
            
            if data.get("result") != "success":
                logger.error(f"Whale Alert error: {data}")
                return []
            
            transactions = []
            for tx in data.get("transactions", []):
                whale_tx = self._parse_transaction(tx)
                if whale_tx:
                    transactions.append(whale_tx)
            
            return transactions
            
        except Exception as e:
            logger.error(f"Error fetching whale transactions: {e}")
            return []
    
    def _parse_transaction(self, tx_data: Dict) -> Optional[WhaleTransaction]:
        """Parse transaction data from API"""
        try:
            amount_usd = tx_data.get("amount_usd", 0)
            
            # Determina whale size
            if amount_usd >= 50_000_000:
                whale_size = WhaleSize.MEGA
            elif amount_usd >= 10_000_000:
                whale_size = WhaleSize.LARGE
            elif amount_usd >= 1_000_000:
                whale_size = WhaleSize.MEDIUM
            else:
                whale_size = WhaleSize.SMALL
            
            return WhaleTransaction(
                transaction_hash=tx_data.get("hash", ""),
                blockchain=tx_data.get("blockchain", ""),
                symbol=tx_data.get("symbol", ""),
                amount=float(tx_data.get("amount", 0)),
                amount_usd=amount_usd,
                from_owner=tx_data.get("from", {}).get("owner_type", "unknown"),
                to_owner=tx_data.get("to", {}).get("owner_type", "unknown"),
                timestamp=tx_data.get("timestamp", 0),
                transaction_type=tx_data.get("transaction_type", "transfer"),
                whale_size=whale_size
            )
            
        except Exception as e:
            logger.error(f"Error parsing transaction: {e}")
            return None


class WhaleTracker:
    """Sistema tracking whale con cooldown e deduplication"""
    
    def __init__(self, whale_api: WhaleAlertAPI):
        self.whale_api = whale_api
        self.seen_transactions: set = set()  # Deduplication
        self.last_check_time = int(time.time())
        
        # Stats
        self.stats = {
            "total_whales_detected": 0,
            "mega_whales": 0,
            "large_whales": 0,
            "medium_whales": 0,
            "total_volume_usd": 0
        }
    
    def check_whale_activity(self) -> List[WhaleTransaction]:
        """
        Controlla nuove transazioni whale
        Returns: Lista transazioni nuove (non duplicate)
        """
        if not self.whale_api.enabled:
            return []
        
        # Fetch transazioni dall'ultimo check
        transactions = self.whale_api.get_recent_transactions(
            start_time=self.last_check_time,
            min_value=1_000_000,  # $1M minimum
            limit=50
        )
        
        # Update last check time
        self.last_check_time = int(time.time())
        
        # Filter duplicates
        new_transactions = []
        for tx in transactions:
            tx_id = f"{tx.blockchain}_{tx.transaction_hash}"
            
            if tx_id not in self.seen_transactions:
                self.seen_transactions.add(tx_id)
                new_transactions.append(tx)
                
                # Update stats
                self.stats["total_whales_detected"] += 1
                self.stats["total_volume_usd"] += tx.amount_usd
                
                if tx.whale_size == WhaleSize.MEGA:
                    self.stats["mega_whales"] += 1
                elif tx.whale_size == WhaleSize.LARGE:
                    self.stats["large_whales"] += 1
                elif tx.whale_size == WhaleSize.MEDIUM:
                    self.stats["medium_whales"] += 1
        
        # Cleanup old transactions (keep last 1000)
        if len(self.seen_transactions) > 1000:
            self.seen_transactions = set(list(self.seen_transactions)[-1000:])
        
        return new_transactions
    
    def get_stats(self) -> Dict:
        """Statistiche whale tracking"""
        return {
            **self.stats,
            "tracked_transactions": len(self.seen_transactions)
        }
    
    def reset_stats(self):
        """Reset statistiche"""
        self.stats = {
            "total_whales_detected": 0,
            "mega_whales": 0,
            "large_whales": 0,
            "medium_whales": 0,
            "total_volume_usd": 0
        }


class WhaleMessageTemplate:
    """Template messaggi Telegram per whale alerts"""
    
    @staticmethod
    def format_whale_alert(whale_tx: WhaleTransaction) -> str:
        """Formatta messaggio whale alert"""
        
        # Header con whale size
        header = f"{whale_tx.whale_size.value}\n"
        
        # Emoji basato su tipo transazione
        if whale_tx.transaction_type == "mint":
            emoji = "🏭"
            action = "MINTED"
        elif whale_tx.transaction_type == "burn":
            emoji = "🔥"
            action = "BURNED"
        else:
            emoji = "🐋"
            action = "TRANSFERRED"
        
        message = f"{header}{emoji} <b>WHALE {action}</b>\n\n"
        
        # Amount
        message += f"💰 <b>${whale_tx.amount_usd:,.0f}</b>\n"
        message += f"📊 {whale_tx.amount:,.2f} {whale_tx.symbol}\n\n"
        
        # Blockchain
        message += f"⛓️ {whale_tx.blockchain.upper()}\n"
        
        # From/To
        from_label = WhaleMessageTemplate._format_owner_type(whale_tx.from_owner)
        to_label = WhaleMessageTemplate._format_owner_type(whale_tx.to_owner)
        
        message += f"📤 From: {from_label}\n"
        message += f"📥 To: {to_label}\n"
        
        # Timestamp
        dt = datetime.fromtimestamp(whale_tx.timestamp)
        message += f"\n⏰ {dt.strftime('%H:%M:%S')}"
        
        # Transaction hash (shortened)
        if whale_tx.transaction_hash:
            short_hash = whale_tx.transaction_hash[:8] + "..." + whale_tx.transaction_hash[-8:]
            message += f"\n🔗 {short_hash}"
        
        return message
    
    @staticmethod
    def _format_owner_type(owner_type: str) -> str:
        """Formatta tipo owner con emoji"""
        emoji_map = {
            "exchange": "🏦 Exchange",
            "whale": "🐋 Whale",
            "unknown": "❓ Unknown",
            "genesis": "🌟 Genesis",
            "miner": "⛏️ Miner",
            "ico": "🚀 ICO",
            "defi": "🌾 DeFi",
            "merchant": "🏪 Merchant"
        }
        
        return emoji_map.get(owner_type.lower(), f"📍 {owner_type.title()}")


# Singleton instance (sarà inizializzato in main.py)
whale_api = WhaleAlertAPI()
whale_tracker = WhaleTracker(whale_api)

__all__ = [
    'WhaleAlertAPI',
    'WhaleTracker', 
    'WhaleTransaction',
    'WhaleSize',
    'WhaleMessageTemplate',
    'whale_api',
    'whale_tracker'
]
