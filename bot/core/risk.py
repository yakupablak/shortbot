"""
Risk Yönetimi Modülü
Günlük drawdown kontrolü, pozisyon büyüklüğü hesaplama, 
güvenli işlem sınırları
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from enum import Enum

from ..utils.config import RiskConfig
from ..utils.exceptions import (
    RiskManagementError,
    DailyDrawdownExceededError,
    InsufficientBalanceError
)
from ..utils.logger import get_logger
from .portfolio import Portfolio, Position

logger = get_logger("risk_manager")


class RiskLevel(str, Enum):
    """Risk seviyeleri"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Uyarı tipleri"""
    DAILY_DRAWDOWN_WARNING = "daily_drawdown_warning"
    DAILY_DRAWDOWN_CRITICAL = "daily_drawdown_critical"
    MAX_POSITIONS_REACHED = "max_positions_reached"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    POSITION_SIZE_VIOLATION = "position_size_violation"
    CONSECUTIVE_LOSSES = "consecutive_losses"


class RiskAlert:
    """Risk uyarısı"""
    
    def __init__(self, alert_type: AlertType, level: RiskLevel, message: str, data: Optional[Dict] = None):
        self.type = alert_type
        self.level = level
        self.message = message
        self.data = data or {}
        self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict:
        return {
            'type': self.type.value,
            'level': self.level.value,
            'message': self.message,
            'data': self.data,
            'timestamp': self.timestamp.isoformat()
        }


class RiskManager:
    """Risk yöneticisi"""
    
    def __init__(self, config: RiskConfig):
        self.config = config
        
        # Alert geçmişi
        self.alert_history: List[RiskAlert] = []
        self.last_daily_reset = datetime.now(timezone.utc).date()
        
        # Risk metrikleri
        self.consecutive_losses = 0
        self.max_consecutive_losses = 5  # Ardışık kayıp limiti
        
        # Portfolio referansı
        self.portfolio: Optional[Portfolio] = None
        
    def set_portfolio(self, portfolio: Portfolio) -> None:
        """Portfolio referansını ayarla"""
        self.portfolio = portfolio
    
    def check_daily_drawdown(self) -> Optional[RiskAlert]:
        """Günlük drawdown kontrolü"""
        if not self.portfolio:
            return None
        
        daily_pnl_pct = abs(self.portfolio.wallet.daily_return_pct)
        
        # Kritik seviye
        if daily_pnl_pct >= self.config.daily_shutdown_threshold:
            alert = RiskAlert(
                AlertType.DAILY_DRAWDOWN_CRITICAL,
                RiskLevel.CRITICAL,
                f"Günlük drawdown kritik seviyeye ulaştı: %{daily_pnl_pct:.1f}",
                {
                    'current_drawdown': daily_pnl_pct,
                    'threshold': self.config.daily_shutdown_threshold,
                    'balance': float(self.portfolio.wallet.balance),
                    'daily_pnl': float(self.portfolio.wallet.daily_pnl)
                }
            )
            self.alert_history.append(alert)
            logger.critical(alert.message)
            return alert
        
        # Uyarı seviyesi
        elif daily_pnl_pct >= self.config.daily_warning_threshold:
            alert = RiskAlert(
                AlertType.DAILY_DRAWDOWN_WARNING,
                RiskLevel.HIGH,
                f"Günlük drawdown uyarı seviyesinde: %{daily_pnl_pct:.1f}",
                {
                    'current_drawdown': daily_pnl_pct,
                    'threshold': self.config.daily_warning_threshold,
                    'balance': float(self.portfolio.wallet.balance),
                    'daily_pnl': float(self.portfolio.wallet.daily_pnl)
                }
            )
            self.alert_history.append(alert)
            logger.warning(alert.message)
            return alert
        
        return None
    
    def calculate_position_size(
        self, 
        symbol: str, 
        price: Decimal, 
        usd_amount: float,
        max_risk_pct: Optional[float] = None
    ) -> Tuple[Decimal, Dict]:
        """Güvenli pozisyon büyüklüğü hesapla"""
        if not self.portfolio:
            raise RiskManagementError("Portfolio referansı ayarlanmamış")
        
        available_balance = self.portfolio.wallet.available_balance
        max_risk_pct = max_risk_pct or self.config.max_portfolio_risk
        
        # Maksimum risk tutarı
        max_risk_amount = available_balance * Decimal(str(max_risk_pct / 100))
        
        # İstenen pozisyon büyüklüğü
        requested_size = Decimal(str(usd_amount)) / price
        requested_notional = requested_size * price
        
        # Risk kontrolleri
        risk_info = {
            'requested_usd': float(requested_notional),
            'max_risk_usd': float(max_risk_amount),
            'available_balance': float(available_balance),
            'risk_ratio': float(requested_notional / available_balance) if available_balance > 0 else 0,
            'adjusted': False
        }
        
        # Yetersiz bakiye kontrolü
        if requested_notional > available_balance:
            raise InsufficientBalanceError(
                f"Yetersiz bakiye: ${available_balance} mevcut, ${requested_notional} gerekli"
            )
        
        # Risk limiti kontrolü
        if requested_notional > max_risk_amount:
            # Pozisyon büyüklüğünü ayarla
            adjusted_size = max_risk_amount / price
            risk_info['adjusted'] = True
            risk_info['adjusted_size'] = float(adjusted_size)
            
            logger.warning(
                f"Pozisyon büyüklüğü risk limiti nedeniyle ayarlandı: "
                f"${requested_notional} -> ${max_risk_amount}"
            )
            
            return adjusted_size, risk_info
        
        return requested_size, risk_info
    
    def validate_new_position(
        self, 
        symbol: str, 
        size: Decimal, 
        price: Decimal,
        max_positions: int
    ) -> List[RiskAlert]:
        """Yeni pozisyon açma kontrolü"""
        alerts = []
        
        if not self.portfolio:
            return alerts
        
        # Maksimum pozisyon sayısı kontrolü
        current_positions = len(self.portfolio.get_open_positions())
        if current_positions >= max_positions:
            alert = RiskAlert(
                AlertType.MAX_POSITIONS_REACHED,
                RiskLevel.MEDIUM,
                f"Maksimum pozisyon sayısına ulaşıldı: {current_positions}/{max_positions}",
                {
                    'current_positions': current_positions,
                    'max_positions': max_positions
                }
            )
            alerts.append(alert)
        
        # Pozisyon büyüklüğü kontrolü
        notional = size * price
        available_balance = self.portfolio.wallet.available_balance
        position_ratio = float(notional / available_balance) if available_balance > 0 else 0
        
        if position_ratio > self.config.max_portfolio_risk / 100:
            alert = RiskAlert(
                AlertType.POSITION_SIZE_VIOLATION,
                RiskLevel.HIGH,
                f"Pozisyon büyüklüğü risk limitini aşıyor: %{position_ratio * 100:.1f}",
                {
                    'position_ratio': position_ratio,
                    'max_risk_ratio': self.config.max_portfolio_risk / 100,
                    'notional_value': float(notional)
                }
            )
            alerts.append(alert)
        
        # Ardışık kayıp kontrolü
        if self.consecutive_losses >= self.max_consecutive_losses:
            alert = RiskAlert(
                AlertType.CONSECUTIVE_LOSSES,
                RiskLevel.HIGH,
                f"Ardışık kayıp limiti aşıldı: {self.consecutive_losses}",
                {
                    'consecutive_losses': self.consecutive_losses,
                    'max_consecutive_losses': self.max_consecutive_losses
                }
            )
            alerts.append(alert)
        
        # Günlük drawdown kontrolü
        drawdown_alert = self.check_daily_drawdown()
        if drawdown_alert:
            alerts.append(drawdown_alert)
        
        # Alert history'e ekle
        for alert in alerts:
            self.alert_history.append(alert)
            
            if alert.level == RiskLevel.CRITICAL:
                logger.critical(alert.message)
            elif alert.level == RiskLevel.HIGH:
                logger.warning(alert.message)
            else:
                logger.info(alert.message)
        
        return alerts
    
    def on_position_closed(self, position: Position) -> None:
        """Pozisyon kapatıldığında çağırılır"""
        # Ardışık kayıp takibi
        if position.realized_pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0  # Kazançlı işlemde sıfırla
        
        logger.debug(
            f"Pozisyon kapatıldı [{position.symbol}]: "
            f"PnL: ${position.realized_pnl}, "
            f"Ardışık kayıp: {self.consecutive_losses}"
        )
    
    def should_stop_trading(self) -> Tuple[bool, Optional[str]]:
        """İşlem durdurulmalı mı kontrolü"""
        if not self.portfolio:
            return False, None
        
        # Günlük drawdown kritik seviye
        daily_pnl_pct = abs(self.portfolio.wallet.daily_return_pct)
        if daily_pnl_pct >= self.config.daily_shutdown_threshold:
            return True, f"Günlük drawdown kritik seviyede: %{daily_pnl_pct:.1f}"
        
        # Ardışık kayıp limiti
        if self.consecutive_losses >= self.max_consecutive_losses:
            return True, f"Ardışık kayıp limiti aşıldı: {self.consecutive_losses}"
        
        # Bakiye çok düştü
        if self.portfolio.wallet.available_balance < Decimal('10'):  # $10 minimum
            return True, "Yetersiz bakiye: $10'un altına düştü"
        
        return False, None
    
    def reset_daily_metrics(self) -> None:
        """Günlük metrikleri sıfırla"""
        current_date = datetime.now(timezone.utc).date()
        
        if current_date > self.last_daily_reset:
            logger.info("Günlük risk metrikleri sıfırlanıyor")
            
            if self.portfolio:
                self.portfolio.wallet.reset_daily()
            
            # Eski alert'leri temizle (24 saat öncesi)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            self.alert_history = [
                alert for alert in self.alert_history 
                if alert.timestamp > cutoff_time
            ]
            
            self.last_daily_reset = current_date
    
    def get_risk_summary(self) -> Dict:
        """Risk özetini al"""
        if not self.portfolio:
            return {'error': 'Portfolio referansı yok'}
        
        recent_alerts = [
            alert for alert in self.alert_history[-10:]  # Son 10 alert
        ]
        
        should_stop, stop_reason = self.should_stop_trading()
        
        return {
            'daily_pnl_pct': self.portfolio.wallet.daily_return_pct,
            'consecutive_losses': self.consecutive_losses,
            'available_balance': float(self.portfolio.wallet.available_balance),
            'open_positions': len(self.portfolio.get_open_positions()),
            'should_stop_trading': should_stop,
            'stop_reason': stop_reason,
            'recent_alerts': [alert.to_dict() for alert in recent_alerts],
            'risk_thresholds': {
                'daily_warning': self.config.daily_warning_threshold,
                'daily_shutdown': self.config.daily_shutdown_threshold,
                'max_portfolio_risk': self.config.max_portfolio_risk
            }
        }
    
    def get_recent_alerts(self, hours: int = 24) -> List[RiskAlert]:
        """Son N saatteki alert'leri al"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [
            alert for alert in self.alert_history
            if alert.timestamp > cutoff_time
        ]
    
    def clear_alert_history(self) -> None:
        """Alert geçmişini temizle"""
        self.alert_history.clear()
        logger.info("Risk alert geçmişi temizlendi") 