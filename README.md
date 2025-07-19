# 🤖 ShortBot - Kripto Short İşlem Botu

**Parametrik, stop-loss'suz, sabit 1 USDT short pozisyon açan kripto trading botu**

## 📋 Özellikler

✅ **Demo/Real Mod** - Güvenli test ve gerçek işlemler  
✅ **Parametrik Strateji** - 15+ teknik indikatör desteği  
✅ **PySide6 GUI** - Modern masaüstü arayüzü  
✅ **Telegram Entegrasyonu** - Uzaktan yönetim ve bildirimler  
✅ **Risk Yönetimi** - Günlük drawdown koruması  
✅ **Windows Credentials Vault** - Güvenli API key saklama  
✅ **Atomic Dizayn** - PEP-8 uyumlu, test edilebilir kod  

## 🚀 Hızlı Başlangıç

### Sistem Gereksinimleri

- **Python 3.11+**
- **Windows 10/11** (Ana hedef platform)
- **8GB+ RAM** (GUI için)
- **İnternet bağlantısı** (Binance API için)

### Kurulum

1. **Python 3.11+ yükleyin:**
   ```bash
   # https://python.org adresinden indirin
   ```

2. **Projeyi klonlayın:**
   ```bash
   git clone https://github.com/your-repo/shortbot.git
   cd shortbot
   ```

3. **Sanal ortam oluşturun:**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```

4. **Bağımlılıkları yükleyin:**
   ```bash
   pip install -r requirements.txt
   ```

5. **TA-Lib kurulumu (Windows):**
   ```bash
   # https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib adresinden
   # uygun .whl dosyasını indirin ve:
   pip install TA_Lib‑0.4.19‑cp311‑cp311‑win_amd64.whl
   ```

### İlk Çalıştırma

```bash
# Demo modu - API key gerektirmez
python main.py --mode demo --trading-mode demo

# GUI modu (geliştiriliyor)
python main.py --mode gui

# CLI modu (geliştiriliyor) 
python main.py --mode cli
```

## ⚙️ Konfigürasyon

### Temel Ayarlar (`config.json`)

```json
{
  "trading_mode": "demo",
  "demo_balance": 1000.0,
  "app": {
    "scan_interval": 60,
    "top_gainers_limit": 20,
    "log_level": "INFO"
  },
  "strategy": {
    "timeframe": "15m",
    "signal_logic": "majority_true",
    "position_size_usd": 1.0,
    "max_concurrent_positions": 5,
    "tp_percentage": 5.0
  },
  "risk": {
    "daily_warning_threshold": 10.0,
    "daily_shutdown_threshold": 20.0
  }
}
```

### Real Mod için API Anahtarları

1. **Binance Futures API** oluşturun ([Binance API Management](https://www.binance.com/en/my/settings/api-management))
2. **Futures Trading** iznini etkinleştirin
3. **IP Restriction** ekleyin (güvenlik için)

```bash
# API anahtarlarını GUI'den girin veya:
python -c "
from bot.utils.encryption import store_api_credentials
store_api_credentials('YOUR_API_KEY', 'YOUR_API_SECRET')
"
```

## 🎯 Strateji Parametreleri

### Desteklenen İndikatörler

- **RSI** - Divergence detection
- **EMA/SMA** - Trend following
- **MACD** - Signal crossovers
- **Bollinger Bands** - Volatility
- **Stochastic RSI** - Momentum
- **ATR** - Volatility stops
- **Ichimoku** - Cloud analysis
- **ADX** - Trend strength
- **Fibonacci** - Retracement levels
- **VWAP** - Volume weighted price
- **Custom Python** - Kendi formülünüz

### Sinyal Mantığı

- **ALL_TRUE**: Tüm indikatörler pozitif
- **MAJORITY_TRUE**: Çoğunluk pozitif (varsayılan)
- **ANY_TRUE**: En az bir indikatör pozitif

## 📊 Risk Yönetimi

- **Günlük %10 uyarısı** - Telegram + GUI bildirimi
- **Günlük %20 kapatma** - Otomatik pozisyon kapatma
- **Liquidation'a kadar bekle** - Stop-loss yok
- **Sabit pozisyon büyüklüğü** - 1-10 USDT arası

## 📱 Telegram Komutları

```
/status    → Bakiye ve pozisyon durumu
/stop      → Botu güvenli kapat
/start     → Botu yeniden başlat
/mode demo → Demo moda geç
/tp 5      → Take profit %5 yap
```

## 🔧 Geliştirme

### Proje Yapısı

```
bot/
├─ core/           # İş mantığı
│  ├─ engine.py        # Ana işlem motoru
│  ├─ signals.py       # İndikatör sistemı
│  ├─ portfolio.py     # Pozisyon yönetimi
│  ├─ risk.py          # Risk kontrolü
│  └─ demo_exchange.py # Simülasyon
├─ ui/             # PySide6 arayüzü
│  ├─ main_window.py   # Ana pencere
│  └─ widgets/         # UI bileşenleri
├─ services/       # Harici servisler
│  ├─ telegram_service.py
│  └─ scheduler.py
└─ utils/          # Yardımcı araçlar
   ├─ config.py        # Konfigürasyon
   ├─ logger.py        # Loglama
   └─ encryption.py    # API key güvenlik
```

### Test Çalıştırma

```bash
# Tüm testler
python -m pytest

# Coverage raporu
python -m pytest --cov=bot --cov-report=html

# Kod kalitesi
black bot/
isort bot/
mypy bot/ --strict
```

### Build

```bash
# Windows MSI paketi
pyinstaller --onefile --noconsole --name ShortBot main.py
```

## ⚠️ Risk Uyarıları

- **Kripto trading yüksek risklidir** - Sadece kaybetmeyi göze alabileceğiniz miktarla işlem yapın
- **Demo modda başlayın** - Real para kullanmadan önce stratejinizi test edin
- **API anahtarlarınızı koruyun** - Asla paylaşmayın, IP restriction kullanın
- **Günlük limitleri ayarlayın** - %20 üzeri kayıplarda otomatik kapatma
- **Bot'u izleyin** - Tam otomatik bırakmayın

## 📞 Destek

- 🐛 **Bug Report**: [GitHub Issues](https://github.com/your-repo/shortbot/issues)
- 💡 **Feature Request**: [GitHub Discussions](https://github.com/your-repo/shortbot/discussions)
- 📖 **Dokümantasyon**: [Wiki](https://github.com/your-repo/shortbot/wiki)

## 📄 Lisans

Bu proje MIT lisansı altında yayınlanmıştır. Detaylar için `LICENSE` dosyasını inceleyin.

---

**⚡ Hızlı başlamak için: `python main.py --mode demo`**
