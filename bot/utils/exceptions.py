"""
ShortBot için özel exception sınıfları
"""


class ShortBotException(Exception):
    """Ana bot exception sınıfı"""
    pass


class ConfigurationError(ShortBotException):
    """Konfigürasyon hatası"""
    pass


class APIError(ShortBotException):
    """API erişim hatası"""
    pass


class BinanceAPIError(APIError):
    """Binance API özel hatası"""
    def __init__(self, message: str, error_code: int = None):
        super().__init__(message)
        self.error_code = error_code


class InsufficientBalanceError(ShortBotException):
    """Yetersiz bakiye hatası"""
    pass


class PositionNotFoundError(ShortBotException):
    """Pozisyon bulunamadı hatası"""
    pass


class InvalidSymbolError(ShortBotException):
    """Geçersiz sembol hatası"""
    pass


class RiskManagementError(ShortBotException):
    """Risk yönetimi hatası"""
    pass


class DailyDrawdownExceededError(RiskManagementError):
    """Günlük drawdown sınırı aşıldı"""
    def __init__(self, current_drawdown: float, limit: float):
        super().__init__(f"Günlük drawdown %{current_drawdown:.1f} sınırı %{limit:.1f} aştı")
        self.current_drawdown = current_drawdown
        self.limit = limit


class TelegramError(ShortBotException):
    """Telegram bot hatası"""
    pass


class IndicatorCalculationError(ShortBotException):
    """İndikatör hesaplama hatası"""
    pass


class OrderExecutionError(ShortBotException):
    """Emir execution hatası"""
    pass


class WebSocketError(ShortBotException):
    """WebSocket bağlantı hatası"""
    pass


class DemoModeError(ShortBotException):
    """Demo mod hatası"""
    pass


class CredentialsError(ShortBotException):
    """API anahtarları hatası"""
    pass 