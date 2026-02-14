"""
📊 Market Monitor - مراقب الأسواق
Real-time market monitoring dashboard
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.analyzer import MarketAnalyzer
from config.settings import Config


class MarketMonitor:
    """
    مراقب الأسواق في الوقت الفعلي
    Real-time market monitor
    """
    
    def __init__(self):
        self.analyzer = MarketAnalyzer()
        self.tracked_markets = {}
        
    def clear_screen(self):
        """Clear terminal screen"""
        print("\033[2J\033[H", end="")
    
    def display_dashboard(self):
        """
        عرض لوحة المراقبة
        Display monitoring dashboard
        """
        self.clear_screen()
        
        print("="*80)
        print("📊 POLYMARKET LIVE MONITOR           " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print("="*80)
        
        # Get markets
        markets = self.analyzer.get_active_markets(limit=10)
        
        if not markets:
            print("\n❌ No markets found\n")
            return
        
        # Display header
        print(f"\n{'#':<3} {'Question':<45} {'YES':<7} {'Volume':<12} {'Liquidity':<12}")
        print("-" * 80)
        
        # Display markets
        for i, market in enumerate(markets, 1):
            question = market.get('question', 'Unknown')[:44]
            volume = float(market.get('volume', 0))
            liquidity = float(market.get('liquidity', 0))
            
            outcomes = market.get('outcomes', [])
            yes_price = 0
            if outcomes:
                yes_price = float(outcomes[0].get('price', 0))
            
            # Color coding for price
            if yes_price < 0.3:
                price_str = f"🟢 ${yes_price:.3f}"
            elif yes_price > 0.7:
                price_str = f"🔴 ${yes_price:.3f}"
            else:
                price_str = f"🟡 ${yes_price:.3f}"
            
            print(f"{i:<3} {question:<45} {price_str:<7} ${volume:>9,.0f}  ${liquidity:>9,.0f}")
        
        # Find opportunities
        opportunities = self.analyzer.find_opportunities(markets, min_confidence=0.6)
        
        if opportunities:
            print("\n" + "="*80)
            print("💎 TRADING OPPORTUNITIES")
            print("="*80)
            
            for opp in opportunities[:3]:  # Top 3
                question = opp['question'][:60]
                conf = opp['confidence'] * 100
                rec = opp['recommendation']
                
                print(f"\n✨ {question}...")
                print(f"   Confidence: {conf:.0f}% | Action: {rec}")
                
                for reason in opp['reasons'][:2]:
                    print(f"   • {reason}")
        
        print("\n" + "="*80)
        print("Press Ctrl+C to stop")
        print("="*80 + "\n")
    
    def run(self, interval: int = 30):
        """
        شغل المراقب
        Run the monitor
        
        Args:
            interval: Update interval in seconds
        """
        print("🚀 Starting Market Monitor...")
        print(f"📡 Updating every {interval} seconds\n")
        
        try:
            while True:
                self.display_dashboard()
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Monitor stopped by user")
            print("👋 Goodbye!\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='📊 Polymarket Market Monitor')
    
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Update interval in seconds (default: 30)'
    )
    
    args = parser.parse_args()
    
    # Create and run monitor
    monitor = MarketMonitor()
    monitor.run(interval=args.interval)


if __name__ == "__main__":
    main()
