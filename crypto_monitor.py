import requests
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

class CryptoMonitor:
    """Monitor crypto prices using CoinGecko API"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.tracked_coins = ["bitcoin", "ethereum", "binancecoin", "cardano", "solana"]
        self.last_prices = {}
        self.alert_thresholds = {
            "bitcoin": 0.05,     # 5% change
            "ethereum": 0.05,    # 5% change
            "default": 0.10      # 10% change for others
        }
    
    def get_prices(self) -> Dict:
        """Get current prices for tracked coins"""
        try:
            ids = ",".join(self.tracked_coins)
            url = f"{self.base_url}/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            print(f"Error fetching prices: {e}")
            return {}
    
    def check_price_changes(self, current_prices: Dict) -> List[Dict]:
        """Check for significant price changes"""
        alerts = []
        
        for coin, data in current_prices.items():
            current_price = data.get("usd", 0)
            change_24h = data.get("usd_24h_change", 0)
            
            # Check if we have previous price
            if coin in self.last_prices:
                last_price = self.last_prices[coin]
                change_percent = ((current_price - last_price) / last_price) * 100
                
                # Get threshold for this coin
                threshold = self.alert_thresholds.get(coin, self.alert_thresholds["default"])
                
                # Check if change exceeds threshold
                if abs(change_percent) >= threshold * 100:
                    alerts.append({
                        "coin": coin.upper(),
                        "current_price": current_price,
                        "last_price": last_price,
                        "change_percent": change_percent,
                        "change_24h": change_24h,
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            # Update last price
            self.last_prices[coin] = current_price
        
        return alerts
    
    def format_alert_message(self, alert: Dict) -> str:
        """Format alert for Telegram"""
        emoji = "📈" if alert["change_percent"] > 0 else "📉"
        direction = "salito" if alert["change_percent"] > 0 else "sceso"
        
        return f"""
{emoji} <b>ALERT PREZZO {alert['coin']}</b>

💰 <b>Prezzo:</b> ${alert['current_price']:,.2f}
📊 <b>Variazione:</b> {alert['change_percent']:+.2f}%
📅 <b>24h:</b> {alert['change_24h']:+.2f}%

Il prezzo è {direction} significativamente!
"""

# Global instance
crypto_monitor = CryptoMonitor()
```

5. **Commit message**: "Add crypto price monitor module"
6. **Clicca**: **"Commit new file"**

## 📝 PASSO 2 - AGGIORNA `main.py`:

1. **Clicca** su `main.py`
2. **Clicca** l'icona matita ✏️
3. **Seleziona tutto** (Ctrl+A) e **cancella**
4. **Apri** il file `C:\Users\giona\Desktop\main_with_monitor.py`
5. **Copia tutto** il contenuto e **incolla** su GitHub
6. **Commit message**: "Add real-time price monitoring"
7. **Clicca**: **"Commit changes"**

## 📝 PASSO 3 - AGGIORNA `requirements.txt`:

1. **Clicca** su `requirements.txt`
2. **Clicca** matita ✏️
3. **Aggiungi** questa riga alla fine:
```
   aiofiles==23.2.1
