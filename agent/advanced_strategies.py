"""
💰 Market Making Strategy - استراتيجية صناعة السوق
الأرباح المستمرة من الـ spread
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import statistics


class MarketMakingStrategy:
    """
    🎯 Market Making Strategy
    
    الفكرة:
    - تضع أوردرات شراء وبيع في نفس الوقت
    - تربح من الفرق (spread)
    - أرباح صغيرة لكن متكررة ومستمرة
    
    مثال:
    - أوردر شراء YES @ $0.48
    - أوردر بيع YES @ $0.52
    - الربح = $0.04 لكل share (8%)
    """
    
    def __init__(self, min_spread: float = 0.03, target_spread: float = 0.05):
        self.name = "Market Making"
        self.min_spread = min_spread  # 3% minimum spread
        self.target_spread = target_spread  # 5% target spread
        self.open_orders = []
        self.completed_trades = []
        self.total_profit = 0.0
        
        print(f"💰 Market Making Strategy initialized")
        print(f"   Min spread: {min_spread*100:.1f}%")
        print(f"   Target spread: {target_spread*100:.1f}%")
    
    def should_make_market(self, analysis: Dict) -> bool:
        """
        قرر إذا نسوي market making في هذا السوق
        Decide if we should make market in this market
        """
        # Criteria for market making
        volume = analysis.get('volume', 0)
        liquidity = analysis.get('liquidity', 0)
        volatility = analysis.get('volatility', 0.5)
        yes_price = analysis.get('current_price_yes', 0.5)
        
        # Good market making conditions:
        conditions = {
            'high_volume': volume >= 10000,  # High trading volume
            'good_liquidity': liquidity >= 5000,  # Good liquidity
            'moderate_volatility': 0.2 < volatility < 0.6,  # Not too crazy
            'reasonable_price': 0.2 < yes_price < 0.8,  # Not extreme
        }
        
        # Need at least 3 out of 4 conditions
        score = sum(conditions.values())
        
        if score >= 3:
            print(f"✅ Good market making opportunity")
            return True
        
        return False
    
    def calculate_orders(self, analysis: Dict, position_size: float) -> Dict:
        """
        حساب أوردرات الشراء والبيع
        Calculate buy and sell orders
        """
        yes_price = analysis.get('current_price_yes', 0.5)
        no_price = analysis.get('current_price_no', 0.5)
        spread = self.target_spread
        
        # Calculate bid/ask prices for YES
        yes_bid = max(0.01, yes_price - spread/2)  # Buy price
        yes_ask = min(0.99, yes_price + spread/2)  # Sell price
        
        # Calculate bid/ask prices for NO
        no_bid = max(0.01, no_price - spread/2)
        no_ask = min(0.99, no_price + spread/2)
        
        # Determine strategy
        if yes_ask - yes_bid >= self.min_spread:
            strategy = "YES"
            buy_price = yes_bid
            sell_price = yes_ask
        elif no_ask - no_bid >= self.min_spread:
            strategy = "NO"
            buy_price = no_bid
            sell_price = no_ask
        else:
            return None  # Spread too small
        
        # Calculate profit per share
        profit_per_share = sell_price - buy_price
        profit_percentage = (profit_per_share / buy_price) * 100
        
        orders = {
            'market_id': analysis['market_id'],
            'question': analysis['question'],
            'strategy': f"Market Making - {strategy}",
            'buy_order': {
                'side': strategy,
                'type': 'BUY',
                'price': buy_price,
                'size': position_size,
                'total_cost': buy_price * position_size,
            },
            'sell_order': {
                'side': strategy,
                'type': 'SELL',
                'price': sell_price,
                'size': position_size,
                'total_return': sell_price * position_size,
            },
            'expected_profit': profit_per_share * position_size,
            'profit_percentage': profit_percentage,
            'spread': sell_price - buy_price,
            'timestamp': datetime.now().isoformat(),
        }
        
        return orders
    
    def execute_market_making(self, analysis: Dict, position_size: float) -> Optional[Dict]:
        """
        نفذ استراتيجية market making
        Execute market making strategy
        """
        if not self.should_make_market(analysis):
            return None
        
        orders = self.calculate_orders(analysis, position_size)
        
        if not orders:
            print(f"⏭️ Spread too small for market making")
            return None
        
        print(f"\n💰 Market Making Opportunity:")
        print(f"📝 {orders['question'][:60]}...")
        print(f"🎯 Strategy: {orders['strategy']}")
        print(f"📊 Buy @ ${orders['buy_order']['price']:.3f}")
        print(f"📊 Sell @ ${orders['sell_order']['price']:.3f}")
        print(f"💵 Spread: ${orders['spread']:.3f} ({orders['profit_percentage']:.1f}%)")
        print(f"💰 Expected Profit: ${orders['expected_profit']:.2f}")
        
        self.open_orders.append(orders)
        
        return orders
    
    def check_orders_status(self):
        """
        تحقق من حالة الأوردرات المفتوحة
        Check status of open orders
        """
        # This would integrate with actual Polymarket API
        # to check if orders are filled
        pass
    
    def get_stats(self) -> Dict:
        """
        احصل على إحصائيات الأداء
        Get performance statistics
        """
        if not self.completed_trades:
            return {
                'total_trades': 0,
                'total_profit': 0.0,
                'avg_profit_per_trade': 0.0,
                'win_rate': 0.0,
            }
        
        wins = sum(1 for t in self.completed_trades if t['profit'] > 0)
        
        return {
            'total_trades': len(self.completed_trades),
            'total_profit': self.total_profit,
            'avg_profit_per_trade': self.total_profit / len(self.completed_trades),
            'win_rate': (wins / len(self.completed_trades)) * 100,
            'open_orders': len(self.open_orders),
        }


class AdvancedWhaleTracker:
    """
    🐋 Advanced Whale Tracking System
    تتبع ذكي للحيتان مع تحليل أنماطهم
    """
    
    def __init__(self, whale_wallets: List[str] = None):
        self.whale_wallets = whale_wallets or []
        self.whale_history = {}
        self.whale_scores = {}
        
        print(f"🐋 Whale Tracker initialized - tracking {len(self.whale_wallets)} whales")
    
    def add_whale(self, wallet: str):
        """أضف حوت للمتابعة"""
        if wallet not in self.whale_wallets:
            self.whale_wallets.append(wallet)
            self.whale_history[wallet] = []
            self.whale_scores[wallet] = {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'total_volume': 0.0,
            }
    
    def track_whale_trade(self, wallet: str, market_id: str, side: str, 
                         amount: float, price: float):
        """
        سجل صفقة حوت
        Track a whale trade
        """
        if wallet not in self.whale_history:
            self.add_whale(wallet)
        
        trade = {
            'market_id': market_id,
            'side': side,
            'amount': amount,
            'price': price,
            'timestamp': datetime.now().isoformat(),
        }
        
        self.whale_history[wallet].append(trade)
        self.whale_scores[wallet]['total_trades'] += 1
        self.whale_scores[wallet]['total_volume'] += amount
    
    def get_whale_signal(self, market_id: str) -> Dict:
        """
        احصل على إشارة من نشاط الحيتان
        Get signal from whale activity
        """
        # Count recent whale trades in this market
        recent_trades = []
        
        for wallet, trades in self.whale_history.items():
            for trade in trades[-10:]:  # Last 10 trades
                if trade['market_id'] == market_id:
                    recent_trades.append(trade)
        
        if not recent_trades:
            return {'signal': 'NEUTRAL', 'strength': 0.0, 'whale_count': 0}
        
        # Analyze whale sentiment
        yes_amount = sum(t['amount'] for t in recent_trades if t['side'] == 'YES')
        no_amount = sum(t['amount'] for t in recent_trades if t['side'] == 'NO')
        total = yes_amount + no_amount
        
        if total == 0:
            return {'signal': 'NEUTRAL', 'strength': 0.0, 'whale_count': len(recent_trades)}
        
        yes_ratio = yes_amount / total
        
        if yes_ratio > 0.7:
            signal = 'STRONG_BUY_YES'
            strength = yes_ratio
        elif yes_ratio > 0.6:
            signal = 'BUY_YES'
            strength = yes_ratio
        elif yes_ratio < 0.3:
            signal = 'STRONG_BUY_NO'
            strength = 1 - yes_ratio
        elif yes_ratio < 0.4:
            signal = 'BUY_NO'
            strength = 1 - yes_ratio
        else:
            signal = 'NEUTRAL'
            strength = 0.5
        
        return {
            'signal': signal,
            'strength': strength,
            'whale_count': len(set(t.get('wallet') for t in recent_trades)),
            'total_volume': total,
            'yes_ratio': yes_ratio,
        }
    
    def get_best_whales(self, top_n: int = 10) -> List[Tuple[str, Dict]]:
        """
        احصل على أفضل الحيتان حسب الأداء
        Get best performing whales
        """
        # Sort by win rate
        sorted_whales = sorted(
            self.whale_scores.items(),
            key=lambda x: x[1]['win_rate'],
            reverse=True
        )
        
        return sorted_whales[:top_n]
    
    def should_copy_whale_trade(self, wallet: str, market_id: str) -> Tuple[bool, float]:
        """
        قرر إذا نقلد صفقة حوت معين
        Decide if we should copy a whale's trade
        
        Returns: (should_copy, confidence)
        """
        if wallet not in self.whale_scores:
            return False, 0.0
        
        score = self.whale_scores[wallet]
        
        # Criteria for copying
        if score['total_trades'] < 5:
            return False, 0.0  # Not enough history
        
        if score['win_rate'] < 0.55:
            return False, 0.0  # Poor performance
        
        # Calculate confidence based on whale's track record
        confidence = min(1.0, (score['win_rate'] - 0.5) * 2)
        
        # Bonus for high volume whales
        if score['total_volume'] > 100000:
            confidence *= 1.1
        
        if score['win_rate'] >= 0.65:
            return True, min(1.0, confidence)
        
        return False, 0.0


class EnhancedRiskManager:
    """
    🛡️ Enhanced Risk Management System
    نظام إدارة مخاطر محترف متعدد الطبقات
    """
    
    def __init__(self, max_position: float, max_daily_loss: float, max_total_exposure: float):
        self.max_position = max_position
        self.max_daily_loss = max_daily_loss
        self.max_total_exposure = max_total_exposure
        
        self.daily_pnl = 0.0
        self.current_exposure = 0.0
        self.positions = []
        
        print(f"🛡️ Risk Manager initialized:")
        print(f"   Max position: ${max_position}")
        print(f"   Max daily loss: ${max_daily_loss}")
        print(f"   Max total exposure: ${max_total_exposure}")
    
    def can_open_position(self, size: float, risk_level: str = 'MEDIUM') -> Tuple[bool, str]:
        """
        تحقق إذا نقدر نفتح مركز جديد
        Check if we can open a new position
        """
        # Check daily loss limit
        if abs(self.daily_pnl) >= self.max_daily_loss:
            return False, f"Daily loss limit reached: ${self.daily_pnl:.2f}"
        
        # Check position size limit
        if size > self.max_position:
            return False, f"Position size ${size:.2f} exceeds max ${self.max_position:.2f}"
        
        # Check total exposure limit
        if self.current_exposure + size > self.max_total_exposure:
            return False, f"Total exposure would exceed limit"
        
        # Additional checks for HIGH risk positions
        if risk_level == 'HIGH':
            if size > self.max_position * 0.5:
                return False, "High risk position too large"
            if len(self.positions) >= 3:
                return False, "Too many open positions for high risk trade"
        
        return True, "OK"
    
    def calculate_position_size(self, confidence: float, risk_level: str, 
                               expected_return: float) -> float:
        """
        حساب حجم المركز الأمثل باستخدام Kelly Criterion
        Calculate optimal position size using Kelly Criterion
        """
        # Kelly Criterion: f* = (bp - q) / b
        # where b = odds, p = win probability, q = loss probability
        
        win_prob = confidence
        loss_prob = 1 - confidence
        
        # Adjust for risk level
        risk_multiplier = {
            'LOW': 1.0,
            'MEDIUM': 0.7,
            'HIGH': 0.5,
        }.get(risk_level, 0.7)
        
        # Calculate Kelly fraction
        if expected_return <= 0:
            return 0.0
        
        kelly_fraction = (win_prob - loss_prob) / expected_return
        
        # Use fraction of Kelly (safer)
        fractional_kelly = kelly_fraction * 0.25 * risk_multiplier
        
        # Calculate size
        position_size = min(
            self.max_position * fractional_kelly,
            self.max_position
        )
        
        return max(10.0, position_size)  # Minimum $10
    
    def update_pnl(self, pnl: float):
        """تحديث الربح/الخسارة"""
        self.daily_pnl += pnl
    
    def add_position(self, size: float):
        """أضف مركز"""
        self.current_exposure += size
        self.positions.append({'size': size, 'timestamp': datetime.now()})
    
    def close_position(self, size: float, pnl: float):
        """أغلق مركز"""
        self.current_exposure = max(0, self.current_exposure - size)
        self.update_pnl(pnl)
        
        # Remove from positions
        for i, pos in enumerate(self.positions):
            if pos['size'] == size:
                del self.positions[i]
                break
    
    def get_risk_stats(self) -> Dict:
        """احصل على إحصائيات المخاطر"""
        return {
            'daily_pnl': self.daily_pnl,
            'current_exposure': self.current_exposure,
            'open_positions': len(self.positions),
            'remaining_daily_budget': self.max_daily_loss - abs(self.daily_pnl),
            'exposure_utilization': (self.current_exposure / self.max_total_exposure) * 100,
        }


# Example usage
if __name__ == "__main__":
    print("🧪 Testing Advanced Trading Components\n")
    
    # Test Market Making
    mm = MarketMakingStrategy()
    
    sample_analysis = {
        'market_id': '123',
        'question': 'Will Bitcoin reach $100k in 2026?',
        'confidence': 0.75,
        'current_price_yes': 0.48,
        'current_price_no': 0.52,
        'volume': 25000,
        'liquidity': 15000,
        'volatility': 0.4,
    }
    
    orders = mm.execute_market_making(sample_analysis, position_size=100)
    
    # Test Whale Tracker
    print(f"\n{'='*70}")
    tracker = AdvancedWhaleTracker()
    tracker.add_whale("0x123...")
    tracker.track_whale_trade("0x123...", "123", "YES", 5000, 0.45)
    
    signal = tracker.get_whale_signal("123")
    print(f"\n🐋 Whale Signal: {signal}")
    
    # Test Risk Manager
    print(f"\n{'='*70}")
    risk_mgr = EnhancedRiskManager(
        max_position=100,
        max_daily_loss=500,
        max_total_exposure=1000
    )
    
    size = risk_mgr.calculate_position_size(0.75, 'MEDIUM', 0.15)
    print(f"\n💰 Calculated position size: ${size:.2f}")
    
    can_trade, reason = risk_mgr.can_open_position(size, 'MEDIUM')
    print(f"Can trade: {can_trade} - {reason}")
