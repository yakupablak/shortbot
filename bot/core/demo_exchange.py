"""
Demo Exchange - Binance simülasyonu
Gerçek para kullanmadan işlem testi yapılmasını sağlar
"""
import asyncio
import random
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from ..utils.config import BotSettings
from ..utils.exceptions import DemoModeError, InsufficientBalanceError, InvalidSymbolError
from ..utils.logger import get_logger
from .portfolio import Portfolio, Position, Order, OrderSide, OrderType, OrderStatus, PositionSide, PositionStatus

logger = get_logger("demo_exchange")


class DemoTicker:
    """Demo ticker verisi"""
    
    def __init__(self, symbol: str, base_price: float):
        self.symbol = symbol
        self.base_price = Decimal(str(base_price))
        self.current_price = self.base_price
        self.last_update = datetime.now(timezone.utc)
        
        # Volatilite parametreleri
        self.volatility = random.uniform(0.02, 0.05)  # %2-5 volatilite
        self.trend = random.uniform(-0.001, 0.001)    # Günlük trend
        
        # 24h istatistikleri
        self.price_24h_ago = self.base_price
        self.high_24h = self.base_price
        self.low_24h = self.base_price
        self.volume_24h = Decimal(str(random.uniform(10000, 1000000)))
        
    def update_price(self) -> Decimal:
        """Fiyat güncelle - realistic market movement"""
        now = datetime.now(timezone.utc)
        dt = (now - self.last_update).total_seconds() / 60  # dakika
        
        # Random walk + trend
        change = random.gauss(self.trend * dt, self.volatility * (dt ** 0.5))
        self.current_price *= Decimal(str(1 + change))
        
        # Min/max limitler (crash koruması)
        min_price = self.base_price * Decimal('0.5')
        max_price = self.base_price * Decimal('2.0')
        self.current_price = max(min_price, min(max_price, self.current_price))
        
        # 24h high/low güncelle
        self.high_24h = max(self.high_24h, self.current_price)
        self.low_24h = min(self.low_24h, self.current_price)
        
        self.last_update = now
        return self.current_price
    
    @property
    def price_change_24h(self) -> float:
        """24h fiyat değişim yüzdesi"""
        if self.price_24h_ago == 0:
            return 0.0
        return float(((self.current_price - self.price_24h_ago) / self.price_24h_ago) * 100)
    
    def to_ticker_dict(self) -> Dict[str, Any]:
        """Binance ticker formatına çevir"""
        return {
            'symbol': self.symbol,
            'lastPrice': str(self.current_price),
            'priceChangePercent': str(self.price_change_24h),
            'highPrice': str(self.high_24h),
            'lowPrice': str(self.low_24h),
            'volume': str(self.volume_24h),
            'count': random.randint(1000, 50000)  # Trade count
        }


class DemoOrderBook:
    """Demo orderbook simülasyonu"""
    
    def __init__(self, symbol: str, base_price: Decimal):
        self.symbol = symbol
        self.base_price = base_price
        self.spread_pct = Decimal('0.001')  # %0.1 spread
        
    def get_best_bid(self) -> Decimal:
        """En iyi bid fiyatı"""
        return self.base_price * (Decimal('1') - self.spread_pct)
    
    def get_best_ask(self) -> Decimal:
        """En iyi ask fiyatı"""
        return self.base_price * (Decimal('1') + self.spread_pct)
    
    def get_market_price(self, side: OrderSide) -> Decimal:
        """Market fiyatı (slipaj olmadan)"""
        if side == OrderSide.BUY:
            return self.get_best_ask()
        else:
            return self.get_best_bid()


class DemoExchange:
    """Demo borsa simülasyonu"""
    
    def __init__(self, settings: BotSettings):
        self.settings = settings
        self.portfolio = Portfolio()
        
        # Demo bakiyesi ayarla
        self.portfolio.wallet.balance = Decimal(str(settings.demo_balance))
        self.portfolio.wallet.available_balance = Decimal(str(settings.demo_balance))
        self.portfolio.wallet.reset_daily()
        
        # Market data
        self.tickers: Dict[str, DemoTicker] = {}
        self.orderbooks: Dict[str, DemoOrderBook] = {}
        
        # Commission rate (Binance Futures)
        self.maker_commission = Decimal('0.0002')  # 0.02%
        self.taker_commission = Decimal('0.0004')  # 0.04%
        
        # Son güncelleme zamanı
        self.last_market_update = datetime.now(timezone.utc)
        
        logger.info(f"Demo exchange başlatıldı - Bakiye: ${settings.demo_balance}")
    
    async def connect(self) -> None:
        """Demo exchange'e bağlan"""
        logger.info("Demo exchange bağlantısı simülasyonu")
        await asyncio.sleep(0.1)  # Async simülasyonu
    
    async def disconnect(self) -> None:
        """Demo exchange bağlantısını kapat"""
        logger.info("Demo exchange bağlantısı kapatıldı")
    
    def _ensure_ticker(self, symbol: str) -> DemoTicker:
        """Ticker'ı oluştur veya getir"""
        if symbol not in self.tickers:
            # Gerçekçi base fiyatlar
            base_prices = {
                'BTCUSDT': 45000.0,
                'ETHUSDT': 2500.0,
                'BNBUSDT': 300.0,
                'ADAUSDT': 0.5,
                'SOLUSDT': 100.0,
                'DOGEUSDT': 0.08,
                'XRPUSDT': 0.6,
                'DOTUSDT': 7.0,
                'AVAXUSDT': 35.0,
                'LINKUSDT': 15.0
            }
            
            base_price = base_prices.get(symbol, random.uniform(1.0, 100.0))
            self.tickers[symbol] = DemoTicker(symbol, base_price)
            self.orderbooks[symbol] = DemoOrderBook(symbol, Decimal(str(base_price)))
        
        return self.tickers[symbol]
    
    def _update_market_data(self) -> None:
        """Market verilerini güncelle"""
        now = datetime.now(timezone.utc)
        if (now - self.last_market_update).total_seconds() < 1:
            return  # Saniyede bir güncelle
        
        for ticker in self.tickers.values():
            new_price = ticker.update_price()
            self.orderbooks[ticker.symbol].base_price = new_price
        
        self.last_market_update = now
    
    # Public API Methods (Binance uyumlu)
    async def get_server_time(self) -> Dict[str, Any]:
        """Server zamanını al"""
        return {
            'serverTime': int(time.time() * 1000)
        }
    
    async def get_exchange_info(self) -> Dict[str, Any]:
        """Exchange bilgilerini al"""
        return {
            'symbols': [
                {
                    'symbol': 'BTCUSDT',
                    'status': 'TRADING',
                    'baseAsset': 'BTC',
                    'quoteAsset': 'USDT',
                    'contractType': 'PERPETUAL'
                }
            ]
        }
    
    async def get_24hr_ticker(self, symbol: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """24h ticker bilgisi"""
        self._update_market_data()
        
        if symbol:
            ticker = self._ensure_ticker(symbol)
            return ticker.to_ticker_dict()
        
        # Tüm tickerlar
        result = []
        for sym in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 
                   'DOGEUSDT', 'XRPUSDT', 'DOTUSDT', 'AVAXUSDT', 'LINKUSDT']:
            ticker = self._ensure_ticker(sym)
            result.append(ticker.to_ticker_dict())
        
        return result
    
    async def get_ticker_price(self, symbol: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Güncel fiyat bilgisi"""
        self._update_market_data()
        
        if symbol:
            ticker = self._ensure_ticker(symbol)
            return {
                'symbol': symbol,
                'price': str(ticker.current_price)
            }
        
        result = []
        for sym in self.tickers.keys():
            result.append({
                'symbol': sym,
                'price': str(self.tickers[sym].current_price)
            })
        
        return result
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List[List[Any]]:
        """Kline/mum verileri (basit simülasyon)"""
        ticker = self._ensure_ticker(symbol)
        
        # Basit OHLCV verisi oluştur
        klines = []
        current_time = int(time.time() * 1000)
        
        for i in range(limit):
            # Geriye doğru zaman
            timestamp = current_time - (i * 60 * 1000)  # 1 dakika aralıklar
            
            # OHLCV simülasyonu
            base = float(ticker.current_price)
            volatility = ticker.volatility
            
            open_price = base * (1 + random.gauss(0, volatility))
            high_price = open_price * (1 + abs(random.gauss(0, volatility/2)))
            low_price = open_price * (1 - abs(random.gauss(0, volatility/2)))
            close_price = open_price * (1 + random.gauss(0, volatility))
            volume = random.uniform(100, 1000)
            
            klines.append([
                timestamp,
                str(open_price),
                str(high_price),
                str(low_price),  
                str(close_price),
                str(volume),
                timestamp + 59999,  # Close time
                str(volume * open_price),  # Quote volume
                random.randint(50, 500),  # Trade count
                str(volume * 0.6),  # Taker buy volume
                str(volume * 0.6 * open_price),  # Taker buy quote volume
                "0"  # Ignore
            ])
        
        return list(reversed(klines))  # Eskiden yeniye
    
    # Trading API Methods
    async def get_account_info(self) -> Dict[str, Any]:
        """Hesap bilgileri"""
        return {
            'totalWalletBalance': str(self.portfolio.wallet.balance),
            'totalUnrealizedProfit': str(self.portfolio.wallet.unrealized_pnl),
            'totalMarginBalance': str(self.portfolio.wallet.margin_balance),
            'availableBalance': str(self.portfolio.wallet.available_balance)
        }
    
    async def get_balance(self) -> List[Dict[str, Any]]:
        """Bakiye bilgileri"""
        return [
            {
                'asset': 'USDT',
                'balance': str(self.portfolio.wallet.balance),
                'crossWalletBalance': str(self.portfolio.wallet.balance),
                'availableBalance': str(self.portfolio.wallet.available_balance)
            }
        ]
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Pozisyon bilgileri"""
        positions = []
        
        for position in self.portfolio.get_open_positions():
            positions.append({
                'symbol': position.symbol,
                'positionAmt': str(position.size if position.side == PositionSide.LONG else -position.size),
                'entryPrice': str(position.entry_price),
                'markPrice': str(position.mark_price),
                'unRealizedProfit': str(position.unrealized_pnl),
                'liquidationPrice': str(position.liquidation_price or 0),
                'positionSide': position.side.value
            })
        
        return positions
    
    async def create_order(
        self,
        symbol: str,
        side: str,
        type: str,
        quantity: Union[str, Decimal],
        price: Optional[Union[str, Decimal]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Emir oluştur (simülasyon)"""
        
        # Ticker'ı otomatik oluştur
        ticker = self._ensure_ticker(symbol)
        orderbook = self.orderbooks[symbol]
        
        # Order parametreleri
        qty = Decimal(str(quantity))
        order_side = OrderSide(side)
        order_type = OrderType(type)
        
        # Market price hesapla
        if order_type == OrderType.MARKET:
            execution_price = orderbook.get_market_price(order_side)
        else:
            execution_price = Decimal(str(price)) if price else ticker.current_price
        
        # Nominal değer
        notional = qty * execution_price
        
        # Commission hesapla
        commission = notional * self.taker_commission
        
        # Marjin kontrolü (short pozisyon için)
        required_margin = notional * Decimal('0.05')  # %5 marjin
        
        if self.portfolio.wallet.available_balance < required_margin + commission:
            raise InsufficientBalanceError("Yetersiz bakiye")
        
        # Order oluştur
        order = Order(
            symbol=symbol,
            side=order_side,
            type=order_type,
            quantity=qty,
            price=execution_price
        )
        
        # Emri hemen doldur (market simülasyonu)
        order.fill(qty, execution_price, commission)
        order.binance_order_id = str(random.randint(100000, 999999))
        
        # Portföye ekle
        self.portfolio.add_order(order)
        
        # Pozisyon oluştur veya güncelle
        position = self.portfolio.get_position(symbol)
        
        if position is None:
            # Yeni pozisyon
            position_side = PositionSide.SHORT if order_side == OrderSide.SELL else PositionSide.LONG
            
            position = Position(
                symbol=symbol,
                side=position_side,
                size=qty,
                entry_price=execution_price,
                mark_price=ticker.current_price,
                margin=required_margin,
                tp_percentage=self.settings.strategy.tp_percentage
            )
            
            position.liquidation_price = position.calculate_liquidation_price()
            position.set_take_profit(self.settings.strategy.tp_percentage)
            position.entry_orders.append(order.id)
            
            # Marjin kullan
            if not self.portfolio.wallet.use_margin(required_margin + commission):
                raise InsufficientBalanceError("Marjin ayıramadı")
            
            self.portfolio.add_position(position)
            
            logger.info(f"Demo pozisyon açıldı: {symbol} {position_side.value} {qty} @ ${execution_price}")
        
        return {
            'orderId': order.binance_order_id,
            'symbol': symbol,
            'status': 'FILLED',
            'executedQty': str(qty),
            'avgPrice': str(execution_price),
            'type': type,
            'side': side
        }
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Emri iptal et"""
        return {
            'orderId': order_id,
            'symbol': symbol,
            'status': 'CANCELED'
        }
    
    # Helper methods
    async def get_top_gainers(self, limit: int = 20) -> List[Dict[str, Any]]:
        """En çok yükselen coinler"""
        tickers = await self.get_24hr_ticker()
        
        # Sadece USDT çiftleri
        usdt_tickers = [t for t in tickers if t['symbol'].endswith('USDT')]
        
        # Price change'e göre sırala
        sorted_tickers = sorted(
            usdt_tickers,
            key=lambda x: float(x['priceChangePercent']),
            reverse=True
        )
        
        return sorted_tickers[:limit]
    
    async def test_connection(self) -> bool:
        """Bağlantı testi"""
        try:
            await self.get_server_time()
            return True
        except:
            return False
    
    def update_positions_mark_prices(self) -> None:
        """Pozisyon mark fiyatlarını güncelle"""
        self._update_market_data()
        
        prices = {}
        for position in self.portfolio.get_open_positions():
            if position.symbol in self.tickers:
                prices[position.symbol] = self.tickers[position.symbol].current_price
        
        self.portfolio.update_positions_mark_prices(prices)
    
    def check_liquidations_and_tps(self) -> None:
        """Likidation ve TP kontrolü"""
        self.update_positions_mark_prices()
        
        # TP kontrolü
        tp_triggered = self.portfolio.check_take_profits()
        for symbol in tp_triggered:
            position = self.portfolio.get_position(symbol)
            if position:
                logger.info(f"Demo TP tetiklendi: {symbol} @ ${position.mark_price}")
                self.portfolio.close_position(symbol, position.mark_price)
        
        # Likidation kontrolü
        liq_triggered = self.portfolio.check_liquidations()
        for symbol in liq_triggered:
            logger.warning(f"Demo likidation: {symbol}")
            self.portfolio.liquidate_position(symbol) 