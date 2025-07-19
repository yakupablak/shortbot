"""
PySide6 Ana Uygulama Sınıfı
QApplication wrapper ve GUI yönetimi
"""
import sys
from typing import Optional
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QObject
from PySide6.QtGui import QIcon, QPixmap, QPainter, QFont

from ..utils.config import BotSettings
from ..utils.logger import get_logger
from .main_window import MainWindow

logger = get_logger("gui_app")


class BotWorkerThread(QThread):
    """Bot worker thread - GUI'yi bloklamadan çalışır"""
    
    # Signals
    status_updated = Signal(dict)
    position_opened = Signal(dict)
    position_closed = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, settings: BotSettings):
        super().__init__()
        self.settings = settings
        self.bot_engine = None
        self.running = False
    
    async def initialize_bot(self):
        """Bot engine'i başlat"""
        try:
            from ..core.engine import TradeEngine
            
            self.bot_engine = TradeEngine(self.settings)
            await self.bot_engine.initialize()
            
            # Event handler'lar
            from ..core.engine import TradingEvent
            self.bot_engine.add_event_handler(TradingEvent.POSITION_OPENED, self._on_position_opened)
            self.bot_engine.add_event_handler(TradingEvent.POSITION_CLOSED, self._on_position_closed)
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            logger.error(f"Bot initialization error: {e}")
            return False
    
    def run(self):
        """Thread ana döngüsü"""
        import asyncio
        
        async def bot_main():
            if await self.initialize_bot():
                await self.bot_engine.start()
                self.running = True
                
                while self.running:
                    # Status güncelle
                    if self.bot_engine:
                        status = self.bot_engine.get_status()
                        self.status_updated.emit(status)
                    
                    await asyncio.sleep(1)
        
        try:
            asyncio.run(bot_main())
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    async def _on_position_opened(self, event, data):
        """Pozisyon açıldığında"""
        self.position_opened.emit(data)
    
    async def _on_position_closed(self, event, data):
        """Pozisyon kapandığında"""
        self.position_closed.emit(data)
    
    def _add_demo_signal_data(self):
        """Demo signal monitoring verisi ekle"""
        try:
            if hasattr(self, 'main_window') and self.main_window:
                from .widgets.signal_monitoring_widget import create_sample_coin_data
                
                # Örnek coin analizleri ekle
                sample_coins = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
                for i, coin in enumerate(sample_coins):
                    if i == 0:  # İlk coin açılmış pozisyon
                        data = create_sample_coin_data(coin, 'opened')
                        data['reason'] = 'RSI aşırı satım (28.5) + MACD pozitif kesişim + Yüksek volume'
                        data['confidence'] = 87
                    elif i == 1:  # İkinci coin reddedilmiş
                        data = create_sample_coin_data(coin, 'rejected')
                        data['reason'] = 'Volume yetersiz (< 1M), trend belirsiz, RSI nötr bölgede'
                        data['confidence'] = 42
                    elif i == 2:  # Üçüncü coin de açılmış
                        data = create_sample_coin_data(coin, 'opened')  
                        data['reason'] = 'Bollinger Bands alt bandında + Güçlü satış baskısı'
                        data['confidence'] = 73
                    else:  # Diğerleri beklemede
                        data = create_sample_coin_data(coin, 'pending')
                        data['reason'] = 'Analiz ediliyor...'
                    
                    # Sinyal monitoring'e ekle
                    if hasattr(self.main_window, 'signal_monitoring_widget'):
                        self.main_window.update_signal_monitoring(coin, data)
                        
        except ImportError:
            pass
    
    def stop_bot(self):
        """Bot'u durdur"""
        self.running = False
        if self.bot_engine:
            import asyncio
            asyncio.create_task(self.bot_engine.stop())


class ShortBotApp(QApplication):
    """Ana GUI uygulaması"""
    
    def __init__(self, settings: BotSettings):
        super().__init__(sys.argv)
        
        self.settings = settings
        self.main_window: Optional[MainWindow] = None
        self.bot_worker: Optional[BotWorkerThread] = None
        self.tray_icon: Optional[QSystemTrayIcon] = None
        
        # Uygulama ayarları
        self.setApplicationName("ShortBot")
        self.setApplicationVersion("1.0.0")
        self.setOrganizationName("ShortBot Team")
        
        # Stil ve tema
        self._setup_style()
        
        # System tray
        self._setup_system_tray()
        
        # Ana pencere
        self.main_window = MainWindow(settings, self)
        
    def _setup_style(self):
        """Uygulama stilini ayarla"""
        if self.settings.app.theme == "dark":
            # Dark theme
            dark_stylesheet = """
            QApplication {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                border: none;
            }
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: #333333;
            }
            QTabBar::tab {
                background-color: #444444;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #555555;
            }
            QTabBar::tab:hover {
                background-color: #666666;
            }
            QPushButton {
                background-color: #0084ff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0066cc;
            }
            QPushButton:pressed {
                background-color: #004499;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #aaaaaa;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #404040;
                border: 1px solid #555555;
                padding: 6px;
                border-radius: 3px;
                color: #ffffff;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 2px solid #0084ff;
            }
            QTableWidget {
                background-color: #333333;
                alternate-background-color: #2a2a2a;
                gridline-color: #555555;
                selection-background-color: #0084ff;
            }
            QTableWidget QHeaderView::section {
                background-color: #444444;
                padding: 6px;
                border: 1px solid #555555;
                font-weight: bold;
            }
            QTextEdit, QPlainTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #555555;
                color: #ffffff;
                font-family: 'Consolas', monospace;
            }
            QScrollBar:vertical {
                background-color: #404040;
                width: 12px;
            }
            QScrollBar::handle:vertical {
                background-color: #666666;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #888888;
            }
            """
            self.setStyleSheet(dark_stylesheet)
        
        # Font ayarları
        font = QFont("Segoe UI", 9)
        self.setFont(font)
    
    def _setup_system_tray(self):
        """System tray icon kurulumu"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray mevcut değil")
            return
        
        # Icon oluştur
        icon = self._create_app_icon()
        
        self.tray_icon = QSystemTrayIcon(icon, self)
        
        # Context menu
        tray_menu = QMenu()
        
        show_action = tray_menu.addAction("Göster")
        show_action.triggered.connect(self.show_main_window)
        
        tray_menu.addSeparator()
        
        start_action = tray_menu.addAction("Bot Başlat")
        start_action.triggered.connect(self.start_bot)
        
        stop_action = tray_menu.addAction("Bot Durdur")
        stop_action.triggered.connect(self.stop_bot)
        
        tray_menu.addSeparator()
        
        quit_action = tray_menu.addAction("Çıkış")
        quit_action.triggered.connect(self.quit_application)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # Çift tıklama
        self.tray_icon.activated.connect(self._on_tray_activated)
        
        self.tray_icon.show()
        logger.info("System tray icon kuruldu")
    
    def _create_app_icon(self) -> QIcon:
        """Uygulama ikonunu oluştur"""
        # Basit bir icon çiz
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Kırmızı daire (short sembolü)
        painter.setBrush(Qt.red)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        
        # Beyaz aşağı ok
        from PySide6.QtCore import QPoint
        painter.setBrush(Qt.white)
        painter.drawPolygon([
            QPoint(16, 8),   # Top
            QPoint(10, 18),  # Bottom left
            QPoint(22, 18)   # Bottom right
        ])
        
        painter.end()
        
        return QIcon(pixmap)
    
    def _on_tray_activated(self, reason):
        """System tray tıklaması"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_main_window()
    
    def show_main_window(self):
        """Ana pencereyi göster"""
        if self.main_window:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
    
    def hide_main_window(self):
        """Ana pencereyi gizle"""
        if self.main_window:
            self.main_window.hide()
    
    def start_bot(self):
        """Bot'u başlat"""
        if self.bot_worker and self.bot_worker.isRunning():
            logger.warning("Bot zaten çalışıyor")
            return
        
        logger.info("Bot başlatılıyor...")
        
        self.bot_worker = BotWorkerThread(self.settings)
        
        # Signal bağlantıları
        self.bot_worker.status_updated.connect(self._on_status_updated)
        self.bot_worker.position_opened.connect(self._on_position_opened)
        self.bot_worker.position_closed.connect(self._on_position_closed)
        self.bot_worker.error_occurred.connect(self._on_error_occurred)
        
        self.bot_worker.start()
        
        # Demo signal monitoring verisi ekle (2 saniye sonra)
        if self.main_window:
            self.bot_worker.main_window = self.main_window
            QTimer.singleShot(2000, self.bot_worker._add_demo_signal_data)
        
        if self.tray_icon:
            self.tray_icon.showMessage(
                "ShortBot",
                "Bot başlatıldı",
                QSystemTrayIcon.Information,
                3000
            )
    
    def stop_bot(self):
        """Bot'u durdur"""
        if not self.bot_worker or not self.bot_worker.isRunning():
            logger.warning("Bot zaten durmuş durumda")
            return
        
        logger.info("Bot durduruluyor...")
        
        self.bot_worker.stop_bot()
        
        if self.tray_icon:
            self.tray_icon.showMessage(
                "ShortBot",
                "Bot durduruldu",
                QSystemTrayIcon.Information,
                3000
            )
    
    def _on_status_updated(self, status):
        """Bot status güncellemesi"""
        if self.main_window:
            self.main_window.update_status(status)
    
    def _on_position_opened(self, position_data):
        """Pozisyon açıldı bildirimi"""
        symbol = position_data.get('symbol', '')
        price = position_data.get('price', 0)
        
        if self.tray_icon:
            self.tray_icon.showMessage(
                "Pozisyon Açıldı",
                f"{symbol} @ ${price:.4f}",
                QSystemTrayIcon.Information,
                5000
            )
        
        if self.main_window:
            self.main_window.on_position_opened(position_data)
    
    def _on_position_closed(self, position_data):
        """Pozisyon kapandı bildirimi"""
        symbol = position_data.get('symbol', '')
        pnl = position_data.get('pnl', 0)
        
        icon_type = QSystemTrayIcon.Information if pnl >= 0 else QSystemTrayIcon.Warning
        
        if self.tray_icon:
            self.tray_icon.showMessage(
                "Pozisyon Kapandı",
                f"{symbol} PnL: ${pnl:.2f}",
                icon_type,
                5000
            )
        
        if self.main_window:
            self.main_window.on_position_closed(position_data)
    
    def _on_error_occurred(self, error_message):
        """Hata oluştu"""
        logger.error(f"Bot error: {error_message}")
        
        if self.tray_icon:
            self.tray_icon.showMessage(
                "Bot Hatası",
                error_message,
                QSystemTrayIcon.Critical,
                10000
            )
        
        if self.main_window:
            self.main_window.show_error(error_message)
    
    def quit_application(self):
        """Uygulamayı kapat"""
        # Bot'u durdur
        if self.bot_worker and self.bot_worker.isRunning():
            reply = QMessageBox.question(
                None,
                "ShortBot",
                "Bot çalışıyor. Yine de çıkmak istiyor musunuz?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                return
            
            self.stop_bot()
            self.bot_worker.wait(5000)  # 5 saniye bekle
        
        # Ayarları kaydet
        try:
            self.settings.save_to_file()
            logger.info("Ayarlar kaydedildi")
        except Exception as e:
            logger.error(f"Ayar kaydetme hatası: {e}")
        
        # Uygulamayı kapat
        self.quit()
    
    def run(self) -> int:
        """Uygulamayı çalıştır"""
        logger.info("ShortBot GUI başlatıldı")
        
        # Ana pencereyi göster
        if self.settings.app.auto_start:
            self.start_bot()
        
        self.show_main_window()
        
        # Event loop
        return self.exec() 