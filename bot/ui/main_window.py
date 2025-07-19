"""
Ana Pencere (MainWindow)
Temel GUI layout ve widget yönetimi
"""
from typing import Any, Dict, Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QLabel, QPushButton, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QStatusBar, QMenuBar, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont, QPolygon

from ..utils.config import BotSettings
from ..utils.logger import get_logger

logger = get_logger("main_window")


class MainWindow(QMainWindow):
    """Ana GUI penceresi"""
    
    def __init__(self, settings: BotSettings, app=None):
        super().__init__()
        
        self.settings = settings
        self.app = app
        
        # Window ayarları
        self.setWindowTitle("ShortBot - Kripto Short İşlem Botu")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # UI elemanları
        self.central_widget: Optional[QWidget] = None
        self.tab_widget: Optional[QTabWidget] = None
        
        # Status bar elemanları
        self.status_label: Optional[QLabel] = None
        self.balance_label: Optional[QLabel] = None
        self.positions_label: Optional[QLabel] = None
        
        # Dashboard elemanları
        self.log_text: Optional[QTextEdit] = None
        self.positions_table: Optional[QTableWidget] = None
        
        # Timer'lar
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(1000)  # 1 saniyede bir güncelle
        
        # UI'yi başlat
        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
    
    def _setup_ui(self):
        """Ana UI'yi kur"""
        # Central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Ana layout
        main_layout = QVBoxLayout(self.central_widget)
        
        # Kontrol paneli
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Tab'ları oluştur
        self._create_dashboard_tab()
        self._create_strategy_tab()
        self._create_risk_tab()
        self._create_api_tab()
        self._create_signal_monitoring_tab()
        self._create_logs_tab()
    
    def _create_control_panel(self) -> QWidget:
        """Kontrol paneli oluştur"""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        
        # Start/Stop butonları
        self.start_button = QPushButton("🚀 BOT BAŞLAT")
        self.start_button.setMinimumHeight(40)
        self.start_button.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.start_button.clicked.connect(self._on_start_clicked)
        
        self.stop_button = QPushButton("⏹️ BOT DURDUR")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        
        self.emergency_button = QPushButton("🛑 ACİL DURDUR")
        self.emergency_button.setMinimumHeight(40)
        self.emergency_button.setStyleSheet(
            "background-color: #dc3545; font-size: 14px; font-weight: bold;"
        )
        self.emergency_button.clicked.connect(self._on_emergency_clicked)
        
        # Status göstergesi
        self.status_indicator = QLabel("⚪ DURDURULDU")
        self.status_indicator.setStyleSheet("font-size: 16px; font-weight: bold; padding: 8px;")
        
        # Layout'a ekle
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.emergency_button)
        layout.addStretch()
        layout.addWidget(self.status_indicator)
        
        return panel
    
    def _create_dashboard_tab(self):
        """Dashboard sekmesi"""
        dashboard = QWidget()
        layout = QVBoxLayout(dashboard)
        
        # Üst panel - İstatistikler
        stats_panel = QWidget()
        stats_layout = QHBoxLayout(stats_panel)
        
        # Balance card
        balance_card = self._create_info_card("Bakiye", "$1,000.00", "#28a745")
        stats_layout.addWidget(balance_card)
        
        # Daily PnL card
        pnl_card = self._create_info_card("Günlük PnL", "$0.00", "#6c757d")
        stats_layout.addWidget(pnl_card)
        
        # Positions card
        positions_card = self._create_info_card("Açık Pozisyon", "0", "#007bff")
        stats_layout.addWidget(positions_card)
        
        # Signals card
        signals_card = self._create_info_card("Toplam Sinyal", "0", "#17a2b8")
        stats_layout.addWidget(signals_card)
        
        layout.addWidget(stats_panel)
        
        # Alt panel - Pozisyon tablosu
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(8)
        self.positions_table.setHorizontalHeaderLabels([
            "Symbol", "Side", "Size", "Entry", "Mark", "PnL", "TP", "Duration"
        ])
        
        # Tablo ayarları
        header = self.positions_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.positions_table.setAlternatingRowColors(True)
        self.positions_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(QLabel("Açık Pozisyonlar:"))
        layout.addWidget(self.positions_table)
        
        self.tab_widget.addTab(dashboard, "📊 Dashboard")
    
    def _create_strategy_tab(self):
        """Strateji sekmesi"""
        try:
            from .widgets.strategy_widget import StrategyBuilderWidget
            strategy_widget = StrategyBuilderWidget(self.settings)
            strategy_widget.settings_changed.connect(self._on_settings_changed)
            self.tab_widget.addTab(strategy_widget, "🎯 Strateji")
        except ImportError:
            # Fallback widget
            strategy = QWidget()
            layout = QVBoxLayout(strategy)
            info_label = QLabel("Strateji widget'ı yükleniyor...")
            info_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(info_label)
            self.tab_widget.addTab(strategy, "🎯 Strateji")
    
    def _create_risk_tab(self):
        """Risk yönetimi sekmesi"""
        try:
            from .widgets.risk_widget import RiskAlertsMainWidget
            risk_widget = RiskAlertsMainWidget(self.settings)
            risk_widget.emergency_stop_requested.connect(self._on_emergency_stop)
            self.tab_widget.addTab(risk_widget, "⚠️ Risk")
        except ImportError:
            # Fallback widget
            risk = QWidget()
            layout = QVBoxLayout(risk)
            info_label = QLabel("Risk widget'ı yükleniyor...")
            info_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(info_label)
            self.tab_widget.addTab(risk, "⚠️ Risk")
    
    def _create_logs_tab(self):
        """Log sekmesi"""
        logs = QWidget()
        layout = QVBoxLayout(logs)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        
        layout.addWidget(QLabel("Sistem Logları:"))
        layout.addWidget(self.log_text)
        
        self.tab_widget.addTab(logs, "📋 Loglar")
    
    def _create_api_tab(self):
        """API & Mode sekmesi"""
        try:
            from .widgets.api_widget import APIModeMainWidget
            api_widget = APIModeMainWidget(self.settings)
            api_widget.settings_changed.connect(self._on_settings_changed)
            self.tab_widget.addTab(api_widget, "🔑 API & Mode")
        except ImportError:
            # Fallback widget
            api = QWidget()
            layout = QVBoxLayout(api)
            info_label = QLabel("API widget'ı yükleniyor...")
            info_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(info_label)
            self.tab_widget.addTab(api, "🔑 API & Mode")
    
    def _create_signal_monitoring_tab(self):
        """Signal Monitoring sekmesi"""
        try:
            from .widgets.signal_monitoring_widget import SignalMonitoringWidget
            self.signal_monitoring_widget = SignalMonitoringWidget(self.settings)
            self.tab_widget.addTab(self.signal_monitoring_widget, "🔍 Sinyal İzleme")
        except ImportError:
            # Fallback widget
            monitoring = QWidget()
            layout = QVBoxLayout(monitoring)
            info_label = QLabel("Sinyal izleme widget'ı yükleniyor...")
            info_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(info_label)
            self.tab_widget.addTab(monitoring, "🔍 Sinyal İzleme")
    
    def _create_info_card(self, title: str, value: str, color: str) -> QWidget:
        """Bilgi kartı oluştur"""
        card = QWidget()
        card.setFixedSize(200, 80)
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {color};
                border-radius: 8px;
                padding: 8px;
            }}
            QLabel {{
                color: white;
                font-weight: bold;
            }}
        """)
        
        layout = QVBoxLayout(card)
        
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 12px;")
        
        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet("font-size: 18px;")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        return card
    
    def _setup_menu(self):
        """Menu bar kur"""
        menubar = self.menuBar()
        
        # Dosya menüsü
        file_menu = menubar.addMenu("Dosya")
        
        settings_action = QAction("Ayarlar", self)
        settings_action.triggered.connect(self._show_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Çıkış", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Bot menüsü
        bot_menu = menubar.addMenu("Bot")
        
        start_action = QAction("Başlat", self)
        start_action.triggered.connect(self._on_start_clicked)
        bot_menu.addAction(start_action)
        
        stop_action = QAction("Durdur", self)
        stop_action.triggered.connect(self._on_stop_clicked)
        bot_menu.addAction(stop_action)
        
        # Yardım menüsü
        help_menu = menubar.addMenu("Yardım")
        
        about_action = QAction("Hakkında", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_status_bar(self):
        """Status bar kur"""
        status_bar = self.statusBar()
        
        self.status_label = QLabel("Bot durduruldu")
        self.balance_label = QLabel("Bakiye: $0.00")
        self.positions_label = QLabel("Pozisyon: 0")
        
        status_bar.addWidget(self.status_label)
        status_bar.addPermanentWidget(self.positions_label)
        status_bar.addPermanentWidget(self.balance_label)
    
    def _update_display(self):
        """Ekran güncelleme"""
        # Bu metod düzenli olarak çalışır ve UI'yi günceller
        pass
    
    # Event Handler'lar
    def _on_start_clicked(self):
        """Başlat butonu tıklandı"""
        if self.app:
            self.app.start_bot()
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.status_indicator.setText("🟢 ÇALIŞIYOR")
            self.status_indicator.setStyleSheet("color: #28a745; font-size: 16px; font-weight: bold; padding: 8px;")
    
    def _on_stop_clicked(self):
        """Durdur butonu tıklandı"""
        if self.app:
            self.app.stop_bot()
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.status_indicator.setText("⚪ DURDURULDU")
            self.status_indicator.setStyleSheet("color: #6c757d; font-size: 16px; font-weight: bold; padding: 8px;")
    
    def _on_emergency_clicked(self):
        """Acil durdur butonu tıklandı"""
        reply = QMessageBox.warning(
            self,
            "Acil Durdurma",
            "Tüm pozisyonlar kapatılacak ve bot durdurulacak.\nEmin misiniz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Emergency stop implementation
            self._on_stop_clicked()
            self.status_indicator.setText("🛑 ACİL DURDURULDU")
            self.status_indicator.setStyleSheet("color: #dc3545; font-size: 16px; font-weight: bold; padding: 8px;")
    
    def _show_settings(self):
        """Ayarlar penceresini göster"""
        QMessageBox.information(self, "Ayarlar", "Ayarlar penceresi henüz hazır değil.")
    
    def _show_about(self):
        """Hakkında penceresini göster"""
        QMessageBox.about(
            self,
            "ShortBot Hakkında",
            "<h3>ShortBot v1.0.0</h3>"
            "<p>Kripto para short işlem botu</p>"
            "<p>Parametrik, stop-loss'suz, sabit 1 USDT pozisyon açar.</p>"
            "<p><b>⚠️ Risk Uyarısı:</b> Trading risklidir!</p>"
            "<p>Sadece kaybetmeyi göze alabileceğiniz miktarla kullanın.</p>"
        )
    
    # Public methods - App tarafından çağırılır
    def update_status(self, status: Dict[str, Any]):
        """Bot status güncellemesi"""
        if self.status_label:
            state = status.get('state', 'unknown')
            trading_mode = status.get('trading_mode', 'demo')
            self.status_label.setText(f"Durum: {state} ({trading_mode})")
        
        portfolio = status.get('portfolio', {})
        
        if self.balance_label:
            balance = portfolio.get('balance', 0)
            self.balance_label.setText(f"Bakiye: ${balance:.2f}")
        
        if self.positions_label:
            positions = portfolio.get('open_positions', 0)
            self.positions_label.setText(f"Pozisyon: {positions}")
    
    def on_position_opened(self, position_data: Dict[str, Any]):
        """Pozisyon açıldığında çağırılır"""
        self.log_to_screen(f"✅ Pozisyon açıldı: {position_data.get('symbol', 'N/A')}")
    
    def on_position_closed(self, position_data: Dict[str, Any]):
        """Pozisyon kapandığında çağırılır"""
        symbol = position_data.get('symbol', 'N/A')
        pnl = position_data.get('pnl', 0)
        emoji = "💚" if pnl >= 0 else "❌"
        self.log_to_screen(f"{emoji} Pozisyon kapatıldı: {symbol} PnL: ${pnl:.2f}")
    
    def show_error(self, error_message: str):
        """Hata göster"""
        self.log_to_screen(f"❌ HATA: {error_message}")
        QMessageBox.critical(self, "Bot Hatası", error_message)
    
    def log_to_screen(self, message: str):
        """Log mesajını ekrana yazdır"""
        if self.log_text:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"
            self.log_text.append(formatted_message)
            
            # Auto-scroll
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def _on_settings_changed(self, *args, **kwargs):
        """Ayarlar değiştiğinde çağırılır"""
        self.log_to_screen("⚙️ Ayarlar değiştirildi")
    
    def _on_emergency_stop(self):
        """Acil durdur butonu çağırıldığında"""
        self.log_to_screen("🛑 Acil durdur komutu alındı!")
        if self.app:
            self.app.stop_bot()
        
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self,
            "Acil Durdurma",
            "Tüm pozisyonlar kapatılmaya çalışılacak ve bot durdurulacak!"
        )
    
    def update_signal_monitoring(self, symbol: str, data: dict):
        """Signal monitoring widget'ını güncelle"""
        if hasattr(self, 'signal_monitoring_widget'):
            self.signal_monitoring_widget.add_coin_analysis(symbol, data)
    
    def update_coin_status(self, symbol: str, status: str, reason: str = "", confidence: int = 0):
        """Coin durumunu güncelle"""
        if hasattr(self, 'signal_monitoring_widget'):
            self.signal_monitoring_widget.update_coin_status(symbol, status, reason, confidence)
    
    def closeEvent(self, event):
        """Pencere kapatılırken"""
        if self.app and hasattr(self.app, 'quit_application'):
            self.app.quit_application()
        event.accept() 