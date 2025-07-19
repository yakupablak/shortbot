"""
Loglama sistemi - Loguru kullanarak seviye bazlı
dönen dosyalar ve GUI entegrasyonu
"""
import sys
from pathlib import Path
from typing import Optional

from loguru import logger as loguru_logger

from .config import get_settings


class LogHandler:
    """Log işleyicisi - dosya ve GUI için"""
    
    def __init__(self):
        self.gui_handler = None
        self.is_initialized = False
    
    def initialize(self) -> None:
        """Log sistemini başlat"""
        if self.is_initialized:
            return
        
        settings = get_settings()
        
        # Önceki handler'ları temizle
        loguru_logger.remove()
        
        # Konsol çıktısı
        loguru_logger.add(
            sys.stdout,
            level=settings.app.log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                   "<level>{message}</level>",
            colorize=True
        )
        
        # Log dizinini oluştur
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Dosya çıktısı - genel loglar
        loguru_logger.add(
            "logs/shortbot.log",
            level=settings.app.log_level,
            rotation=settings.app.log_rotation,
            retention=settings.app.log_retention,
            compression="zip",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            encoding="utf-8"
        )
        
        # İşlem logları
        loguru_logger.add(
            "logs/trades.log",
            level="INFO",
            rotation="1 day",
            retention="90 days",
            compression="zip",
            filter=lambda record: "trade" in record.get("extra", {}),
            format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
            encoding="utf-8"
        )
        
        # Hata logları
        loguru_logger.add(
            "logs/errors.log",
            level="ERROR",
            rotation="1 week",
            retention="30 days",
            compression="zip",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message} | {exception}",
            encoding="utf-8"
        )
        
        self.is_initialized = True
        loguru_logger.info("Log sistemi başlatıldı")
    
    def set_gui_handler(self, handler_func) -> None:
        """GUI log handler'ı ayarla"""
        self.gui_handler = handler_func
        
        # GUI için özel handler ekle
        if handler_func:
            loguru_logger.add(
                handler_func,
                level="DEBUG",
                format="{time:HH:mm:ss} | {level: <8} | {message}",
                colorize=False
            )
    
    def log_trade(self, message: str, **kwargs) -> None:
        """İşlem logu - özel formatlama ile"""
        loguru_logger.bind(trade=True).info(message, **kwargs)
    
    def set_level(self, level: str) -> None:
        """Log seviyesini değiştir"""
        # Bu işlem için logger'ı yeniden başlatmak gerekir
        settings = get_settings()
        settings.app.log_level = level
        self.is_initialized = False
        self.initialize()


# Global log handler
log_handler = LogHandler()


def get_logger(name: str = None):
    """Logger instance al"""
    if not log_handler.is_initialized:
        log_handler.initialize()
    
    if name:
        return loguru_logger.bind(name=name)
    return loguru_logger


def log_trade(message: str, **kwargs):
    """İşlem logu kısayolu"""
    log_handler.log_trade(message, **kwargs)


# Ana logger
logger = get_logger("shortbot") 