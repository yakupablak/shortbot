"""
Teknik Analiz ve Sinyal Üretim Sistemi
15+ indikatör desteği ile short sinyal oluşturur
"""
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from decimal import Decimal

import numpy as np
import pandas as pd

try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False
    print("TA-Lib bulunamadı. Basit indikatörler kullanılacak.")

from ..utils.config import IndicatorConfig, SignalLogic
from ..utils.exceptions import IndicatorCalculationError
from ..utils.logger import get_logger

logger = get_logger("signals")


class TechnicalIndicators:
    """Teknik indikatör hesaplamaları"""
    
    @staticmethod
    def sma(data: List[float], period: int) -> List[float]:
        """Simple Moving Average"""
        if len(data) < period:
            return [np.nan] * len(data)
        
        result = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(np.nan)
            else:
                result.append(sum(data[i-period+1:i+1]) / period)
        
        return result
    
    @staticmethod
    def ema(data: List[float], period: int) -> List[float]:
        """Exponential Moving Average"""
        if len(data) == 0:
            return []
        
        multiplier = 2.0 / (period + 1)
        result = [data[0]]  # İlk değer
        
        for i in range(1, len(data)):
            ema_val = (data[i] * multiplier) + (result[-1] * (1 - multiplier))
            result.append(ema_val)
        
        return result
    
    @staticmethod
    def rsi(data: List[float], period: int = 14) -> List[float]:
        """Relative Strength Index"""
        if HAS_TALIB:
            return talib.RSI(np.array(data), timeperiod=period).tolist()
        
        # Manuel RSI hesaplama
        if len(data) < period + 1:
            return [np.nan] * len(data)
        
        deltas = [data[i] - data[i-1] for i in range(1, len(data))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        # İlk RS hesapla
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        rs_values = []
        rsi_values = [np.nan] * period
        
        for i in range(period, len(gains)):
            if avg_loss == 0:
                rsi_val = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_val = 100.0 - (100.0 / (1.0 + rs))
            
            rsi_values.append(rsi_val)
            
            # Sonraki iterasyon için ortalama güncelle
            if i < len(gains) - 1:
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        return [np.nan] + rsi_values
    
    @staticmethod
    def macd(data: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[float], List[float], List[float]]:
        """MACD - Moving Average Convergence Divergence"""
        if HAS_TALIB:
            macd_line, signal_line, histogram = talib.MACD(np.array(data), fast, slow, signal)
            return macd_line.tolist(), signal_line.tolist(), histogram.tolist()
        
        # Manuel MACD hesaplama
        ema_fast = TechnicalIndicators.ema(data, fast)
        ema_slow = TechnicalIndicators.ema(data, slow)
        
        macd_line = []
        for i in range(len(data)):
            if np.isnan(ema_fast[i]) or np.isnan(ema_slow[i]):
                macd_line.append(np.nan)
            else:
                macd_line.append(ema_fast[i] - ema_slow[i])
        
        # Signal line (MACD'nin EMA'sı)
        signal_line = TechnicalIndicators.ema([x for x in macd_line if not np.isnan(x)], signal)
        
        # Eksik değerleri doldur
        while len(signal_line) < len(macd_line):
            signal_line.insert(0, np.nan)
        
        # Histogram
        histogram = []
        for i in range(len(macd_line)):
            if np.isnan(macd_line[i]) or np.isnan(signal_line[i]):
                histogram.append(np.nan)
            else:
                histogram.append(macd_line[i] - signal_line[i])
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(data: List[float], period: int = 20, std: float = 2.0) -> Tuple[List[float], List[float], List[float]]:
        """Bollinger Bands"""
        if HAS_TALIB:
            upper, middle, lower = talib.BBANDS(np.array(data), timeperiod=period, nbdevup=std, nbdevdn=std)
            return upper.tolist(), middle.tolist(), lower.tolist()
        
        # Manuel hesaplama
        sma_values = TechnicalIndicators.sma(data, period)
        upper, lower = [], []
        
        for i in range(len(data)):
            if i < period - 1:
                upper.append(np.nan)
                lower.append(np.nan)
            else:
                # Standart sapma hesapla
                subset = data[i-period+1:i+1]
                mean = sma_values[i]
                variance = sum((x - mean) ** 2 for x in subset) / period
                std_dev = math.sqrt(variance)
                
                upper.append(mean + (std * std_dev))
                lower.append(mean - (std * std_dev))
        
        return upper, sma_values, lower
    
    @staticmethod
    def atr(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[float]:
        """Average True Range"""
        if HAS_TALIB:
            return talib.ATR(np.array(high), np.array(low), np.array(close), timeperiod=period).tolist()
        
        # Manuel ATR hesaplama
        tr_values = []
        
        for i in range(len(close)):
            if i == 0:
                tr = high[i] - low[i]
            else:
                tr = max(
                    high[i] - low[i],
                    abs(high[i] - close[i-1]),
                    abs(low[i] - close[i-1])
                )
            tr_values.append(tr)
        
        return TechnicalIndicators.sma(tr_values, period)
    
    @staticmethod
    def stochastic_rsi(data: List[float], period: int = 14, k_period: int = 3, d_period: int = 3) -> Tuple[List[float], List[float]]:
        """Stochastic RSI"""
        rsi_values = TechnicalIndicators.rsi(data, period)
        
        # RSI'nin Stochastic hesaplama
        k_values = []
        for i in range(len(rsi_values)):
            if i < period - 1:
                k_values.append(np.nan)
                continue
            
            rsi_subset = [x for x in rsi_values[i-period+1:i+1] if not np.isnan(x)]
            if len(rsi_subset) == 0:
                k_values.append(np.nan)
                continue
            
            rsi_min = min(rsi_subset)
            rsi_max = max(rsi_subset)
            
            if rsi_max == rsi_min:
                k_val = 50.0
            else:
                k_val = ((rsi_values[i] - rsi_min) / (rsi_max - rsi_min)) * 100.0
            
            k_values.append(k_val)
        
        # %K ve %D hesapla
        k_smooth = TechnicalIndicators.sma([x for x in k_values if not np.isnan(x)], k_period)
        d_values = TechnicalIndicators.sma([x for x in k_smooth if not np.isnan(x)], d_period)
        
        # Listeleri eşitle
        while len(k_smooth) < len(k_values):
            k_smooth.insert(0, np.nan)
        while len(d_values) < len(k_values):
            d_values.insert(0, np.nan)
        
        return k_smooth, d_values


class DivergenceDetector:
    """Divergence (uyumsuzluk) tespiti"""
    
    @staticmethod
    def find_peaks_and_troughs(data: List[float], min_distance: int = 5) -> Tuple[List[int], List[int]]:
        """Tepe ve dip noktalarını bul"""
        if len(data) < min_distance * 2 + 1:
            return [], []
        
        peaks = []
        troughs = []
        
        for i in range(min_distance, len(data) - min_distance):
            is_peak = True
            is_trough = True
            
            # Çevresindeki değerleri kontrol et
            for j in range(i - min_distance, i + min_distance + 1):
                if j == i:
                    continue
                
                if data[j] >= data[i]:
                    is_peak = False
                if data[j] <= data[i]:
                    is_trough = False
            
            if is_peak:
                peaks.append(i)
            if is_trough:
                troughs.append(i)
        
        return peaks, troughs
    
    @staticmethod
    def detect_bearish_divergence(prices: List[float], indicator: List[float], min_size: float = 2.0) -> bool:
        """Bearish divergence tespiti (short sinyal)"""
        if len(prices) < 20 or len(indicator) < 20:
            return False
        
        # Son 50 bar içinde ara
        price_subset = prices[-50:]
        indicator_subset = indicator[-50:]
        
        price_peaks, _ = DivergenceDetector.find_peaks_and_troughs(price_subset)
        indicator_peaks, _ = DivergenceDetector.find_peaks_and_troughs(indicator_subset)
        
        # En az 2 tepe olmalı
        if len(price_peaks) < 2 or len(indicator_peaks) < 2:
            return False
        
        # Son iki tepeyi kontrol et
        last_price_peak = price_peaks[-1]
        prev_price_peak = price_peaks[-2] 
        
        last_ind_peak = indicator_peaks[-1]
        prev_ind_peak = indicator_peaks[-2]
        
        # Fiyat yüksek tepe, indikatör düşük tepe
        price_higher = price_subset[last_price_peak] > price_subset[prev_price_peak]
        indicator_lower = indicator_subset[last_ind_peak] < indicator_subset[prev_ind_peak]
        
        if price_higher and indicator_lower:
            # Divergence büyüklüğü yeterli mi?
            price_diff = abs(price_subset[last_price_peak] - price_subset[prev_price_peak]) / price_subset[prev_price_peak] * 100
            return price_diff >= min_size
        
        return False


class CandlestickPatterns:
    """Mum çubuk pattern analizi"""
    
    @staticmethod
    def analyze_wick_body_ratio(open_price: float, high: float, low: float, close: float) -> Dict[str, float]:
        """Wick/Body oranı analizi"""
        body = abs(close - open_price)
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        total_wick = upper_wick + lower_wick
        
        if body == 0:
            body = 0.0001  # Division by zero koruması
        
        return {
            'body': body,
            'upper_wick': upper_wick,
            'lower_wick': lower_wick,
            'total_wick': total_wick,
            'wick_body_ratio': total_wick / body,
            'upper_wick_ratio': upper_wick / (high - low) if high != low else 0
        }
    
    @staticmethod
    def is_shooting_star(open_price: float, high: float, low: float, close: float, min_ratio: float = 2.0) -> bool:
        """Shooting Star pattern (bearish)"""
        analysis = CandlestickPatterns.analyze_wick_body_ratio(open_price, high, low, close)
        
        # Üst fitil uzun, alt fitil kısa, küçük body
        return (analysis['upper_wick_ratio'] > 0.6 and 
                analysis['wick_body_ratio'] >= min_ratio and
                analysis['upper_wick'] > analysis['lower_wick'] * 2)
    
    @staticmethod
    def is_doji(open_price: float, high: float, low: float, close: float, threshold: float = 0.1) -> bool:
        """Doji pattern (indecision)"""
        total_range = high - low
        body = abs(close - open_price)
        
        if total_range == 0:
            return False
        
        return (body / total_range) <= threshold


class StrategyEngine:
    """Ana strateji motoru"""
    
    def __init__(self, config: IndicatorConfig, signal_logic: SignalLogic):
        self.config = config
        self.signal_logic = signal_logic
        self.divergence_detector = DivergenceDetector()
        
    def calculate_indicators(self, klines: List[List[Any]]) -> Dict[str, List[float]]:
        """Tüm indikatörleri hesapla"""
        if len(klines) < 50:
            raise IndicatorCalculationError("Yetersiz veri - en az 50 mum gerekli")
        
        # OHLCV verilerini parse et
        opens = [float(k[1]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        closes = [float(k[4]) for k in klines]
        volumes = [float(k[5]) for k in klines]
        
        indicators = {}
        
        try:
            # RSI
            indicators['rsi'] = TechnicalIndicators.rsi(closes, self.config.rsi_period)
            
            # EMA
            indicators['ema_fast'] = TechnicalIndicators.ema(closes, self.config.ema_fast)
            indicators['ema_slow'] = TechnicalIndicators.ema(closes, self.config.ema_slow)
            
            # SMA
            indicators['sma'] = TechnicalIndicators.sma(closes, self.config.sma_period)
            
            # MACD
            macd_line, signal_line, histogram = TechnicalIndicators.macd(
                closes, self.config.macd_fast, self.config.macd_slow, self.config.macd_signal
            )
            indicators['macd'] = macd_line
            indicators['macd_signal'] = signal_line
            indicators['macd_histogram'] = histogram
            
            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = TechnicalIndicators.bollinger_bands(
                closes, self.config.bb_period, self.config.bb_std
            )
            indicators['bb_upper'] = bb_upper
            indicators['bb_middle'] = bb_middle
            indicators['bb_lower'] = bb_lower
            
            # ATR
            indicators['atr'] = TechnicalIndicators.atr(highs, lows, closes, self.config.atr_period)
            
            # Stochastic RSI
            stoch_k, stoch_d = TechnicalIndicators.stochastic_rsi(
                closes, self.config.stoch_rsi_period, self.config.stoch_k_period, self.config.stoch_d_period
            )
            indicators['stoch_k'] = stoch_k
            indicators['stoch_d'] = stoch_d
            
        except Exception as e:
            logger.error(f"İndikatör hesaplama hatası: {e}")
            raise IndicatorCalculationError(f"İndikatör hesaplama hatası: {e}")
        
        return indicators
    
    def generate_short_signals(self, klines: List[List[Any]]) -> Dict[str, Union[bool, float]]:
        """Short sinyalleri üret"""
        indicators = self.calculate_indicators(klines)
        signals = {}
        
        # Son değerleri al
        current_idx = -1
        
        try:
            # RSI Overbought
            if len(indicators['rsi']) > abs(current_idx):
                current_rsi = indicators['rsi'][current_idx]
                signals['rsi_overbought'] = current_rsi > self.config.rsi_overbought
            
            # RSI Divergence
            if len(indicators['rsi']) > 50:
                closes = [float(k[4]) for k in klines]
                signals['rsi_divergence'] = self.divergence_detector.detect_bearish_divergence(
                    closes, indicators['rsi'], self.config.rsi_divergence_min_size
                )
            
            # EMA Crossover (Fast below Slow = Bearish)
            if len(indicators['ema_fast']) > abs(current_idx) and len(indicators['ema_slow']) > abs(current_idx):
                signals['ema_bearish'] = indicators['ema_fast'][current_idx] < indicators['ema_slow'][current_idx]
            
            # Price below SMA
            current_close = float(klines[current_idx][4])
            if len(indicators['sma']) > abs(current_idx):
                signals['price_below_sma'] = current_close < indicators['sma'][current_idx]
            
            # MACD Bearish
            if (len(indicators['macd']) > abs(current_idx) and 
                len(indicators['macd_signal']) > abs(current_idx)):
                signals['macd_bearish'] = (indicators['macd'][current_idx] < indicators['macd_signal'][current_idx] and
                                          indicators['macd'][current_idx] < 0)
            
            # Bollinger Bands - Price near upper band (overbought)
            if len(indicators['bb_upper']) > abs(current_idx):
                bb_position = (current_close - indicators['bb_lower'][current_idx]) / \
                             (indicators['bb_upper'][current_idx] - indicators['bb_lower'][current_idx])
                signals['bb_overbought'] = bb_position > 0.8
            
            # Stochastic RSI Overbought
            if len(indicators['stoch_k']) > abs(current_idx):
                signals['stoch_overbought'] = indicators['stoch_k'][current_idx] > 80
            
            # Candlestick Pattern
            if len(klines) > 0:
                last_candle = klines[current_idx]
                open_price = float(last_candle[1])
                high = float(last_candle[2])
                low = float(last_candle[3])
                close = float(last_candle[4])
                
                # Wick/Body ratio
                analysis = CandlestickPatterns.analyze_wick_body_ratio(open_price, high, low, close)
                signals['wick_body_ratio'] = analysis['wick_body_ratio'] >= self.config.wick_body_ratio
                
                # Shooting star
                signals['shooting_star'] = CandlestickPatterns.is_shooting_star(open_price, high, low, close)
            
            # Custom expression
            if self.config.custom_expression:
                try:
                    # Güvenli evaluation için sınırlı context
                    context = {
                        'rsi': indicators['rsi'][current_idx] if len(indicators['rsi']) > abs(current_idx) else 0,
                        'close': current_close,
                        'ema_fast': indicators['ema_fast'][current_idx] if len(indicators['ema_fast']) > abs(current_idx) else 0,
                        'ema_slow': indicators['ema_slow'][current_idx] if len(indicators['ema_slow']) > abs(current_idx) else 0,
                        'macd': indicators['macd'][current_idx] if len(indicators['macd']) > abs(current_idx) else 0
                    }
                    
                    signals['custom'] = eval(self.config.custom_expression, {"__builtins__": {}}, context)
                except:
                    signals['custom'] = False
            
        except Exception as e:
            logger.error(f"Sinyal üretim hatası: {e}")
            return {'error': True, 'message': str(e)}
        
        return signals
    
    def should_open_short(self, klines: List[List[Any]]) -> Tuple[bool, Dict[str, Any]]:
        """Short pozisyon açılmalı mı?"""
        if not self.config.enabled:
            return False, {'reason': 'İndikatörler devre dışı'}
        
        signals = self.generate_short_signals(klines)
        
        if 'error' in signals:
            return False, signals
        
        # Sinyal mantığına göre karar ver
        true_signals = sum(1 for v in signals.values() if v is True)
        total_signals = len([v for v in signals.values() if isinstance(v, bool)])
        
        if total_signals == 0:
            return False, {'reason': 'Hesaplanabilir sinyal yok'}
        
        decision = False
        
        if self.signal_logic == SignalLogic.ALL_TRUE:
            decision = all(v is True for v in signals.values() if isinstance(v, bool))
            reason = f"Tüm sinyaller pozitif: {true_signals}/{total_signals}"
        
        elif self.signal_logic == SignalLogic.MAJORITY_TRUE:
            decision = true_signals > total_signals / 2
            reason = f"Çoğunluk pozitif: {true_signals}/{total_signals}"
        
        elif self.signal_logic == SignalLogic.ANY_TRUE:
            decision = true_signals > 0
            reason = f"En az bir sinyal pozitif: {true_signals}/{total_signals}"
        
        return decision, {
            'signals': signals,
            'true_count': true_signals,
            'total_count': total_signals,
            'reason': reason
        } 