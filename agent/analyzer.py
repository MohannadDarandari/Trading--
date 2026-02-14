"""
📊 Market Analyzer - تحليل أسواق Polymarket
يحلل الأسواق ويعطي توصيات
"""

import requests
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json


class MarketAnalyzer:
    """محلل أسواق Polymarket"""
    
    def __init__(self, api_url: str = "https://clob.polymarket.com"):
        self.api_url = api_url
        self.cache = {}
        self.cache_duration = 60  # seconds
    
    def get_active_markets(self, limit: int = 20) -> List[Dict]:
        """
        احصل على الأسواق النشطة
        Get active markets
        """
        try:
            url = f"{self.api_url}/markets"
            params = {
                'limit': limit,
                'closed': False,
                '_clobOrderBy': 'volume',
                '_limit': limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                markets = response.json()
                print(f"✅ Found {len(markets)} active markets")
                return markets
            else:
                print(f"❌ Failed to fetch markets: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error fetching markets: {e}")
            return []
    
    def get_market_details(self, market_id: str) -> Optional[Dict]:
        """
        احصل على تفاصيل سوق معين
        Get specific market details
        """
        # Check cache first
        cache_key = f"market_{market_id}"
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if time.time() - cached_time < self.cache_duration:
                return cached_data
        
        try:
            url = f"{self.api_url}/markets/{market_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                market_data = response.json()
                self.cache[cache_key] = (time.time(), market_data)
                return market_data
            else:
                print(f"⚠️ Failed to fetch market {market_id}")
                return None
                
        except Exception as e:
            print(f"❌ Error fetching market details: {e}")
            return None
    
    def analyze_market(self, market: Dict) -> Dict:
        """
        حلل سوق وأعط score
        Analyze a market and return a score
        """
        analysis = {
            'market_id': market.get('id', ''),
            'question': market.get('question', 'Unknown'),
            'confidence': 0.0,
            'recommendation': 'HOLD',  # BUY_YES, BUY_NO, HOLD
            'reasons': [],
            'current_price_yes': 0.0,
            'volume': 0.0,
            'liquidity': 0.0
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
                
                # Get volume & liquidity
                volume = float(market.get('volume', 0))
                liquidity = float(market.get('liquidity', 0))
                
                analysis['volume'] = volume
                analysis['liquidity'] = liquidity
                
                # Analysis criteria
                confidence = 0.0
                reasons = []
                
                # 1. Price analysis (هل السعر غلط؟)
                if yes_price < 0.3:
                    confidence += 0.3
                    reasons.append(f"Low YES price ({yes_price:.2f}) - potential upside")
                    analysis['recommendation'] = 'BUY_YES'
                elif yes_price > 0.7:
                    confidence += 0.3
                    reasons.append(f"High YES price ({yes_price:.2f}) - consider NO")
                    analysis['recommendation'] = 'BUY_NO'
                
                # 2. Volume analysis (هل فيه نشاط؟)
                if volume > 10000:
                    confidence += 0.2
                    reasons.append(f"High volume (${volume:,.0f})")
                elif volume < 1000:
                    confidence -= 0.1
                    reasons.append(f"Low volume (${volume:,.0f}) - risky")
                
                # 3. Liquidity analysis (هل تقدر تبيع بسهولة؟)
                if liquidity > 5000:
                    confidence += 0.2
                    reasons.append(f"Good liquidity (${liquidity:,.0f})")
                elif liquidity < 500:
                    confidence -= 0.2
                    reasons.append(f"Low liquidity (${liquidity:,.0f}) - hard to exit")
                
                # 4. Price inefficiency (هل السعر منطقي؟)
                price_sum = yes_price + no_price
                if abs(price_sum - 1.0) > 0.05:
                    confidence += 0.3
                    reasons.append(f"Price inefficiency detected ({price_sum:.3f}) - arbitrage opportunity!")
                
                analysis['confidence'] = max(0.0, min(1.0, confidence))
                analysis['reasons'] = reasons
            
        except Exception as e:
            print(f"⚠️ Error analyzing market: {e}")
        
        return analysis
    
    def find_opportunities(self, markets: List[Dict], min_confidence: float = 0.6) -> List[Dict]:
        """
        ابحث عن فرص تداول جيدة
        Find good trading opportunities
        """
        opportunities = []
        
        print(f"\n🔍 Analyzing {len(markets)} markets...")
        
        for market in markets:
            analysis = self.analyze_market(market)
            
            if analysis['confidence'] >= min_confidence:
                opportunities.append(analysis)
                print(f"✨ Opportunity found: {analysis['question'][:60]}...")
                print(f"   Confidence: {analysis['confidence']*100:.0f}% | Recommendation: {analysis['recommendation']}")
        
        # Sort by confidence
        opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        
        print(f"\n📊 Found {len(opportunities)} opportunities with confidence >= {min_confidence*100:.0f}%")
        
        return opportunities
    
    def get_whale_trades(self, whale_addresses: List[str]) -> List[Dict]:
        """
        تتبع تداولات الحيتان
        Track whale trades (copy trading)
        """
        # Note: This requires access to on-chain data or Polymarket's trade API
        # For now, this is a placeholder
        print("🐋 Whale tracking feature - requires additional API access")
        return []
    
    def display_market_summary(self, market: Dict):
        """
        اعرض ملخص السوق
        Display market summary
        """
        analysis = self.analyze_market(market)
        
        print("\n" + "="*70)
        print(f"📊 {analysis['question']}")
        print("="*70)
        print(f"🎯 Current YES price: ${analysis['current_price_yes']:.3f}")
        print(f"💰 Volume: ${analysis['volume']:,.0f}")
        print(f"💧 Liquidity: ${analysis['liquidity']:,.0f}")
        print(f"🎲 Confidence: {analysis['confidence']*100:.0f}%")
        print(f"📈 Recommendation: {analysis['recommendation']}")
        print(f"\n💡 Analysis:")
        for reason in analysis['reasons']:
            print(f"   • {reason}")
        print("="*70 + "\n")


# Example usage
if __name__ == "__main__":
    analyzer = MarketAnalyzer()
    
    print("🚀 Starting Market Analyzer Test\n")
    
    # Get active markets
    markets = analyzer.get_active_markets(limit=10)
    
    if markets:
        # Analyze first market
        print("\n📊 Analyzing first market:")
        analyzer.display_market_summary(markets[0])
        
        # Find opportunities
        opportunities = analyzer.find_opportunities(markets, min_confidence=0.5)
        
        if opportunities:
            print(f"\n🎯 Top opportunity:")
            top = opportunities[0]
            print(f"   {top['question'][:60]}...")
            print(f"   Confidence: {top['confidence']*100:.0f}%")
            print(f"   Action: {top['recommendation']}")
    else:
        print("❌ No markets found - check API connection")
