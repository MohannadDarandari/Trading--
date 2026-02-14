# 🚀 سكريبت التشغيل السريع | Quick Launch Script

Write-Host ""
Write-Host "=" -NoNewline; Write-Host ("="*79)
Write-Host "🚀 Advanced Polymarket Trading Bot v2.0 - Quick Launcher"
Write-Host "=" -NoNewline; Write-Host ("="*79)
Write-Host ""

# Check Python
Write-Host "🔍 Checking Python installation..."
$pythonCmd = $null

if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
}

if (-not $pythonCmd) {
    Write-Host "❌ Python not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python 3.10+ from: https://www.python.org/"
    Write-Host "Make sure to check 'Add Python to PATH' during installation"
    Write-Host ""
    Pause
    exit 1
}

# Check .env file
if (-not (Test-Path ".env")) {
    Write-Host "⚠️ .env file not found!" -ForegroundColor Yellow
    Write-Host "Creating .env from template..."
    
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✅ Created .env file" -ForegroundColor Green
        Write-Host ""
        Write-Host "⚠️  IMPORTANT: Edit .env and add your keys!" -ForegroundColor Yellow
        Write-Host ""
        $response = Read-Host "Open .env now to edit? (y/n)"
        if ($response -eq "y") {
            notepad .env
            Write-Host ""
            Write-Host "Press any key after you've edited .env..."
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        }
    } else {
        Write-Host "❌ .env.example not found!" -ForegroundColor Red
        Pause
        exit 1
    }
}

Write-Host ""
Write-Host "🎯 Select Mode:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. 🧪 DRY RUN (Safe - No Real Trades) - RECOMMENDED"
Write-Host "2. 📊 Monitor Markets Only"
Write-Host "3. 🔧 Check Setup"
Write-Host "4. 💰 LIVE TRADING (Real Money!)"
Write-Host "5. 📈 View Opportunities"
Write-Host ""

$choice = Read-Host "Enter choice (1-5)"

Write-Host ""
Write-Host "=" -NoNewline; Write-Host ("="*79)

switch ($choice) {
    "1" {
        Write-Host "🧪 Starting DRY RUN mode..."
        Write-Host "=" -NoNewline; Write-Host ("="*79)
        Write-Host ""
        & $pythonCmd agent/trader_advanced.py --dry-run --interval 60
    }
    "2" {
        Write-Host "📊 Starting Market Monitor..."
        Write-Host "=" -NoNewline; Write-Host ("="*79)
        Write-Host ""
        & $pythonCmd scripts/monitor.py --interval 30
    }
    "3" {
        Write-Host "🔧 Checking Setup..."
        Write-Host "=" -NoNewline; Write-Host ("="*79)
        Write-Host ""
        & $pythonCmd scripts/utils.py check
    }
    "4" {
        Write-Host "⚠️  LIVE TRADING MODE" -ForegroundColor Red
        Write-Host "=" -NoNewline; Write-Host ("="*79)
        Write-Host ""
        Write-Host "⚠️  WARNING: This will trade with real money!" -ForegroundColor Yellow
        Write-Host ""
        $confirm = Read-Host "Are you absolutely sure? Type 'YES' to continue"
        
        if ($confirm -eq "YES") {
            Write-Host ""
            Write-Host "Starting LIVE trading..."
            & $pythonCmd agent/trader_advanced.py --interval 60
        } else {
            Write-Host "❌ Cancelled" -ForegroundColor Yellow
        }
    }
    "5" {
        Write-Host "💎 Searching for opportunities..."
        Write-Host "=" -NoNewline; Write-Host ("="*79)
        Write-Host ""
        & $pythonCmd scripts/utils.py opportunities
    }
    default {
        Write-Host "❌ Invalid choice" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=" -NoNewline; Write-Host ("="*79)
Write-Host ""
Pause
