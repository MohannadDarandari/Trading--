"""
⚙️ Configuration Settings for Polymarket Trading Bot
إعدادات البوت
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

class Config:
    """Bot configuration"""
    
    # ============================================
    # 🔐 WALLET & BLOCKCHAIN
    # ============================================
    PRIVATE_KEY = os.getenv('PRIVATE_KEY', '')
    RPC_URL = os.getenv('RPC_URL', 'https://polygon-mainnet.g.alchemy.com/v2/demo')
    CHAIN_ID = int(os.getenv('CHAIN_ID', '137'))
    
    # ============================================
    # 🌐 POLYMARKET API
    # ============================================
    POLYMARKET_API_URL = os.getenv('POLYMARKET_API_URL', 'https://clob.polymarket.com')
    POLYMARKET_HOST = os.getenv('POLYMARKET_HOST', 'clob.polymarket.com')

    # Optional HTTP/SOCKS proxy (for blocked networks)
    PROXY_URL = os.getenv('PROXY_URL', '')
    PROXY_ENABLED = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
    
    # ============================================
    # 💰 TRADING LIMITS
    # ============================================
    MAX_POSITION_SIZE = float(os.getenv('MAX_POSITION_SIZE', '50'))  # USD
    MAX_DAILY_TRADES = int(os.getenv('MAX_DAILY_TRADES', '10'))
    STOP_LOSS = float(os.getenv('STOP_LOSS', '0.2'))  # 20%
    TAKE_PROFIT = float(os.getenv('TAKE_PROFIT', '0.5'))  # 50%
    
    # ============================================
    # 🎯 STRATEGY
    # ============================================
    STRATEGY = os.getenv('STRATEGY', 'copy_whales')
    MIN_CONFIDENCE = float(os.getenv('MIN_CONFIDENCE', '0.7'))
    DRY_RUN = os.getenv('DRY_RUN', 'true').lower() == 'true'
    
    # ============================================
    # 📊 WHALE TRACKING
    # ============================================
    WHALE_WALLETS = os.getenv('WHALE_WALLETS', '').split(',')
    WHALE_WALLETS = [w.strip() for w in WHALE_WALLETS if w.strip()]
    MIN_WHALE_TRADE_SIZE = float(os.getenv('MIN_WHALE_TRADE_SIZE', '100'))
    
    # ============================================
    # 🔔 NOTIFICATIONS
    # ============================================
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
    
    # ============================================
    # 🛠️ ADVANCED
    # ============================================
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    DATA_DIR = Path(os.getenv('DATA_DIR', './data'))
    AUTO_RESTART = os.getenv('AUTO_RESTART', 'true').lower() == 'true'
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    GAS_MULTIPLIER = float(os.getenv('GAS_MULTIPLIER', '1.1'))
    
    # ============================================
    # 📁 DIRECTORIES
    # ============================================
    LOGS_DIR = DATA_DIR / 'logs'
    MARKETS_DIR = DATA_DIR / 'markets'
    TRADES_DIR = DATA_DIR / 'trades'
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        errors = []
        
        if not cls.PRIVATE_KEY or cls.PRIVATE_KEY == 'your_polygon_wallet_private_key_here':
            errors.append("❌ PRIVATE_KEY not configured in .env")
        
        if 'demo' in cls.RPC_URL or 'YOUR_API_KEY' in cls.RPC_URL:
            errors.append("⚠️ Using demo RPC - get a real one from Alchemy/Infura")
        
        if cls.MAX_POSITION_SIZE > 1000:
            errors.append("⚠️ MAX_POSITION_SIZE is very high - consider lowering it")
        
        return errors
    
    @classmethod
    def setup_directories(cls):
        """Create necessary directories"""
        for directory in [cls.DATA_DIR, cls.LOGS_DIR, cls.MARKETS_DIR, cls.TRADES_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def display(cls):
        """Display current configuration (safe print)"""
        print("\n" + "="*60)
        print("🤖 POLYMARKET TRADING BOT CONFIGURATION")
        print("="*60)
        print(f"🔹 Strategy: {cls.STRATEGY}")
        print(f"🔹 Max Position: ${cls.MAX_POSITION_SIZE}")
        print(f"🔹 Max Daily Trades: {cls.MAX_DAILY_TRADES}")
        print(f"🔹 Stop Loss: {cls.STOP_LOSS*100}%")
        print(f"🔹 Take Profit: {cls.TAKE_PROFIT*100}%")
        print(f"🔹 Min Confidence: {cls.MIN_CONFIDENCE*100}%")
        print(f"🔹 Network: Polygon (Chain ID: {cls.CHAIN_ID})")
        print(f"🔹 Wallet: {cls.PRIVATE_KEY[:6]}...{cls.PRIVATE_KEY[-4:] if cls.PRIVATE_KEY else 'NOT SET'}")
        print(f"🔹 Dry Run: {'✅ YES (Safe Mode)' if cls.DRY_RUN else '❌ NO (Real Trading!)'}")
        
        if cls.WHALE_WALLETS:
            print(f"🔹 Tracking {len(cls.WHALE_WALLETS)} whale wallet(s)")
        
        print("="*60 + "\n")


# Validate on import
if __name__ != "__main__":
    validation_errors = Config.validate()
    if validation_errors:
        print("\n⚠️ Configuration warnings:")
        for error in validation_errors:
            print(f"  {error}")
