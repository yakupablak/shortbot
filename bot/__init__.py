"""
ShortBot - Kripto para short işlem botu
Parametrik, stop-loss'suz, sabit 1 USDT short pozisyon açan bot
"""

__version__ = "1.0.0"
__author__ = "ShortBot Team"

# Ana sınıfları dışarı export et
from .utils.config import BotSettings, TradingMode
from .utils.logger import get_logger
from .core.engine import TradeEngine, EngineState, TradingEvent
from .core.portfolio import Portfolio, Position, Order, Wallet
from .core.demo_exchange import DemoExchange
from .core.signals import StrategyEngine, TechnicalIndicators

# Public API
__all__ = [
    # Version
    "__version__",
    "__author__",
    
    # Configuration
    "BotSettings",
    "TradingMode",
    
    # Core Classes
    "TradeEngine", 
    "EngineState",
    "TradingEvent",
    "Portfolio",
    "Position", 
    "Order",
    "Wallet",
    "DemoExchange",
    "StrategyEngine",
    "TechnicalIndicators",
    
    # Utils
    "get_logger",
] 