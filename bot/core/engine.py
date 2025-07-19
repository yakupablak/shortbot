"""
Ana İşlem Motoru (TradeEngine)
Asenkron state-machine ile otomatik işlem yönetimi
"""
import asyncio
from contextlib import AsyncExitStack
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal

from ..utils.config import BotSettings, TradingMode
from ..utils.exceptions import (
    ShortBotException, 
    DailyDrawdownExceededError,
    InsufficientBalanceError,
    RiskManagementError
)
from ..utils.logger import get_logger, log_trade
from .binance_rest import BinanceRestClient
from .demo_exchange import DemoExchange
from .signals import StrategyEngine
from .portfolio import Portfolio

logger = get_logger("trade_engine")


class EngineState(str, Enum):
    """Engine durumları"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"
    SAFE_SHUTDOWN = "safe_shutdown"


class TradingEvent(str, Enum):
    """İşlem olayları"""
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    EMERGENCY_STOP = "emergency_stop"
    DAILY_RESET = "daily_reset"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_LIQUIDATED = "position_liquidated"
    DRAWDOWN_WARNING = "drawdown_warning"
    DRAWDOWN_CRITICAL = "drawdown_critical"


class TradeEngine(AsyncExitStack):
    """Ana işlem motoru"""
    
    def __init__(self, settings: BotSettings):
        super().__init__()
        self.settings = settings
        self.state = EngineState.STOPPED
        
        # Exchange client
        self.exchange: Optional[Union[BinanceRestClient, DemoExchange]] = None
        
        # Strateji ve portföy
        self.strategy: Optional[StrategyEngine] = None
        self.portfolio: Optional[Portfolio] = None
        
        # Async kontrol
        self.running = False
        self.main_task: Optional[asyncio.Task] = None
        self.position_monitor_task: Optional[asyncio.Task] = None
        
        # Event callback'leri
        self.event_handlers: Dict[TradingEvent, List] = {}
        
        # Performance tracking
        self.start_time: Optional[datetime] = None
        self.last_scan_time: Optional[datetime] = None
        self.scan_count = 0
        self.signals_generated = 0
        self.positions_opened = 0
        
    async def __aenter__(self):
        """Async context manager giriş"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager çıkış"""
        await self.shutdown()
    
    def add_event_handler(self, event: TradingEvent, handler) -> None:
        """Event handler ekle"""
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)
    
    async def emit_event(self, event: TradingEvent, data: Optional[Dict[str, Any]] = None) -> None:
        """Event yayınla"""
        if event in self.event_handlers:
            for handler in self.event_handlers[event]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event, data or {})
                    else:
                        handler(event, data or {})
                except Exception as e:
                    logger.error(f"Event handler hatası [{event}]: {e}")
    
    async def initialize(self) -> None:
        """Engine'i başlat"""
        logger.info(f"TradeEngine başlatılıyor - Mod: {self.settings.trading_mode}")
        self.state = EngineState.STARTING
        
        try:
            # Exchange client oluştur
            if self.settings.trading_mode == TradingMode.DEMO:
                self.exchange = DemoExchange(self.settings)
                self.portfolio = self.exchange.portfolio
            else:
                self.exchange = BinanceRestClient(self.settings.binance)
                self.portfolio = Portfolio()
                
                # Real modda başlangıç bakiyesi yükle
                await self.exchange.connect()
                account_info = await self.exchange.get_account_info()
                balance = Decimal(account_info['totalWalletBalance'])
                self.portfolio.wallet.balance = balance
                self.portfolio.wallet.available_balance = balance
                self.portfolio.wallet.reset_daily()
            
            # Strateji oluştur
            self.strategy = StrategyEngine(
                self.settings.strategy.indicators,
                self.settings.strategy.signal_logic
            )
            
            # Exchange'e bağlan
            if hasattr(self.exchange, 'connect'):
                await self.exchange.connect()
            
            # Bağlantı testi
            if not await self.exchange.test_connection():
                raise ShortBotException("Exchange bağlantı testi başarısız")
            
            logger.info(f"TradeEngine başlatıldı - Bakiye: ${self.portfolio.wallet.balance}")
            
        except Exception as e:
            self.state = EngineState.ERROR
            logger.error(f"Engine başlatma hatası: {e}")
            raise
    
    async def start(self) -> None:
        """İşlem döngüsünü başlat"""
        if self.state != EngineState.STARTING:
            await self.initialize()
        
        self.running = True
        self.state = EngineState.RUNNING
        self.start_time = datetime.now(timezone.utc)
        
        # Ana döngü
        self.main_task = asyncio.create_task(self._main_loop())
        
        # Pozisyon izleme
        self.position_monitor_task = asyncio.create_task(self._position_monitor())
        
        await self.emit_event(TradingEvent.START, {
            'timestamp': self.start_time.isoformat(),
            'mode': self.settings.trading_mode,
            'balance': float(self.portfolio.wallet.balance)
        })
        
        logger.info("İşlem döngüsü başlatıldı")
    
    async def stop(self) -> None:
        """İşlem döngüsünü durdur"""
        logger.info("İşlem döngüsü durduruluyor...")
        self.state = EngineState.STOPPING
        self.running = False
        
        # Task'ları iptal et
        if self.main_task:
            self.main_task.cancel()
        if self.position_monitor_task:
            self.position_monitor_task.cancel()
        
        # Task'ların bitmesini bekle
        try:
            if self.main_task:
                await self.main_task
        except asyncio.CancelledError:
            pass
        
        try:
            if self.position_monitor_task:
                await self.position_monitor_task
        except asyncio.CancelledError:
            pass
        
        self.state = EngineState.STOPPED
        
        await self.emit_event(TradingEvent.STOP, {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'scan_count': self.scan_count,
            'positions_opened': self.positions_opened
        })
        
        logger.info("İşlem döngüsü durduruldu")
    
    async def emergency_stop(self) -> None:
        """Acil durdur - tüm pozisyonları kapat"""
        logger.warning("ACIL DURDURMA - Tüm pozisyonlar kapatılıyor")
        self.state = EngineState.SAFE_SHUTDOWN
        
        try:
            # Tüm açık pozisyonları kapat
            open_positions = self.portfolio.get_open_positions()
            
            for position in open_positions:
                try:
                    await self._close_position(position.symbol, "EMERGENCY_STOP")
                    logger.info(f"Pozisyon acil kapatıldı: {position.symbol}")
                except Exception as e:
                    logger.error(f"Pozisyon kapatma hatası [{position.symbol}]: {e}")
            
            await self.emit_event(TradingEvent.EMERGENCY_STOP, {
                'closed_positions': len(open_positions),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Acil durdurma hatası: {e}")
        
        finally:
            await self.stop()
    
    async def _main_loop(self) -> None:
        """Ana işlem döngüsü"""
        logger.info("Ana işlem döngüsü başladı")
        
        while self.running and self.state == EngineState.RUNNING:
            try:
                await self._process_scan_cycle()
                await asyncio.sleep(self.settings.app.scan_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ana döngü hatası: {e}")
                await asyncio.sleep(10)  # Hata durumunda bekle
        
        logger.info("Ana işlem döngüsü sona erdi")
    
    async def _position_monitor(self) -> None:
        """Pozisyon izleme döngüsü"""
        logger.info("Pozisyon izleme başladı")
        
        while self.running and self.state == EngineState.RUNNING:
            try:
                await self._monitor_positions()
                await asyncio.sleep(30)  # 30 saniyede bir kontrol
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Pozisyon izleme hatası: {e}")
                await asyncio.sleep(5)
        
        logger.info("Pozisyon izleme sona erdi")
    
    async def _process_scan_cycle(self) -> None:
        """Bir tarama döngüsünü işle"""
        self.scan_count += 1
        self.last_scan_time = datetime.now(timezone.utc)
        
        try:
            # Günlük risk kontrolü
            await self._check_daily_drawdown()
            
            # En çok yükselen coinleri al
            top_gainers = await self.exchange.get_top_gainers(self.settings.app.top_gainers_limit)
            
            logger.debug(f"Tarama #{self.scan_count}: {len(top_gainers)} coin kontrol ediliyor")
            
            # Her coin için sinyal kontrolü
            for ticker in top_gainers:
                if not self.running:
                    break
                
                symbol = ticker['symbol']
                
                # Maksimum pozisyon kontrolü
                if not self.portfolio.can_open_position(self.settings.strategy.max_concurrent_positions):
                    logger.debug("Maksimum pozisyon sayısına ulaşıldı")
                    break
                
                # Zaten pozisyon var mı?
                if self.portfolio.get_position(symbol):
                    continue
                
                try:
                    # Sinyal kontrolü
                    should_short, signal_data = await self._check_short_signal(symbol)
                    self.signals_generated += 1
                    
                    if should_short:
                        await self._open_short_position(symbol, signal_data)
                        
                except Exception as e:
                    logger.error(f"Sinyal kontrolü hatası [{symbol}]: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Tarama döngüsü hatası: {e}")
    
    async def _check_short_signal(self, symbol: str) -> tuple[bool, Dict[str, Any]]:
        """Short sinyal kontrolü"""
        try:
            # Kline verilerini al
            klines = await self.exchange.get_klines(
                symbol, 
                self.settings.strategy.timeframe.value,
                limit=150  # Yeterli veri için
            )
            
            if len(klines) < 50:
                return False, {'error': 'Yetersiz veri'}
            
            # Strateji sinyalini kontrol et
            should_short, signal_info = self.strategy.should_open_short(klines)
            
            return should_short, signal_info
            
        except Exception as e:
            logger.error(f"Sinyal kontrolü hatası [{symbol}]: {e}")
            return False, {'error': str(e)}
    
    async def _open_short_position(self, symbol: str, signal_data: Dict[str, Any]) -> None:
        """Short pozisyon aç"""
        try:
            # Pozisyon büyüklüğü hesapla
            current_price = await self._get_current_price(symbol)
            position_size = self.settings.strategy.position_size_usd
            quantity = Decimal(str(position_size)) / current_price
            
            # Minimum quantity kontrolü
            quantity = max(quantity, Decimal('0.001'))  # Binance min
            
            # Emri gönder
            order_result = await self.exchange.create_order(
                symbol=symbol,
                side="SELL",  # Short
                type="MARKET",
                quantity=quantity
            )
            
            self.positions_opened += 1
            
            # Log ve event
            log_trade(f"SHORT AÇILDI: {symbol} | Qty: {quantity} | Price: ${current_price} | Reason: {signal_data.get('reason', 'N/A')}")
            
            await self.emit_event(TradingEvent.POSITION_OPENED, {
                'symbol': symbol,
                'side': 'SHORT',
                'quantity': float(quantity),
                'price': float(current_price),
                'signal_data': signal_data,
                'order_id': order_result.get('orderId'),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            logger.info(f"Short pozisyon açıldı: {symbol} @ ${current_price}")
            
        except InsufficientBalanceError:
            logger.warning(f"Yetersiz bakiye - pozisyon açılamadı: {symbol}")
        except Exception as e:
            logger.error(f"Pozisyon açma hatası [{symbol}]: {e}")
    
    async def _close_position(self, symbol: str, reason: str = "MANUAL") -> bool:
        """Pozisyon kapat"""
        try:
            position = self.portfolio.get_position(symbol)
            if not position:
                return False
            
            # Market emir ile kapat
            order_result = await self.exchange.create_order(
                symbol=symbol,
                side="BUY",  # Short pozisyonu kapatmak için BUY
                type="MARKET",
                quantity=position.size,
                reduce_only=True
            )
            
            # Portföyü güncelle
            current_price = await self._get_current_price(symbol)
            self.portfolio.close_position(symbol, current_price)
            
            # Log ve event
            log_trade(f"POZISYON KAPANDI: {symbol} | PnL: ${position.realized_pnl} | Reason: {reason}")
            
            await self.emit_event(TradingEvent.POSITION_CLOSED, {
                'symbol': symbol,
                'pnl': float(position.realized_pnl),
                'reason': reason,
                'order_id': order_result.get('orderId'),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Pozisyon kapatma hatası [{symbol}]: {e}")
            return False
    
    async def _monitor_positions(self) -> None:
        """Pozisyonları izle (TP, Liquidation)"""
        try:
            # Demo modda özel handling
            if isinstance(self.exchange, DemoExchange):
                self.exchange.check_liquidations_and_tps()
                return
            
            # Real modda pozisyon fiyatlarını güncelle
            open_positions = self.portfolio.get_open_positions()
            if not open_positions:
                return
            
            # Güncel fiyatları al
            symbols = [p.symbol for p in open_positions]
            prices = {}
            
            for symbol in symbols:
                try:
                    current_price = await self._get_current_price(symbol)
                    prices[symbol] = current_price
                except:
                    continue
            
            # Pozisyonları güncelle
            self.portfolio.update_positions_mark_prices(prices)
            
            # TP kontrolü
            tp_triggered = self.portfolio.check_take_profits()
            for symbol in tp_triggered:
                await self._close_position(symbol, "TAKE_PROFIT")
            
            # Liquidation kontrolü
            liq_triggered = self.portfolio.check_liquidations()
            for symbol in liq_triggered:
                logger.warning(f"Liquidation tetiklendi: {symbol}")
                self.portfolio.liquidate_position(symbol)
                
                await self.emit_event(TradingEvent.POSITION_LIQUIDATED, {
                    'symbol': symbol,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
            
        except Exception as e:
            logger.error(f"Pozisyon monitoring hatası: {e}")
    
    async def _get_current_price(self, symbol: str) -> Decimal:
        """Güncel fiyat al"""
        ticker = await self.exchange.get_ticker_price(symbol)
        return Decimal(str(ticker['price']))
    
    async def _check_daily_drawdown(self) -> None:
        """Günlük drawdown kontrolü"""
        daily_pnl_pct = self.portfolio.wallet.daily_return_pct
        
        # Uyarı seviyesi
        if abs(daily_pnl_pct) >= self.settings.risk.daily_warning_threshold:
            logger.warning(f"Günlük drawdown uyarısı: %{daily_pnl_pct:.1f}")
            
            await self.emit_event(TradingEvent.DRAWDOWN_WARNING, {
                'daily_pnl_pct': daily_pnl_pct,
                'threshold': self.settings.risk.daily_warning_threshold,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        
        # Kritik seviye - acil durdur
        if abs(daily_pnl_pct) >= self.settings.risk.daily_shutdown_threshold:
            logger.critical(f"Günlük drawdown kritik seviyesi: %{daily_pnl_pct:.1f}")
            
            await self.emit_event(TradingEvent.DRAWDOWN_CRITICAL, {
                'daily_pnl_pct': daily_pnl_pct,
                'threshold': self.settings.risk.daily_shutdown_threshold,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            # Acil durdurma
            await self.emergency_stop()
            
            raise DailyDrawdownExceededError(abs(daily_pnl_pct), self.settings.risk.daily_shutdown_threshold)
    
    async def shutdown(self) -> None:
        """Engine'i kapat"""
        if self.state not in [EngineState.STOPPED, EngineState.ERROR]:
            await self.stop()
        
        # Exchange bağlantısını kapat
        if self.exchange and hasattr(self.exchange, 'disconnect'):
            await self.exchange.disconnect()
        
        logger.info("TradeEngine kapatıldı")
    
    # Public API
    def get_status(self) -> Dict[str, Any]:
        """Engine durumunu al"""
        uptime = None
        if self.start_time:
            uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        return {
            'state': self.state.value,
            'running': self.running,
            'trading_mode': self.settings.trading_mode.value,
            'uptime': uptime,
            'scan_count': self.scan_count,
            'signals_generated': self.signals_generated,
            'positions_opened': self.positions_opened,
            'last_scan': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'portfolio': {
                'balance': float(self.portfolio.wallet.balance) if self.portfolio else 0,
                'daily_pnl': float(self.portfolio.wallet.daily_pnl) if self.portfolio else 0,
                'open_positions': len(self.portfolio.get_open_positions()) if self.portfolio else 0
            }
        } 