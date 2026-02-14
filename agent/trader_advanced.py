"""
🤖 ADVANCED Polymarket Trading Bot v2.0 - البوت المحترف
Most powerful automated trading system for Polymarket
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import Config
from agent.advanced_analyzer import AdvancedMarketAnalyzer
from agent.advanced_strategies import (
    MarketMakingStrategy,
    AdvancedWhaleTracker,
    EnhancedRiskManager
)
from agent.strategies import StrategyFactory


class AdvancedPolymarketTrader:
    """
    🚀 Advanced Polymarket Trading Bot v2.0
    
    المميزات:
    - تحليل AI متقدم
    - Market Making Strategy
    - Whale Tracking الذكي
    - Risk Management احترافي
    - Multi-strategy execution
    """
    
    def __init__(self, strategies: List[str] = None, dry_run: bool = None):
        """Initialize the advanced trading bot"""
        
        print("\n" + "="*80)
        print("🚀 ADVANCED Polymarket Trading Bot v2.0")
        print("   💎 Premium Edition with AI & Multi-Strategy")
        print("="*80 + "\n")
        
        # Setup configuration
        Config.setup_directories()
        Config.display()
        
        # Validate configuration
        errors = Config.validate()
        if errors:
            print("\n⚠️ Configuration warnings:")
            for error in errors:
                print(f"   {error}")
            
            if not Config.DRY_RUN and any("PRIVATE_KEY" in e for e in errors):
                print("\n❌ Critical: PRIVATE_KEY required for live trading")
                print("💡 Set DRY_RUN=true in .env to test without real trades\n")
                sys.exit(1)
        
        # Override dry_run if specified
        if dry_run is not None:
            Config.DRY_RUN = dry_run
        
        # === Initialize Advanced Components ===
        
        # 1. Advanced Market Analyzer with AI
        print("\n🧠 Initializing AI Market Analyzer...")
        self.analyzer = AdvancedMarketAnalyzer(Config.POLYMARKET_API_URL)
        
        # 2. Market Making Strategy
        print("💰 Initializing Market Making Strategy...")
        self.market_maker = MarketMakingStrategy(
            min_spread=0.03,
            target_spread=0.05
        )
        
        # 3. Whale Tracker
        print("🐋 Initializing Whale Tracker...")
        self.whale_tracker = AdvancedWhaleTracker(
            whale_wallets=Config.WHALE_WALLETS
        )
        
        # 4. Risk Manager
        print("🛡️ Initializing Risk Manager...")
        self.risk_manager = EnhancedRiskManager(
            max_position=Config.MAX_POSITION_SIZE,
            max_daily_loss=Config.MAX_POSITION_SIZE * 5,  # Max loss = 5x position size
            max_total_exposure=Config.MAX_POSITION_SIZE * 10  # Max exposure = 10x position size
        )
        
        # 5. Additional Strategies (from original)
        print("📊 Loading Additional Strategies...")
        self.strategies = strategies or [Config.STRATEGY]
        self.strategy_instances = []
        
        for strategy_name in self.strategies:
            strategy = StrategyFactory.create_strategy(
                strategy_name,
                whale_addresses=Config.WHALE_WALLETS,
                min_whale_trade_size=Config.MIN_WHALE_TRADE_SIZE,
            )
            self.strategy_instances.append(strategy)
        
        # Trading state
        self.active_positions = []
        self.daily_trades = 0
        self.total_profit = 0.0
        self.daily_profit = 0.0
        self.session_start = datetime.now()
        
        # Performance tracking
        self.trades_history = []
        self.opportunities_found = 0
        self.opportunities_taken = 0
        
        # Safety check
        if Config.DRY_RUN:
            print("\n✅ DRY RUN MODE - Safe testing (no real trades)")
        else:
            print("\n⚠️ LIVE TRADING MODE - REAL MONEY AT RISK!")
            print("⏰ Starting in 10 seconds... (Ctrl+C to cancel)")
            print("💡 Press Ctrl+C now if you want to enable dry-run mode\n")
            try:
                time.sleep(10)
            except KeyboardInterrupt:
                print("\n✋ Cancelled - Switch to dry-run mode?")
                response = input("Enable dry-run? (y/n): ")
                if response.lower() == 'y':
                    Config.DRY_RUN = True
                    print("✅ Switched to DRY RUN mode")
                else:
                    print("❌ Exiting...")
                    sys.exit(0)
        
        print(f"\n{'='*80}")
        print(f"🎯 Ready to trade! Running {len(self.strategies)} strategies")
        print(f"{'='*80}\n")
    
    def find_opportunities(self):
        """
        ابحث عن فرص تداول باستخدام التحليل المتقدم
        Find trading opportunities using advanced analysis
        """
        print(f"\n{'='*80}")
        print(f"🔍 MARKET SCAN [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
        print(f"{'='*80}")
        
        # Get high-quality markets
        markets = self.analyzer.get_active_markets(
            limit=50,
            min_volume=5000  # Only markets with decent volume
        )
        
        if not markets:
            print("❌ No markets found")
            return []
        
        print(f"📊 Analyzing {len(markets)} markets with advanced AI...")
        
        # Find all types of opportunities
        all_opportunities = []
        
        # 1. Find arbitrage opportunities (highest priority)
        print("\n🔍 Scanning for arbitrage opportunities...")
        arbitrage_opps = self.analyzer.find_best_opportunities(
            markets,
            min_confidence=0.6,
            strategy_filter='arbitrage'
        )
        all_opportunities.extend(arbitrage_opps)
        
        # 2. Find market making opportunities
        print("\n🔍 Scanning for market making opportunities...")
        for market in markets:
            analysis = self.analyzer.analyze_market_advanced(market)
            if self.market_maker.should_make_market(analysis):
                analysis['strategy_type'] = 'MARKET_MAKING'
                all_opportunities.append(analysis)
        
        # 3. Find momentum opportunities
        print("\n🔍 Scanning for momentum opportunities...")
        momentum_opps = self.analyzer.find_best_opportunities(
            markets,
            min_confidence=0.5,
            strategy_filter='momentum'
        )
        all_opportunities.extend(momentum_opps)
        
        # 4. Check whale signals
        print("\n🔍 Checking whale signals...")
        for market in markets[:20]:  # Check top 20 markets
            market_id = market.get('id')
            whale_signal = self.whale_tracker.get_whale_signal(market_id)
            
            if whale_signal['signal'] not in ['NEUTRAL'] and whale_signal['strength'] > 0.7:
                analysis = self.analyzer.analyze_market_advanced(market)
                analysis['confidence'] = max(analysis['confidence'], whale_signal['strength'] * 0.8)
                analysis['strategy_type'] = 'WHALE_FOLLOWING'
                analysis['whale_signal'] = whale_signal
                all_opportunities.append(analysis)
        
        # Remove duplicates (same market_id)
        seen_markets = set()
        unique_opportunities = []
        for opp in all_opportunities:
            if opp['market_id'] not in seen_markets:
                seen_markets.add(opp['market_id'])
                unique_opportunities.append(opp)
        
        # Sort by expected value (return * confidence)
        unique_opportunities.sort(
            key=lambda x: x.get('expected_return', 0) * x['confidence'],
            reverse=True
        )
        
        self.opportunities_found += len(unique_opportunities)
        
        # Display summary
        print(f"\n{'='*80}")
        print(f"💎 FOUND {len(unique_opportunities)} OPPORTUNITIES")
        print(f"{'='*80}")
        
        if unique_opportunities:
            print(f"\n🏆 Top 5 Opportunities:\n")
            for i, opp in enumerate(unique_opportunities[:5], 1):
                ev = opp.get('expected_return', 0) * opp['confidence'] * 100
                strategy_type = opp.get('strategy_type', opp.get('opportunity_type', 'UNKNOWN'))
                
                print(f"{i}. [{strategy_type}] {opp['question'][:50]}...")
                print(f"   💰 EV: {ev:.1f}% | 🎲 Confidence: {opp['confidence']*100:.0f}% | ⚠️ Risk: {opp['risk_level']}")
                
                if i < len(unique_opportunities):
                    print()
        
        return unique_opportunities
    
    def execute_trade(self, opportunity: Dict) -> bool:
        """
        نفذ صفقة مع فحوصات أمان متعددة
        Execute a trade with multiple safety checks
        """
        # === Risk Management Checks ===
        
        # 1. Check daily trade limit
        if self.daily_trades >= Config.MAX_DAILY_TRADES:
            print(f"⏭️ Daily trade limit reached ({Config.MAX_DAILY_TRADES})")
            return False
        
        # 2. Calculate position size using risk manager
        position_size = self.risk_manager.calculate_position_size(
            confidence=opportunity['confidence'],
            risk_level=opportunity['risk_level'],
            expected_return=opportunity.get('expected_return', 0.1)
        )
        
        # 3. Check if we can open position
        can_trade, reason = self.risk_manager.can_open_position(
            position_size,
            opportunity['risk_level']
        )
        
        if not can_trade:
            print(f"⏭️ Risk check failed: {reason}")
            return False
        
        # 4. Strategy-specific execution
        strategy_type = opportunity.get('strategy_type', opportunity.get('opportunity_type'))
        
        if strategy_type == 'MARKET_MAKING':
            return self._execute_market_making(opportunity, position_size)
        else:
            return self._execute_directional_trade(opportunity, position_size)
    
    def _execute_market_making(self, opportunity: Dict, position_size: float) -> bool:
        """
        نفذ استراتيجية market making
        Execute market making strategy
        """
        orders = self.market_maker.execute_market_making(opportunity, position_size)
        
        if not orders:
            return False
        
        # Log the trade
        trade_record = {
            'timestamp': datetime.now().isoformat(),
            'type': 'MARKET_MAKING',
            'market_id': opportunity['market_id'],
            'question': opportunity['question'],
            'orders': orders,
            'position_size': position_size,
            'dry_run': Config.DRY_RUN,
        }
        
        self.trades_history.append(trade_record)
        self.daily_trades += 1
        self.opportunities_taken += 1
        self.risk_manager.add_position(position_size)
        
        self._log_trade(trade_record)
        
        return True
    
    def _execute_directional_trade(self, opportunity: Dict, position_size: float) -> bool:
        """
        نفذ صفقة اتجاهية (شراء YES أو NO)
        Execute directional trade (buy YES or NO)
        """
        trade = {
            'timestamp': datetime.now().isoformat(),
            'market_id': opportunity['market_id'],
            'question': opportunity['question'],
            'action': opportunity['recommendation'],
            'position_size': position_size,
            'entry_price': opportunity['current_price_yes'],
            'confidence': opportunity['confidence'],
            'expected_return': opportunity.get('expected_return', 0),
            'risk_level': opportunity['risk_level'],
            'strategy_type': opportunity.get('strategy_type', 'UNKNOWN'),
            'reasons': opportunity.get('reasons', []),
            'dry_run': Config.DRY_RUN,
        }
        
        print(f"\n{'='*80}")
        print(f"💰 EXECUTING TRADE")
        print(f"{'='*80}")
        print(f"📝 Market: {trade['question'][:60]}...")
        print(f"🎯 Action: {trade['action']}")
        print(f"💵 Size: ${trade['position_size']:.2f}")
        print(f"💹 Entry: ${trade['entry_price']:.3f}")
        print(f"🎲 Confidence: {trade['confidence']*100:.0f}%")
        print(f"📊 Strategy: {trade['strategy_type']}")
        print(f"⚠️ Risk: {trade['risk_level']}")
        print(f"💰 Expected Return: {trade['expected_return']*100:.1f}%")
        
        if opportunity.get('reasons'):
            print(f"\n💡 Reasons:")
            for reason in opportunity['reasons'][:3]:
                print(f"   • {reason}")
        
        if Config.DRY_RUN:
            print(f"\n✅ [DRY RUN] Trade simulated")
        else:
            print(f"\n🔄 Executing LIVE trade...")
            # Real execution would go here
            # success = self._execute_real_trade(trade)
            print(f"⚠️ Real execution not yet implemented")
            print(f"💡 Set DRY_RUN=true to test safely")
        
        print(f"{'='*80}\n")
        
        # Update state
        self.active_positions.append(trade)
        self.daily_trades += 1
        self.opportunities_taken += 1
        self.risk_manager.add_position(position_size)
        
        # Log trade
        self.trades_history.append(trade)
        self._log_trade(trade)
        
        return True
    
    def _log_trade(self, trade: Dict):
        """سجل الصفقة"""
        try:
            log_file = Config.TRADES_DIR / f"trades_{datetime.now().strftime('%Y%m%d')}.json"
            
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    trades = json.load(f)
            else:
                trades = []
            
            trades.append(trade)
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(trades, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Failed to log trade: {e}")
    
    def display_stats(self):
        """اعرض إحصائيات مفصلة"""
        print(f"\n{'='*80}")
        print(f"📈 PERFORMANCE DASHBOARD")
        print(f"{'='*80}")
        
        # Session info
        session_duration = (datetime.now() - self.session_start).total_seconds() / 60
        print(f"\n⏱️ Session Duration: {session_duration:.1f} minutes")
        
        # Trading stats
        print(f"\n📊 Trading Statistics:")
        print(f"   Opportunities Found: {self.opportunities_found}")
        print(f"   Opportunities Taken: {self.opportunities_taken}")
        print(f"   Success Rate: {(self.opportunities_taken/max(1,self.opportunities_found))*100:.1f}%")
        print(f"   Trades Today: {self.daily_trades} / {Config.MAX_DAILY_TRADES}")
        print(f"   Active Positions: {len(self.active_positions)}")
        
        # P&L
        print(f"\n💰 Profit & Loss:")
        print(f"   Daily P&L: ${self.daily_profit:+.2f}")
        print(f"   Total P&L: ${self.total_profit:+.2f}")
        
        # Risk stats
        risk_stats = self.risk_manager.get_risk_stats()
        print(f"\n🛡️ Risk Management:")
        print(f"   Current Exposure: ${risk_stats['current_exposure']:.2f}")
        print(f"   Exposure Utilization: {risk_stats['exposure_utilization']:.1f}%")
        print(f"   Remaining Daily Budget: ${risk_stats['remaining_daily_budget']:.2f}")
        
        # Market Making stats
        mm_stats = self.market_maker.get_stats()
        if mm_stats['total_trades'] > 0:
            print(f"\n💰 Market Making:")
            print(f"   Total Trades: {mm_stats['total_trades']}")
            print(f"   Total Profit: ${mm_stats['total_profit']:.2f}")
            print(f"   Win Rate: {mm_stats['win_rate']:.1f}%")
            print(f"   Avg Profit/Trade: ${mm_stats['avg_profit_per_trade']:.2f}")
        
        print(f"{'='*80}\n")
    
    def run(self, interval: int = 60):
        """
        شغل البوت
        Run the trading bot
        """
        print(f"🤖 Bot started - Multi-strategy execution")
        print(f"📡 Scanning every {interval} seconds")
        print(f"🎯 Strategies: {', '.join(self.strategies)}")
        print(f"Press Ctrl+C to stop\n")
        
        try:
            scan_count = 0
            
            while True:
                scan_count += 1
                
                # Find opportunities
                opportunities = self.find_opportunities()
                
                # Execute best opportunities
                if opportunities:
                    # Take top N opportunities based on daily limit
                    remaining_trades = Config.MAX_DAILY_TRADES - self.daily_trades
                    opportunities_to_take = min(remaining_trades, 3, len(opportunities))
                    
                    for opportunity in opportunities[:opportunities_to_take]:
                        self.execute_trade(opportunity)
                        time.sleep(2)  # Small delay between trades
                
                # Display stats every 5 scans
                if scan_count % 5 == 0:
                    self.display_stats()
                
                # Wait for next scan
                print(f"⏰ Next scan in {interval} seconds...")
                print(f"{'='*80}\n")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print(f"\n\n🛑 Bot stopped by user")
            self.display_stats()
            
            # Save final report
            self._save_session_report()
            
            print("👋 Goodbye!\n")
    
    def _save_session_report(self):
        """حفظ تقرير الجلسة"""
        try:
            report = {
                'session_start': self.session_start.isoformat(),
                'session_end': datetime.now().isoformat(),
                'total_trades': len(self.trades_history),
                'opportunities_found': self.opportunities_found,
                'opportunities_taken': self.opportunities_taken,
                'daily_profit': self.daily_profit,
                'total_profit': self.total_profit,
                'trades': self.trades_history,
            }
            
            report_file = Config.TRADES_DIR / f"session_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Session report saved: {report_file.name}")
        except Exception as e:
            print(f"⚠️ Failed to save session report: {e}")


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description='🤖 Advanced Polymarket Trading Bot v2.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run with all strategies
  python trader_advanced.py --dry-run
  
  # Live trading with specific strategies
  python trader_advanced.py --strategies arbitrage market_making
  
  # Fast scanning (30 seconds interval)
  python trader_advanced.py --dry-run --interval 30
        """
    )
    
    parser.add_argument(
        '--strategies',
        nargs='+',
        choices=['copy_whales', 'arbitrage', 'momentum', 'manual', 'market_making'],
        default=['arbitrage', 'momentum'],
        help='Trading strategies to use (can specify multiple)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in simulation mode (no real trades) - RECOMMENDED FOR TESTING'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Scan interval in seconds (default: 60)'
    )
    
    args = parser.parse_args()
    
    # Create and run advanced trader
    trader = AdvancedPolymarketTrader(
        strategies=args.strategies,
        dry_run=args.dry_run
    )
    
    # Run the bot
    trader.run(interval=args.interval)


if __name__ == "__main__":
    main()
