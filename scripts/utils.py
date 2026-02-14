"""
🔧 Utility Scripts - أدوات مساعدة
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.analyzer import MarketAnalyzer
from config.settings import Config


def check_setup():
    """
    ✅ تحقق من إعداد المشروع
    Check if project is setup correctly
    """
    print("\n" + "="*70)
    print("🔍 CHECKING PROJECT SETUP")
    print("="*70 + "\n")
    
    # Check .env file
    env_file = Path('.env')
    if env_file.exists():
        print("✅ .env file exists")
    else:
        print("❌ .env file not found")
        print("💡 Run: copy .env.example .env")
        return False
    
    # Check configuration
    errors = Config.validate()
    if errors:
        print("\n⚠️ Configuration issues:")
        for error in errors:
            print(f"   {error}")
    else:
        print("✅ Configuration valid")
    
    # Check directories
    Config.setup_directories()
    print("✅ Directories created")
    
    # Check API connection
    print("\n🌐 Testing Polymarket API connection...")
    analyzer = MarketAnalyzer()
    markets = analyzer.get_active_markets(limit=1)
    
    if markets:
        print(f"✅ API connection successful - found {len(markets)} market(s)")
    else:
        print("❌ API connection failed")
        return False
    
    print("\n" + "="*70)
    print("✅ Setup check complete!")
    print("="*70 + "\n")
    
    return True


def view_markets():
    """
    📊 عرض الأسواق النشطة
    View active markets
    """
    print("\n" + "="*70)
    print("📊 ACTIVE MARKETS ON POLYMARKET")
    print("="*70 + "\n")
    
    analyzer = MarketAnalyzer()
    markets = analyzer.get_active_markets(limit=10)
    
    if not markets:
        print("❌ No markets found")
        return
    
    for i, market in enumerate(markets, 1):
        question = market.get('question', 'Unknown')
        volume = float(market.get('volume', 0))
        liquidity = float(market.get('liquidity', 0))
        
        outcomes = market.get('outcomes', [])
        yes_price = 0
        if outcomes:
            yes_price = float(outcomes[0].get('price', 0))
        
        print(f"{i}. {question[:60]}...")
        print(f"   YES: ${yes_price:.3f} | Volume: ${volume:,.0f} | Liquidity: ${liquidity:,.0f}")
        print()
    
    print("="*70 + "\n")


def analyze_market_by_id(market_id: str):
    """
    🔍 حلل سوق معين
    Analyze a specific market
    """
    analyzer = MarketAnalyzer()
    
    print(f"\n🔍 Fetching market {market_id}...")
    market = analyzer.get_market_details(market_id)
    
    if not market:
        print(f"❌ Market {market_id} not found")
        return
    
    analyzer.display_market_summary(market)


def find_opportunities():
    """
    💎 ابحث عن فرص تداول
    Find trading opportunities
    """
    print("\n" + "="*70)
    print("💎 SEARCHING FOR OPPORTUNITIES")
    print("="*70 + "\n")
    
    analyzer = MarketAnalyzer()
    markets = analyzer.get_active_markets(limit=20)
    
    if not markets:
        print("❌ No markets found")
        return
    
    opportunities = analyzer.find_opportunities(markets, min_confidence=0.5)
    
    if not opportunities:
        print("😕 No good opportunities found")
        return
    
    print(f"\n✨ Found {len(opportunities)} opportunities:\n")
    
    for i, opp in enumerate(opportunities[:5], 1):  # Top 5
        print(f"{i}. {opp['question'][:60]}...")
        print(f"   Confidence: {opp['confidence']*100:.0f}%")
        print(f"   Recommendation: {opp['recommendation']}")
        print(f"   Reasons:")
        for reason in opp['reasons'][:3]:
            print(f"      • {reason}")
        print()
    
    print("="*70 + "\n")


def test_strategy(strategy_name: str):
    """
    🧪 اختبر استراتيجية
    Test a trading strategy
    """
    from agent.strategies import StrategyFactory
    
    print("\n" + "="*70)
    print(f"🧪 TESTING STRATEGY: {strategy_name.upper()}")
    print("="*70 + "\n")
    
    # Create strategy
    strategy = StrategyFactory.create_strategy(strategy_name)
    
    # Get markets
    analyzer = MarketAnalyzer()
    markets = analyzer.get_active_markets(limit=10)
    
    if not markets:
        print("❌ No markets found")
        return
    
    # Test strategy on each market
    trades_count = 0
    
    for market in markets:
        analysis = analyzer.analyze_market(market)
        
        if strategy.should_trade(analysis):
            position_size = strategy.get_position_size(analysis, max_size=100)
            
            print(f"✅ Would trade: {analysis['question'][:50]}...")
            print(f"   Action: {analysis['recommendation']}")
            print(f"   Size: ${position_size:.2f}")
            print(f"   Confidence: {analysis['confidence']*100:.0f}%")
            print()
            
            trades_count += 1
    
    print(f"\n📊 Strategy would execute {trades_count} trades")
    print("="*70 + "\n")


def show_wallet_balance():
    """
    💰 عرض رصيد المحفظة
    Show wallet balance
    """
    try:
        from web3 import Web3
        
        print("\n" + "="*70)
        print("💰 WALLET BALANCE")
        print("="*70 + "\n")
        
        # Connect to RPC
        w3 = Web3(Web3.HTTPProvider(Config.RPC_URL))
        
        if not w3.is_connected():
            print("❌ Failed to connect to RPC")
            return
        
        # Get wallet address from private key
        from eth_account import Account
        account = Account.from_key(Config.PRIVATE_KEY)
        address = account.address
        
        # Get MATIC balance
        balance_wei = w3.eth.get_balance(address)
        balance_matic = w3.from_wei(balance_wei, 'ether')
        
        print(f"📍 Address: {address}")
        print(f"💎 MATIC Balance: {balance_matic:.6f} MATIC")
        
        # Note: To get USDC balance, need to call USDC contract
        print(f"\n💡 To trade on Polymarket, you need USDC on Polygon")
        print(f"   Get USDC: https://app.uniswap.org/")
        
        print("\n" + "="*70 + "\n")
        
    except Exception as e:
        print(f"❌ Error checking balance: {e}")
        print("💡 Make sure PRIVATE_KEY is set in .env")


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='🔧 Trading Bot Utilities')
    
    parser.add_argument('action', choices=[
        'check',
        'markets',
        'opportunities',
        'test-strategy',
        'balance',
    ], help='Action to perform')
    
    parser.add_argument('--strategy', type=str, help='Strategy name for test-strategy')
    parser.add_argument('--market-id', type=str, help='Market ID to analyze')
    
    args = parser.parse_args()
    
    if args.action == 'check':
        check_setup()
    
    elif args.action == 'markets':
        view_markets()
    
    elif args.action == 'opportunities':
        find_opportunities()
    
    elif args.action == 'test-strategy':
        if not args.strategy:
            print("❌ Please specify --strategy (copy_whales, arbitrage, momentum, manual)")
        else:
            test_strategy(args.strategy)
    
    elif args.action == 'balance':
        show_wallet_balance()
