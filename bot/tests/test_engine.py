"""
Test: Engine modülü
TradeEngine temel testleri
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from bot.core.engine import TradeEngine, EngineState, TradingEvent
from bot.utils.config import BotSettings


class TestTradeEngine:
    """TradeEngine test sınıfı"""
    
    @pytest.fixture
    def settings(self):
        """Test settings"""
        return BotSettings(demo_balance=1000.0)
    
    def test_initialization(self, settings):
        """TradeEngine başlatma testi"""
        engine = TradeEngine(settings)
        
        assert engine.settings == settings
        assert engine.state == EngineState.STOPPED
        assert engine.running == False
        assert engine.portfolio is None  # Henüz initialize edilmedi
        assert engine.strategy is None   # Henüz initialize edilmedi
    
    @pytest.mark.asyncio
    async def test_initialization_async(self, settings):
        """Async başlatma testi"""
        engine = TradeEngine(settings)
        
        await engine.initialize()
        
        # Initialize sonrası kontroller
        assert engine.exchange is not None
        assert engine.portfolio is not None
        assert engine.strategy is not None
    
    def test_status_reporting(self, settings):
        """Status raporlama testi"""
        engine = TradeEngine(settings)
        
        status = engine.get_status()
        
        required_fields = [
            'state', 'trading_mode', 'uptime', 
            'scan_count', 'signals_generated', 'positions_opened'
        ]
        
        for field in required_fields:
            assert field in status
        
        assert status['state'] == EngineState.STOPPED
        assert status['trading_mode'] == engine.settings.trading_mode
    
    def test_event_handlers(self, settings):
        """Event handler sistemi testi"""
        engine = TradeEngine(settings)
        
        handler_called = False
        test_data = None
        
        async def test_handler(event: TradingEvent, data: dict):
            nonlocal handler_called, test_data
            handler_called = True
            test_data = data
        
        engine.add_event_handler(TradingEvent.POSITION_OPENED, test_handler)
        
        # Event handlers doğru eklendi mi
        assert TradingEvent.POSITION_OPENED in engine.event_handlers
        assert len(engine.event_handlers[TradingEvent.POSITION_OPENED]) == 1


class TestEngineIntegration:
    """Basit entegrasyon testleri"""
    
    @pytest.mark.asyncio
    async def test_demo_initialization(self):
        """Demo mod başlatma testi"""
        settings = BotSettings(demo_balance=500.0)
        engine = TradeEngine(settings)
        
        await engine.initialize()
        
        # Demo exchange kontrolü
        assert engine.exchange is not None
        assert engine.portfolio.wallet.balance == 500.0
        
        await engine.shutdown()
    
    @pytest.mark.asyncio
    async def test_engine_lifecycle(self):
        """Engine yaşam döngüsü testi"""
        settings = BotSettings()
        
        async with TradeEngine(settings) as engine:
            assert engine.exchange is not None
            assert engine.state == EngineState.STOPPED
            
            # Kısa süre çalıştır
            task = asyncio.create_task(engine.start())
            await asyncio.sleep(0.1)
            
            assert engine.running == True
            
            await engine.stop()
            assert engine.running == False
            
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 