# Auto Installer for Trading Bot
Write-Host ""
Write-Host "Polymarket Trading Bot - Auto Installer" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[Step 1/4] Checking Python..." -ForegroundColor Yellow
$pythonExists = $false

try {
    $ver = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Python found: $ver" -ForegroundColor Green
        $pythonExists = $true
    }
} catch {}

if (-not $pythonExists) {
    Write-Host "  Python NOT found!" -ForegroundColor Red
    Write-Host "  Opening download page..." -ForegroundColor Cyan
    Start-Process "https://www.python.org/downloads/"
    Write-Host ""
    Write-Host "  Remember to check: Add Python to PATH" -ForegroundColor Yellow
    Read-Host "  Press Enter after installing Python"
    exit
}

Write-Host ""

# Check .env file
Write-Host "[Step 2/4] Checking configuration..." -ForegroundColor Yellow

if (Test-Path ".env") {
    Write-Host "  .env file exists" -ForegroundColor Green
} else {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "  Created .env file" -ForegroundColor Green
        Write-Host "  Remember to edit it!" -ForegroundColor Yellow
    }
}

Write-Host ""

# Install packages
Write-Host "[Step 3/4] Installing Python packages..." -ForegroundColor Yellow
Write-Host "  This may take 2-3 minutes..." -ForegroundColor Gray
Write-Host ""

python -m pip install --upgrade pip --quiet 2>&1 | Out-Null
python -m pip install -r requirements.txt --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "  All packages installed successfully!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  Some packages may have failed to install" -ForegroundColor Yellow
}

Write-Host ""

# Test
Write-Host "[Step 4/4] Testing installation..." -ForegroundColor Yellow

python -c "import web3; print('  web3: OK')" 2>$null
python -c "import streamlit; print('  streamlit: OK')" 2>$null
python -c "import plotly; print('  plotly: OK')" 2>$null
python -c "import pandas; print('  pandas: OK')" 2>$null

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "Installation Complete!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Edit configuration file:" -ForegroundColor White
Write-Host "     notepad .env" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Launch Web Dashboard:" -ForegroundColor White
Write-Host "     streamlit run dashboard.py" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Or run bot directly:" -ForegroundColor White
Write-Host "     python agent/trader_advanced.py --dry-run" -ForegroundColor Gray
Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

$answer = Read-Host "Launch Dashboard now? (y/n)"

if ($answer -eq "y") {
    Write-Host ""
    Write-Host "Starting Dashboard..." -ForegroundColor Cyan
    Write-Host "Opening at: http://localhost:8501" -ForegroundColor Yellow
    Write-Host ""
    streamlit run dashboard.py
} else {
    Write-Host ""
    Write-Host "Done! Use: streamlit run dashboard.py" -ForegroundColor Green
}
