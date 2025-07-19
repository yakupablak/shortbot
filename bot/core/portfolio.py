"""
Portföy yönetimi modelleri
Position, Order, Wallet sınıfları ve portföy izleme
"""
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, validator

from ..utils.exceptions import PositionNotFoundError, InsufficientBalanceError


class OrderSide(str, Enum):
    """Emir yönü"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Emir tipi"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    """Emir durumu"""
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PositionSide(str, Enum):
    """Pozisyon yönü"""
    LONG = "LONG"
    SHORT = "SHORT"


class PositionStatus(str, Enum):
    """Pozisyon durumu"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"


class Order(BaseModel):
    """Emir modeli"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.NEW
    
    # İşlem bilgileri
    filled_quantity: Decimal = Decimal('0')
    avg_price: Optional[Decimal] = None
    commission: Decimal = Decimal('0')
    commission_asset: str = "USDT"
    
    # Zaman damgaları
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    filled_at: Optional[datetime] = None
    
    # Binance emir ID'si (demo modda None)
    binance_order_id: Optional[str] = None
    
    @property
    def is_filled(self) -> bool:
        """Emir tamamen dolduruldu mu?"""
        return self.status == OrderStatus.FILLED
    
    @property
    def remaining_quantity(self) -> Decimal:
        """Kalan miktar"""
        return self.quantity - self.filled_quantity
    
    def fill(self, quantity: Decimal, price: Decimal, commission: Decimal = Decimal('0')) -> None:
        """Emri (kısmen) doldur"""
        self.filled_quantity += quantity
        
        if self.avg_price is None:
            self.avg_price = price
        else:
            # Ağırlıklı ortalama hesapla
            total_value = (self.avg_price * (self.filled_quantity - quantity)) + (price * quantity)
            self.avg_price = total_value / self.filled_quantity
        
        self.commission += commission
        self.updated_at = datetime.now(timezone.utc)
        
        if self.filled_quantity >= self.quantity:
            self.status = OrderStatus.FILLED
            self.filled_at = datetime.now(timezone.utc)
        elif self.filled_quantity > Decimal('0'):
            self.status = OrderStatus.PARTIALLY_FILLED


class Position(BaseModel):
    """Pozisyon modeli"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    side: PositionSide
    size: Decimal  # Pozitif değer
    entry_price: Decimal
    mark_price: Decimal
    liquidation_price: Optional[Decimal] = None
    
    status: PositionStatus = PositionStatus.OPEN
    
    # Finansal bilgiler
    margin: Decimal = Decimal('0')
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    total_commission: Decimal = Decimal('0')
    
    # Take Profit ayarları
    tp_price: Optional[Decimal] = None
    tp_percentage: Optional[float] = None
    
    # Zaman damgaları
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    
    # Emir geçmişi
    entry_orders: List[str] = Field(default_factory=list)  # Order ID'leri
    exit_orders: List[str] = Field(default_factory=list)
    
    @property
    def is_short(self) -> bool:
        """Short pozisyon mu?"""
        return self.side == PositionSide.SHORT
    
    @property
    def is_long(self) -> bool:
        """Long pozisyon mu?"""
        return self.side == PositionSide.LONG
    
    @property
    def notional_value(self) -> Decimal:
        """Nominal değer (USDT)"""
        return self.size * self.mark_price
    
    def update_mark_price(self, new_price: Decimal) -> None:
        """Mark price güncelle ve unrealized PnL hesapla"""
        self.mark_price = new_price
        self.unrealized_pnl = self.calculate_unrealized_pnl()
        self.updated_at = datetime.now(timezone.utc)
    
    def calculate_unrealized_pnl(self) -> Decimal:
        """Unrealized PnL hesapla"""
        if self.is_short:
            # Short pozisyonda fiyat düşerse kar
            pnl = (self.entry_price - self.mark_price) * self.size
        else:
            # Long pozisyonda fiyat yüksekse kar
            pnl = (self.mark_price - self.entry_price) * self.size
        
        return pnl
    
    def calculate_liquidation_price(self, maintenance_margin_rate: float = 0.004) -> Decimal:
        """Likidation fiyatını hesapla"""
        if self.is_short:
            # Short için liq price = entry_price * (1 + maintenance_margin_rate)
            liq_price = self.entry_price * (Decimal('1') + Decimal(str(maintenance_margin_rate)))
        else:
            # Long için liq price = entry_price * (1 - maintenance_margin_rate)  
            liq_price = self.entry_price * (Decimal('1') - Decimal(str(maintenance_margin_rate)))
        
        return liq_price
    
    def set_take_profit(self, tp_percentage: float) -> None:
        """Take profit seviyesi ayarla"""
        self.tp_percentage = tp_percentage
        
        if self.is_short:
            # Short pozisyonda TP fiyat düşüşü
            self.tp_price = self.entry_price * (Decimal('1') - Decimal(str(tp_percentage / 100)))
        else:
            # Long pozisyonda TP fiyat artışı
            self.tp_price = self.entry_price * (Decimal('1') + Decimal(str(tp_percentage / 100)))
    
    def check_take_profit(self) -> bool:
        """Take profit seviyesine ulaşıldı mı?"""
        if self.tp_price is None:
            return False
        
        if self.is_short:
            return self.mark_price <= self.tp_price
        else:
            return self.mark_price >= self.tp_price
    
    def check_liquidation(self) -> bool:
        """Likidation seviyesine ulaşıldı mı?"""
        if self.liquidation_price is None:
            return False
        
        if self.is_short:
            return self.mark_price >= self.liquidation_price
        else:
            return self.mark_price <= self.liquidation_price
    
    def close(self, close_price: Decimal, commission: Decimal = Decimal('0')) -> None:
        """Pozisyonu kapat"""
        self.status = PositionStatus.CLOSED
        self.closed_at = datetime.now(timezone.utc)
        
        # Realized PnL hesapla
        if self.is_short:
            self.realized_pnl = (self.entry_price - close_price) * self.size
        else:
            self.realized_pnl = (close_price - self.entry_price) * self.size
        
        self.realized_pnl -= commission
        self.total_commission += commission
        self.unrealized_pnl = Decimal('0')
    
    def liquidate(self) -> None:
        """Pozisyonu likidasyona uğrat"""
        self.status = PositionStatus.LIQUIDATED
        self.closed_at = datetime.now(timezone.utc)
        
        # Likidasyonda margin tamamen kaybedilir
        self.realized_pnl = -self.margin
        self.unrealized_pnl = Decimal('0')


class Wallet(BaseModel):
    """Cüzdan modeli"""
    balance: Decimal = Decimal('0')  # Toplam bakiye
    available_balance: Decimal = Decimal('0')  # Kullanılabilir bakiye
    margin_balance: Decimal = Decimal('0')  # Marjda kullanılan tutar
    unrealized_pnl: Decimal = Decimal('0')  # Toplam unrealized PnL
    
    # Günlük takip
    daily_start_balance: Decimal = Decimal('0')  # Gün başı bakiye
    daily_pnl: Decimal = Decimal('0')  # Günlük PnL
    daily_trades: int = 0  # Günlük işlem sayısı
    
    # İstatistikler
    total_realized_pnl: Decimal = Decimal('0')
    total_commission: Decimal = Decimal('0')
    win_count: int = 0
    loss_count: int = 0
    
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def equity(self) -> Decimal:
        """Toplam equity (balance + unrealized PnL)"""
        return self.balance + self.unrealized_pnl
    
    @property
    def daily_return_pct(self) -> float:
        """Günlük getiri yüzdesi"""
        if self.daily_start_balance == 0:
            return 0.0
        return float((self.daily_pnl / self.daily_start_balance) * 100)
    
    @property
    def win_rate(self) -> float:
        """Kazanma oranı"""
        total_trades = self.win_count + self.loss_count
        if total_trades == 0:
            return 0.0
        return self.win_count / total_trades
    
    def add_balance(self, amount: Decimal) -> None:
        """Bakiye ekle"""
        self.balance += amount
        self.available_balance += amount
        self.last_updated = datetime.now(timezone.utc)
    
    def use_margin(self, amount: Decimal) -> bool:
        """Marjin kullan"""
        if self.available_balance >= amount:
            self.available_balance -= amount
            self.margin_balance += amount
            self.last_updated = datetime.now(timezone.utc)
            return True
        return False
    
    def free_margin(self, amount: Decimal) -> None:
        """Marjini serbest bırak"""
        self.margin_balance = max(Decimal('0'), self.margin_balance - amount)
        self.available_balance += amount
        self.last_updated = datetime.now(timezone.utc)
    
    def update_unrealized_pnl(self, total_unrealized: Decimal) -> None:
        """Toplam unrealized PnL güncelle"""
        self.unrealized_pnl = total_unrealized
        self.last_updated = datetime.now(timezone.utc)
    
    def realize_pnl(self, pnl: Decimal, commission: Decimal = Decimal('0')) -> None:
        """PnL realize et"""
        net_pnl = pnl - commission
        
        self.balance += net_pnl
        self.available_balance += net_pnl
        self.total_realized_pnl += net_pnl
        self.total_commission += commission
        self.daily_pnl += net_pnl
        self.daily_trades += 1
        
        if net_pnl > 0:
            self.win_count += 1
        else:
            self.loss_count += 1
        
        self.last_updated = datetime.now(timezone.utc)
    
    def reset_daily(self) -> None:
        """Günlük sayaçları sıfırla"""
        self.daily_start_balance = self.balance
        self.daily_pnl = Decimal('0')
        self.daily_trades = 0
        self.last_updated = datetime.now(timezone.utc)


class Portfolio(BaseModel):
    """Portföy yöneticisi"""
    positions: Dict[str, Position] = Field(default_factory=dict)  # symbol -> position
    orders: Dict[str, Order] = Field(default_factory=dict)  # order_id -> order
    wallet: Wallet = Field(default_factory=Wallet)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_order(self, order: Order) -> None:
        """Yeni emir ekle"""
        self.orders[order.id] = order
        self.updated_at = datetime.now(timezone.utc)
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Emir getir"""
        return self.orders.get(order_id)
    
    def add_position(self, position: Position) -> None:
        """Pozisyon ekle/güncelle"""
        self.positions[position.symbol] = position
        self.updated_at = datetime.now(timezone.utc)
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Pozisyon getir"""
        return self.positions.get(symbol)
    
    def close_position(self, symbol: str, close_price: Decimal, commission: Decimal = Decimal('0')) -> bool:
        """Pozisyon kapat"""
        position = self.get_position(symbol)
        if not position or position.status != PositionStatus.OPEN:
            return False
        
        # Pozisyonu kapat
        position.close(close_price, commission)
        
        # Marjini serbest bırak
        self.wallet.free_margin(position.margin)
        
        # PnL realize et
        self.wallet.realize_pnl(position.realized_pnl, commission)
        
        self.updated_at = datetime.now(timezone.utc)
        return True
    
    def liquidate_position(self, symbol: str) -> bool:
        """Pozisyonu likide et"""
        position = self.get_position(symbol)
        if not position or position.status != PositionStatus.OPEN:
            return False
        
        # Likidation
        position.liquidate()
        
        # Margin kaybı
        self.wallet.realize_pnl(position.realized_pnl)
        
        self.updated_at = datetime.now(timezone.utc)
        return True
    
    def get_open_positions(self) -> List[Position]:
        """Açık pozisyonları getir"""
        return [pos for pos in self.positions.values() if pos.status == PositionStatus.OPEN]
    
    def get_total_unrealized_pnl(self) -> Decimal:
        """Toplam unrealized PnL"""
        total = Decimal('0')
        for position in self.get_open_positions():
            total += position.unrealized_pnl
        return total
    
    def update_positions_mark_prices(self, prices: Dict[str, Decimal]) -> None:
        """Pozisyon mark fiyatlarını güncelle"""
        for symbol, price in prices.items():
            position = self.get_position(symbol)
            if position and position.status == PositionStatus.OPEN:
                position.update_mark_price(price)
        
        # Wallet unrealized PnL güncelle
        self.wallet.update_unrealized_pnl(self.get_total_unrealized_pnl())
        self.updated_at = datetime.now(timezone.utc)
    
    def check_take_profits(self) -> List[str]:
        """Take profit tetiklenen pozisyonları kontrol et"""
        triggered = []
        for position in self.get_open_positions():
            if position.check_take_profit():
                triggered.append(position.symbol)
        return triggered
    
    def check_liquidations(self) -> List[str]:
        """Likidation tetiklenen pozisyonları kontrol et"""
        triggered = []
        for position in self.get_open_positions():
            if position.check_liquidation():
                triggered.append(position.symbol)
        return triggered
    
    def get_position_count(self) -> int:
        """Açık pozisyon sayısı"""
        return len(self.get_open_positions())
    
    def can_open_position(self, max_positions: int) -> bool:
        """Yeni pozisyon açılabilir mi?"""
        return self.get_position_count() < max_positions 