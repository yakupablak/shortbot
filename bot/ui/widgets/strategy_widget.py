"""
Strategy Builder Widget
İndikatör ayarları ve sinyal kuralları GUI'si
"""
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QSpinBox, QDoubleSpinBox, 
    QCheckBox, QComboBox, QPushButton, QTextEdit,
    QSlider, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, Signal

from ...utils.config import BotSettings, IndicatorConfig, StrategyConfig, SignalLogic, TimeFrame


class IndicatorGroup(QGroupBox):
    """İndikatör grup widget'ı"""
    
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(True)
        
        self.layout = QGridLayout(self)
        self.row = 0
    
    def add_parameter(self, name: str, widget: QWidget, description: str = ""):
        """Parametre ekle"""
        label = QLabel(f"{name}:")
        if description:
            label.setToolTip(description)
            widget.setToolTip(description)
        
        self.layout.addWidget(label, self.row, 0)
        self.layout.addWidget(widget, self.row, 1)
        self.row += 1


class StrategyBuilderWidget(QWidget):
    """Strategy Builder ana widget'ı"""
    
    # Signals
    settings_changed = Signal()
    
    def __init__(self, settings: BotSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        
        self._init_ui()
        self._connect_signals()
        self._load_settings()
    
    def _init_ui(self):
        """UI'yi başlat"""
        main_layout = QVBoxLayout(self)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Strategy genel ayarları
        strategy_group = self._create_strategy_group()
        scroll_layout.addWidget(strategy_group)
        
        # İndikatör grupları
        self.rsi_group = self._create_rsi_group()
        scroll_layout.addWidget(self.rsi_group)
        
        self.ema_group = self._create_ema_group()
        scroll_layout.addWidget(self.ema_group)
        
        self.macd_group = self._create_macd_group()
        scroll_layout.addWidget(self.macd_group)
        
        self.bb_group = self._create_bollinger_group()
        scroll_layout.addWidget(self.bb_group)
        
        self.custom_group = self._create_custom_group()
        scroll_layout.addWidget(self.custom_group)
        
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)
        
        # Alt butonlar
        button_layout = QHBoxLayout()
        
        self.reset_btn = QPushButton("🔄 Varsayılana Sıfırla")
        self.test_btn = QPushButton("🧪 Strateji Test Et")
        self.save_btn = QPushButton("💾 Kaydet")
        
        button_layout.addWidget(self.reset_btn)
        button_layout.addWidget(self.test_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(button_layout)
    
    def _create_strategy_group(self) -> QGroupBox:
        """Strateji genel ayarları grubu"""
        group = QGroupBox("📈 Strateji Ayarları")
        layout = QGridLayout(group)
        
        # Timeframe
        layout.addWidget(QLabel("Zaman Dilimi:"), 0, 0)
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems([tf.value for tf in TimeFrame])
        layout.addWidget(self.timeframe_combo, 0, 1)
        
        # Take Profit
        layout.addWidget(QLabel("Take Profit (%):"), 1, 0)
        self.tp_spin = QDoubleSpinBox()
        self.tp_spin.setRange(0.1, 50.0)
        self.tp_spin.setSingleStep(0.5)
        self.tp_spin.setDecimals(1)
        self.tp_spin.setSuffix("%")
        layout.addWidget(self.tp_spin, 1, 1)
        
        # Signal Logic
        layout.addWidget(QLabel("Sinyal Mantığı:"), 2, 0)
        self.signal_logic_combo = QComboBox()
        self.signal_logic_combo.addItems([
            "Tümü Doğru (AND)",
            "Çoğunluk Doğru (MAJORITY)", 
            "En Az Biri Doğru (OR)"
        ])
        layout.addWidget(self.signal_logic_combo, 2, 1)
        
        # Max positions
        layout.addWidget(QLabel("Maksimum Pozisyon:"), 3, 0)
        self.max_pos_spin = QSpinBox()
        self.max_pos_spin.setRange(1, 10)
        layout.addWidget(self.max_pos_spin, 3, 1)
        
        return group
    
    def _create_rsi_group(self) -> IndicatorGroup:
        """RSI grup widget'ı"""
        group = IndicatorGroup("📊 RSI (Relative Strength Index)")
        
        # RSI Period
        self.rsi_period = QSpinBox()
        self.rsi_period.setRange(5, 50)
        group.add_parameter("Period", self.rsi_period, "RSI hesaplama periyodu (örn: 14)")
        
        # Overbought threshold
        self.rsi_overbought = QDoubleSpinBox()
        self.rsi_overbought.setRange(60, 90)
        self.rsi_overbought.setValue(70)
        group.add_parameter("Aşırı Alım", self.rsi_overbought, "RSI aşırı alım seviyesi")
        
        # Oversold threshold  
        self.rsi_oversold = QDoubleSpinBox()
        self.rsi_oversold.setRange(10, 40)
        self.rsi_oversold.setValue(30)
        group.add_parameter("Aşırı Satım", self.rsi_oversold, "RSI aşırı satım seviyesi")
        
        return group
    
    def _create_ema_group(self) -> IndicatorGroup:
        """EMA grup widget'ı"""
        group = IndicatorGroup("📈 EMA (Exponential Moving Average)")
        
        # Fast EMA
        self.ema_fast = QSpinBox()
        self.ema_fast.setRange(5, 50)
        self.ema_fast.setValue(12)
        group.add_parameter("Hızlı EMA", self.ema_fast, "Kısa vadeli EMA periyodu")
        
        # Slow EMA
        self.ema_slow = QSpinBox()
        self.ema_slow.setRange(20, 200)
        self.ema_slow.setValue(26)
        group.add_parameter("Yavaş EMA", self.ema_slow, "Uzun vadeli EMA periyodu")
        
        return group
    
    def _create_macd_group(self) -> IndicatorGroup:
        """MACD grup widget'ı"""
        group = IndicatorGroup("🌊 MACD (Moving Average Convergence Divergence)")
        
        # MACD Fast
        self.macd_fast = QSpinBox()
        self.macd_fast.setRange(8, 20)
        self.macd_fast.setValue(12)
        group.add_parameter("Hızlı", self.macd_fast, "MACD hızlı EMA")
        
        # MACD Slow
        self.macd_slow = QSpinBox() 
        self.macd_slow.setRange(20, 35)
        self.macd_slow.setValue(26)
        group.add_parameter("Yavaş", self.macd_slow, "MACD yavaş EMA")
        
        # MACD Signal
        self.macd_signal = QSpinBox()
        self.macd_signal.setRange(7, 15)
        self.macd_signal.setValue(9)
        group.add_parameter("Sinyal", self.macd_signal, "MACD sinyal EMA")
        
        return group
    
    def _create_bollinger_group(self) -> IndicatorGroup:
        """Bollinger Bands grup widget'ı"""
        group = IndicatorGroup("📏 Bollinger Bands")
        
        # BB Period
        self.bb_period = QSpinBox()
        self.bb_period.setRange(10, 50)
        self.bb_period.setValue(20)
        group.add_parameter("Period", self.bb_period, "Bollinger Bands periyodu")
        
        # BB Standard Deviation
        self.bb_std = QDoubleSpinBox()
        self.bb_std.setRange(1.0, 3.0)
        self.bb_std.setSingleStep(0.1)
        self.bb_std.setValue(2.0)
        group.add_parameter("Std Sapma", self.bb_std, "Standart sapma çarpanı")
        
        return group
    
    def _create_custom_group(self) -> IndicatorGroup:
        """Özel strateji grup widget'ı"""
        group = IndicatorGroup("⚙️ Özel Strateji")
        
        layout = QVBoxLayout()
        
        label = QLabel("Python ifadesi (isteğe bağlı):")
        layout.addWidget(label)
        
        self.custom_expression = QTextEdit()
        self.custom_expression.setMaximumHeight(100)
        self.custom_expression.setPlaceholderText(
            "Örnek: rsi > 70 and macd < 0 and close < bb_lower\n"
            "Kullanılabilir değişkenler: rsi, ema_fast, ema_slow, macd, bb_upper, bb_lower, close, volume"
        )
        layout.addWidget(self.custom_expression)
        
        group.setLayout(layout)
        return group
    
    def _connect_signals(self):
        """Signal bağlantıları"""
        # Strategy settings
        self.timeframe_combo.currentTextChanged.connect(self.settings_changed.emit)
        self.tp_spin.valueChanged.connect(self.settings_changed.emit)
        self.signal_logic_combo.currentTextChanged.connect(self.settings_changed.emit)
        self.max_pos_spin.valueChanged.connect(self.settings_changed.emit)
        
        # Indicator settings
        for widget in [self.rsi_period, self.rsi_overbought, self.rsi_oversold,
                       self.ema_fast, self.ema_slow, self.macd_fast, self.macd_slow,
                       self.macd_signal, self.bb_period, self.bb_std]:
            widget.valueChanged.connect(self.settings_changed.emit)
        
        self.custom_expression.textChanged.connect(self.settings_changed.emit)
        
        # Buttons
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        self.test_btn.clicked.connect(self._test_strategy)
        self.save_btn.clicked.connect(self._save_settings)
    
    def _load_settings(self):
        """Ayarları UI'ye yükle"""
        strategy = self.settings.strategy
        indicators = strategy.indicators
        
        # Strategy
        self.timeframe_combo.setCurrentText(strategy.timeframe.value)
        self.tp_spin.setValue(strategy.tp_percentage)
        
        signal_logic_map = {
            SignalLogic.ALL_TRUE: 0,
            SignalLogic.MAJORITY_TRUE: 1,
            SignalLogic.ANY_TRUE: 2
        }
        self.signal_logic_combo.setCurrentIndex(signal_logic_map.get(strategy.signal_logic, 1))
        self.max_pos_spin.setValue(strategy.max_concurrent_positions)
        
        # Indicators
        self.rsi_period.setValue(indicators.rsi_period)
        self.rsi_overbought.setValue(indicators.rsi_overbought)
        self.rsi_oversold.setValue(indicators.rsi_oversold)
        
        self.ema_fast.setValue(indicators.ema_fast)
        self.ema_slow.setValue(indicators.ema_slow)
        
        self.macd_fast.setValue(indicators.macd_fast)
        self.macd_slow.setValue(indicators.macd_slow)
        self.macd_signal.setValue(indicators.macd_signal)
        
        self.bb_period.setValue(indicators.bb_period)
        self.bb_std.setValue(indicators.bb_std)
        
        if indicators.custom_expression:
            self.custom_expression.setPlainText(indicators.custom_expression)
    
    def _save_settings(self):
        """Ayarları kaydet"""
        # Strategy settings
        self.settings.strategy.timeframe = TimeFrame(self.timeframe_combo.currentText())
        self.settings.strategy.tp_percentage = self.tp_spin.value()
        
        signal_logic_map = [
            SignalLogic.ALL_TRUE,
            SignalLogic.MAJORITY_TRUE, 
            SignalLogic.ANY_TRUE
        ]
        self.settings.strategy.signal_logic = signal_logic_map[self.signal_logic_combo.currentIndex()]
        self.settings.strategy.max_concurrent_positions = self.max_pos_spin.value()
        
        # Indicator settings
        indicators = self.settings.strategy.indicators
        indicators.rsi_period = self.rsi_period.value()
        indicators.rsi_overbought = self.rsi_overbought.value()
        indicators.rsi_oversold = self.rsi_oversold.value()
        
        indicators.ema_fast = self.ema_fast.value()
        indicators.ema_slow = self.ema_slow.value()
        
        indicators.macd_fast = self.macd_fast.value()
        indicators.macd_slow = self.macd_slow.value()
        indicators.macd_signal = self.macd_signal.value()
        
        indicators.bb_period = self.bb_period.value()
        indicators.bb_std = self.bb_std.value()
        
        indicators.custom_expression = self.custom_expression.toPlainText().strip()
        
        # Dosyaya kaydet
        try:
            self.settings.save_to_file()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Başarılı", "Strateji ayarları kaydedildi!")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Hata", f"Ayarlar kaydedilemedi: {e}")
    
    def _reset_to_defaults(self):
        """Varsayılan değerlere sıfırla"""
        from PySide6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self, 
            "Sıfırla",
            "Tüm strateji ayarları varsayılan değerlere sıfırlanacak. Emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Yeni default settings oluştur
            default_settings = BotSettings()
            self.settings.strategy = default_settings.strategy
            self._load_settings()
            self.settings_changed.emit()
    
    def _test_strategy(self):
        """Strateji test et"""
        from PySide6.QtWidgets import QMessageBox
        
        QMessageBox.information(
            self,
            "Strateji Testi",
            "Strateji test özelliği yakında eklenecek!\n\n"
            "Test edilecek:\n"
            "• Son 1000 mum verisi\n" 
            "• Sinyal üretim performansı\n"
            "• Backtest sonuçları"
        ) 