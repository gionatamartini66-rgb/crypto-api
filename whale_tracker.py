"""
Whale Tracker - API V2 Updated + Extended Wallet List
Etherscan ha deprecato V1, ora usa V2
"""

import os
import requests
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

class WhaleTracker:
    """Traccia whale wallets - Updated for API V2"""
    
    def __init__(self):
        self.etherscan_key = os.getenv('ETHERSCAN_API_KEY')
        self.bscscan_key = os.getenv('BSCSCAN_API_KEY')
        
        # API V2 endpoints
        self.etherscan_api = "https://api.etherscan.io/v2/api"
        self.bscscan_api = "https://api.bscscan.com/api"  # BSC usa ancora V1
        
        # [WHALE] EXPANDED WHALE WALLET LIST - 30+ WALLETS
        self.known_whales_eth = [
            # Binance Wallets (Top 5)
            "0x28C6c06298d514Db089934071355E5743bf21d60",  # Binance 14
            "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549",  # Binance 15
            "0xDFd5293D8e347dFe59E90eFd55b2956a1343963d",  # Binance 16
            "0x56Eddb7aa87536c09CCc2793473599fD21A8b17F",  # Binance Hot
            "0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE",  # Binance Main
            
            # Wintermute (Top Market Maker)
            "0x9696f59E4d72E237BE84fFD425DCaD154Bf96976",  # Wintermute Trading
            "0x00000000ae347930bd1e7b0f35588b92280f9e75",  # Wintermute 2
            
            # Jump Trading (HFT Giant)
            "0xF977814e90dA44bFA03b6295A0616a897441aceC",  # Jump Trading Main
            "0x0548F59fEE79f8832C299e01dCA5c76F034F558e",  # Jump Trading 2
            
            # Cumberland DRW (OTC Desk)
            "0x5c0401e81Bc07Ca70fAD469b45b96B3dF3D7a76A",  # Cumberland Main
            "0x176F3DAb24a159341c0509bB36B833E7fdd0a132",  # Cumberland 2
            
            # Alameda Research (Legacy Monitoring)
            "0x477573f212A7bdD5F7C12889bd1ad0aA44fb82aa",  # Alameda Main
            "0x2FAF487A4414Fe77e2327F0bf4AE2a264a776AD2",  # Alameda FTX
            
            # Galaxy Digital (Institutional)
            "0x1E8150050A7a4715aad42b905C08df76883f396F",  # Galaxy Digital Main
            "0x61EDCDf5bb737ADffE5043706e7C5bb1f1a56eEA",  # Galaxy Digital 2
            
            # Three Arrows Capital (Legacy)
            "0x4862733B5FdDFd35f35ea8CCf08F5045e57388B3",  # 3AC Main
            
            # Coinbase Institutional
            "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3",  # Coinbase 1
            "0x503828976D22510aad0201ac7EC88293211D23Da",  # Coinbase 2
            "0xddfAbCdc4D8FfC6d5beaf154f18B778f892A0740",  # Coinbase 3
            
            # Kraken Exchange
            "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2",  # Kraken 1
            "0x0A869d79a7052C7f1b55a8EbAbbEa3420F0D1E13",  # Kraken 2
            
            # Gemini Exchange
            "0x5F65f7b609678448494De4C87521CdF6cEf1e932",  # Gemini Main
            "0xd24400ae8BfEBb18cA49Be86258a3C749cf46853",  # Gemini 2
            
            # Bitfinex
            "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",  # Bitfinex 1
            "0x876EabF441B2EE5B5b0554Fd502a8E0600950cFa",  # Bitfinex 2
            
            # Crypto.com
            "0x6262998Ced04146fA42253a5C0AF90CA02dfd2A3",  # Crypto.com Main
        ]
        
        self.known_whales_bsc = [
            # Binance BSC (Top Wallets)
            "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3",  # Binance BSC Hot
            "0xF977814e90dA44bFA03b6295A0616a897441aceC",  # Binance BSC Main
            "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",  # Binance BSC 8
            
            # PancakeSwap (DEX Giant)
            "0x73feaa1eE314F8c655E354234017bE2193C9E24E",  # PancakeSwap Main
            "0x1B96B92314C44b159149f7E0303511fB2Fc4774f",  # PancakeSwap V3
            "0xa5f208e072434bC67592E4C49C1B991BA79BCA46",  # PancakeSwap Team
            
            # Trust Wallet
            "0x9Ac64Cc6e4415144C455BD8E4837Fea55603e5c3",  # Trust Wallet Main
            
            # Venus Protocol
            "0xfD36E2c2a6789Db23113685031d7F16329158384",  # Venus Main
            
            # Alpaca Finance
            "0x158Da805682BdC8ee32d52833aD41E74bb951E59",  # Alpaca Main
        ]
    
    def get_token_supply(self, token_address: str, chain: str = "eth"):
        """Get total supply of token"""
        try:
            if chain == "eth":
                api_url = "https://api.etherscan.io/v2/api"
                api_key = self.etherscan_key
            else:
                api_url = self.bscscan_api
                api_key = self.bscscan_key
            
            params = {
                'chainid': 1 if chain == "eth" else 56,
                'module': 'stats',
                'action': 'tokensupply',
                'contractaddress': token_address,
                'apikey': api_key
            }
            
            response = requests.get(api_url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == '1':
                return float(data['result'])
            return None
            
        except Exception as e:
            print(f"Error getting supply: {e}")
            return None
    
    def get_token_balance(self, token_address: str, wallet_address: str, chain: str = "eth"):
        """Get token balance for specific wallet"""
        try:
            if chain == "eth":
                api_url = "https://api.etherscan.io/v2/api"
                chainid = 1
            else:
                api_url = self.bscscan_api
                chainid = 56
            
            api_key = self.etherscan_key if chain == "eth" else self.bscscan_key
            
            params = {
                'chainid': chainid,
                'module': 'account',
                'action': 'tokenbalance',
                'contractaddress': token_address,
                'address': wallet_address,
                'tag': 'latest',
                'apikey': api_key
            }
            
            response = requests.get(api_url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == '1':
                return float(data['result'])
            return 0
            
        except Exception as e:
            print(f"Error getting balance: {e}")
            return 0
    
    def detect_accumulation(self, token_address: str, chain: str = "eth"):
        """
        Rileva accumulation analizzando top holders conosciuti
        Usa liste predefinite di whale wallets
        """
        
        # Seleziona wallet list per chain
        whale_list = self.known_whales_eth if chain == "eth" else self.known_whales_bsc
        
        print(f"\nAnalyzing whale accumulation for token: {token_address[:10]}...")
        
        total_supply = self.get_token_supply(token_address, chain)
        if not total_supply:
            print("Could not get total supply")
            return None
        
        print(f"Total supply: {total_supply:,.0f}")
        
        # Analizza balance di whale conosciute
        whale_data = []
        total_whale_balance = 0
        
        for wallet in whale_list:
            balance = self.get_token_balance(token_address, wallet, chain)
            if balance > 0:
                percentage = (balance / total_supply * 100)
                whale_data.append({
                    'address': wallet,
                    'balance': balance,
                    'percentage': percentage
                })
                total_whale_balance += balance
                print(f"  Whale {wallet[:10]}...: {percentage:.2f}%")
        
        if not whale_data:
            print("No significant whale holdings detected")
            return None
        
        total_whale_percentage = (total_whale_balance / total_supply * 100)
        
        # Determina signal
        if total_whale_percentage > 30:
            signal = 'HIGH'
            alert = True
            emoji = 'ALERT'
        elif total_whale_percentage > 15:
            signal = 'MEDIUM'
            alert = True
            emoji = 'WARNING'
        else:
            signal = 'LOW'
            alert = False
            emoji = 'OK'
        
        print(f"\n{emoji} Signal: {signal} ({total_whale_percentage:.2f}% whale ownership)")
        
        return {
            'whale_count': len(whale_data),
            'total_whale_percentage': round(total_whale_percentage, 2),
            'signal': signal,
            'alert': alert,
            'whale_data': whale_data,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_whale_list_for_chain(self, chain: str = "eth") -> List[str]:
        """Ritorna lista whale per chain"""
        return self.known_whales_eth if chain == "eth" else self.known_whales_bsc


if __name__ == "__main__":
    tracker = WhaleTracker()
    print("Whale Tracker V2 Extended - Ready!")
    print(f"Monitoring {len(tracker.known_whales_eth)} ETH wallets")
    print(f"Monitoring {len(tracker.known_whales_bsc)} BSC wallets")
    
    # Test with USDT
    usdt = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    result = tracker.detect_accumulation(usdt, 'eth')
    
    if result:
        print(f"\nRESULTS:")
        print(f"  Whales detected: {result['whale_count']}")
        print(f"  Total whale %: {result['total_whale_percentage']}%")
        print(f"  Signal: {result['signal']}")
        print(f"  Alert: {result['alert']}")
