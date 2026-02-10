# Crypto Relative Strength Scanner 🚀

Advanced cryptocurrency pair trading scanner with real-time analysis, scoring, and notifications.

## ✨ Features

### 📊 **Real-time Analysis**
- Monitor 15+ major cryptocurrencies
- Calculate relative strength vs Bitcoin
- Multi-timeframe analysis (1h, 4h, 1d, 1w)
- Automated scoring and ranking system

### 🔔 **Smart Notifications**
- NTFY integration for instant alerts
- Trading signals for best pairs
- Market condition alerts
- Daily summary reports

### 🎯 **Trading Pair Discovery**
- Identify Strong vs Weak coin pairs
- Mean reversion opportunities
- Breakout detection
- Confidence scoring for each pair

### 📈 **Beautiful Dashboard**
- Interactive heatmaps
- Real-time rankings
- Performance charts
- Syria timezone support

## 🛠️ Installation

### Prerequisites
- Python 3.11+
- Git
- NTFY account (optional, for notifications)

### Quick Start

```bash
# Clone repository
git clone https://github.com/yourusername/crypto-scanner.git
cd crypto-scanner

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run the application
python -m uvicorn backend.main:app --reload
