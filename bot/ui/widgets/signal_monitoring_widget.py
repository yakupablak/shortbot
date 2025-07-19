"""
Signal Monitoring Widget
Taranan coinler ve sinyal analizi sonuçlarını gösteren widget
"""
from datetime import datetime
from typing import Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QPushButton, QFrame, QGroupBox, QTextEdit,
    QProgressBar, QComboBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QBrush

from ...utils.config import BotSettings


class CoinAnalysisDialog(QWidget):
    """Coin detay analizi gösterme penceresi"""
    
    def __init__(self, coin_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.coin_data = coin_data
        self.setWindowTitle(f"Analiz Detayı - {coin_data.get('symbol', 'N/A')}")
        self.setFixedSize(600, 500)
        self._init_ui()
    
    def _init_ui(self):
        """UI'yi başlat"""
        layout = QVBoxLayout(self)
        
        # Header bilgisi
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 5px; padding: 10px;")
        header_layout = QVBoxLayout(header_frame)
        
        symbol_label = QLabel(f"🪙 {self.coin_data.get('symbol', 'N/A')}")
        symbol_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(symbol_label)
        
        price_label = QLabel(f"💰 Fiyat: ${self.coin_data.get('price', 0):.4f}")
        price_change_pct = self.coin_data.get('price_change_pct', 0)
        price_change_color = "green" if price_change_pct > 0 else "red"
        price_change_label = QLabel(f"📈 24h Değişim: %{price_change_pct:.2f}")
        price_change_label.setStyleSheet(f"color: {price_change_color}; font-weight: bold;")
        
        header_layout.addWidget(price_label)
        header_layout.addWidget(price_change_label)
        layout.addWidget(header_frame)
        
        # Sinyal analizi
        signal_group = QGroupBox("🎯 Sinyal Analizi")
        signal_layout = QVBoxLayout(signal_group)
        
        # Ana sinyal durumu
        signal_status = self.coin_data.get('signal_status', 'unknown')
        status_colors = {
            'opened': 'green',
            'rejected': 'red', 
            'pending': 'orange',
            'unknown': 'gray'
        }
        status_texts = {
            'opened': '✅ POZİSYON AÇILDI',
            'rejected': '❌ POZİSYON REDDEDİLDİ',
            'pending': '⏳ ANALİZ EDİLİYOR',
            'unknown': '❓ BİLİNMİYOR'
        }
        
        status_label = QLabel(status_texts.get(signal_status, 'Bilinmiyor'))
        status_label.setStyleSheet(f"color: {status_colors.get(signal_status, 'black')}; font-size: 14px; font-weight: bold;")
        signal_layout.addWidget(status_label)
        
        # Sinyal nedeni
        reason = self.coin_data.get('reason', 'Analiz bekleniyor...')
        reason_label = QLabel(f"📝 Neden: {reason}")
        reason_label.setWordWrap(True)
        signal_layout.addWidget(reason_label)
        
        layout.addWidget(signal_group)
        
        # İndikatör değerleri
        indicators_group = QGroupBox("📊 İndikatör Değerleri")
        indicators_layout = QVBoxLayout(indicators_group)
        
        indicators = self.coin_data.get('indicators', {})
        if indicators:
            for indicator, value in indicators.items():
                if isinstance(value, (int, float)) and not str(value).isalpha():
                    indicator_label = QLabel(f"{indicator.upper()}: {value:.2f}")
                else:
                    indicator_label = QLabel(f"{indicator.upper()}: {value}")
                indicators_layout.addWidget(indicator_label)
        else:
            indicators_layout.addWidget(QLabel("İndikatör verileri henüz mevcut değil"))
        
        layout.addWidget(indicators_group)
        
        # Kapatma butonu
        close_btn = QPushButton("Kapat")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)


class SignalMonitoringWidget(QWidget):
    """Signal Monitoring ana widget'ı"""
    
    # Signals
    coin_analysis_requested = Signal(str)  # symbol
    
    def __init__(self, settings: BotSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.coin_data: Dict[str, Dict[str, Any]] = {}  # symbol -> data
        
        self._init_ui()
        self._setup_timer()
    
    def _init_ui(self):
        """UI'yi başlat"""
        main_layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("🔍 Sinyal İzleme & Coin Analizi")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Kontrol butonları
        self.clear_btn = QPushButton("🗑️ Temizle")
        self.refresh_btn = QPushButton("🔄 Yenile")
        self.export_btn = QPushButton("📊 Dışa Aktar")
        
        header_layout.addWidget(self.clear_btn)
        header_layout.addWidget(self.refresh_btn)
        header_layout.addWidget(self.export_btn)
        
        main_layout.addLayout(header_layout)
        
        # İstatistik paneli
        stats_frame = QFrame()
        stats_frame.setFrameStyle(QFrame.Box)
        stats_frame.setStyleSheet("background-color: #e3f2fd; padding: 10px; border-radius: 5px;")
        stats_layout = QHBoxLayout(stats_frame)
        
        self.total_scanned_label = QLabel("📈 Taranan: 0")
        self.positions_opened_label = QLabel("✅ Açılan: 0")
        self.positions_rejected_label = QLabel("❌ Reddedilen: 0")
        self.success_rate_label = QLabel("🎯 Başarı: 0%")
        
        for label in [self.total_scanned_label, self.positions_opened_label, 
                     self.positions_rejected_label, self.success_rate_label]:
            label.setStyleSheet("font-weight: bold; margin: 5px;")
            stats_layout.addWidget(label)
        
        main_layout.addWidget(stats_frame)
        
        # Ana tablo
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(8)
        self.signals_table.setHorizontalHeaderLabels([
            "Coin", "Fiyat", "24h %", "Tarih/Saat", "Durum", "Neden", "Güven", "Detay"
        ])
        
        # Tablo ayarları
        header = self.signals_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)           # Coin
        header.setSectionResizeMode(1, QHeaderView.Fixed)           # Fiyat  
        header.setSectionResizeMode(2, QHeaderView.Fixed)           # 24h %
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Tarih
        header.setSectionResizeMode(4, QHeaderView.Fixed)           # Durum
        header.setSectionResizeMode(5, QHeaderView.Stretch)         # Neden
        header.setSectionResizeMode(6, QHeaderView.Fixed)           # Güven
        header.setSectionResizeMode(7, QHeaderView.Fixed)           # Detay
        
        # Kolon genişlikleri
        self.signals_table.setColumnWidth(0, 80)   # Coin
        self.signals_table.setColumnWidth(1, 80)   # Fiyat
        self.signals_table.setColumnWidth(2, 60)   # 24h %
        self.signals_table.setColumnWidth(4, 100)  # Durum
        self.signals_table.setColumnWidth(6, 60)   # Güven
        self.signals_table.setColumnWidth(7, 80)   # Detay
        
        self.signals_table.setAlternatingRowColors(True)
        self.signals_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.signals_table.setMaximumHeight(400)
        
        main_layout.addWidget(self.signals_table)
        
        # Log paneli
        log_group = QGroupBox("📋 Son Aktiviteler")
        log_layout = QVBoxLayout(log_group)
        
        self.activity_log = QTextEdit()
        self.activity_log.setMaximumHeight(150)
        self.activity_log.setReadOnly(True)
        self.activity_log.setPlaceholderText("Aktivite logları burada görünecek...")
        
        log_layout.addWidget(self.activity_log)
        main_layout.addWidget(log_group)
        
        # Signal bağlantıları
        self._connect_signals()
    
    def _connect_signals(self):
        """Signal bağlantıları"""
        self.clear_btn.clicked.connect(self._clear_data)
        self.refresh_btn.clicked.connect(self._refresh_data)
        self.export_btn.clicked.connect(self._export_data)
        
        # Tablo double-click
        self.signals_table.cellDoubleClicked.connect(self._on_cell_double_clicked)
    
    def _setup_timer(self):
        """Güncelleme timer'ı"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_statistics)
        self.update_timer.start(5000)  # 5 saniyede bir güncelle
    
    def add_coin_analysis(self, symbol: str, data: Dict[str, Any]):
        """Yeni coin analizi ekle"""
        self.coin_data[symbol] = {
            'symbol': symbol,
            'price': data.get('price', 0),
            'price_change_pct': data.get('price_change_pct', 0),
            'timestamp': datetime.now(),
            'signal_status': data.get('signal_status', 'pending'),
            'reason': data.get('reason', 'Analiz ediliyor...'),
            'confidence': data.get('confidence', 0),
            'indicators': data.get('indicators', {}),
            'volume': data.get('volume', 0)
        }
        
        self._update_table()
        self._log_activity(f"🔍 {symbol} analiz edildi - {data.get('signal_status', 'pending')}")
    
    def update_coin_status(self, symbol: str, status: str, reason: str = "", confidence: int = 0):
        """Coin durumunu güncelle"""
        if symbol in self.coin_data:
            self.coin_data[symbol]['signal_status'] = status
            self.coin_data[symbol]['reason'] = reason
            self.coin_data[symbol]['confidence'] = confidence
            self.coin_data[symbol]['timestamp'] = datetime.now()
            
            self._update_table()
            
            status_emoji = {
                'opened': '✅',
                'rejected': '❌', 
                'pending': '⏳'
            }
            
            emoji = status_emoji.get(status, '❓')
            self._log_activity(f"{emoji} {symbol}: {reason}")
    
    def _update_table(self):
        """Tabloyu güncelle"""
        self.signals_table.setRowCount(len(self.coin_data))
        
        for row, (symbol, data) in enumerate(self.coin_data.items()):
            # Coin
            coin_item = QTableWidgetItem(symbol)
            self.signals_table.setItem(row, 0, coin_item)
            
            # Fiyat
            price_item = QTableWidgetItem(f"${data['price']:.4f}")
            self.signals_table.setItem(row, 1, price_item)
            
            # 24h değişim
            change_pct = data['price_change_pct']
            change_item = QTableWidgetItem(f"{change_pct:+.1f}%")
            change_item.setForeground(QBrush(QColor('green' if change_pct > 0 else 'red')))
            self.signals_table.setItem(row, 2, change_item)
            
            # Tarih/saat
            time_item = QTableWidgetItem(data['timestamp'].strftime("%H:%M:%S"))
            self.signals_table.setItem(row, 3, time_item)
            
            # Durum
            status = data['signal_status']
            status_text = {
                'opened': '✅ Açıldı',
                'rejected': '❌ Red', 
                'pending': '⏳ Bekliyor'
            }.get(status, '❓ Bilinmiyor')
            
            status_item = QTableWidgetItem(status_text)
            
            # Durum rengine göre renklendirme
            status_colors = {
                'opened': QColor(0, 150, 0),
                'rejected': QColor(200, 0, 0),
                'pending': QColor(200, 100, 0)
            }
            if status in status_colors:
                status_item.setForeground(QBrush(status_colors[status]))
            
            self.signals_table.setItem(row, 4, status_item)
            
            # Neden
            reason_item = QTableWidgetItem(data['reason'][:50] + "..." if len(data['reason']) > 50 else data['reason'])
            reason_item.setToolTip(data['reason'])  # Tam metin tooltip'te
            self.signals_table.setItem(row, 5, reason_item)
            
            # Güven skoru
            confidence_item = QTableWidgetItem(f"{data['confidence']}%")
            self.signals_table.setItem(row, 6, confidence_item)
            
            # Detay butonu
            detail_btn = QPushButton("📊")
            detail_btn.setMaximumSize(30, 25)
            detail_btn.clicked.connect(lambda checked, s=symbol: self._show_coin_detail(s))
            self.signals_table.setCellWidget(row, 7, detail_btn)
        
        self._update_statistics()
    
    def _update_statistics(self):
        """İstatistikleri güncelle"""
        total = len(self.coin_data)
        opened = sum(1 for data in self.coin_data.values() if data['signal_status'] == 'opened')
        rejected = sum(1 for data in self.coin_data.values() if data['signal_status'] == 'rejected')
        
        success_rate = (opened / max(opened + rejected, 1)) * 100
        
        self.total_scanned_label.setText(f"📈 Taranan: {total}")
        self.positions_opened_label.setText(f"✅ Açılan: {opened}")
        self.positions_rejected_label.setText(f"❌ Reddedilen: {rejected}")
        self.success_rate_label.setText(f"🎯 Başarı: {success_rate:.1f}%")
    
    def _log_activity(self, message: str):
        """Aktivite loguna ekle"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        self.activity_log.append(log_entry)
        
        # Scroll to bottom
        cursor = self.activity_log.textCursor()
        cursor.movePosition(cursor.End)
        self.activity_log.setTextCursor(cursor)
    
    def _on_cell_double_clicked(self, row: int, column: int):
        """Hücreye çift tıklandığında"""
        if column == 0:  # Symbol column
            symbol_item = self.signals_table.item(row, 0)
            if symbol_item:
                symbol = symbol_item.text()
                self._show_coin_detail(symbol)
    
    def _show_coin_detail(self, symbol: str):
        """Coin detay penceresini göster"""
        if symbol in self.coin_data:
            detail_dialog = CoinAnalysisDialog(self.coin_data[symbol], self)
            detail_dialog.show()
    
    def _clear_data(self):
        """Verileri temizle"""
        self.coin_data.clear()
        self.signals_table.setRowCount(0)
        self.activity_log.clear()
        self._update_statistics()
        self._log_activity("🗑️ Veriler temizlendi")
    
    def _refresh_data(self):
        """Verileri yenile"""
        self._update_table()
        self._log_activity("🔄 Veriler yenilendi")
    
    def _export_data(self):
        """Verileri dışa aktar"""
        if not self.coin_data:
            self._log_activity("⚠️ Dışa aktarılacak veri yok")
            return
        
        try:
            from PySide6.QtWidgets import QFileDialog
            import json
            
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Sinyal Verilerini Kaydet",
                f"signal_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "JSON Files (*.json)"
            )
            
            if filename:
                # Datetime objeleri JSON serializable yap
                export_data = {}
                for symbol, data in self.coin_data.items():
                    export_data[symbol] = data.copy()
                    export_data[symbol]['timestamp'] = data['timestamp'].isoformat()
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                self._log_activity(f"📊 Veriler dışa aktarıldı: {filename}")
                
        except Exception as e:
            self._log_activity(f"❌ Dışa aktarma hatası: {e}")


# Helper functions for integration
def create_sample_coin_data(symbol: str, status: str = "pending") -> Dict[str, Any]:
    """Test için örnek coin verisi oluştur"""
    import random
    
    return {
        'price': random.uniform(0.1, 100.0),
        'price_change_pct': random.uniform(-10, 15),
        'signal_status': status,
        'reason': f"Test analizi - {status}",
        'confidence': random.randint(60, 95),
        'indicators': {
            'rsi': random.uniform(20, 80),
            'ema_fast': random.uniform(0.1, 100),
            'macd': random.uniform(-0.1, 0.1)
        },
        'volume': random.randint(100000, 10000000)
    } 