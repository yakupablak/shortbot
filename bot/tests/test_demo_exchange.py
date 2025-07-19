"""
Test: Demo Exchange
"""
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from bot.core.demo_exchange import DemoExchange, DemoTicker
from bot.utils.config import BotSettings


class TestDemoTicker:
    """DemoTicker test sınıfı"""
    
    def test_initialization(self):
        """Ticker başlatma testi"""
        ticker = DemoTicker("BTCUSDT", 45000.0)
        
        assert ticker.symbol == "BTCUSDT"
        assert ticker.base_price == Decimal('45000.0')
        assert ticker.current_price == ticker.base_price
        assert ticker.high_24h == ticker.base_price
        assert ticker.low_24h == ticker.base_price
    
    def test_price_update(self):
        """Fiyat güncelleme testi"""
        ticker = DemoTicker("BTCUSDT", 45000.0)
        original_price = ticker.current_price
        
        # Fiyat güncellemesi
        new_price = ticker.update_price()
        
        assert isinstance(new_price, Decimal)
        # Fiyat değişmiş olmalı (volatilite nedeniyle)
        # Not: Random olduğu için kesin assertion yapmıyoruz
    
    def test_price_change_calculation(self):
        """24h fiyat değişimi hesaplaması"""
        ticker = DemoTicker("BTCUSDT", 45000.0)
        
        # İlk durumda değişim %0 olmalı
        assert ticker.price_change_24h == 0.0
        
        # Fiyatı manuel değiştir
        ticker.current_price = Decimal('46800.0')  # %4 artış
        
        change_pct = ticker.price_change_24h
        assert abs(change_pct - 4.0) < 0.1  # Yaklaşık %4
    
    def test_ticker_dict_format(self):
        """Ticker dict formatı testi"""
        ticker = DemoTicker("ETHUSDT", 2500.0)
        ticker_dict = ticker.to_ticker_dict()
        
        required_fields = ['symbol', 'lastPrice', 'priceChangePercent', 
                          'highPrice', 'lowPrice', 'volume', 'count']
        
        for field in required_fields:
            assert field in ticker_dict
        
        assert ticker_dict['symbol'] == 'ETHUSDT'
        assert isinstance(ticker_dict['count'], int)


class TestDemoExchange:
    """DemoExchange test sınıfı"""
    
    @pytest.fixture
    def settings(self):
        """Test settings"""
        return BotSettings(demo_balance=1000.0)
    
    @pytest.fixture
    def exchange(self, settings):
        """Test exchange"""
        return DemoExchange(settings)
    
    def test_initialization(self, exchange):
        """Exchange başlatma testi"""
        assert exchange.portfolio is not None
        assert exchange.portfolio.wallet.balance == Decimal('1000.0')
        assert len(exchange.tickers) == 0
    
    @pytest.mark.asyncio
    async def test_connection(self, exchange):
        """Bağlantı testi"""
        await exchange.connect()
        # Demo exchange için bağlantı her zaman başarılı
        
        await exchange.disconnect()
        # Disconnect işlemi de sorunsuz çalışmalı
    
    @pytest.mark.asyncio
    async def test_server_time(self, exchange):
        """Server time endpoint"""
        result = await exchange.get_server_time()
        
        assert 'serverTime' in result
        assert isinstance(result['serverTime'], int)
    
    @pytest.mark.asyncio
    async def test_ticker_creation(self, exchange):
        """Ticker oluşturma testi"""
        symbol = 'BTCUSDT'
        
        # İlk çağrıda ticker oluşturulmalı
        ticker = exchange._ensure_ticker(symbol)
        
        assert ticker.symbol == symbol
        assert symbol in exchange.tickers
        
        # İkinci çağrıda aynı ticker dönmeli
        ticker2 = exchange._ensure_ticker(symbol)
        assert ticker is ticker2
    
    @pytest.mark.asyncio
    async def test_24hr_ticker(self, exchange):
        """24h ticker endpoint"""
        # Tek sembol
        btc_ticker = await exchange.get_24hr_ticker('BTCUSDT')
        
        assert btc_ticker['symbol'] == 'BTCUSDT'
        assert 'lastPrice' in btc_ticker
        assert 'priceChangePercent' in btc_ticker
        
        # Tüm semboller
        all_tickers = await exchange.get_24hr_ticker()
        
        assert isinstance(all_tickers, list)
        assert len(all_tickers) > 0
    
    @pytest.mark.asyncio
    async def test_klines_generation(self, exchange):
        """Kline veri üretimi"""
        symbol = 'BTCUSDT'
        interval = '1m'
        limit = 100
        
        klines = await exchange.get_klines(symbol, interval, limit)
        
        assert isinstance(klines, list)
        assert len(klines) == limit
        
        # Her kline 12 alan içermeli
        for kline in klines:
            assert len(kline) == 12
            
            # OHLCV alanları numeric olmalı
            assert isinstance(float(kline[1]), float)  # Open
            assert isinstance(float(kline[2]), float)  # High
            assert isinstance(float(kline[3]), float)  # Low
            assert isinstance(float(kline[4]), float)  # Close
            assert isinstance(float(kline[5]), float)  # Volume
    
    @pytest.mark.asyncio
    async def test_account_info(self, exchange):
        """Hesap bilgileri endpoint"""
        account_info = await exchange.get_account_info()
        
        assert 'totalWalletBalance' in account_info
        assert 'availableBalance' in account_info
        assert float(account_info['totalWalletBalance']) == 1000.0
    
    @pytest.mark.asyncio
    async def test_balance_info(self, exchange):
        """Bakiye bilgileri endpoint"""
        balance_info = await exchange.get_balance()
        
        assert isinstance(balance_info, list)
        assert len(balance_info) > 0
        
        usdt_balance = balance_info[0]
        assert usdt_balance['asset'] == 'USDT'
        assert float(usdt_balance['balance']) == 1000.0
    
    @pytest.mark.asyncio
    async def test_create_order(self, exchange):
        """Emir oluşturma testi"""
        symbol = 'BTCUSDT'
        side = 'SELL'  # Short
        order_type = 'MARKET'
        quantity = '0.001'
        
        # Emir oluştur
        order_result = await exchange.create_order(
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity
        )
        
        assert order_result['symbol'] == symbol
        assert order_result['status'] == 'FILLED'
        assert 'orderId' in order_result
        
        # Portföyde pozisyon oluşmuş olmalı
        position = exchange.portfolio.get_position(symbol)
        assert position is not None
        assert position.symbol == symbol
        assert position.side.value == 'SHORT'
    
    @pytest.mark.asyncio
    async def test_insufficient_balance(self, exchange):
        """Yetersiz bakiye testi"""
        symbol = 'BTCUSDT'
        
        # Çok büyük bir pozisyon açmaya çalış
        from bot.utils.exceptions import InsufficientBalanceError
        
        with pytest.raises(InsufficientBalanceError):
            await exchange.create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity='100'  # Çok büyük miktar
            )
    
    @pytest.mark.asyncio
    async def test_invalid_symbol(self, exchange):
        """Geçersiz sembol testi"""
        from bot.utils.exceptions import InvalidSymbolError
        
        # Exchange'de olmayan bir sembol
        with pytest.raises(InvalidSymbolError):
            await exchange.create_order(
                symbol='INVALID',
                side='SELL', 
                type='MARKET',
                quantity='0.001'
            )
    
    @pytest.mark.asyncio
    async def test_top_gainers(self, exchange):
        """En çok yükselen coinler"""
        gainers = await exchange.get_top_gainers(limit=5)
        
        assert isinstance(gainers, list)
        assert len(gainers) <= 5
        
        if gainers:
            # İlk eleman en çok yükselmiş olmalı
            first_gainer = gainers[0]
            assert 'symbol' in first_gainer
            assert 'priceChangePercent' in first_gainer
            assert first_gainer['symbol'].endswith('USDT')
    
    @pytest.mark.asyncio
    async def test_position_monitoring(self, exchange):
        """Pozisyon takip testi"""
        symbol = 'BTCUSDT'
        
        # Pozisyon aç
        await exchange.create_order(
            symbol=symbol,
            side='SELL',
            type='MARKET',
            quantity='0.001'
        )
        
        # İlk durumda açık pozisyon var
        positions = exchange.portfolio.get_open_positions()
        assert len(positions) == 1
        
        # Market data güncelle
        exchange.update_positions_mark_prices()
        
        # TP/Liquidation kontrol
        exchange.check_liquidations_and_tps()
        
        # Pozisyon hâlâ açık olmalı (TP/liq tetiklenmemişse)
        positions_after = exchange.portfolio.get_open_positions()
        # Bu test market hareketlerine bağlı, kesin assertion yapmıyoruz
    
    def test_commission_calculation(self, exchange):
        """Komisyon hesaplama testi"""
        assert exchange.maker_commission == Decimal('0.0002')
        assert exchange.taker_commission == Decimal('0.0004')
        
        # Komisyon Binance futures oranlarında olmalı


class TestDemoExchangeIntegration:
    """Entegrasyon testleri"""
    
    @pytest.mark.asyncio
    async def test_full_trading_cycle(self):
        """Tam işlem döngüsü testi"""
        settings = BotSettings(demo_balance=2000.0)
        exchange = DemoExchange(settings)
        
        symbol = 'ETHUSDT'
        
        # 1. Pozisyon aç
        order_result = await exchange.create_order(
            symbol=symbol,
            side='SELL',
            type='MARKET',
            quantity='0.01'
        )
        
        assert order_result['status'] == 'FILLED'
        
        # 2. Pozisyon kontrol
        position = exchange.portfolio.get_position(symbol)
        assert position is not None
        assert position.symbol == symbol
        
        # 3. Market data güncelle
        exchange.update_positions_mark_prices()
        
        # 4. Pozisyon manuel kapat
        close_result = await exchange.create_order(
            symbol=symbol,
            side='BUY',  # Short pozisyonu kapatmak için BUY
            type='MARKET',
            quantity=str(position.size),
            reduce_only=True
        )
        
        # Kapanış işlemi başarılı olmalı
        assert close_result['status'] == 'FILLED'
    
    @pytest.mark.asyncio
    async def test_multiple_positions(self):
        """Çoklu pozisyon testi"""
        settings = BotSettings(demo_balance=5000.0)
        exchange = DemoExchange(settings)
        
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
        
        # Birden fazla pozisyon aç
        for symbol in symbols:
            await exchange.create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity='0.001'
            )
        
        # Tüm pozisyonlar açılmış olmalı
        positions = exchange.portfolio.get_open_positions()
        assert len(positions) == len(symbols)
        
        # Her sembol için pozisyon var mı kontrol
        position_symbols = [p.symbol for p in positions]
        for symbol in symbols:
            assert symbol in position_symbols 