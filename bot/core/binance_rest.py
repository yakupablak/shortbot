"""
Binance Futures REST API Client
Asenkron HTTP istekleri ve API yönetimi
"""
import hashlib
import hmac
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode

import aiohttp
from aiohttp import ClientSession

from ..utils.config import BinanceConfig
from ..utils.exceptions import BinanceAPIError, APIError
from ..utils.logger import get_logger

logger = get_logger("binance_rest")


class BinanceRestClient:
    """Binance Futures REST API Client"""
    
    def __init__(self, config: BinanceConfig):
        self.config = config
        self.api_key = config.api_key
        self.api_secret = config.api_secret
        
        # Base URLs
        if config.testnet:
            self.base_url = "https://testnet.binancefuture.com"
        else:
            self.base_url = "https://fapi.binance.com"
        
        self.session: Optional[ClientSession] = None
        
        # Rate limiting
        self.last_request_time = 0
        self.request_count = 0
        self.rate_limit_window = 60  # saniye
    
    async def __aenter__(self):
        """Async context manager giriş"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager çıkış"""
        await self.disconnect()
    
    async def connect(self) -> None:
        """HTTP session başlat"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.info("Binance REST client bağlantısı kuruldu")
    
    async def disconnect(self) -> None:
        """HTTP session kapat"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("Binance REST client bağlantısı kapatıldı")
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """HMAC SHA256 imza oluştur"""
        if not self.api_secret:
            raise BinanceAPIError("API Secret gerekli")
        
        query_string = urlencode(params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _add_auth_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Authentication parametreleri ekle"""
        params['timestamp'] = int(time.time() * 1000)
        params['recvWindow'] = 5000
        
        signature = self._generate_signature(params)
        params['signature'] = signature
        
        return params
    
    async def _rate_limit_check(self) -> None:
        """Rate limit kontrol"""
        current_time = time.time()
        
        # Dakika başına reset
        if current_time - self.last_request_time > self.rate_limit_window:
            self.request_count = 0
            self.last_request_time = current_time
        
        # Rate limit kontrolü
        if self.request_count >= self.config.requests_per_minute:
            sleep_time = self.rate_limit_window - (current_time - self.last_request_time)
            if sleep_time > 0:
                logger.warning(f"Rate limit aşıldı, {sleep_time:.1f}s bekleniyor")
                import asyncio
                await asyncio.sleep(sleep_time)
                self.request_count = 0
                self.last_request_time = time.time()
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        authenticated: bool = False
    ) -> Dict[str, Any]:
        """HTTP isteği gönder"""
        if not self.session:
            await self.connect()
        
        await self._rate_limit_check()
        
        url = f"{self.base_url}{endpoint}"
        headers = {}
        
        if authenticated and self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        
        if params is None:
            params = {}
        
        if authenticated:
            params = self._add_auth_params(params)
        
        try:
            self.request_count += 1
            
            if method.upper() == 'GET':
                async with self.session.get(url, params=params, headers=headers) as response:
                    return await self._handle_response(response)
            elif method.upper() == 'POST':
                async with self.session.post(url, data=params, headers=headers) as response:
                    return await self._handle_response(response)
            elif method.upper() == 'DELETE':
                async with self.session.delete(url, params=params, headers=headers) as response:
                    return await self._handle_response(response)
            else:
                raise APIError(f"Desteklenmeyen HTTP method: {method}")
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP istek hatası: {e}")
            raise APIError(f"HTTP istek hatası: {e}")
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """HTTP yanıtını işle"""
        try:
            data = await response.json()
        except Exception:
            text = await response.text()
            logger.error(f"JSON parse hatası: {text}")
            raise BinanceAPIError("Geçersiz JSON yanıtı")
        
        if response.status == 200:
            return data
        
        # Binance API error
        error_code = data.get('code', response.status)
        error_msg = data.get('msg', 'Bilinmeyen hata')
        
        logger.error(f"Binance API hatası [{error_code}]: {error_msg}")
        raise BinanceAPIError(error_msg, error_code)
    
    # Public endpoints
    async def get_server_time(self) -> Dict[str, Any]:
        """Sunucu zamanını al"""
        return await self._make_request('GET', '/fapi/v1/time')
    
    async def get_exchange_info(self) -> Dict[str, Any]:
        """Exchange bilgilerini al"""
        return await self._make_request('GET', '/fapi/v1/exchangeInfo')
    
    async def get_24hr_ticker(self, symbol: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """24 saatlik ticker bilgisi"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        return await self._make_request('GET', '/fapi/v1/ticker/24hr', params)
    
    async def get_ticker_price(self, symbol: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Güncel fiyat bilgisi"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        return await self._make_request('GET', '/fapi/v1/ticker/price', params)
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 500, 
                         start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[List[Any]]:
        """Kline/mum verileri"""
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': min(limit, 1500)  # Binance limiti
        }
        
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        return await self._make_request('GET', '/fapi/v1/klines', params)
    
    # Authenticated endpoints
    async def get_account_info(self) -> Dict[str, Any]:
        """Hesap bilgileri"""
        return await self._make_request('GET', '/fapi/v2/account', authenticated=True)
    
    async def get_balance(self) -> List[Dict[str, Any]]:
        """Bakiye bilgileri"""
        return await self._make_request('GET', '/fapi/v2/balance', authenticated=True)
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Aktif pozisyonlar"""
        return await self._make_request('GET', '/fapi/v2/positionRisk', authenticated=True)
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Açık emirler"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        return await self._make_request('GET', '/fapi/v1/openOrders', params, authenticated=True)
    
    async def create_order(
        self,
        symbol: str,
        side: str,
        type: str,
        quantity: Union[str, Decimal],
        price: Optional[Union[str, Decimal]] = None,
        stop_price: Optional[Union[str, Decimal]] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """Yeni emir oluştur"""
        params = {
            'symbol': symbol,
            'side': side,
            'type': type,
            'quantity': str(quantity),
            'timeInForce': time_in_force
        }
        
        if price is not None:
            params['price'] = str(price)
        if stop_price is not None:
            params['stopPrice'] = str(stop_price)
        if reduce_only:
            params['reduceOnly'] = 'true'
        
        return await self._make_request('POST', '/fapi/v1/order', params, authenticated=True)
    
    async def cancel_order(self, symbol: str, order_id: Optional[str] = None,
                          client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """Emri iptal et"""
        params = {'symbol': symbol}
        
        if order_id:
            params['orderId'] = order_id
        elif client_order_id:
            params['origClientOrderId'] = client_order_id
        else:
            raise APIError("order_id veya client_order_id gerekli")
        
        return await self._make_request('DELETE', '/fapi/v1/order', params, authenticated=True)
    
    async def cancel_all_orders(self, symbol: str) -> Dict[str, Any]:
        """Tüm emirleri iptal et"""
        params = {'symbol': symbol}
        return await self._make_request('DELETE', '/fapi/v1/allOpenOrders', params, authenticated=True)
    
    async def change_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Kaldıraç değiştir"""
        params = {
            'symbol': symbol,
            'leverage': leverage
        }
        return await self._make_request('POST', '/fapi/v1/leverage', params, authenticated=True)
    
    async def change_margin_type(self, symbol: str, margin_type: str) -> Dict[str, Any]:
        """Marjin tipini değiştir (ISOLATED/CROSSED)"""
        params = {
            'symbol': symbol,
            'marginType': margin_type
        }
        return await self._make_request('POST', '/fapi/v1/marginType', params, authenticated=True)
    
    # Helper methods
    async def get_top_gainers(self, limit: int = 20) -> List[Dict[str, Any]]:
        """En çok yükselen coinleri al"""
        tickers = await self.get_24hr_ticker()
        
        # USDT perpetual kontratları filtrele
        usdt_tickers = [
            ticker for ticker in tickers 
            if ticker['symbol'].endswith('USDT') and 
               not ticker['symbol'].endswith('_') and  # Quarterly'leri çıkar
               ticker['count'] > 1000  # Yeterli volume
        ]
        
        # Price change percent'e göre sırala
        sorted_tickers = sorted(
            usdt_tickers,
            key=lambda x: float(x['priceChangePercent']),
            reverse=True
        )
        
        return sorted_tickers[:limit]
    
    async def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Sembol bilgilerini al"""
        exchange_info = await self.get_exchange_info()
        
        for symbol_info in exchange_info.get('symbols', []):
            if symbol_info['symbol'] == symbol:
                return symbol_info
        
        return None
    
    async def test_connection(self) -> bool:
        """Bağlantı testi"""
        try:
            await self.get_server_time()
            logger.info("Binance bağlantı testi başarılı")
            return True
        except Exception as e:
            logger.error(f"Binance bağlantı testi başarısız: {e}")
            return False 