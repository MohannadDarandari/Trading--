# 🚀 Quick Launch - تشغيل سريع
Write-Host ""
Write-Host "🔥 ULTIMATE POLYMARKET BOT" -ForegroundColor Cyan
Write-Host "Based on Real $10→$450K Strategies" -ForegroundColor Yellow
Write-Host ""

Write-Host "Choose launch mode:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. 🤖 Ultimate Bot (All Strategies)" -ForegroundColor White
Write-Host "2. 🎨 Dashboard (Web UI)" -ForegroundColor White
Write-Host "3. 🔧 Simple Bot (Original)" -ForegroundColor White
Write-Host "4. ⚙️  Configure .env" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Enter choice (1-4)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "🚀 Launching ULTIMATE BOT..." -ForegroundColor Green
        Write-Host ""
        Write-Host "📊 Strategies Active:" -ForegroundColor Cyan
        Write-Host "   ✅ Weather Arbitrage (NOAA)" -ForegroundColor Gray
        Write-Host "   ✅ Low-Risk NO Positions" -ForegroundColor Gray
        Write-Host "   ✅ Logical Gap Exploiter" -ForegroundColor Gray
        Write-Host "   ✅ Mispricing Detection (>8%)" -ForegroundColor Gray
        Write-Host "   ✅ Kelly Criterion (max 6%)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "⏱️  Scan interval: 10 minutes" -ForegroundColor Yellow
        Write-Host "🎯 Target: 500-1000 markets/scan" -ForegroundColor Yellow
        Write-Host ""
        py agent/ultimate_bot.py
    }
    "2" {
        Write-Host ""
        Write-Host "🎨 Launching Dashboard..." -ForegroundColor Green
        Write-Host "Opening at: http://localhost:8501" -ForegroundColor Cyan
        Write-Host ""
        streamlit run dashboard.py
    }
    "3" {
        Write-Host ""
        Write-Host "🔧 Launching Simple Bot..." -ForegroundColor Green
        Write-Host ""
        py agent/trader_advanced.py --dry-run
    }
    "4" {
        Write-Host ""
        Write-Host "⚙️  Opening .env configuration..." -ForegroundColor Green
        notepad .env
    }
    default {
        Write-Host ""
        Write-Host "❌ Invalid choice" -ForegroundColor Red
    }
}
