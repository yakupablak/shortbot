"""
Bildirim Sistemi (Notifier)
Observer pattern ile event-driven bildirimler
"""
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass

from ..utils.logger import get_logger

logger = get_logger("notifier")


class NotificationLevel(str, Enum):
    """Bildirim seviyeleri"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationType(str, Enum):
    """Bildirim tipleri"""
    SYSTEM = "system"
    TRADING = "trading"
    POSITION = "position"
    RISK = "risk"
    MARKET = "market"
    USER = "user"


@dataclass
class Notification:
    """Bildirim modeli"""
    id: str
    type: NotificationType
    level: NotificationLevel
    title: str
    message: str
    data: Dict[str, Any]
    timestamp: datetime
    channel: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'type': self.type.value,
            'level': self.level.value,
            'title': self.title,
            'message': self.message,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'channel': self.channel
        }


class NotificationChannel(ABC):
    """Bildirim kanalı arayüzü"""
    
    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.level_filter = NotificationLevel.INFO
    
    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Bildirim gönder"""
        pass
    
    def should_send(self, notification: Notification) -> bool:
        """Bu bildirim gönderilmeli mi?"""
        if not self.enabled:
            return False
        
        # Level kontrolü
        level_priority = {
            NotificationLevel.DEBUG: 0,
            NotificationLevel.INFO: 1,
            NotificationLevel.WARNING: 2,
            NotificationLevel.ERROR: 3,
            NotificationLevel.CRITICAL: 4
        }
        
        return level_priority[notification.level] >= level_priority[self.level_filter]


class LogChannel(NotificationChannel):
    """Log dosyasına bildirim gönderme"""
    
    def __init__(self):
        super().__init__("log")
    
    async def send(self, notification: Notification) -> bool:
        """Log'a bildirim yaz"""
        try:
            log_message = f"[{notification.type.value.upper()}] {notification.title}: {notification.message}"
            
            if notification.level == NotificationLevel.DEBUG:
                logger.debug(log_message)
            elif notification.level == NotificationLevel.INFO:
                logger.info(log_message)
            elif notification.level == NotificationLevel.WARNING:
                logger.warning(log_message)
            elif notification.level == NotificationLevel.ERROR:
                logger.error(log_message)
            elif notification.level == NotificationLevel.CRITICAL:
                logger.critical(log_message)
            
            return True
            
        except Exception as e:
            logger.error(f"Log channel hatası: {e}")
            return False


class TelegramChannel(NotificationChannel):
    """Telegram bildirim kanalı"""
    
    def __init__(self, telegram_service):
        super().__init__("telegram")
        self.telegram_service = telegram_service
        self.level_filter = NotificationLevel.INFO  # Telegram için min level
    
    async def send(self, notification: Notification) -> bool:
        """Telegram'a bildirim gönder"""
        if not self.telegram_service or not self.telegram_service.config.enabled:
            return False
        
        try:
            # Level'e göre emoji
            level_emojis = {
                NotificationLevel.DEBUG: "🔍",
                NotificationLevel.INFO: "ℹ️",
                NotificationLevel.WARNING: "⚠️",
                NotificationLevel.ERROR: "❌",
                NotificationLevel.CRITICAL: "🚨"
            }
            
            emoji = level_emojis.get(notification.level, "📢")
            
            message = (
                f"{emoji} **{notification.title}**\n"
                f"{notification.message}\n"
                f"🕐 {notification.timestamp.strftime('%H:%M:%S')}"
            )
            
            return await self.telegram_service.send_message(message)
            
        except Exception as e:
            logger.error(f"Telegram channel hatası: {e}")
            return False


class ConsoleChannel(NotificationChannel):
    """Konsol bildirim kanalı"""
    
    def __init__(self):
        super().__init__("console")
    
    async def send(self, notification: Notification) -> bool:
        """Konsola bildirim yazdır"""
        try:
            timestamp = notification.timestamp.strftime('%H:%M:%S')
            level_colors = {
                NotificationLevel.DEBUG: '\033[36m',    # Cyan
                NotificationLevel.INFO: '\033[32m',     # Green
                NotificationLevel.WARNING: '\033[33m',  # Yellow
                NotificationLevel.ERROR: '\033[31m',    # Red
                NotificationLevel.CRITICAL: '\033[35m'  # Magenta
            }
            
            color = level_colors.get(notification.level, '\033[0m')
            reset = '\033[0m'
            
            console_message = (
                f"{color}[{timestamp}] [{notification.level.value.upper()}] "
                f"{notification.title}: {notification.message}{reset}"
            )
            
            print(console_message)
            return True
            
        except Exception as e:
            logger.error(f"Console channel hatası: {e}")
            return False


class EmailChannel(NotificationChannel):
    """Email bildirim kanalı (placeholder)"""
    
    def __init__(self, smtp_config: Optional[Dict] = None):
        super().__init__("email")
        self.smtp_config = smtp_config
        self.level_filter = NotificationLevel.WARNING  # Sadece önemli bildirimleri email'le gönder
    
    async def send(self, notification: Notification) -> bool:
        """Email gönder (henüz implement edilmedi)"""
        # TODO: SMTP email implementation
        logger.debug(f"Email channel - {notification.title}: {notification.message}")
        return True


class NotificationManager:
    """Bildirim yöneticisi - Observer pattern"""
    
    def __init__(self):
        self.channels: Dict[str, NotificationChannel] = {}
        self.observers: List[Callable] = []
        self.notification_history: List[Notification] = []
        self.max_history = 1000
        
        # Bildirim sayaçları
        self.stats = {
            'total_sent': 0,
            'by_level': {level.value: 0 for level in NotificationLevel},
            'by_type': {ntype.value: 0 for ntype in NotificationType},
            'by_channel': {}
        }
        
        # Varsayılan kanalları ekle
        self.add_channel(LogChannel())
        self.add_channel(ConsoleChannel())
    
    def add_channel(self, channel: NotificationChannel) -> None:
        """Bildirim kanalı ekle"""
        self.channels[channel.name] = channel
        self.stats['by_channel'][channel.name] = 0
        logger.debug(f"Bildirim kanalı eklendi: {channel.name}")
    
    def remove_channel(self, channel_name: str) -> bool:
        """Bildirim kanalını kaldır"""
        if channel_name in self.channels:
            del self.channels[channel_name]
            logger.debug(f"Bildirim kanalı kaldırıldı: {channel_name}")
            return True
        return False
    
    def enable_channel(self, channel_name: str, enabled: bool = True) -> bool:
        """Kanalı etkinleştir/devre dışı bırak"""
        if channel_name in self.channels:
            self.channels[channel_name].enabled = enabled
            status = "etkinleştirildi" if enabled else "devre dışı bırakıldı"
            logger.debug(f"Kanal {channel_name} {status}")
            return True
        return False
    
    def set_channel_level(self, channel_name: str, level: NotificationLevel) -> bool:
        """Kanal minimum level'ını ayarla"""
        if channel_name in self.channels:
            self.channels[channel_name].level_filter = level
            logger.debug(f"Kanal {channel_name} minimum level: {level.value}")
            return True
        return False
    
    def add_observer(self, callback: Callable) -> None:
        """Observer ekle"""
        self.observers.append(callback)
    
    def remove_observer(self, callback: Callable) -> bool:
        """Observer kaldır"""
        try:
            self.observers.remove(callback)
            return True
        except ValueError:
            return False
    
    async def notify(
        self,
        ntype: NotificationType,
        level: NotificationLevel,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        channels: Optional[List[str]] = None
    ) -> str:
        """Bildirim gönder"""
        
        # Bildirim objesi oluştur
        notification = Notification(
            id=f"notif_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
            type=ntype,
            level=level,
            title=title,
            message=message,
            data=data or {},
            timestamp=datetime.now(timezone.utc)
        )
        
        # Geçmişe ekle
        self.notification_history.append(notification)
        if len(self.notification_history) > self.max_history:
            self.notification_history.pop(0)
        
        # İstatistikleri güncelle
        self.stats['total_sent'] += 1
        self.stats['by_level'][level.value] += 1
        self.stats['by_type'][ntype.value] += 1
        
        # Observer'ları bilgilendir
        for observer in self.observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(notification)
                else:
                    observer(notification)
            except Exception as e:
                logger.error(f"Observer callback hatası: {e}")
        
        # Kanallar belirtilmemişse tümüne gönder
        target_channels = channels or list(self.channels.keys())
        
        # Her kanala gönder
        tasks = []
        for channel_name in target_channels:
            if channel_name in self.channels:
                channel = self.channels[channel_name]
                
                if channel.should_send(notification):
                    tasks.append(self._send_to_channel(channel, notification))
        
        # Paralel gönderim
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Başarılı gönderimler için istatistik güncelle
            for i, result in enumerate(results):
                if result is True:
                    channel_name = target_channels[i]
                    if channel_name in self.stats['by_channel']:
                        self.stats['by_channel'][channel_name] += 1
        
        return notification.id
    
    async def _send_to_channel(self, channel: NotificationChannel, notification: Notification) -> bool:
        """Belirli kanala bildirim gönder"""
        try:
            return await channel.send(notification)
        except Exception as e:
            logger.error(f"Kanal {channel.name} gönderim hatası: {e}")
            return False
    
    # Kısayol metodlar
    async def debug(self, title: str, message: str, **kwargs) -> str:
        return await self.notify(NotificationType.SYSTEM, NotificationLevel.DEBUG, title, message, **kwargs)
    
    async def info(self, title: str, message: str, **kwargs) -> str:
        return await self.notify(NotificationType.SYSTEM, NotificationLevel.INFO, title, message, **kwargs)
    
    async def warning(self, title: str, message: str, **kwargs) -> str:
        return await self.notify(NotificationType.SYSTEM, NotificationLevel.WARNING, title, message, **kwargs)
    
    async def error(self, title: str, message: str, **kwargs) -> str:
        return await self.notify(NotificationType.SYSTEM, NotificationLevel.ERROR, title, message, **kwargs)
    
    async def critical(self, title: str, message: str, **kwargs) -> str:
        return await self.notify(NotificationType.SYSTEM, NotificationLevel.CRITICAL, title, message, **kwargs)
    
    # Trading specific notifications
    async def trading_info(self, title: str, message: str, **kwargs) -> str:
        return await self.notify(NotificationType.TRADING, NotificationLevel.INFO, title, message, **kwargs)
    
    async def position_opened(self, symbol: str, side: str, size: float, price: float, **kwargs) -> str:
        return await self.notify(
            NotificationType.POSITION,
            NotificationLevel.INFO,
            "Position Açıldı",
            f"{symbol} {side} {size} @ ${price:.4f}",
            data={'symbol': symbol, 'side': side, 'size': size, 'price': price},
            **kwargs
        )
    
    async def position_closed(self, symbol: str, pnl: float, reason: str = "", **kwargs) -> str:
        level = NotificationLevel.INFO if pnl >= 0 else NotificationLevel.WARNING
        title = "Position Kapatıldı"
        message = f"{symbol} PnL: ${pnl:.2f}"
        if reason:
            message += f" ({reason})"
        
        return await self.notify(
            NotificationType.POSITION,
            level,
            title,
            message,
            data={'symbol': symbol, 'pnl': pnl, 'reason': reason},
            **kwargs
        )
    
    async def risk_alert(self, alert_type: str, message: str, level: NotificationLevel = NotificationLevel.WARNING, **kwargs) -> str:
        return await self.notify(
            NotificationType.RISK,
            level,
            f"Risk Uyarısı: {alert_type}",
            message,
            **kwargs
        )
    
    # Utility methods
    def get_recent_notifications(self, count: int = 50) -> List[Notification]:
        """Son bildirimleri al"""
        return self.notification_history[-count:]
    
    def get_notifications_by_level(self, level: NotificationLevel, count: int = 50) -> List[Notification]:
        """Belirli level'daki bildirimleri al"""
        filtered = [n for n in self.notification_history if n.level == level]
        return filtered[-count:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Bildirim istatistikleri"""
        return {
            'total_notifications': self.stats['total_sent'],
            'by_level': self.stats['by_level'].copy(),
            'by_type': self.stats['by_type'].copy(),
            'by_channel': self.stats['by_channel'].copy(),
            'active_channels': len([c for c in self.channels.values() if c.enabled]),
            'total_channels': len(self.channels),
            'history_size': len(self.notification_history)
        }
    
    def clear_history(self) -> None:
        """Bildirim geçmişini temizle"""
        self.notification_history.clear()
        logger.debug("Bildirim geçmişi temizlendi")
    
    def reset_stats(self) -> None:
        """İstatistikleri sıfırla"""
        self.stats = {
            'total_sent': 0,
            'by_level': {level.value: 0 for level in NotificationLevel},
            'by_type': {ntype.value: 0 for ntype in NotificationType},
            'by_channel': {name: 0 for name in self.channels.keys()}
        }
        logger.debug("Bildirim istatistikleri sıfırlandı")


# Global notifier instance
global_notifier = NotificationManager()


# Kısayol fonksiyonlar
async def notify(ntype: NotificationType, level: NotificationLevel, title: str, message: str, **kwargs) -> str:
    return await global_notifier.notify(ntype, level, title, message, **kwargs)

async def info(title: str, message: str, **kwargs) -> str:
    return await global_notifier.info(title, message, **kwargs)

async def warning(title: str, message: str, **kwargs) -> str:
    return await global_notifier.warning(title, message, **kwargs)

async def error(title: str, message: str, **kwargs) -> str:
    return await global_notifier.error(title, message, **kwargs)

async def critical(title: str, message: str, **kwargs) -> str:
    return await global_notifier.critical(title, message, **kwargs) 