"""
Risk & Alerts Widget
Risk yönetimi ve uyarı ayarları GUI'si
"""
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QSpinBox, QDoubleSpinBox, 
    QCheckBox, QComboBox, QPushButton, QTextEdit,
    QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor

from ...utils.config import BotSettings, RiskConfig
from ...core.risk import RiskAlert, RiskLevel


class RiskMetricsWidget(QGroupBox):
    """Risk metrikleri gösterge widget'ı"""
    
    def __init__(self, parent=None):
        super().__init__("📊 Güncel Risk Metrikleri", parent)
        
        layout = QGridLayout(self)
        
        # Daily PnL
        layout.addWidget(QLabel("Günlük PnL:"), 0, 0)
        self.daily_pnl_label = QLabel("$0.00")
        self.daily_pnl_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.daily_pnl_label, 0, 1)
        
        # Drawdown progress
        layout.addWidget(QLabel("Drawdown Seviyesi:"), 1, 0)
        self.drawdown_progress = QProgressBar()
        self.drawdown_progress.setRange(0, 100)
        self.drawdown_progress.setFormat("%{value}%")
        layout.addWidget(self.drawdown_progress, 1, 1)
        
        # Open positions
        layout.addWidget(QLabel("Açık Pozisyon:"), 2, 0)
        self.positions_label = QLabel("0")
        self.positions_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.positions_label, 2, 1)
        
        # Consecutive losses
        layout.addWidget(QLabel("Ardışık Kayıp:"), 3, 0)
        self.losses_label = QLabel("0")
        layout.addWidget(self.losses_label, 3, 1)
        
        # Available balance
        layout.addWidget(QLabel("Kullanılabilir Bakiye:"), 4, 0)
        self.balance_label = QLabel("$1000.00")
        self.balance_label.setStyleSheet("font-weight: bold; color: green;")
        layout.addWidget(self.balance_label, 4, 1)
    
    def update_metrics(self, metrics: dict):
        """Risk metriklerini güncelle"""
        # Daily PnL
        pnl = metrics.get('daily_pnl', 0)
        self.daily_pnl_label.setText(f"${pnl:.2f}")
        self.daily_pnl_label.setStyleSheet(
            f"font-weight: bold; font-size: 14px; color: {'red' if pnl < 0 else 'green'};"
        )
        
        # Drawdown progress
        drawdown_pct = abs(metrics.get('daily_pnl_pct', 0))
        self.drawdown_progress.setValue(int(drawdown_pct))
        
        # Progress bar rengi
        if drawdown_pct < 5:
            color = "green"
        elif drawdown_pct < 10:
            color = "orange"  
        else:
            color = "red"
        
        self.drawdown_progress.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)
        
        # Diğer metrikler
        self.positions_label.setText(str(metrics.get('open_positions', 0)))
        self.losses_label.setText(str(metrics.get('consecutive_losses', 0)))
        self.balance_label.setText(f"${metrics.get('available_balance', 0):.2f}")


class RiskAlertsWidget(QGroupBox):
    """Risk uyarıları tablo widget'ı"""
    
    def __init__(self, parent=None):
        super().__init__("🚨 Risk Uyarıları", parent)
        
        layout = QVBoxLayout(self)
        
        # Alerts table
        self.alerts_table = QTableWidget()
        self.alerts_table.setColumnCount(4)
        self.alerts_table.setHorizontalHeaderLabels([
            "Zaman", "Seviye", "Tür", "Mesaj"
        ])
        
        header = self.alerts_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Zaman
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Seviye
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Tür
        header.setSectionResizeMode(3, QHeaderView.Stretch)           # Mesaj
        
        self.alerts_table.setAlternatingRowColors(True)
        self.alerts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.alerts_table.setMaximumHeight(200)
        
        layout.addWidget(self.alerts_table)
        
        # Clear button
        clear_btn = QPushButton("🗑️ Uyarıları Temizle")
        clear_btn.clicked.connect(self._clear_alerts)
        layout.addWidget(clear_btn)
    
    def add_alert(self, alert: RiskAlert):
        """Yeni alert ekle"""
        row = self.alerts_table.rowCount()
        self.alerts_table.insertRow(row)
        
        # Zaman
        time_item = QTableWidgetItem(alert.timestamp.strftime("%H:%M:%S"))
        self.alerts_table.setItem(row, 0, time_item)
        
        # Seviye
        level_item = QTableWidgetItem(alert.level.value.upper())
        
        # Seviye rengine göre renklendirme
        level_colors = {
            RiskLevel.LOW: QColor(0, 255, 0),      # Green
            RiskLevel.MEDIUM: QColor(255, 165, 0), # Orange
            RiskLevel.HIGH: QColor(255, 0, 0),     # Red
            RiskLevel.CRITICAL: QColor(128, 0, 128) # Purple
        }
        
        if alert.level in level_colors:
            level_item.setBackground(level_colors[alert.level])
        
        self.alerts_table.setItem(row, 1, level_item)
        
        # Tür
        type_item = QTableWidgetItem(alert.type.value)
        self.alerts_table.setItem(row, 2, type_item)
        
        # Mesaj
        message_item = QTableWidgetItem(alert.message)
        self.alerts_table.setItem(row, 3, message_item)
        
        # En son eklenen üstte göster
        self.alerts_table.scrollToTop()
    
    def _clear_alerts(self):
        """Tüm uyarıları temizle"""
        self.alerts_table.setRowCount(0)


class RiskSettingsWidget(QGroupBox):
    """Risk ayarları widget'ı"""
    
    settings_changed = Signal()
    
    def __init__(self, settings: BotSettings, parent=None):
        super().__init__("⚙️ Risk Ayarları", parent)
        
        self.settings = settings
        self._init_ui()
        self._connect_signals()
        self._load_settings()
    
    def _init_ui(self):
        """UI'yi başlat"""
        layout = QGridLayout(self)
        
        # Daily warning threshold
        layout.addWidget(QLabel("Günlük Uyarı Eşiği (%):"), 0, 0)
        self.warning_threshold_spin = QDoubleSpinBox()
        self.warning_threshold_spin.setRange(1.0, 20.0)
        self.warning_threshold_spin.setSingleStep(0.5)
        self.warning_threshold_spin.setDecimals(1)
        self.warning_threshold_spin.setSuffix("%")
        layout.addWidget(self.warning_threshold_spin, 0, 1)
        
        # Daily shutdown threshold
        layout.addWidget(QLabel("Günlük Durdurma Eşiği (%):"), 1, 0)
        self.shutdown_threshold_spin = QDoubleSpinBox()
        self.shutdown_threshold_spin.setRange(5.0, 50.0)
        self.shutdown_threshold_spin.setSingleStep(1.0)
        self.shutdown_threshold_spin.setDecimals(1)
        self.shutdown_threshold_spin.setSuffix("%")
        layout.addWidget(self.shutdown_threshold_spin, 1, 1)
        
        # Max portfolio risk
        layout.addWidget(QLabel("Maksimum Portföy Riski (%):"), 2, 0)
        self.max_portfolio_risk_spin = QDoubleSpinBox()
        self.max_portfolio_risk_spin.setRange(1.0, 25.0)
        self.max_portfolio_risk_spin.setSingleStep(1.0)
        self.max_portfolio_risk_spin.setDecimals(1)
        self.max_portfolio_risk_spin.setSuffix("%")
        layout.addWidget(self.max_portfolio_risk_spin, 2, 1)
        
        # Emergency stop button
        self.emergency_stop_btn = QPushButton("🛑 ACİL DURDUR")
        self.emergency_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        layout.addWidget(self.emergency_stop_btn, 3, 0, 1, 2)
        
        # Save button
        self.save_btn = QPushButton("💾 Risk Ayarlarını Kaydet")
        layout.addWidget(self.save_btn, 4, 0, 1, 2)
    
    def _connect_signals(self):
        """Signal bağlantıları"""
        self.warning_threshold_spin.valueChanged.connect(self.settings_changed.emit)
        self.shutdown_threshold_spin.valueChanged.connect(self.settings_changed.emit)
        self.max_portfolio_risk_spin.valueChanged.connect(self.settings_changed.emit)
        
        self.save_btn.clicked.connect(self._save_settings)
    
    def _load_settings(self):
        """Ayarları UI'ye yükle"""
        risk = self.settings.risk
        
        self.warning_threshold_spin.setValue(risk.daily_warning_threshold)
        self.shutdown_threshold_spin.setValue(risk.daily_shutdown_threshold)
        self.max_portfolio_risk_spin.setValue(risk.max_portfolio_risk)
    
    def _save_settings(self):
        """Ayarları kaydet"""
        self.settings.risk.daily_warning_threshold = self.warning_threshold_spin.value()
        self.settings.risk.daily_shutdown_threshold = self.shutdown_threshold_spin.value()
        self.settings.risk.max_portfolio_risk = self.max_portfolio_risk_spin.value()
        
        try:
            self.settings.save_to_file()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Başarılı", "Risk ayarları kaydedildi!")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Hata", f"Ayarlar kaydedilemedi: {e}")


class RiskAlertsMainWidget(QWidget):
    """Risk & Alerts ana widget'ı"""
    
    emergency_stop_requested = Signal()
    
    def __init__(self, settings: BotSettings, parent=None):
        super().__init__(parent)
        
        self.settings = settings
        self._init_ui()
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_metrics)
        self.update_timer.start(1000)  # Her saniye güncelle
    
    def _init_ui(self):
        """UI'yi başlat"""
        layout = QVBoxLayout(self)
        
        # Risk metrikleri
        self.metrics_widget = RiskMetricsWidget()
        layout.addWidget(self.metrics_widget)
        
        # Risk ayarları ve uyarılar
        middle_layout = QHBoxLayout()
        
        # Risk ayarları (sol)
        self.settings_widget = RiskSettingsWidget(self.settings)
        self.settings_widget.emergency_stop_btn.clicked.connect(self.emergency_stop_requested.emit)
        middle_layout.addWidget(self.settings_widget)
        
        # Risk uyarıları (sağ)
        self.alerts_widget = RiskAlertsWidget()
        middle_layout.addWidget(self.alerts_widget)
        
        layout.addLayout(middle_layout)
        
        # Alt bilgi paneli
        info_frame = QFrame()
        info_frame.setFrameStyle(QFrame.Box)
        info_frame.setStyleSheet("background-color: #f8f9fa; padding: 10px; border-radius: 5px;")
        
        info_layout = QVBoxLayout(info_frame)
        info_label = QLabel(
            "ℹ️ <b>Risk Yönetimi Bilgilendirmesi:</b><br>"
            "• Günlük uyarı eşiği aşıldığında bildirim alırsınız<br>"
            "• Günlük durdurma eşiği aşıldığında bot otomatik durur<br>"
            "• Maksimum portföy riski her pozisyon için geçerlidir<br>"
            "• Acil durdur butonu tüm pozisyonları kapatır"
        )
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        
        layout.addWidget(info_frame)
    
    def _update_metrics(self):
        """Risk metriklerini güncelle"""
        # Mock data - gerçek uygulamada bot engine'den gelecek
        metrics = {
            'daily_pnl': 0.0,
            'daily_pnl_pct': 0.0,
            'open_positions': 0,
            'consecutive_losses': 0,
            'available_balance': 1000.0
        }
        
        self.metrics_widget.update_metrics(metrics)
    
    def add_risk_alert(self, alert: RiskAlert):
        """Risk uyarısı ekle"""
        self.alerts_widget.add_alert(alert)
    
    def update_metrics_from_engine(self, metrics: dict):
        """Bot engine'den metrikleri güncelle"""
        self.metrics_widget.update_metrics(metrics) 