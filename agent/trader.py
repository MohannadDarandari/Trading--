"""
🤖 Polymarket Trading Bot - البوت الرئيسي
Main trading agent
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import Config
from agent.analyzer import MarketAnalyzer
from agent.strategies import StrategyFactory


class PolymarketTrader:
    """
    🤖 Polymarket Trading Agent
    بوت تداول Polymarket
    """
    
    def __init__(self, strategy_name: str = None, dry_run: bool = None):
        """Initialize the trading bot"""
        
        print("\n" + "="*80)
        print("🚀 Polymarket Trading Bot v1.0")
        print("="*80 + "\n")
        
        # Setup configuration
        Config.setup_directories()
        Config.display()
        
        # Validate configuration
        errors = Config.validate()
        if errors:
            print("\n❌ Configuration errors found:")
            for error in errors:
                print(f"   {error}")
            
            if not Config.DRY_RUN:
                print("\n⚠️ Critical errors found. Please fix .env file before continuing.")
                print("💡 Copy .env.example to .env and add your actual values\n")
                sys.exit(1)
        
        # Override dry_run if specified
        if dry_run is not None:
            Config.DRY_RUN = dry_run
        
        # Initialize components
        self.analyzer = MarketAnalyzer(Config.POLYMARKET_API_URL)
        
        # Create strategy
        strategy_name = strategy_name or Config.STRATEGY
        self.strategy = StrategyFactory.create_strategy(
            strategy_name,
            whale_addresses=Config.WHALE_WALLETS,
            min_whale_trade_size=Config.MIN_WHALE_TRADE_SIZE,
        )
        
        # Trading state
        self.active_positions = []
        self.daily_trades = 0
        self.total_profit = 0.0
        self.daily_profit = 0.0
        
        # Safety
        if Config.DRY_RUN:
            print("✅ DRY RUN MODE - No real trades will be executed")
        else:
            print("⚠️ LIVE TRADING MODE - Real money at risk!")
            print("⏰ Starting in 10 seconds... (Ctrl+C to cancel)\n")
            try:
                time.sleep(10)
            except KeyboardInterrupt:
                print("\n❌ Cancelled by user")
                sys.exit(0)
    
    def find_opportunities(self):
        """
        ابحث عن فرص تداول
        Find trading opportunities
        """
        print("\n" + "="*80)
        print(f"🔍 Scanning markets... [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
        print("="*80)
        
        # Get active markets
        markets = self.analyzer.get_active_markets(limit=20)
        
        if not markets:
            print("❌ No markets found")
            return []
        
        # Find opportunities
        opportunities = self.analyzer.find_opportunities(
            markets,
            min_confidence=Config.MIN_CONFIDENCE
        )
        
        return opportunities
    
    def execute_trade(self, opportunity: Dict):
        """
        نفذ صفقة
        Execute a trade
        """
        # Check daily trade limit
        if self.daily_trades >= Config.MAX_DAILY_TRADES:
            print(f"⚠️ Daily trade limit reached ({Config.MAX_DAILY_TRADES})")
            return False
        
        # Check if strategy wants to trade
        if not self.strategy.should_trade(opportunity):
            print(f"⏭️ Strategy '{self.strategy.name}' skipped this opportunity")
            return False
        
        # Calculate position size
        position_size = self.strategy.get_position_size(
            opportunity,
            Config.MAX_POSITION_SIZE
        )
        
        # Prepare trade details
        trade = {
            'market_id': opportunity['market_id'],
            'question': opportunity['question'],
            'recommendation': opportunity['recommendation'],
            'confidence': opportunity['confidence'],
            'position_size': position_size,
            'entry_price': opportunity['current_price_yes'],
            'timestamp': datetime.now().isoformat(),
            'strategy': self.strategy.name,
        }
        
        print("\n" + "="*80)
        print("💰 TRADE EXECUTION")
        print("="*80)
        print(f"📝 Market: {trade['question'][:60]}...")
        print(f"🎯 Action: {trade['recommendation']}")
        print(f"💵 Size: ${trade['position_size']:.2f}")
        print(f"💹 Entry Price: ${trade['entry_price']:.3f}")
        print(f"🎲 Confidence: {trade['confidence']*100:.0f}%")
        print(f"📊 Strategy: {trade['strategy']}")
        
        if Config.DRY_RUN:
            print("\n✅ [DRY RUN] Trade simulated successfully")
            print("   (No real trade executed)")
        else:
            # Execute real trade here
            # This would use py-clob-client or Web3
            print("\n🔄 Executing real trade...")
            success = self._execute_real_trade(trade)
            
            if success:
                print("✅ Trade executed successfully!")
            else:
                print("❌ Trade execution failed")
                return False
        
        # Update state
        self.active_positions.append(trade)
        self.daily_trades += 1
        
        # Log trade
        self._log_trade(trade)
        
        print("="*80 + "\n")
        
        return True
    
    def _execute_real_trade(self, trade: Dict) -> bool:
        """
        نفذ صفقة حقيقية
        Execute a real trade using Polymarket API
        
        ⚠️ This requires:
        - py-clob-client library
        - Wallet with USDC on Polygon
        - Proper API authentication
        """
        try:
            # Note: This is a placeholder
            # Real implementation would use py-clob-client
            
            # from py_clob_client.client import ClobClient
            # from py_clob_client.constants import POLYGON
            # 
            # client = ClobClient(
            #     key=Config.PRIVATE_KEY,
            #     chain_id=Config.CHAIN_ID,
            #     host=Config.POLYMARKET_HOST,
            # )
            # 
            # # Place order
            # order = client.create_order(...)
            # 
            # return True
            
            print("⚠️ Real trade execution not implemented yet")
            print("💡 To enable real trading:")
            print("   1. Install py-clob-client")
            print("   2. Add Polymarket API integration")
            print("   3. Ensure wallet has USDC on Polygon")
            
            return False
            
        except Exception as e:
            print(f"❌ Trade execution error: {e}")
            return False
    
    def monitor_positions(self):
        """
        راقب الصفقات المفتوحة
        Monitor open positions
        """
        if not self.active_positions:
            return
        
        print("\n" + "="*80)
        print("📊 MONITORING POSITIONS")
        print("="*80)
        
        for position in self.active_positions:
            # Get current price
            market_id = position['market_id']
            market = self.analyzer.get_market_details(market_id)
            
            if not market:
                continue
            
            # Calculate P&L
            entry_price = position['entry_price']
            current_price = float(market.get('outcomes', [{}])[0].get('price', entry_price))
            position_size = position['position_size']
            
            # Calculate profit/loss
            if position['recommendation'] == 'BUY_YES':
                pnl = (current_price - entry_price) * position_size
            else:
                pnl = (entry_price - current_price) * position_size
            
            pnl_percent = (pnl / position_size) * 100 if position_size > 0 else 0
            
            print(f"\n📝 {position['question'][:50]}...")
            print(f"   Entry: ${entry_price:.3f} → Current: ${current_price:.3f}")
            print(f"   P&L: ${pnl:+.2f} ({pnl_percent:+.1f}%)")
            
            # Check stop loss / take profit
            if pnl_percent <= -Config.STOP_LOSS * 100:
                print(f"   🛑 STOP LOSS triggered!")
                # Close position
            elif pnl_percent >= Config.TAKE_PROFIT * 100:
                print(f"   🎯 TAKE PROFIT triggered!")
                # Close position
        
        print("="*80 + "\n")
    
    def _log_trade(self, trade: Dict):
        """
        سجل الصفقة في ملف
        Log trade to file
        """
        try:
            log_file = Config.TRADES_DIR / f"trades_{datetime.now().strftime('%Y%m%d')}.json"
            
            # Load existing trades
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    trades = json.load(f)
            else:
                trades = []
            
            # Add new trade
            trades.append(trade)
            
            # Save
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(trades, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            print(f"⚠️ Failed to log trade: {e}")
    
    def display_stats(self):
        """
        اعرض إحصائيات التداول
        Display trading statistics
        """
        print("\n" + "="*80)
        print("📈 TRADING STATISTICS")
        print("="*80)
        print(f"🔹 Strategy: {self.strategy.name}")
        print(f"🔹 Trades today: {self.daily_trades} / {Config.MAX_DAILY_TRADES}")
        print(f"🔹 Active positions: {len(self.active_positions)}")
        print(f"🔹 Daily P&L: ${self.daily_profit:+.2f}")
        print(f"🔹 Total P&L: ${self.total_profit:+.2f}")
        print("="*80 + "\n")
    
    def run(self, interval: int = 60):
        """
        شغل البوت
        Run the trading bot
        
        Args:
            interval: Time between scans (seconds)
        """
        print(f"🤖 Bot started - scanning every {interval} seconds")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                # Find opportunities
                opportunities = self.find_opportunities()
                
                # Execute trades
                if opportunities:
                    for opportunity in opportunities[:3]:  # Max 3 per scan
                        self.execute_trade(opportunity)
                        time.sleep(2)  # Small delay between trades
                
                # Monitor positions
                self.monitor_positions()
                
                # Display stats
                self.display_stats()
                
                # Wait for next scan
                print(f"⏰ Next scan in {interval} seconds...\n")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Bot stopped by user")
            self.display_stats()
            print("👋 Goodbye!\n")


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description='🤖 Polymarket Trading Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python trader.py --strategy copy_whales --dry-run
  python trader.py --strategy arbitrage --budget 100
  python trader.py --watch "Will Bitcoin reach $100k?"
        """
    )
    
    parser.add_argument(
        '--strategy',
        type=str,
        choices=['copy_whales', 'arbitrage', 'momentum', 'manual'],
        help='Trading strategy to use'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in simulation mode (no real trades)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Scan interval in seconds (default: 60)'
    )
    
    parser.add_argument(
        '--watch',
        type=str,
        help='Watch a specific market (question text)'
    )
    
    args = parser.parse_args()
    
    # Create and run trader
    trader = PolymarketTrader(
        strategy_name=args.strategy,
        dry_run=args.dry_run
    )
    
    # Run the bot
    trader.run(interval=args.interval)


if __name__ == "__main__":
    main()
