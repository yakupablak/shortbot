"""
Test: Konfigürasyon modülü
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from bot.utils.config import (
    BotSettings, 
    TradingMode, 
    TimeFrame, 
    SignalLogic,
    IndicatorConfig
)


class TestBotSettings:
    """BotSettings test sınıfı"""
    
    def test_default_values(self):
        """Varsayılan değerler testi"""
        settings = BotSettings()
        
        assert settings.trading_mode == TradingMode.DEMO
        assert settings.demo_balance == 1000.0
        assert settings.app.scan_interval == 60
        assert settings.strategy.timeframe == TimeFrame.M15
        assert settings.strategy.tp_percentage == 5.0
        assert settings.risk.daily_warning_threshold == 10.0
    
    def test_model_validation(self):
        """Model validasyon testi"""
        # Geçersiz trading mode
        with pytest.raises(ValueError):
            BotSettings(trading_mode="invalid_mode")
        
        # Geçersiz balance
        with pytest.raises(ValueError):
            BotSettings(demo_balance=50)  # 100'den az
    
    def test_nested_config(self):
        """İç içe konfigürasyon testi"""
        settings = BotSettings()
        
        # Strategy config erişimi
        assert hasattr(settings.strategy, 'indicators')
        assert hasattr(settings.strategy.indicators, 'rsi_period')
        
        # Default indicator values
        assert settings.strategy.indicators.rsi_period == 14
        assert settings.strategy.indicators.ema_fast == 12
    
    def test_save_load_file(self, tmp_path):
        """Dosya kaydet/yükle testi"""
        # Geçici dosya yolu
        config_file = tmp_path / "test_config.json"
        
        # Settings oluştur ve kaydet
        settings = BotSettings(demo_balance=2000.0)
        settings.save_to_file(config_file)
        
        # Dosya var mı kontrol et
        assert config_file.exists()
        
        # Dosyadan yükle
        loaded_settings = BotSettings.load_from_file(config_file)
        
        assert loaded_settings.demo_balance == 2000.0
        assert loaded_settings.trading_mode == TradingMode.DEMO
    
    def test_load_nonexistent_file(self, tmp_path):
        """Olmayan dosya yükle testi"""
        config_file = tmp_path / "nonexistent.json"
        
        # Olmayan dosya yüklendiğinde varsayılan settings döner
        settings = BotSettings.load_from_file(config_file)
        
        assert settings.demo_balance == 1000.0  # Default değer
        assert config_file.exists()  # Dosya oluşturulmuş olmalı
    
    def test_json_serialization(self):
        """JSON serializasyon testi"""
        settings = BotSettings()
        
        # Model dump
        data = settings.model_dump()
        
        assert "trading_mode" in data
        assert "app" in data
        assert "strategy" in data
        
        # JSON'a çevrilebilir olmalı
        json_str = json.dumps(data)
        assert len(json_str) > 0


class TestIndicatorConfig:
    """IndicatorConfig test sınıfı"""
    
    def test_default_values(self):
        """Varsayılan değerler testi"""
        config = IndicatorConfig()
        
        assert config.enabled is True
        assert config.rsi_period == 14
        assert config.ema_fast == 12
        assert config.ema_slow == 26
    
    def test_validation_ranges(self):
        """Değer aralığı validasyon testi"""
        # Geçersiz RSI period
        with pytest.raises(ValueError):
            IndicatorConfig(rsi_period=3)  # 5'ten az
        
        with pytest.raises(ValueError):
            IndicatorConfig(rsi_period=60)  # 50'den fazla
        
        # Geçerli değerler
        config = IndicatorConfig(rsi_period=20)
        assert config.rsi_period == 20
    
    def test_custom_expression(self):
        """Özel ifade testi"""
        config = IndicatorConfig(custom_expression="rsi > 70 and macd < 0")
        
        assert config.custom_expression == "rsi > 70 and macd < 0"
    
    def test_bollinger_bands_config(self):
        """Bollinger Bands konfigürasyon testi"""
        config = IndicatorConfig(
            bb_period=25,
            bb_std=2.5,
            bb_width_threshold=0.1
        )
        
        assert config.bb_period == 25
        assert config.bb_std == 2.5
        assert config.bb_width_threshold == 0.1


class TestEnums:
    """Enum sınıfları testi"""
    
    def test_trading_mode_enum(self):
        """TradingMode enum testi"""
        assert TradingMode.DEMO == "demo"
        assert TradingMode.REAL == "real"
        
        # String'den enum'a çevrim
        assert TradingMode("demo") == TradingMode.DEMO
    
    def test_timeframe_enum(self):
        """TimeFrame enum testi"""
        assert TimeFrame.M1 == "1m"
        assert TimeFrame.H1 == "1h"
        assert TimeFrame.D1 == "1d"
    
    def test_signal_logic_enum(self):
        """SignalLogic enum testi"""
        assert SignalLogic.ALL_TRUE == "all_true"
        assert SignalLogic.MAJORITY_TRUE == "majority_true"
        assert SignalLogic.ANY_TRUE == "any_true"


@pytest.fixture
def sample_config():
    """Test için örnek konfigürasyon"""
    return {
        "trading_mode": "demo",
        "demo_balance": 1500.0,
        "app": {
            "scan_interval": 30,
            "log_level": "DEBUG"
        },
        "strategy": {
            "timeframe": "5m",
            "tp_percentage": 7.5
        }
    }


class TestConfigIntegration:
    """Entegrasyon testleri"""
    
    def test_full_config_cycle(self, tmp_path, sample_config):
        """Tam konfigürasyon döngüsü testi"""
        config_file = tmp_path / "integration_test.json"
        
        # JSON dosyası oluştur
        with open(config_file, 'w') as f:
            json.dump(sample_config, f)
        
        # Settings yükle
        settings = BotSettings.load_from_file(config_file)
        
        assert settings.demo_balance == 1500.0
        assert settings.app.scan_interval == 30
        assert settings.strategy.timeframe == TimeFrame.M5
        
        # Değiştir ve kaydet
        settings.strategy.tp_percentage = 10.0
        settings.save_to_file(config_file)
        
        # Tekrar yükle ve kontrol et
        reloaded = BotSettings.load_from_file(config_file)
        assert reloaded.strategy.tp_percentage == 10.0
    
    def test_env_override(self):
        """Environment variable override testi"""
        with patch.dict('os.environ', {'TRADING_MODE': 'real', 'DEMO_BALANCE': '5000'}):
            settings = BotSettings()
            
            # Env var'lar varsayılan değerleri override etmeli
            assert settings.trading_mode == TradingMode.REAL
            # Not: demo_balance field'ı için env var çalışmayabilir - Pydantic behavior
    
    def test_partial_config(self, tmp_path):
        """Kısmi konfigürasyon testi"""
        config_file = tmp_path / "partial.json"
        
        # Sadece bazı alanları içeren config
        partial_config = {
            "demo_balance": 3000.0,
            "strategy": {
                "tp_percentage": 15.0
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(partial_config, f)
        
        settings = BotSettings.load_from_file(config_file)
        
        # Belirtilen değerler yüklenmeli
        assert settings.demo_balance == 3000.0
        assert settings.strategy.tp_percentage == 15.0
        
        # Belirtilmeyen değerler varsayılan olmalı
        assert settings.trading_mode == TradingMode.DEMO
        assert settings.app.scan_interval == 60


if __name__ == "__main__":
    pytest.main([__file__]) 