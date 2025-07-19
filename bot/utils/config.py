"""
Konfigürasyon yönetimi - Pydantic BaseSettings kullanarak
tüm bot parametrelerini yönetir
"""
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union

from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings


class TradingMode(str, Enum):
    """İşlem modu"""
    DEMO = "demo"
    REAL = "real"


class TimeFrame(str, Enum):
    """Zaman dilimleri"""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class SignalLogic(str, Enum):
    """Sinyal mantığı"""
    ALL_TRUE = "all_true"
    MAJORITY_TRUE = "majority_true"
    ANY_TRUE = "any_true"


class MarginType(str, Enum):
    """Marjin tipi"""
    CROSS = "cross"
    ISOLATED = "isolated"


class IndicatorConfig(BaseModel):
    """İndikatör konfigürasyonu"""
    enabled: bool = True
    
    # RSI Ayarları
    rsi_period: int = Field(default=14, ge=5, le=50)
    rsi_oversold: float = Field(default=30.0, ge=10.0, le=40.0)
    rsi_overbought: float = Field(default=70.0, ge=60.0, le=90.0)
    rsi_divergence_min_size: float = Field(default=5.0, ge=1.0, le=20.0)
    
    # EMA Ayarları
    ema_fast: int = Field(default=12, ge=5, le=50)
    ema_slow: int = Field(default=26, ge=20, le=100)
    
    # SMA Ayarları
    sma_period: int = Field(default=20, ge=5, le=100)
    
    # MACD Ayarları
    macd_fast: int = Field(default=12, ge=5, le=50)
    macd_slow: int = Field(default=26, ge=20, le=100)
    macd_signal: int = Field(default=9, ge=5, le=20)
    macd_divergence_threshold: float = Field(default=2.0, ge=0.5, le=10.0)
    
    # Bollinger Bands Ayarları
    bb_period: int = Field(default=20, ge=10, le=50)
    bb_std: float = Field(default=2.0, ge=1.0, le=3.0)
    bb_width_threshold: float = Field(default=0.05, ge=0.01, le=0.2)
    
    # Stochastic RSI Ayarları
    stoch_k_period: int = Field(default=3, ge=1, le=10)
    stoch_d_period: int = Field(default=3, ge=1, le=10)
    stoch_rsi_period: int = Field(default=14, ge=5, le=50)
    
    # ATR Ayarları
    atr_period: int = Field(default=14, ge=5, le=50)
    atr_multiplier: float = Field(default=2.0, ge=1.0, le=5.0)
    
    # Ichimoku Ayarları
    ichi_tenkan: int = Field(default=9, ge=5, le=20)
    ichi_kijun: int = Field(default=26, ge=20, le=50)
    ichi_senkou_b: int = Field(default=52, ge=40, le=100)
    
    # ADX Ayarları
    adx_period: int = Field(default=14, ge=5, le=50)
    adx_trend_threshold: float = Field(default=25.0, ge=15.0, le=40.0)
    
    # Mum analizi
    wick_body_ratio: float = Field(default=2.0, ge=1.5, le=5.0)
    
    # Özel Python ifadesi
    custom_expression: Optional[str] = None


class StrategyConfig(BaseModel):
    """Strateji konfigürasyonu"""
    timeframe: TimeFrame = TimeFrame.M15
    signal_logic: SignalLogic = SignalLogic.MAJORITY_TRUE
    indicators: IndicatorConfig = Field(default_factory=IndicatorConfig)
    
    # Pozisyon ayarları
    position_size_usd: float = Field(default=1.0, ge=1.0, le=10.0)
    max_concurrent_positions: int = Field(default=5, ge=1, le=20)
    margin_type: MarginType = MarginType.CROSS
    
    # Take Profit ayarları
    tp_percentage: float = Field(default=5.0, ge=1.0, le=50.0)
    tp_use_indicator: bool = False
    tp_indicator_condition: Optional[str] = "rsi < 30"


class RiskConfig(BaseModel):
    """Risk yönetimi konfigürasyonu"""
    # Günlük drawdown sınırları
    daily_warning_threshold: float = Field(default=10.0, ge=5.0, le=20.0)
    daily_shutdown_threshold: float = Field(default=20.0, ge=10.0, le=50.0)
    
    # Pozisyon büyüklüğü
    max_portfolio_risk: float = Field(default=5.0, ge=1.0, le=20.0)
    
    # Likidasyona kadar bekle
    use_stop_loss: bool = False


class TelegramConfig(BaseModel):
    """Telegram bot konfigürasyonu"""
    enabled: bool = False
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    
    # Mesaj ayarları
    notify_new_position: bool = True
    notify_tp_hit: bool = True
    notify_liquidation: bool = True
    notify_daily_summary: bool = True
    notify_warnings: bool = True


class BinanceConfig(BaseModel):
    """Binance API konfigürasyonu"""
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    testnet: bool = False
    
    # API sınırları
    requests_per_minute: int = Field(default=1200, ge=100, le=2400)
    
    # WebSocket ayarları
    ws_timeout: int = Field(default=60, ge=30, le=300)


class AppConfig(BaseModel):
    """Uygulama genel konfigürasyonu"""
    # Tarama ayarları
    scan_interval: int = Field(default=60, ge=30, le=300)  # saniye
    top_gainers_limit: int = Field(default=20, ge=10, le=50)
    update_interval: int = Field(default=60, ge=30, le=300)  # saniye
    
    # Loglama
    log_level: str = Field(default="INFO")
    log_rotation: str = Field(default="1 day")
    log_retention: str = Field(default="30 days")
    
    # GUI ayarları
    theme: str = Field(default="dark")
    auto_start: bool = False


class BotSettings(BaseSettings):
    """Ana bot ayarları - çevre değişkenlerinden ve config.json'dan yüklenir"""
    
    # İşlem modu
    trading_mode: TradingMode = TradingMode.DEMO
    
    # Alt konfigürasyonlar
    app: AppConfig = Field(default_factory=AppConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    binance: BinanceConfig = Field(default_factory=BinanceConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    
    # Demo mod için başlangıç bakiyesi
    demo_balance: float = Field(default=1000.0, ge=100.0, le=100000.0)
    
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        json_file = "config.json"
        json_file_encoding = "utf-8"
    
    def save_to_file(self, file_path: Union[str, Path] = "config.json") -> None:
        """Ayarları JSON dosyasına kaydet"""
        import json
        
        config_dict = self.model_dump()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load_from_file(cls, file_path: Union[str, Path] = "config.json") -> "BotSettings":
        """JSON dosyasından ayarları yükle"""
        import json
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
            return cls(**config_dict)
        except FileNotFoundError:
            # Dosya yoksa varsayılan ayarlarla oluştur
            settings = cls()
            settings.save_to_file(file_path)
            return settings
    
    @validator("trading_mode")
    def validate_trading_mode(cls, v: TradingMode) -> TradingMode:
        """İşlem modunun geçerli olduğunu kontrol et"""
        if v not in TradingMode:
            raise ValueError(f"Geçersiz işlem modu: {v}")
        return v


# Global ayarlar instance'ı
settings: Optional[BotSettings] = None


def get_settings() -> BotSettings:
    """Global ayarları al veya oluştur"""
    global settings
    if settings is None:
        settings = BotSettings.load_from_file()
    return settings


def reload_settings() -> BotSettings:
    """Ayarları yeniden yükle"""
    global settings
    settings = BotSettings.load_from_file()
    return settings 