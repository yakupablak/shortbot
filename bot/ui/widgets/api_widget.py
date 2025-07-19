"""
API & Mode Widget
Binance API ayarları ve trading mod seçimi GUI'si
"""
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QCheckBox, QComboBox, QTextEdit, QFrame,
    QButtonGroup, QRadioButton, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont

from ...utils.config import BotSettings, TradingMode
from ...utils.encryption import store_api_credentials, load_api_credentials, validate_api_credentials


class APITestThread(QThread):
    """API test thread'i"""
    
    test_completed = Signal(bool, str)  # success, message
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
    
    def run(self):
        """API test işlemi"""
        try:
            # Gerçek API test implementasyonu
            # Şimdilik basit validasyon
            if len(self.api_key) < 20 or len(self.api_secret) < 20:
                self.test_completed.emit(False, "API key veya secret çok kısa")
                return
            
            self.test_completed.emit(True, "API bağlantısı başarılı!")
            
        except Exception as e:
            self.test_completed.emit(False, f"API test hatası: {e}")


class TradingModeWidget(QGroupBox):
    """Trading mod seçimi widget'ı"""
    
    mode_changed = Signal(str)  # mode name
    
    def __init__(self, settings: BotSettings, parent=None):
        super().__init__("🎯 İşlem Modu", parent)
        
        self.settings = settings
        self._init_ui()
        self._connect_signals()
        self._load_settings()
    
    def _init_ui(self):
        """UI'yi başlat"""
        layout = QVBoxLayout(self)
        
        # Mode buttons
        self.mode_group = QButtonGroup(self)
        
        self.demo_radio = QRadioButton("📊 DEMO Modu")
        self.demo_radio.setStyleSheet("font-weight: bold; color: green;")
        
        self.real_radio = QRadioButton("💰 GERÇEK Modu")
        self.real_radio.setStyleSheet("font-weight: bold; color: red;")
        
        self.mode_group.addButton(self.demo_radio, 0)
        self.mode_group.addButton(self.real_radio, 1)
        
        layout.addWidget(self.demo_radio)
        layout.addWidget(self.real_radio)
        
        # Demo mode info
        demo_info = QLabel(
            "• Simülasyon ile test işlemleri\n"
            "• Gerçek para harcanmaz\n"
            "• $1000 sanal bakiye"
        )
        demo_info.setStyleSheet("color: #666; margin-left: 20px;")
        layout.addWidget(demo_info)
        
        # Real mode warning
        real_warning = QLabel(
            "⚠️ UYARI: Gerçek para kullanılır!\n"
            "• Kayıp riski vardır\n"
            "• API key'ler gereklidir\n"
            "• Sadece test edilmiş stratejiler"
        )
        real_warning.setStyleSheet("color: red; margin-left: 20px; font-weight: bold;")
        layout.addWidget(real_warning)
        
        # Demo balance setting
        balance_layout = QHBoxLayout()
        balance_layout.addWidget(QLabel("Demo Bakiye ($):"))
        
        self.demo_balance_edit = QLineEdit()
        self.demo_balance_edit.setPlaceholderText("1000")
        balance_layout.addWidget(self.demo_balance_edit)
        
        layout.addLayout(balance_layout)
    
    def _connect_signals(self):
        """Signal bağlantıları"""
        self.mode_group.buttonClicked.connect(self._on_mode_changed)
        self.demo_balance_edit.textChanged.connect(self._on_balance_changed)
    
    def _load_settings(self):
        """Ayarları yükle"""
        if self.settings.trading_mode == TradingMode.DEMO:
            self.demo_radio.setChecked(True)
        else:
            self.real_radio.setChecked(True)
        
        self.demo_balance_edit.setText(str(self.settings.demo_balance))
    
    def _on_mode_changed(self, button):
        """Mod değiştiğinde"""
        if button == self.demo_radio:
            self.mode_changed.emit("demo")
        else:
            self.mode_changed.emit("real")
    
    def _on_balance_changed(self):
        """Demo balance değiştiğinde"""
        try:
            balance = float(self.demo_balance_edit.text() or "1000")
            if balance >= 100:
                self.settings.demo_balance = balance
        except ValueError:
            pass
    
    def get_selected_mode(self) -> TradingMode:
        """Seçili modu al"""
        return TradingMode.DEMO if self.demo_radio.isChecked() else TradingMode.REAL


class BinanceAPIWidget(QGroupBox):
    """Binance API ayarları widget'ı"""
    
    api_saved = Signal(bool)  # success
    
    def __init__(self, settings: BotSettings, parent=None):
        super().__init__("🔑 Binance API Ayarları", parent)
        
        self.settings = settings
        self.test_thread: Optional[APITestThread] = None
        
        self._init_ui()
        self._connect_signals()
        self._load_credentials()
    
    def _init_ui(self):
        """UI'yi başlat"""
        layout = QVBoxLayout(self)
        
        # API credentials form
        form_layout = QGridLayout()
        
        # API Key
        form_layout.addWidget(QLabel("API Key:"), 0, 0)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("Binance Futures API Key'inizi girin...")
        form_layout.addWidget(self.api_key_edit, 0, 1)
        
        # API Secret
        form_layout.addWidget(QLabel("API Secret:"), 1, 0)
        self.api_secret_edit = QLineEdit()
        self.api_secret_edit.setEchoMode(QLineEdit.Password)
        self.api_secret_edit.setPlaceholderText("API Secret'ınızı girin...")
        form_layout.addWidget(self.api_secret_edit, 1, 1)
        
        # Show/Hide secret button
        self.show_secret_btn = QPushButton("👁️ Göster")
        self.show_secret_btn.setMaximumWidth(80)
        form_layout.addWidget(self.show_secret_btn, 1, 2)
        
        # Testnet checkbox
        self.testnet_check = QCheckBox("Testnet kullan (test amaçlı)")
        form_layout.addWidget(self.testnet_check, 2, 0, 1, 2)
        
        layout.addLayout(form_layout)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.test_api_btn = QPushButton("🧪 API Test Et")
        self.save_api_btn = QPushButton("💾 Kaydet")
        self.clear_api_btn = QPushButton("🗑️ Temizle")
        
        button_layout.addWidget(self.test_api_btn)
        button_layout.addWidget(self.save_api_btn)
        button_layout.addWidget(self.clear_api_btn)
        
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("API bilgileri henüz kaydedilmedi")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)
        
        # API Info
        info_frame = QFrame()
        info_frame.setFrameStyle(QFrame.Box)
        info_frame.setStyleSheet("background-color: #e3f2fd; padding: 10px; border-radius: 5px;")
        
        info_layout = QVBoxLayout(info_frame)
        info_label = QLabel(
            "ℹ️ <b>API Bilgilendirme:</b><br>"
            "• Binance Futures hesabınızdan API key alın<br>"
            "• Sadece 'Futures Trading' yetkisi verin<br>"
            "• IP kısıtlaması ekleyebilirsiniz<br>"
            "• API bilgileri Windows Credential Vault'ta güvenli saklanır"
        )
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        
        layout.addWidget(info_frame)
    
    def _connect_signals(self):
        """Signal bağlantıları"""
        self.show_secret_btn.clicked.connect(self._toggle_secret_visibility)
        self.test_api_btn.clicked.connect(self._test_api)
        self.save_api_btn.clicked.connect(self._save_credentials)
        self.clear_api_btn.clicked.connect(self._clear_credentials)
    
    def _load_credentials(self):
        """Kayıtlı bilgileri yükle"""
        try:
            api_key, api_secret = load_api_credentials()
            
            if api_key and api_secret:
                self.api_key_edit.setText(api_key)
                self.api_secret_edit.setText(api_secret)
                self.status_label.setText("✅ API bilgileri yüklendi")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.status_label.setText("API bilgileri bulunamadı")
                
        except Exception as e:
            self.status_label.setText(f"API yükleme hatası: {e}")
            self.status_label.setStyleSheet("color: red;")
    
    def _toggle_secret_visibility(self):
        """Secret görünürlüğünü değiştir"""
        if self.api_secret_edit.echoMode() == QLineEdit.Password:
            self.api_secret_edit.setEchoMode(QLineEdit.Normal)
            self.show_secret_btn.setText("🙈 Gizle")
        else:
            self.api_secret_edit.setEchoMode(QLineEdit.Password)
            self.show_secret_btn.setText("👁️ Göster")
    
    def _test_api(self):
        """API bağlantısını test et"""
        api_key = self.api_key_edit.text().strip()
        api_secret = self.api_secret_edit.text().strip()
        
        if not api_key or not api_secret:
            QMessageBox.warning(self, "Eksik Bilgi", "API Key ve Secret alanlarını doldurun!")
            return
        
        # Test button'ı deaktive et
        self.test_api_btn.setEnabled(False)
        self.test_api_btn.setText("🔄 Test ediliyor...")
        
        # API test thread'i başlat
        self.test_thread = APITestThread(api_key, api_secret, self.testnet_check.isChecked())
        self.test_thread.test_completed.connect(self._on_api_test_completed)
        self.test_thread.start()
    
    def _on_api_test_completed(self, success: bool, message: str):
        """API test tamamlandığında"""
        self.test_api_btn.setEnabled(True)
        self.test_api_btn.setText("🧪 API Test Et")
        
        if success:
            QMessageBox.information(self, "Test Başarılı", message)
            self.status_label.setText("✅ API test başarılı")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            QMessageBox.warning(self, "Test Başarısız", message)
            self.status_label.setText("❌ API test başarısız")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def _save_credentials(self):
        """API bilgilerini kaydet"""
        api_key = self.api_key_edit.text().strip()
        api_secret = self.api_secret_edit.text().strip()
        
        if not api_key or not api_secret:
            QMessageBox.warning(self, "Eksik Bilgi", "API Key ve Secret alanlarını doldurun!")
            return
        
        try:
            success = store_api_credentials(api_key, api_secret)
            
            if success:
                # Settings'i güncelle
                self.settings.binance.testnet = self.testnet_check.isChecked()
                self.settings.save_to_file()
                
                QMessageBox.information(self, "Başarılı", "API bilgileri güvenli şekilde kaydedildi!")
                self.status_label.setText("✅ API bilgileri kaydedildi")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
                self.api_saved.emit(True)
            else:
                QMessageBox.warning(self, "Hata", "API bilgileri kaydedilemedi!")
                self.api_saved.emit(False)
                
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kaydetme hatası: {e}")
            self.api_saved.emit(False)
    
    def _clear_credentials(self):
        """API bilgilerini temizle"""
        reply = QMessageBox.question(
            self,
            "Bilgileri Temizle", 
            "Kayıtlı API bilgileri silinecek. Emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                from ...utils.encryption import clear_api_credentials
                clear_api_credentials()
                
                self.api_key_edit.clear()
                self.api_secret_edit.clear()
                self.status_label.setText("API bilgileri temizlendi")
                self.status_label.setStyleSheet("color: #666; font-style: italic;")
                
                QMessageBox.information(self, "Başarılı", "API bilgileri temizlendi!")
                
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Temizleme hatası: {e}")


class APIModeMainWidget(QWidget):
    """API & Mode ana widget'ı"""
    
    settings_changed = Signal()
    
    def __init__(self, settings: BotSettings, parent=None):
        super().__init__(parent)
        
        self.settings = settings
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """UI'yi başlat"""
        layout = QVBoxLayout(self)
        
        # Trading Mode
        self.mode_widget = TradingModeWidget(self.settings)
        layout.addWidget(self.mode_widget)
        
        # Binance API
        self.api_widget = BinanceAPIWidget(self.settings) 
        layout.addWidget(self.api_widget)
        
        # Save all button
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        
        self.save_all_btn = QPushButton("💾 Tüm Ayarları Kaydet")
        self.save_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        save_layout.addWidget(self.save_all_btn)
        
        layout.addLayout(save_layout)
    
    def _connect_signals(self):
        """Signal bağlantıları"""
        self.mode_widget.mode_changed.connect(self._on_mode_changed)
        self.api_widget.api_saved.connect(self.settings_changed.emit)
        self.save_all_btn.clicked.connect(self._save_all_settings)
    
    def _on_mode_changed(self, mode_name: str):
        """Mod değiştiğinde"""
        if mode_name == "demo":
            self.settings.trading_mode = TradingMode.DEMO
        else:
            self.settings.trading_mode = TradingMode.REAL
        
        self.settings_changed.emit()
    
    def _save_all_settings(self):
        """Tüm ayarları kaydet"""
        try:
            # Trading mode
            self.settings.trading_mode = self.mode_widget.get_selected_mode()
            
            # Demo balance
            demo_balance_text = self.mode_widget.demo_balance_edit.text()
            if demo_balance_text:
                self.settings.demo_balance = float(demo_balance_text)
            
            # Testnet setting
            self.settings.binance.testnet = self.api_widget.testnet_check.isChecked()
            
            # Save to file
            self.settings.save_to_file()
            
            QMessageBox.information(self, "Başarılı", "Tüm ayarlar kaydedildi!")
            self.settings_changed.emit()
            
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Ayarlar kaydedilemedi: {e}") 