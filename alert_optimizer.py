"""
Alert Optimizer - Sistema Intelligente di Gestione Alert
Riduce false positive e spam notifiche
"""
import time
from typing import Dict, Set, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

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
    SENTIMENT = "SENTIMENT"

@dataclass
class AlertRecord:
    """Record di un alert inviato"""
    coin_id: str
    alert_type: AlertType
    timestamp: float
    price: float
    priority: AlertPriority

class AlertOptimizer:
    """
    Sistema di ottimizzazione alert con:
    - Cooldown per coin
    - Filtri volume/market cap
    - Priorità intelligente
    - Rate limiting
    """
    
    def __init__(self):
        # Cooldown tracking
        self.alert_history: Dict[str, AlertRecord] = {}
        
        # Configurazione cooldown (secondi)
        self.cooldown_config = {
            AlertPriority.HIGH: 1800,    # 30 minuti
            AlertPriority.MEDIUM: 3600,  # 1 ora
            AlertPriority.LOW: 7200      # 2 ore
        }
        
        # Filtri minimi
        self.min_volume_24h = 1_000_000  # $1M volume minimo
        self.min_market_cap = 10_000_000  # $10M market cap minimo
        
        # Rate limiting
        self.max_alerts_per_minute = 5
        self.alerts_sent_minute: list = []
        
        # Statistiche
        self.stats = {
            "total_checks": 0,
            "alerts_sent": 0,
            "alerts_blocked_cooldown": 0,
            "alerts_blocked_filters": 0,
            "alerts_blocked_rate_limit": 0
        }
    
    def should_send_alert(
        self, 
        coin_id: str,
        alert_type: AlertType,
        crypto_data: Dict,
        priority: AlertPriority = AlertPriority.MEDIUM
    ) -> tuple[bool, Optional[str]]:
        """
        Determina se un alert deve essere inviato
        
        Returns:
            (should_send: bool, reason: str)
        """
        self.stats["total_checks"] += 1
        
        # 1. Check rate limiting globale
        if not self._check_rate_limit():
            self.stats["alerts_blocked_rate_limit"] += 1
            return False, "Rate limit raggiunto"
        
        # 2. Check filtri base (volume, market cap)
        passes_filters, filter_reason = self._check_filters(crypto_data)
        if not passes_filters:
            self.stats["alerts_blocked_filters"] += 1
            return False, filter_reason
        
        # 3. Check cooldown specifico coin
        alert_key = f"{coin_id}_{alert_type.value}"
        
        if alert_key in self.alert_history:
            last_alert = self.alert_history[alert_key]
            cooldown_seconds = self.cooldown_config[last_alert.priority]
            time_since_last = time.time() - last_alert.timestamp
            
            if time_since_last < cooldown_seconds:
                remaining = cooldown_seconds - time_since_last
                self.stats["alerts_blocked_cooldown"] += 1
                return False, f"Cooldown attivo ({remaining/60:.1f} min rimanenti)"
        
        # 4. Check priority override (HIGH bypassa alcuni filtri)
        if priority == AlertPriority.HIGH:
            # Alert HIGH sempre passano se non in cooldown
            pass
        
        # Alert approvato!
        return True, "Alert approvato"
    
    def record_alert(
        self,
        coin_id: str,
        alert_type: AlertType,
        price: float,
        priority: AlertPriority
    ):
        """Registra alert inviato per tracking cooldown"""
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
    
    def _check_rate_limit(self) -> bool:
        """Verifica rate limiting globale"""
        now = time.time()
        
        # Rimuovi alert più vecchi di 1 minuto
        self.alerts_sent_minute = [
            t for t in self.alerts_sent_minute 
            if now - t < 60
        ]
        
        return len(self.alerts_sent_minute) < self.max_alerts_per_minute
    
    def _track_rate_limit(self):
        """Traccia alert per rate limiting"""
        self.alerts_sent_minute.append(time.time())
    
    def _check_filters(self, crypto_data: Dict) -> tuple[bool, Optional[str]]:
        """
        Applica filtri qualità:
        - Volume 24h minimo
        - Market cap minimo
        - Prezzo valido
        """
        # Volume 24h
        volume = crypto_data.get('volume24h', 0)
        if volume < self.min_volume_24h:
            return False, f"Volume basso (${volume:,.0f})"
        
        # Market cap
        market_cap = crypto_data.get('marketCap', 0)
        if market_cap < self.min_market_cap:
            return False, f"Market cap basso (${market_cap:,.0f})"
        
        # Prezzo valido
        price = crypto_data.get('price', 0)
        if price <= 0:
            return False, "Prezzo non valido"
        
        return True, None
    
    def get_priority(
        self,
        alert_type: AlertType,
        crypto_data: Dict
    ) -> AlertPriority:
        """
        Determina priorità alert basata su:
        - Tipo di alert
        - Variazione prezzo
        - Volume
        - Market cap
        """
        change_24h = abs(crypto_data.get('change24h', 0))
        volume = crypto_data.get('volume24h', 0)
        market_cap = crypto_data.get('marketCap', 0)
        
        # Regole priorità HIGH
        if alert_type == AlertType.WHALE:
            return AlertPriority.HIGH
        
        if alert_type == AlertType.PUMP and change_24h > 100:
            return AlertPriority.HIGH
        
        if alert_type == AlertType.STRONG_BUY and market_cap > 1_000_000_000:
            return AlertPriority.HIGH
        
        # Regole priorità MEDIUM
        if alert_type == AlertType.STRONG_BUY:
            return AlertPriority.MEDIUM
        
        if alert_type == AlertType.PUMP and change_24h > 50:
            return AlertPriority.MEDIUM
        
        if alert_type == AlertType.VOLUME_SPIKE:
            return AlertPriority.MEDIUM
        
        # Default LOW
        return AlertPriority.LOW
    
    def cleanup_old_alerts(self, max_age_hours: int = 24):
        """Rimuove alert vecchi dalla history"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        self.alert_history = {
            key: record 
            for key, record in self.alert_history.items()
            if record.timestamp > cutoff_time
        }
    
    def get_stats(self) -> Dict:
        """Restituisce statistiche sistema"""
        return {
            **self.stats,
            "active_cooldowns": len(self.alert_history),
            "success_rate": (
                self.stats["alerts_sent"] / self.stats["total_checks"] * 100
                if self.stats["total_checks"] > 0 else 0
            )
        }
    
    def reset_stats(self):
        """Reset statistiche"""
        self.stats = {
            "total_checks": 0,
            "alerts_sent": 0,
            "alerts_blocked_cooldown": 0,
            "alerts_blocked_filters": 0,
            "alerts_blocked_rate_limit": 0
        }


class MessageTemplate:
    """Template messaggi Telegram ottimizzati"""
    
    @staticmethod
    def format_alert(
        alert_type: AlertType,
        priority: AlertPriority,
        crypto_data: Dict
    ) -> str:
        """Formatta messaggio alert basato su tipo e priorità"""
        
        name = crypto_data['name']
        symbol = crypto_data['symbol']
        price = crypto_data['price']
        change = crypto_data.get('change24h', 0)
        
        # Header con priorità
        header = f"{priority.value}\n"
        
        if alert_type == AlertType.STRONG_BUY:
            emoji = "🚀"
            title = "STRONG BUY SIGNAL"
            extra = f"🤖 AI Score: {crypto_data.get('aiScore', 'N/A')}/100"
            
        elif alert_type == AlertType.WHALE:
            emoji = "🐋"
            title = "WHALE ACTIVITY"
            extra = f"📊 Activity: {crypto_data.get('whaleActivity', 'HIGH')}"
            
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
        
        # Costruisci messaggio
        message = f"{header}{emoji} <b>{title}</b>\n\n"
        message += f"💎 {name} ({symbol})\n"
        message += f"💰 ${price:.8f}\n"
        
        if change != 0:
            direction = "📈" if change > 0 else "📉"
            message += f"{direction} {change:+.2f}% (24h)\n"
        
        if extra:
            message += f"\n{extra}"
        
        # Footer con timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        message += f"\n\n⏰ {timestamp}"
        
        return message


# Singleton instance
alert_optimizer = AlertOptimizer()

__all__ = ['AlertOptimizer', 'AlertType', 'AlertPriority', 'MessageTemplate', 'alert_optimizer']
