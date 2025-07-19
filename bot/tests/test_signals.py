"""
Test: Signals modülü 
Technical indicators temel testleri
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from bot.core.signals import TechnicalIndicators, StrategyEngine
from bot.utils.config import BotSettings, IndicatorConfig, SignalLogic


class TestTechnicalIndicators:
    """TechnicalIndicators test sınıfı"""
    
    def test_rsi_calculation(self):
        """RSI hesaplama testi"""
        # Test verileri
        closes = [45000.0, 45100.0, 44950.0, 45200.0, 45050.0, 45300.0, 45100.0, 44800.0, 45400.0, 45250.0,
                  45500.0, 45200.0, 44900.0, 45600.0, 45350.0, 45700.0, 45400.0, 45100.0, 45800.0, 45600.0]
        
        rsi_values = TechnicalIndicators.rsi(closes, 14)
        
        assert isinstance(rsi_values, list)
        assert len(rsi_values) == len(closes)
        
        # RSI değerleri 0-100 arasında olmalı (NaN hariç)
        for rsi in rsi_values[-5:]:  # Son 5 değer
            if not np.isnan(rsi):
                assert 0 <= rsi <= 100
    
    def test_ema_calculation(self):
        """EMA hesaplama testi"""
        closes = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 109.0]
        
        ema_values = TechnicalIndicators.ema(closes, 5)
        
        assert len(ema_values) == len(closes)
        
        # EMA değerleri pozitif olmalı
        for ema in ema_values:
            assert ema > 0
    
    def test_sma_calculation(self):
        """SMA hesaplama testi"""
        closes = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 109.0]
        
        sma_values = TechnicalIndicators.sma(closes, 5)
        
        assert len(sma_values) == len(closes)
        
        # Son SMA değeri doğru mu
        last_sma = sum(closes[-5:]) / 5
        assert abs(sma_values[-1] - last_sma) < 0.01
    
    def test_macd_calculation(self):
        """MACD hesaplama testi"""
        closes = [float(x) for x in range(100, 130)]  # 30 veri noktası
        
        macd_line, signal_line, histogram = TechnicalIndicators.macd(closes)
        
        assert len(macd_line) == len(closes)
        assert len(signal_line) == len(closes)
        assert len(histogram) == len(closes)


class TestStrategyEngine:
    """StrategyEngine test sınıfı"""
    
    @pytest.fixture
    def sample_klines(self):
        """Test için örnek kline verisi"""
        klines = []
        for i in range(60):  # 60 mum verisi
            timestamp = 1640995200000 + (i * 60000)  # 1dk aralık
            price = 45000 + (i * 10)  # Yükselen trend
            klines.append([
                timestamp,  # timestamp
                price,      # open
                price + 50, # high
                price - 50, # low
                price + 25, # close
                1000,       # volume
                0, 0, 0, 0, 0, 0  # diğer alanlar
            ])
        return klines
    
    def test_strategy_engine_creation(self):
        """StrategyEngine yaratma testi"""
        config = IndicatorConfig()
        signal_logic = SignalLogic.MAJORITY_TRUE
        
        engine = StrategyEngine(config, signal_logic)
        
        assert engine.config == config
        assert engine.signal_logic == signal_logic
    
    def test_calculate_indicators(self, sample_klines):
        """İndikatör hesaplama testi"""
        config = IndicatorConfig()
        signal_logic = SignalLogic.MAJORITY_TRUE
        engine = StrategyEngine(config, signal_logic)
        
        indicators = engine.calculate_indicators(sample_klines)
        
        # Temel indikatörler hesaplandı mı
        assert 'rsi' in indicators
        assert 'ema_fast' in indicators
        assert 'ema_slow' in indicators
        assert 'macd' in indicators
        
        # Veri uzunluğu doğru mu
        assert len(indicators['rsi']) == len(sample_klines)
        assert len(indicators['ema_fast']) == len(sample_klines)


class TestSimpleIntegration:
    """Basit entegrasyon testleri"""
    
    def test_bot_settings_creation(self):
        """BotSettings oluşturma testi"""
        settings = BotSettings()
        
        assert settings.trading_mode.value == "demo"
        assert settings.demo_balance == 1000.0
        assert settings.strategy.indicators.rsi_period == 14
    
    def test_indicator_config_validation(self):
        """IndicatorConfig validasyon testi"""
        config = IndicatorConfig(rsi_period=20, ema_fast=10)
        
        assert config.rsi_period == 20
        assert config.ema_fast == 10
        
        # Geçersiz değer testi
        with pytest.raises(ValueError):
            IndicatorConfig(rsi_period=3)  # Minimum 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 