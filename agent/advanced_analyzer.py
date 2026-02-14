"""
🧠 Advanced AI Analyzer - محلل ذكاء اصطناعي متقدم
Enhanced market analysis with ML capabilities
"""

import requests
import time
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import statistics


class AdvancedMarketAnalyzer:
    """محلل أسواق متقدم مع AI"""
    
    def __init__(self, api_url: str = "https://gamma-api.polymarket.com"):
        from config.settings import Config
        self.api_url = api_url
        self.clob_url = "https://clob.polymarket.com"
        self.cache = {}
        self.cache_duration = 30  # seconds
        self.last_fetch_error = None
        self.last_fetch_mode = "live"
        self.session = self._build_session(Config)
        
        # Historical data storage
        self.price_history = defaultdict(list)
        self.volume_history = defaultdict(list)
        self.whale_trades = []
        
        # Performance tracking
        self.market_scores = {}
        self.prediction_accuracy = {}
        
        print("🧠 Advanced AI Analyzer initialized")
    
    def get_active_markets(self, limit: int = 50, min_volume: float = 1000) -> List[Dict]:
        """
        احصل على الأسواق النشطة مع فلترة ذكية (Gamma API)
        Get active markets with smart filtering
        """
        try:
            # Use Gamma API which has volume, liquidity, outcomePrices
            url = f"{self.api_url}/markets"
            params = {
                'limit': min(limit * 3, 300),  # fetch more to filter
                'active': 'true',
                'closed': 'false',
                'order': 'volume',
                'ascending': 'false',
            }
            
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                self.last_fetch_error = None
                self.last_fetch_mode = "live"
                raw = response.json()
                
                # Gamma API returns a list directly
                if isinstance(raw, list):
                    markets = raw
                elif isinstance(raw, dict):
                    markets = raw.get('data', raw.get('markets', []))
                else:
                    markets = []
                
                # Normalize & filter
                filtered = []
                for market in markets:
                    if not isinstance(market, dict):
                        continue
                    
                    volume = float(market.get('volume', 0) or 0)
                    liquidity = float(market.get('liquidity', 0) or 0)
                    
                    # Parse outcomePrices -> outcomes
                    if 'outcomePrices' in market:
                        op = market.get('outcomePrices', '[]')
                        try:
                            prices = json.loads(op) if isinstance(op, str) else op
                            market['outcomes'] = [{'price': float(p)} for p in prices]
                        except:
                            market['outcomes'] = [{'price': 0.5}, {'price': 0.5}]
                    elif 'outcomes' not in market:
                        market['outcomes'] = [{'price': 0.5}, {'price': 0.5}]
                    
                    # Filter: active, has volume
                    if volume >= min_volume and liquidity >= 100:
                        filtered.append(market)
                
                print(f"✅ Found {len(filtered)} high-quality markets (from {len(markets)} total)")
                return filtered[:limit]
            else:
                self.last_fetch_error = f"HTTP {response.status_code}"
                self.last_fetch_mode = "demo"
                print(f"❌ Failed to fetch markets: {response.status_code}. Using demo data.")
                return self._get_demo_markets(limit=limit, min_volume=min_volume)
                
        except Exception as e:
            self.last_fetch_error = str(e)
            self.last_fetch_mode = "demo"
            print(f"❌ Error fetching markets: {e}. Using demo data.")
            return self._get_demo_markets(limit=limit, min_volume=min_volume)

    def _get_demo_markets(self, limit: int = 50, min_volume: float = 1000) -> List[Dict]:
        """Provide demo markets when network is blocked/unavailable."""
        demo_markets = [
            {
                "id": "demo-weather-nyc",
                "question": "Will it rain in New York on Feb 15, 2026?",
                "volume": 12500,
                "liquidity": 6200,
                "outcomes": [{"price": 0.58}, {"price": 0.44}]
            },
            {
                "id": "demo-btc-100k",
                "question": "Will BTC be above $100K by Dec 31, 2026?",
                "volume": 54000,
                "liquidity": 18000,
                "outcomes": [{"price": 0.42}, {"price": 0.60}]
            },
            {
                "id": "demo-elections",
                "question": "Will the incumbent win the 2026 election?",
                "volume": 32000,
                "liquidity": 9500,
                "outcomes": [{"price": 0.51}, {"price": 0.52}]
            },
            {
                "id": "demo-sports",
                "question": "Will Team A win the championship?",
                "volume": 8900,
                "liquidity": 4200,
                "outcomes": [{"price": 0.63}, {"price": 0.39}]
            },
            {
                "id": "demo-crypto",
                "question": "Will ETH be above $6K by Dec 31, 2026?",
                "volume": 21000,
                "liquidity": 8300,
                "outcomes": [{"price": 0.36}, {"price": 0.66}]
            },
            {
                "id": "demo-weather-miami",
                "question": "Will it be above 85F in Miami on Feb 15, 2026?",
                "volume": 7400,
                "liquidity": 5100,
                "outcomes": [{"price": 0.72}, {"price": 0.30}]
            }
        ]

        filtered = [m for m in demo_markets if float(m.get("volume", 0)) >= min_volume]
        return filtered[:limit]

    def get_top_events(self, limit: int = 10) -> List[Dict]:
        """Get top events by volume from Gamma API."""
        try:
            r = self.session.get(f"{self.api_url}/events",
                                 params={'limit': str(limit), 'active': 'true', 'closed': 'false',
                                         'order': 'volume', 'ascending': 'false'},
                                 timeout=15)
            if r.status_code == 200:
                events = r.json() if isinstance(r.json(), list) else r.json().get('data', [])
                return events
        except Exception as e:
            print(f"❌ Events fetch error: {e}")
        return []

    def _build_session(self, config) -> requests.Session:
        """Create a requests session with optional proxy support."""
        session = requests.Session()

        if getattr(config, "PROXY_ENABLED", False) and getattr(config, "PROXY_URL", ""):
            session.proxies.update({
                "http": config.PROXY_URL,
                "https": config.PROXY_URL,
            })

        session.headers.update({
            "User-Agent": "PolymarketBot/1.0"
        })

        return session
    
    def analyze_market_advanced(self, market: Dict) -> Dict:
        """
        تحليل متقدم مع scoring ذكي
        Advanced analysis with intelligent scoring
        """
        analysis = {
            'market_id': market.get('id', ''),
            'question': market.get('question', 'Unknown'),
            'confidence': 0.0,
            'recommendation': 'HOLD',
            'reasons': [],
            'scores': {},
            'current_price_yes': 0.0,
            'current_price_no': 0.0,
            'volume': 0.0,
            'liquidity': 0.0,
            'momentum': 0.0,
            'volatility': 0.0,
            'opportunity_type': None,
            'risk_level': 'MEDIUM',
            'expected_return': 0.0,
        }
        
        try:
            # Get current prices
            outcomes = market.get('outcomes', [])
            if len(outcomes) >= 2:
                yes_outcome = outcomes[0]
                no_outcome = outcomes[1]
                
                yes_price = float(yes_outcome.get('price', 0))
                no_price = float(no_outcome.get('price', 0))
                
                analysis['current_price_yes'] = yes_price
                analysis['current_price_no'] = no_price
                
                # Get volume & liquidity
                volume = float(market.get('volume', 0))
                liquidity = float(market.get('liquidity', 0))
                
                analysis['volume'] = volume
                analysis['liquidity'] = liquidity
                
                # === Advanced Scoring System ===
                scores = {}
                confidence = 0.0
                reasons = []
                
                # 1. ARBITRAGE DETECTION (أقوى فرصة!)
                arbitrage_score, arb_profit = self._detect_arbitrage(yes_price, no_price)
                scores['arbitrage'] = arbitrage_score
                
                if arbitrage_score > 0.7:
                    confidence += 0.35
                    reasons.append(f"🔥 ARBITRAGE OPPORTUNITY! Potential: {arb_profit*100:.1f}%")
                    analysis['opportunity_type'] = 'ARBITRAGE'
                    analysis['recommendation'] = 'BUY_BOTH'  # Buy both sides
                    analysis['expected_return'] = arb_profit
                
                # 2. PRICE INEFFICIENCY (سعر غير منطقي)
                inefficiency_score = self._calculate_inefficiency(yes_price, volume, liquidity)
                scores['inefficiency'] = inefficiency_score
                
                if inefficiency_score > 0.6:
                    confidence += 0.25
                    direction = "YES" if yes_price < 0.4 else "NO"
                    reasons.append(f"📊 Price inefficiency detected - {direction} undervalued")
                    if not analysis['opportunity_type']:
                        analysis['opportunity_type'] = 'MISPRICING'
                        analysis['recommendation'] = f'BUY_{direction}'
                
                # 3. MOMENTUM ANALYSIS (زخم السوق)
                momentum_score = self._calculate_momentum(market.get('id'), yes_price, volume)
                scores['momentum'] = momentum_score
                analysis['momentum'] = momentum_score
                
                if momentum_score > 0.6:
                    confidence += 0.15
                    reasons.append(f"📈 Strong momentum: {momentum_score*100:.0f}%")
                
                # 4. LIQUIDITY SCORE (سهولة الخروج)
                liquidity_score = self._score_liquidity(liquidity, volume)
                scores['liquidity'] = liquidity_score
                
                if liquidity_score > 0.7:
                    confidence += 0.1
                    reasons.append(f"💧 Excellent liquidity: ${liquidity:,.0f}")
                elif liquidity_score < 0.3:
                    confidence -= 0.15
                    reasons.append(f"⚠️ Low liquidity risk: ${liquidity:,.0f}")
                    analysis['risk_level'] = 'HIGH'
                
                # 5. VOLUME ANALYSIS (نشاط السوق)
                volume_score = self._score_volume(volume)
                scores['volume'] = volume_score
                
                if volume_score > 0.7:
                    confidence += 0.1
                    reasons.append(f"📊 High trading activity: ${volume:,.0f}")
                
                # 6. VOLATILITY (تقلبات السعر)
                volatility = self._calculate_volatility(market.get('id'), yes_price)
                scores['volatility'] = volatility
                analysis['volatility'] = volatility
                
                if volatility > 0.5:
                    reasons.append(f"⚡ High volatility: {volatility*100:.0f}% - Risk & Opportunity")
                
                # 7. RISK-REWARD RATIO
                risk_reward = self._calculate_risk_reward(yes_price, no_price, liquidity, volatility)
                scores['risk_reward'] = risk_reward
                
                if risk_reward > 2.0:  # 2:1 or better
                    confidence += 0.05
                    reasons.append(f"💎 Excellent Risk/Reward: {risk_reward:.1f}:1")
                
                # === Final Confidence Calculation ===
                analysis['confidence'] = max(0.0, min(1.0, confidence))
                analysis['scores'] = scores
                analysis['reasons'] = reasons
                
                # Set risk level based on factors
                if liquidity < 1000 or volatility > 0.6:
                    analysis['risk_level'] = 'HIGH'
                elif liquidity > 10000 and volatility < 0.3:
                    analysis['risk_level'] = 'LOW'
                
                # Expected return calculation
                if not analysis['expected_return']:
                    analysis['expected_return'] = self._estimate_return(yes_price, no_price, confidence)
            
        except Exception as e:
            print(f"⚠️ Error analyzing market: {e}")
        
        return analysis
    
    def _detect_arbitrage(self, yes_price: float, no_price: float) -> Tuple[float, float]:
        """
        كشف فرص المراجحة
        Detect arbitrage opportunities
        
        Returns: (score, potential_profit)
        """
        total_price = yes_price + no_price
        
        # Perfect arbitrage: total != 1.0
        deviation = abs(total_price - 1.0)
        
        # Score based on deviation
        if deviation >= 0.05:  # 5%+ deviation
            score = min(1.0, deviation / 0.1)
            potential_profit = deviation / total_price
            return score, potential_profit
        elif deviation >= 0.03:  # 3-5% deviation
            score = 0.7
            potential_profit = deviation / total_price
            return score, potential_profit
        elif deviation >= 0.02:  # 2-3% deviation
            score = 0.5
            potential_profit = deviation / total_price
            return score, potential_profit
        else:
            return 0.0, 0.0
    
    def _calculate_inefficiency(self, yes_price: float, volume: float, liquidity: float) -> float:
        """
        حساب عدم كفاءة السعر
        Calculate price inefficiency
        """
        score = 0.0
        
        # Extreme prices are often mispriced
        if yes_price < 0.25 or yes_price > 0.75:
            score += 0.4
        
        # Low volume + extreme price = higher chance of mispricing
        if volume < 5000 and (yes_price < 0.3 or yes_price > 0.7):
            score += 0.3
        
        # Good liquidity + extreme price = opportunity
        if liquidity > 5000 and (yes_price < 0.35 or yes_price > 0.65):
            score += 0.3
        
        return min(1.0, score)
    
    def _calculate_momentum(self, market_id: str, current_price: float, volume: float) -> float:
        """
        حساب زخم السوق
        Calculate market momentum
        """
        # Store price history
        self.price_history[market_id].append({
            'price': current_price,
            'volume': volume,
            'timestamp': time.time()
        })
        
        # Keep only last 50 data points
        if len(self.price_history[market_id]) > 50:
            self.price_history[market_id] = self.price_history[market_id][-50:]
        
        history = self.price_history[market_id]
        
        if len(history) < 3:
            return 0.5  # Neutral
        
        # Calculate momentum based on price trend and volume
        recent_prices = [h['price'] for h in history[-10:]]
        older_prices = [h['price'] for h in history[-20:-10]] if len(history) >= 20 else recent_prices
        
        recent_avg = statistics.mean(recent_prices)
        older_avg = statistics.mean(older_prices)
        
        # Price direction
        price_change = recent_avg - older_avg
        
        # Volume trend
        recent_volume = statistics.mean([h['volume'] for h in history[-5:]])
        
        momentum = 0.5  # Neutral start
        
        if price_change > 0.05:
            momentum += 0.3
        elif price_change > 0.02:
            momentum += 0.15
        elif price_change < -0.05:
            momentum += 0.3  # Oversold opportunity
        
        if recent_volume > volume * 1.5:  # Increasing volume
            momentum += 0.2
        
        return min(1.0, momentum)
    
    def _score_liquidity(self, liquidity: float, volume: float) -> float:
        """
        تقييم السيولة
        Score liquidity
        """
        if liquidity >= 20000:
            return 1.0
        elif liquidity >= 10000:
            return 0.9
        elif liquidity >= 5000:
            return 0.7
        elif liquidity >= 2000:
            return 0.5
        elif liquidity >= 1000:
            return 0.3
        else:
            return 0.1
    
    def _score_volume(self, volume: float) -> float:
        """
        تقييم حجم التداول
        Score trading volume
        """
        if volume >= 50000:
            return 1.0
        elif volume >= 20000:
            return 0.8
        elif volume >= 10000:
            return 0.6
        elif volume >= 5000:
            return 0.4
        else:
            return 0.2
    
    def _calculate_volatility(self, market_id: str, current_price: float) -> float:
        """
        حساب التقلبات
        Calculate volatility
        """
        history = self.price_history.get(market_id, [])
        
        if len(history) < 5:
            return 0.3  # Assume medium volatility
        
        prices = [h['price'] for h in history[-20:]]
        
        if len(prices) < 2:
            return 0.3
        
        # Calculate standard deviation
        try:
            stdev = statistics.stdev(prices)
            # Normalize to 0-1 scale
            volatility = min(1.0, stdev * 3)  # 3x stdev = high volatility
            return volatility
        except:
            return 0.3
    
    def _calculate_risk_reward(self, yes_price: float, no_price: float, 
                               liquidity: float, volatility: float) -> float:
        """
        حساب نسبة المخاطرة للعائد
        Calculate risk/reward ratio
        """
        # Potential reward (distance to $1.00)
        reward_yes = 1.0 - yes_price
        reward_no = 1.0 - no_price
        max_reward = max(reward_yes, reward_no)
        
        # Risk factors
        risk = yes_price if yes_price < 0.5 else no_price
        
        # Adjust for liquidity and volatility
        if liquidity < 2000:
            risk *= 1.5
        if volatility > 0.5:
            risk *= 1.3
        
        if risk == 0:
            return 0.0
        
        ratio = max_reward / risk
        return ratio
    
    def _estimate_return(self, yes_price: float, no_price: float, confidence: float) -> float:
        """
        تقدير العائد المتوقع
        Estimate expected return
        """
        # Simple expected value calculation
        yes_ev = (1.0 - yes_price) * confidence - yes_price * (1 - confidence)
        no_ev = (1.0 - no_price) * confidence - no_price * (1 - confidence)
        
        return max(yes_ev, no_ev)
    
    def find_best_opportunities(self, markets: List[Dict], min_confidence: float = 0.6,
                               strategy_filter: str = None) -> List[Dict]:
        """
        ابحث عن أفضل الفرص مع فلترة بالاستراتيجية
        Find best opportunities with strategy filtering
        """
        opportunities = []
        
        print(f"\n🔍 Analyzing {len(markets)} markets for opportunities...")
        
        for market in markets:
            analysis = self.analyze_market_advanced(market)
            
            # Filter by confidence
            if analysis['confidence'] < min_confidence:
                continue
            
            # Filter by strategy if specified
            if strategy_filter:
                if strategy_filter == 'arbitrage' and analysis['opportunity_type'] != 'ARBITRAGE':
                    continue
                elif strategy_filter == 'momentum' and analysis['momentum'] < 0.6:
                    continue
            
            opportunities.append(analysis)
        
        # Sort by expected return * confidence (expected value)
        opportunities.sort(
            key=lambda x: x['expected_return'] * x['confidence'],
            reverse=True
        )
        
        # Display results
        print(f"\n💎 Found {len(opportunities)} opportunities:")
        for i, opp in enumerate(opportunities[:5], 1):
            ev = opp['expected_return'] * opp['confidence'] * 100
            print(f"{i}. {opp['question'][:50]}...")
            print(f"   Type: {opp['opportunity_type']} | Confidence: {opp['confidence']*100:.0f}%")
            print(f"   Expected Value: {ev:.1f}% | Risk: {opp['risk_level']}")
        
        return opportunities
    
    def track_whale_trade(self, wallet: str, market_id: str, side: str, amount: float):
        """
        تتبع صفقات الحيتان
        Track whale trades
        """
        self.whale_trades.append({
            'wallet': wallet,
            'market_id': market_id,
            'side': side,
            'amount': amount,
            'timestamp': datetime.now().isoformat(),
        })
        
        # Keep only recent trades
        if len(self.whale_trades) > 1000:
            self.whale_trades = self.whale_trades[-1000:]
    
    def get_whale_signals(self, market_id: str) -> Dict:
        """
        احصل على إشارات الحيتان لسوق معين
        Get whale signals for a specific market
        """
        recent_trades = [t for t in self.whale_trades 
                        if t['market_id'] == market_id
                        and (datetime.now() - datetime.fromisoformat(t['timestamp']).replace(tzinfo=None)).seconds < 3600]
        
        if not recent_trades:
            return {'signal': 'NEUTRAL', 'strength': 0.0, 'count': 0}
        
        yes_amount = sum(t['amount'] for t in recent_trades if t['side'] == 'YES')
        no_amount = sum(t['amount'] for t in recent_trades if t['side'] == 'NO')
        
        total = yes_amount + no_amount
        if total == 0:
            return {'signal': 'NEUTRAL', 'strength': 0.0, 'count': len(recent_trades)}
        
        yes_ratio = yes_amount / total
        
        if yes_ratio > 0.7:
            return {'signal': 'BUY_YES', 'strength': yes_ratio, 'count': len(recent_trades)}
        elif yes_ratio < 0.3:
            return {'signal': 'BUY_NO', 'strength': 1 - yes_ratio, 'count': len(recent_trades)}
        else:
            return {'signal': 'NEUTRAL', 'strength': 0.5, 'count': len(recent_trades)}


# Example usage
if __name__ == "__main__":
    analyzer = AdvancedMarketAnalyzer()
    
    print("🚀 Testing Advanced AI Analyzer\n")
    
    # Get markets
    markets = analyzer.get_active_markets(limit=20, min_volume=5000)
    
    if markets:
        # Find best opportunities
        opportunities = analyzer.find_best_opportunities(markets, min_confidence=0.5)
        
        if opportunities:
            print(f"\n🎯 Top Opportunity Details:")
            top = opportunities[0]
            print(f"\n{'='*70}")
            print(f"📊 {top['question']}")
            print(f"{'='*70}")
            print(f"🎲 Confidence: {top['confidence']*100:.0f}%")
            print(f"🎯 Type: {top['opportunity_type']}")
            print(f"📈 Recommendation: {top['recommendation']}")
            print(f"💰 Expected Return: {top['expected_return']*100:.1f}%")
            print(f"⚠️ Risk Level: {top['risk_level']}")
            print(f"\n💡 Detailed Scores:")
            for score_name, score_value in top['scores'].items():
                print(f"   {score_name}: {score_value*100:.0f}%")
            print(f"\n💡 Reasons:")
            for reason in top['reasons']:
                print(f"   • {reason}")
            print(f"{'='*70}\n")
    else:
        print("❌ No markets found")
