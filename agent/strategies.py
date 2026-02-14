"""
🎯 Trading Strategies - استراتيجيات التداول
"""

from typing import Dict, List, Optional
from datetime import datetime
import random


class TradingStrategy:
    """Base trading strategy class"""
    
    def __init__(self, name: str):
        self.name = name
        self.trades_today = 0
        self.total_profit = 0.0
    
    def should_trade(self, market_analysis: Dict) -> bool:
        """Decide if we should trade this market"""
        raise NotImplementedError
    
    def get_position_size(self, market_analysis: Dict, max_size: float) -> float:
        """Calculate position size"""
        confidence = market_analysis.get('confidence', 0)
        return min(max_size * confidence, max_size)


class CopyWhalesStrategy(TradingStrategy):
    """
    🐋 استراتيجية نسخ الحيتان
    Copy trades from big wallets (whales)
    """
    
    def __init__(self, whale_addresses: List[str], min_whale_trade_size: float = 100):
        super().__init__("Copy Whales")
        self.whale_addresses = whale_addresses
        self.min_whale_trade_size = min_whale_trade_size
        print(f"🐋 Copy Whales Strategy initialized - tracking {len(whale_addresses)} whales")
    
    def should_trade(self, market_analysis: Dict) -> bool:
        """
        نتداول إذا:
        1. حوت كبير دخل الصفقة
        2. حجم الصفقة كبير بما يكفي
        """
        # Note: This would require whale tracking data
        # For now, using confidence as proxy
        
        confidence = market_analysis.get('confidence', 0)
        volume = market_analysis.get('volume', 0)
        
        # Trade if:
        # - High confidence (whale signal)
        # - Good volume
        if confidence >= 0.7 and volume >= 5000:
            print(f"🐋 Whale signal detected! Confidence: {confidence*100:.0f}%")
            return True
        
        return False
    
    def get_position_size(self, market_analysis: Dict, max_size: float) -> float:
        """
        حجم الصفقة بناءً على حجم صفقة الحوت
        Position size based on whale trade size
        """
        confidence = market_analysis.get('confidence', 0)
        
        # More aggressive sizing for whale signals
        if confidence >= 0.8:
            return max_size * 0.8  # 80% of max
        elif confidence >= 0.7:
            return max_size * 0.5  # 50% of max
        else:
            return max_size * 0.3  # 30% of max


class ArbitrageStrategy(TradingStrategy):
    """
    ⚖️ استراتيجية المراجحة (Arbitrage)
    Exploit price inefficiencies
    """
    
    def __init__(self, min_inefficiency: float = 0.05):
        super().__init__("Arbitrage")
        self.min_inefficiency = min_inefficiency
        print(f"⚖️ Arbitrage Strategy initialized - min inefficiency: {min_inefficiency*100:.0f}%")
    
    def should_trade(self, market_analysis: Dict) -> bool:
        """
        نتداول إذا فيه خلل في السعر
        Trade if there's a price inefficiency
        """
        # Check if "arbitrage opportunity" in reasons
        reasons = market_analysis.get('reasons', [])
        
        for reason in reasons:
            if 'arbitrage' in reason.lower() or 'inefficiency' in reason.lower():
                print(f"⚖️ Arbitrage opportunity found!")
                return True
        
        # Alternative: check confidence + volume
        confidence = market_analysis.get('confidence', 0)
        volume = market_analysis.get('volume', 0)
        liquidity = market_analysis.get('liquidity', 0)
        
        if confidence >= 0.6 and liquidity >= 3000:
            return True
        
        return False
    
    def get_position_size(self, market_analysis: Dict, max_size: float) -> float:
        """
        حجم أكبر للفرص الواضحة
        Larger size for clear arbitrage
        """
        confidence = market_analysis.get('confidence', 0)
        
        # Arbitrage opportunities = size up
        if confidence >= 0.8:
            return max_size  # 100% of max
        elif confidence >= 0.6:
            return max_size * 0.7  # 70% of max
        else:
            return max_size * 0.4  # 40% of max


class MomentumStrategy(TradingStrategy):
    """
    📈 استراتيجية الزخم (Momentum)
    Follow the trend
    """
    
    def __init__(self, min_volume: float = 5000):
        super().__init__("Momentum")
        self.min_volume = min_volume
        print(f"📈 Momentum Strategy initialized - min volume: ${min_volume:,.0f}")
    
    def should_trade(self, market_analysis: Dict) -> bool:
        """
        نتداول إذا:
        1. فيه حجم تداول كبير (momentum)
        2. السعر يتحرك في اتجاه واضح
        """
        volume = market_analysis.get('volume', 0)
        confidence = market_analysis.get('confidence', 0)
        current_price = market_analysis.get('current_price_yes', 0.5)
        
        # High volume + clear direction
        if volume >= self.min_volume:
            # Strong uptrend or downtrend
            if current_price < 0.4 or current_price > 0.6:
                if confidence >= 0.5:
                    print(f"📈 Momentum detected! Volume: ${volume:,.0f}")
                    return True
        
        return False
    
    def get_position_size(self, market_analysis: Dict, max_size: float) -> float:
        """
        حجم بناءً على قوة الزخم
        Size based on momentum strength
        """
        volume = market_analysis.get('volume', 0)
        confidence = market_analysis.get('confidence', 0)
        
        # Stronger momentum = bigger size
        if volume >= 20000 and confidence >= 0.6:
            return max_size * 0.8  # 80% of max
        elif volume >= 10000 and confidence >= 0.5:
            return max_size * 0.6  # 60% of max
        else:
            return max_size * 0.4  # 40% of max


class ManualStrategy(TradingStrategy):
    """
    🎮 استراتيجية يدوية (Manual)
    You decide what to trade
    """
    
    def __init__(self):
        super().__init__("Manual")
        print(f"🎮 Manual Strategy initialized - you're in control!")
    
    def should_trade(self, market_analysis: Dict) -> bool:
        """
        Always ask the user
        """
        # In manual mode, display opportunities but don't auto-trade
        return False
    
    def get_position_size(self, market_analysis: Dict, max_size: float) -> float:
        """
        User decides
        """
        return max_size * 0.5  # Default 50%


class StrategyFactory:
    """
    مصنع الاستراتيجيات
    Factory to create strategies
    """
    
    @staticmethod
    def create_strategy(strategy_name: str, **kwargs) -> TradingStrategy:
        """
        أنشئ استراتيجية بناءً على الاسم
        Create a strategy by name
        """
        strategies = {
            'copy_whales': CopyWhalesStrategy,
            'arbitrage': ArbitrageStrategy,
            'momentum': MomentumStrategy,
            'manual': ManualStrategy,
        }
        
        strategy_name_lower = strategy_name.lower()
        
        if strategy_name_lower not in strategies:
            print(f"⚠️ Unknown strategy: {strategy_name}")
            print(f"Available strategies: {', '.join(strategies.keys())}")
            return ManualStrategy()
        
        strategy_class = strategies[strategy_name_lower]
        
        # Create strategy with appropriate kwargs
        if strategy_name_lower == 'copy_whales':
            whale_addresses = kwargs.get('whale_addresses', [])
            min_whale_trade_size = kwargs.get('min_whale_trade_size', 100)
            return strategy_class(whale_addresses, min_whale_trade_size)
        
        elif strategy_name_lower == 'arbitrage':
            min_inefficiency = kwargs.get('min_inefficiency', 0.05)
            return strategy_class(min_inefficiency)
        
        elif strategy_name_lower == 'momentum':
            min_volume = kwargs.get('min_volume', 5000)
            return strategy_class(min_volume)
        
        else:
            return strategy_class()


# Example usage
if __name__ == "__main__":
    print("🎯 Testing Trading Strategies\n")
    
    # Sample market analysis
    sample_analysis = {
        'market_id': '123',
        'question': 'Will Bitcoin reach $100k in 2026?',
        'confidence': 0.75,
        'recommendation': 'BUY_YES',
        'current_price_yes': 0.35,
        'volume': 15000,
        'liquidity': 8000,
        'reasons': ['Price inefficiency detected', 'High volume']
    }
    
    # Test each strategy
    strategies = [
        StrategyFactory.create_strategy('copy_whales', whale_addresses=['0x123', '0x456']),
        StrategyFactory.create_strategy('arbitrage'),
        StrategyFactory.create_strategy('momentum'),
        StrategyFactory.create_strategy('manual'),
    ]
    
    for strategy in strategies:
        print(f"\n{'='*60}")
        print(f"Testing: {strategy.name}")
        print(f"{'='*60}")
        
        should_trade = strategy.should_trade(sample_analysis)
        position_size = strategy.get_position_size(sample_analysis, max_size=100)
        
        print(f"Should trade: {should_trade}")
        print(f"Position size: ${position_size:.2f}")
