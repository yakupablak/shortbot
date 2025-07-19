"""
Binance WebSocket Client
Real-time fiyat ve pozisyon güncellemeleri
"""
import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urlencode
import hashlib
import hmac
import time

import websockets
from websockets import WebSocketServerProtocol

from ..utils.config import BinanceConfig
from ..utils.exceptions import WebSocketError
from ..utils.logger import get_logger

logger = get_logger("binance_ws")


class BinanceWebSocketClient:
    """Binance WebSocket Client"""
    
    def __init__(self, config: BinanceConfig):
        self.config = config
        self.api_key = config.api_key
        self.api_secret = config.api_secret
        
        # WebSocket URLs
        if config.testnet:
            self.ws_base_url = "wss://testnet.binancefuture.com"
        else:
            self.ws_base_url = "wss://fstream.binance.com"
        
        # Stream URLs
        self.public_stream_url = f"{self.ws_base_url}/ws"
        self.user_stream_url = f"{self.ws_base_url}/ws"
        
        # WebSocket bağlantıları
        self.public_ws: Optional[WebSocketServerProtocol] = None
        self.user_ws: Optional[WebSocketServerProtocol] = None
        
        # Stream yönetimi
        self.subscribed_streams: Set[str] = set()
        self.stream_handlers: Dict[str, List[Callable]] = {}
        
        # Bağlantı durumu
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        
        # Tasks
        self.public_task: Optional[asyncio.Task] = None
        self.user_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> None:
        """WebSocket bağlantılarını başlat"""
        logger.info("Binance WebSocket bağlantısı kuruluyor...")
        
        try:
            # Public streams
            self.public_task = asyncio.create_task(self._connect_public_stream())
            
            # User data stream (authenticated)
            if self.api_key and self.api_secret:
                self.user_task = asyncio.create_task(self._connect_user_stream())
            
            # Heartbeat
            self.heartbeat_task = asyncio.create_task(self._heartbeat())
            
            self.is_connected = True
            logger.info("Binance WebSocket bağlantısı kuruldu")
            
        except Exception as e:
            logger.error(f"WebSocket bağlantı hatası: {e}")
            raise WebSocketError(f"Bağlantı hatası: {e}")
    
    async def disconnect(self) -> None:
        """WebSocket bağlantılarını kapat"""
        logger.info("Binance WebSocket bağlantısı kapatılıyor...")
        self.is_connected = False
        
        # Tasks'ları iptal et
        for task in [self.public_task, self.user_task, self.heartbeat_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # WebSocket bağlantılarını kapat
        if self.public_ws:
            await self.public_ws.close()
        if self.user_ws:
            await self.user_ws.close()
        
        logger.info("Binance WebSocket bağlantısı kapatıldı")
    
    async def _connect_public_stream(self) -> None:
        """Public stream bağlantısı"""
        while self.is_connected:
            try:
                async with websockets.connect(
                    self.public_stream_url,
                    ping_interval=20,
                    ping_timeout=10
                ) as websocket:
                    self.public_ws = websocket
                    logger.info("Public stream bağlantısı kuruldu")
                    
                    # Mevcut stream'leri yeniden subscribe et
                    if self.subscribed_streams:
                        await self._resubscribe_streams()
                    
                    # Mesaj dinleme
                    async for message in websocket:
                        await self._handle_public_message(message)
                        
            except websockets.exceptions.ConnectionClosed:
                if self.is_connected:
                    logger.warning("Public stream bağlantısı kesildi, yeniden bağlanılıyor...")
                    await self._reconnect_delay()
            except Exception as e:
                logger.error(f"Public stream hatası: {e}")
                if self.is_connected:
                    await self._reconnect_delay()
    
    async def _connect_user_stream(self) -> None:
        """User data stream bağlantısı"""
        while self.is_connected:
            try:
                # Listen key al
                listen_key = await self._get_listen_key()
                if not listen_key:
                    await asyncio.sleep(30)
                    continue
                
                # User stream'e bağlan
                user_stream_url = f"{self.user_stream_url}/{listen_key}"
                
                async with websockets.connect(
                    user_stream_url,
                    ping_interval=20,
                    ping_timeout=10
                ) as websocket:
                    self.user_ws = websocket
                    logger.info("User stream bağlantısı kuruldu")
                    
                    # Mesaj dinleme
                    async for message in websocket:
                        await self._handle_user_message(message)
                        
            except websockets.exceptions.ConnectionClosed:
                if self.is_connected:
                    logger.warning("User stream bağlantısı kesildi, yeniden bağlanılıyor...")
                    await self._reconnect_delay()
            except Exception as e:
                logger.error(f"User stream hatası: {e}")
                if self.is_connected:
                    await self._reconnect_delay()
    
    async def _get_listen_key(self) -> Optional[str]:
        """User data stream için listen key al"""
        try:
            import aiohttp
            
            url = f"{self.config.api_base_url if hasattr(self.config, 'api_base_url') else 'https://fapi.binance.com'}/fapi/v1/listenKey"
            headers = {'X-MBX-APIKEY': self.api_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('listenKey')
                    else:
                        logger.error(f"Listen key alma hatası: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Listen key hatası: {e}")
            return None
    
    async def _handle_public_message(self, message: str) -> None:
        """Public stream mesajını işle"""
        try:
            data = json.loads(message)
            
            # Stream türüne göre handler çağır
            stream = data.get('stream', '')
            
            for stream_pattern, handlers in self.stream_handlers.items():
                if stream_pattern in stream:
                    for handler in handlers:
                        try:
                            await handler(data)
                        except Exception as e:
                            logger.error(f"Stream handler hatası [{stream}]: {e}")
                            
        except json.JSONDecodeError:
            logger.warning("Geçersiz JSON mesajı alındı")
        except Exception as e:
            logger.error(f"Public mesaj işleme hatası: {e}")
    
    async def _handle_user_message(self, message: str) -> None:
        """User stream mesajını işle"""
        try:
            data = json.loads(message)
            
            event_type = data.get('e', '')
            
            # Event türüne göre handler çağır
            handlers = self.stream_handlers.get(f"user_{event_type}", [])
            for handler in handlers:
                try:
                    await handler(data)
                except Exception as e:
                    logger.error(f"User event handler hatası [{event_type}]: {e}")
                    
        except json.JSONDecodeError:
            logger.warning("Geçersiz user stream JSON mesajı")
        except Exception as e:
            logger.error(f"User mesaj işleme hatası: {e}")
    
    async def _heartbeat(self) -> None:
        """WebSocket heartbeat"""
        while self.is_connected:
            try:
                # 30 dakikada bir listen key'i yenile
                await asyncio.sleep(1800)  # 30 dakika
                
                if self.user_ws and self.api_key:
                    await self._refresh_listen_key()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat hatası: {e}")
    
    async def _refresh_listen_key(self) -> None:
        """Listen key'i yenile"""
        try:
            import aiohttp
            
            url = f"{self.config.api_base_url if hasattr(self.config, 'api_base_url') else 'https://fapi.binance.com'}/fapi/v1/listenKey"
            headers = {'X-MBX-APIKEY': self.api_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.put(url, headers=headers) as response:
                    if response.status == 200:
                        logger.debug("Listen key yenilendi")
                    else:
                        logger.warning(f"Listen key yenileme hatası: {response.status}")
                        
        except Exception as e:
            logger.error(f"Listen key yenileme hatası: {e}")
    
    async def _reconnect_delay(self) -> None:
        """Yeniden bağlanma gecikmesi"""
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts > self.max_reconnect_attempts:
            logger.error("Maksimum yeniden bağlanma denemesi aşıldı")
            self.is_connected = False
            return
        
        delay = min(30, 2 ** self.reconnect_attempts)  # Exponential backoff
        logger.info(f"Yeniden bağlanma gecikmesi: {delay} saniye")
        await asyncio.sleep(delay)
    
    async def _resubscribe_streams(self) -> None:
        """Mevcut stream'leri yeniden subscribe et"""
        if not self.subscribed_streams:
            return
        
        streams = list(self.subscribed_streams)
        subscribe_message = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": int(time.time())
        }
        
        await self.public_ws.send(json.dumps(subscribe_message))
        logger.info(f"Stream'ler yeniden subscribe edildi: {len(streams)}")
    
    # Public API Methods
    async def subscribe_ticker(self, symbol: str, handler: Callable) -> None:
        """Ticker stream'ini subscribe et"""
        stream = f"{symbol.lower()}@ticker"
        await self._subscribe_stream(stream, handler)
    
    async def subscribe_kline(self, symbol: str, interval: str, handler: Callable) -> None:
        """Kline stream'ini subscribe et"""
        stream = f"{symbol.lower()}@kline_{interval}"
        await self._subscribe_stream(stream, handler)
    
    async def subscribe_book_ticker(self, symbol: str, handler: Callable) -> None:
        """Book ticker stream'ini subscribe et"""
        stream = f"{symbol.lower()}@bookTicker"
        await self._subscribe_stream(stream, handler)
    
    async def subscribe_user_data(self, handler: Callable) -> None:
        """User data stream'ini subscribe et"""
        if not self.api_key:
            raise WebSocketError("User data stream için API key gerekli")
        
        # Position updates
        self.add_stream_handler("user_ACCOUNT_UPDATE", handler)
        # Order updates  
        self.add_stream_handler("user_ORDER_TRADE_UPDATE", handler)
    
    async def _subscribe_stream(self, stream: str, handler: Callable) -> None:
        """Stream'i subscribe et"""
        self.subscribed_streams.add(stream)
        self.add_stream_handler(stream, handler)
        
        if self.public_ws:
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": [stream],
                "id": int(time.time())
            }
            
            await self.public_ws.send(json.dumps(subscribe_message))
            logger.debug(f"Stream subscribe edildi: {stream}")
    
    async def unsubscribe_stream(self, stream: str) -> None:
        """Stream subscription'ını iptal et"""
        if stream in self.subscribed_streams:
            self.subscribed_streams.remove(stream)
            
            if self.public_ws:
                unsubscribe_message = {
                    "method": "UNSUBSCRIBE", 
                    "params": [stream],
                    "id": int(time.time())
                }
                
                await self.public_ws.send(json.dumps(unsubscribe_message))
                logger.debug(f"Stream unsubscribe edildi: {stream}")
    
    def add_stream_handler(self, stream: str, handler: Callable) -> None:
        """Stream handler ekle"""
        if stream not in self.stream_handlers:
            self.stream_handlers[stream] = []
        self.stream_handlers[stream].append(handler)
    
    def remove_stream_handler(self, stream: str, handler: Callable) -> None:
        """Stream handler kaldır"""
        if stream in self.stream_handlers:
            try:
                self.stream_handlers[stream].remove(handler)
            except ValueError:
                pass 