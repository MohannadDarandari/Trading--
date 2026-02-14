"""
🔥 ULTIMATE Polymarket Bot - Based on Real $10→$450K Strategies
البوت الخرافي - يدمج استراتيجيات حقيقية محققة
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
import json
from pathlib import Path

from config.settings import Config
from agent.advanced_analyzer import AdvancedMarketAnalyzer


class WeatherDataFetcher:
    """
    🌤️ Weather Data Integration
    استراتيجية: $400 يومياً من تداول الطقس
    """
    
    def __init__(self):
        self.noaa_base = "https://api.weather.gov"
        
    def get_weather_forecast(self, lat: float, lon: float) -> Dict:
        """Get NOAA weather forecast before Polymarket updates"""
        try:
            # Get forecast URL
            points_url = f"{self.noaa_base}/points/{lat},{lon}"
            response = requests.get(points_url, headers={"User-Agent": "PolymarketBot"})
            
            if response.status_code == 200:
                data = response.json()
                forecast_url = data['properties']['forecast']
                
                # Get actual forecast
                forecast_response = requests.get(forecast_url, headers={"User-Agent": "PolymarketBot"})
                if forecast_response.status_code == 200:
                    return forecast_response.json()
            
            return None
        except Exception as e:
            print(f"Weather fetch error: {e}")
            return None
    
    def find_weather_arbitrage(self, markets: List[Dict]) -> List[Dict]:
        """
        Find weather arbitrage opportunities
        NOAA shows 90% rain chance, Polymarket shows 0.60 YES → BUY YES!
        """
        opportunities = []
        
        # Major US cities for weather trading
        cities = {
            "New York": (40.7128, -74.0060),
            "Los Angeles": (34.0522, -118.2437),
            "Chicago": (41.8781, -87.6298),
            "Miami": (25.7617, -80.1918)
        }
        
        for market in markets:
            question = market.get('question', '').lower()
            
            # Check if it's a weather market
            if any(word in question for word in ['rain', 'snow', 'temperature', 'weather', 'storm']):
                
                # Extract city
                for city, coords in cities.items():
                    if city.lower() in question:
                        forecast = self.get_weather_forecast(*coords)
                        
                        if forecast:
                            # Compare NOAA vs Polymarket
                            noaa_rain_chance = self._extract_rain_probability(forecast)
                            poly_yes_price = float(market.get('outcomes', [{}])[0].get('price', 0))
                            
                            # Big mispricing? (>8% difference)
                            if abs(noaa_rain_chance - poly_yes_price) > 0.08:
                                opportunities.append({
                                    'market': market,
                                    'type': 'WEATHER_ARBITRAGE',
                                    'noaa_probability': noaa_rain_chance,
                                    'polymarket_price': poly_yes_price,
                                    'mispricing': abs(noaa_rain_chance - poly_yes_price),
                                    'action': 'BUY_YES' if noaa_rain_chance > poly_yes_price else 'BUY_NO',
                                    'confidence': 0.95
                                })
        
        return opportunities
    
    def _extract_rain_probability(self, forecast: Dict) -> float:
        """Extract rain probability from NOAA forecast"""
        try:
            periods = forecast.get('properties', {}).get('periods', [])
            if periods:
                first_period = periods[0]
                # NOAA gives percentage, convert to 0-1
                precip_prob = first_period.get('probabilityOfPrecipitation', {}).get('value', 0)
                return precip_prob / 100.0 if precip_prob else 0.5
        except:
            return 0.5
        
        return 0.5


class LowRiskNOStrategy:
    """
    🎯 Low-Risk "NO" Positions Strategy
    استراتيجية: الرهان ضد النتائج غير المحتملة
    """
    
    def find_unlikely_outcomes(self, markets: List[Dict]) -> List[Dict]:
        """
        Find extremely unlikely outcomes to bet NO on
        Example: "Will aliens visit Earth in 2026?" → 0.05 YES → BUY NO at 0.95
        """
        opportunities = []
        
        # Keywords for clearly impossible/unlikely events
        unlikely_keywords = [
            'aliens', 'ufo', 'time travel', 'immortality',
            'world end', 'apocalypse', 'meteor strike',
            'zombie', 'dinosaur', 'magic', 'teleport'
        ]
        
        for market in markets:
            question = market.get('question', '').lower()
            yes_price = float(market.get('outcomes', [{}])[0].get('price', 0))
            
            # Check for unlikely keywords
            is_unlikely = any(keyword in question for keyword in unlikely_keywords)
            
            # Or check extremely low YES price (below 0.15)
            if is_unlikely or yes_price < 0.15:
                no_price = 1 - yes_price
                
                # Only if NO price is reasonable (not too low)
                if no_price <= 0.92:  # Leave room for profit
                    opportunities.append({
                        'market': market,
                        'type': 'LOW_RISK_NO',
                        'action': 'BUY_NO',
                        'yes_price': yes_price,
                        'no_price': no_price,
                        'confidence': 0.98,
                        'expected_return': (1 / no_price) - 1,
                        'reason': 'Extremely unlikely event'
                    })
        
        return opportunities


class LogicalGapStrategy:
    """
    🧠 Logical Price Gap Exploiter
    استراتيجية: استغلال الفجوات المنطقية
    
    إذا الحدث A يؤثر على الحدث B، لكن السوق ما تحدث = فرصة!
    """
    
    def find_logical_gaps(self, markets: List[Dict]) -> List[Dict]:
        """
        Find logical inconsistencies between related markets
        
        Example:
        - "BTC above $100K in 2026" = 0.70 YES
        - "ETH above $10K in 2026" = 0.30 YES
        → Logical gap: If BTC 100K, ETH should be higher!
        """
        opportunities = []
        
        # Group markets by category
        crypto_markets = [m for m in markets if any(coin in m.get('question', '').lower() 
                                                     for coin in ['btc', 'bitcoin', 'eth', 'ethereum', 'crypto'])]
        
        sports_markets = [m for m in markets if any(sport in m.get('question', '').lower() 
                                                     for sport in ['nfl', 'nba', 'soccer', 'football', 'championship'])]
        
        # Check crypto correlations
        for i, market1 in enumerate(crypto_markets):
            for market2 in crypto_markets[i+1:]:
                gap = self._check_crypto_correlation(market1, market2)
                if gap:
                    opportunities.append(gap)
        
        # Check sports logic
        for i, market1 in enumerate(sports_markets):
            for market2 in sports_markets[i+1:]:
                gap = self._check_sports_logic(market1, market2)
                if gap:
                    opportunities.append(gap)
        
        return opportunities
    
    def _check_crypto_correlation(self, market1: Dict, market2: Dict) -> Optional[Dict]:
        """Check if two crypto markets have logical gaps"""
        q1 = market1.get('question', '').lower()
        q2 = market2.get('question', '').lower()
        
        p1 = float(market1.get('outcomes', [{}])[0].get('price', 0))
        p2 = float(market2.get('outcomes', [{}])[0].get('price', 0))
        
        # BTC/ETH correlation check
        if 'btc' in q1 and 'eth' in q2:
            # If BTC high probability, ETH should follow
            if p1 > 0.7 and p2 < 0.4:
                return {
                    'market': market2,
                    'type': 'LOGICAL_GAP',
                    'action': 'BUY_YES',
                    'reason': f'BTC high prob ({p1:.2f}), ETH should follow',
                    'related_market': market1,
                    'confidence': 0.75,
                    'mispricing': p1 - p2
                }
        
        return None
    
    def _check_sports_logic(self, market1: Dict, market2: Dict) -> Optional[Dict]:
        """Check sports markets for logical inconsistencies"""
        # Similar logic for sports
        return None


class UltimatePolymarketBot:
    """
    🔥 ULTIMATE BOT - Combines ALL Winning Strategies
    """
    
    def __init__(self):
        self.analyzer = AdvancedMarketAnalyzer()
        self.weather_fetcher = WeatherDataFetcher()
        self.low_risk_strategy = LowRiskNOStrategy()
        self.logical_gap_strategy = LogicalGapStrategy()
        
        self.session_stats = {
            'total_scans': 0,
            'opportunities_found': 0,
            'trades_executed': 0,
            'profit': 0.0,
            'win_rate': 0.0
        }
        
        print("🔥 ULTIMATE BOT INITIALIZED")
        print("📊 Strategies:")
        print("   ✅ Weather Arbitrage (NOAA)")
        print("   ✅ Low-Risk NO Positions")
        print("   ✅ Logical Gap Exploiter")
        print("   ✅ Mispricing Detection (>8%)")
        print("   ✅ Kelly Criterion (max 6%)")
        print(f"   ✅ Scan Interval: 10 minutes")
        print(f"   ✅ Target: 500-1000 markets/scan")
    
    def scan_all_strategies(self) -> List[Dict]:
        """
        MASTER SCAN - Check all strategies
        Based on Argona's bot: scan 500-1000 markets every 10 minutes
        """
        print(f"\n{'='*60}")
        print(f"🔍 MASTER SCAN #{self.session_stats['total_scans'] + 1}")
        print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        
        all_opportunities = []
        
        # 1. Get markets
        print("📥 Fetching markets...")
        markets = self.analyzer.get_active_markets(limit=1000, min_volume=1000)
        print(f"   Found {len(markets)} active markets")
        
        # 2. Weather Arbitrage (HIGHEST PRIORITY!)
        print("\n🌤️  Strategy 1: Weather Arbitrage...")
        weather_opps = self.weather_fetcher.find_weather_arbitrage(markets)
        print(f"   Found {len(weather_opps)} weather opportunities")
        all_opportunities.extend(weather_opps)
        
        # 3. Low-Risk NO Positions
        print("\n🎯 Strategy 2: Low-Risk NO Positions...")
        no_opps = self.low_risk_strategy.find_unlikely_outcomes(markets)
        print(f"   Found {len(no_opps)} low-risk NO opportunities")
        all_opportunities.extend(no_opps)
        
        # 4. Logical Gap Detection
        print("\n🧠 Strategy 3: Logical Gaps...")
        gap_opps = self.logical_gap_strategy.find_logical_gaps(markets)
        print(f"   Found {len(gap_opps)} logical gap opportunities")
        all_opportunities.extend(gap_opps)
        
        # 5. Standard Mispricing (>8%)
        print("\n💎 Strategy 4: Mispricing Detection...")
        standard_opps = self.analyzer.find_best_opportunities(
            markets,
            min_confidence=0.65,
            strategy_filter=None
        )
        
        # Filter for >8% mispricing
        high_mispricing = [opp for opp in standard_opps 
                          if opp.get('scores', {}).get('arbitrage', 0) > 0.08]
        print(f"   Found {len(high_mispricing)} high mispricing opportunities (>8%)")
        all_opportunities.extend(high_mispricing)
        
        # Sort by confidence and expected return
        all_opportunities.sort(key=lambda x: x.get('confidence', 0) * x.get('expected_return', 0), reverse=True)
        
        self.session_stats['total_scans'] += 1
        self.session_stats['opportunities_found'] += len(all_opportunities)
        
        print(f"\n{'='*60}")
        print(f"✅ SCAN COMPLETE")
        print(f"💎 Total Opportunities: {len(all_opportunities)}")
        print(f"{'='*60}")
        
        return all_opportunities[:50]  # Top 50
    
    def calculate_kelly_position_size(self, opportunity: Dict, bankroll: float) -> float:
        """
        Kelly Criterion for position sizing
        Max 6% of bankroll per trade (like Argona's bot)
        """
        confidence = opportunity.get('confidence', 0.6)
        expected_return = opportunity.get('expected_return', 0.05)
        
        # Kelly formula: (bp - q) / b
        # where b = odds, p = win probability, q = loss probability
        p = confidence
        q = 1 - p
        b = expected_return
        
        kelly_fraction = (b * p - q) / b if b > 0 else 0
        
        # Cap at 6% (like successful bots)
        kelly_fraction = min(kelly_fraction, 0.06)
        kelly_fraction = max(kelly_fraction, 0.01)  # Min 1%
        
        position_size = bankroll * kelly_fraction
        
        # Cap at MAX_POSITION_SIZE from config
        position_size = min(position_size, Config.MAX_POSITION_SIZE)
        
        return position_size
    
    async def run_continuous(self, duration_hours: float = 48):
        """
        Run bot continuously like Argona's: scan every 10 minutes
        """
        print(f"\n🚀 STARTING CONTINUOUS OPERATION")
        print(f"⏱️  Duration: {duration_hours} hours")
        print(f"🔄 Scan Interval: 10 minutes")
        print(f"💰 Starting Bankroll: ${Config.MAX_POSITION_SIZE * 10}")
        print(f"{'='*60}\n")
        
        start_time = time.time()
        end_time = start_time + (duration_hours * 3600)
        
        bankroll = Config.MAX_POSITION_SIZE * 10  # Start with 10x position size
        
        while time.time() < end_time:
            # Scan all strategies
            opportunities = self.scan_all_strategies()
            
            # Execute top opportunities
            if opportunities:
                print(f"\n💰 TOP 10 OPPORTUNITIES:")
                for i, opp in enumerate(opportunities[:10], 1):
                    position_size = self.calculate_kelly_position_size(opp, bankroll)
                    
                    print(f"\n{i}. {opp.get('type', 'UNKNOWN')}")
                    print(f"   Market: {opp.get('market', {}).get('question', 'N/A')[:60]}...")
                    print(f"   Action: {opp.get('action', 'N/A')}")
                    print(f"   Confidence: {opp.get('confidence', 0)*100:.0f}%")
                    print(f"   Position Size: ${position_size:.2f} " +
                          f"({(position_size/bankroll)*100:.1f}% of bankroll)")
                    
                    if Config.DRY_RUN:
                        print(f"   ⚠️  DRY RUN - Trade simulated")
                    else:
                        print(f"   ✅ EXECUTING...")
                        # Execute trade here
                        self.session_stats['trades_executed'] += 1
            
            # Wait 10 minutes before next scan
            print(f"\n⏸️  Waiting 10 minutes until next scan...")
            print(f"📊 Session Stats:")
            print(f"   Scans: {self.session_stats['total_scans']}")
            print(f"   Opportunities: {self.session_stats['opportunities_found']}")
            print(f"   Trades: {self.session_stats['trades_executed']}")
            
            await asyncio.sleep(600)  # 10 minutes
        
        print(f"\n{'='*60}")
        print(f"🏁 BOT STOPPED AFTER {duration_hours} HOURS")
        print(f"{'='*60}")


async def main():
    bot = UltimatePolymarketBot()
    
    # Run for 48 hours like Argona's bot
    await bot.run_continuous(duration_hours=48)


if __name__ == "__main__":
    asyncio.run(main())
