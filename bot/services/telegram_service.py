"""
Telegram Bot Servisi
Bildirimler, uzaktan komut yönetimi, durum raporları
"""
import asyncio
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, BotCommand
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramAPIError

from ..utils.config import TelegramConfig, TradingMode
from ..utils.exceptions import TelegramError
from ..utils.logger import get_logger
from ..core.engine import TradeEngine, TradingEvent

logger = get_logger("telegram_service")


class TelegramService:
    """Telegram bot servisi"""
    
    def __init__(self, config: TelegramConfig):
        self.config = config
        self.bot: Optional[Bot] = None
        self.dp: Dispatcher = Dispatcher()
        self.router: Router = Router()
        
        # Bağlı servisler
        self.trade_engine: Optional[TradeEngine] = None
        
        # Bot durumu
        self.is_running = False
        self.polling_task: Optional[asyncio.Task] = None
        
        # Komut handler'ları kaydet
        self._setup_handlers()
        
        # Bot komutları
        self.commands = [
            BotCommand(command="status", description="Bot durumu ve portföy bilgisi"),
            BotCommand(command="stop", description="Botu güvenli durdur"),
            BotCommand(command="start_bot", description="Botu yeniden başlat"),
            BotCommand(command="mode", description="Trading modunu değiştir (demo/real)"),
            BotCommand(command="tp", description="Take profit yüzdesini değiştir"),
            BotCommand(command="balance", description="Bakiye durumu"),
            BotCommand(command="positions", description="Açık pozisyonlar"),
            BotCommand(command="help", description="Yardım menüsü")
        ]
    
    async def initialize(self, trade_engine: TradeEngine) -> None:
        """Telegram servisini başlat"""
        if not self.config.enabled:
            logger.info("Telegram servisi devre dışı")
            return
        
        if not self.config.bot_token or not self.config.chat_id:
            logger.warning("Telegram bot token veya chat ID eksik")
            return
        
        try:
            self.trade_engine = trade_engine
            self.bot = Bot(token=self.config.bot_token)
            
            # Bot bilgilerini al
            bot_info = await self.bot.get_me()
            logger.info(f"Telegram bot başlatıldı: @{bot_info.username}")
            
            # Komutları ayarla
            await self.bot.set_my_commands(self.commands)
            
            # Event handler'lar ekle
            self._register_event_handlers()
            
            # Dispatcher'ı başlat
            self.dp.include_router(self.router)
            
            # Polling başlat
            self.is_running = True
            self.polling_task = asyncio.create_task(self._start_polling())
            
            # Başlatma mesajı gönder
            await self.send_message(
                "🚀 **ShortBot Başlatıldı**\n"
                f"Mod: {self.trade_engine.settings.trading_mode}\n"
                f"Bakiye: ${self.trade_engine.portfolio.wallet.balance}\n"
                "Komutlar için /help yazın"
            )
            
        except Exception as e:
            logger.error(f"Telegram servis başlatma hatası: {e}")
            raise TelegramError(f"Telegram başlatma hatası: {e}")
    
    async def shutdown(self) -> None:
        """Telegram servisini kapat"""
        if not self.is_running:
            return
        
        logger.info("Telegram servisi kapatılıyor...")
        self.is_running = False
        
        # Polling'i durdur
        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
        
        # Bot session'unu kapat
        if self.bot:
            await self.bot.session.close()
        
        logger.info("Telegram servisi kapatıldı")
    
    def _setup_handlers(self) -> None:
        """Komut handler'larını kaydet"""
        
        @self.router.message(CommandStart())
        async def start_handler(message: Message) -> None:
            await self._handle_start(message)
        
        @self.router.message(Command("status"))
        async def status_handler(message: Message) -> None:
            await self._handle_status(message)
        
        @self.router.message(Command("stop"))
        async def stop_handler(message: Message) -> None:
            await self._handle_stop(message)
        
        @self.router.message(Command("start_bot"))
        async def start_bot_handler(message: Message) -> None:
            await self._handle_start_bot(message)
        
        @self.router.message(Command("mode"))
        async def mode_handler(message: Message) -> None:
            await self._handle_mode(message)
        
        @self.router.message(Command("tp"))
        async def tp_handler(message: Message) -> None:
            await self._handle_tp(message)
        
        @self.router.message(Command("balance"))
        async def balance_handler(message: Message) -> None:
            await self._handle_balance(message)
        
        @self.router.message(Command("positions"))
        async def positions_handler(message: Message) -> None:
            await self._handle_positions(message)
        
        @self.router.message(Command("help"))
        async def help_handler(message: Message) -> None:
            await self._handle_help(message)
    
    def _register_event_handlers(self) -> None:
        """Trade engine event handler'larını kaydet"""
        if not self.trade_engine:
            return
        
        # Pozisyon açıldığında
        self.trade_engine.add_event_handler(
            TradingEvent.POSITION_OPENED, 
            self._on_position_opened
        )
        
        # Pozisyon kapandığında
        self.trade_engine.add_event_handler(
            TradingEvent.POSITION_CLOSED,
            self._on_position_closed
        )
        
        # Likidasyonda
        self.trade_engine.add_event_handler(
            TradingEvent.POSITION_LIQUIDATED,
            self._on_position_liquidated
        )
        
        # Drawdown uyarısı
        self.trade_engine.add_event_handler(
            TradingEvent.DRAWDOWN_WARNING,
            self._on_drawdown_warning
        )
        
        # Kritik drawdown
        self.trade_engine.add_event_handler(
            TradingEvent.DRAWDOWN_CRITICAL,
            self._on_drawdown_critical
        )
        
        # Bot durduruldu
        self.trade_engine.add_event_handler(
            TradingEvent.STOP,
            self._on_bot_stopped
        )
    
    async def _start_polling(self) -> None:
        """Bot polling başlat"""
        try:
            await self.dp.start_polling(self.bot)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Telegram polling hatası: {e}")
    
    # Event Handlers
    async def _on_position_opened(self, event: TradingEvent, data: Dict[str, Any]) -> None:
        """Pozisyon açıldığında bildirim"""
        if not self.config.notify_new_position:
            return
        
        symbol = data['symbol']
        price = data['price']
        quantity = data['quantity']
        
        message = (
            "🔴 **SHORT AÇILDI**\n"
            f"Symbol: {symbol}\n"
            f"Entry: ${price:.4f}\n"
            f"Qty: {quantity:.6f}\n"
            f"Time: {datetime.now(timezone.utc).strftime('%H:%M:%S')}"
        )
        
        await self.send_message(message)
    
    async def _on_position_closed(self, event: TradingEvent, data: Dict[str, Any]) -> None:
        """Pozisyon kapandığında bildirim"""
        if not self.config.notify_tp_hit:
            return
        
        symbol = data['symbol']
        pnl = data['pnl']
        reason = data['reason']
        
        emoji = "✅" if pnl > 0 else "❌"
        
        message = (
            f"{emoji} **POZISYON KAPANDI**\n"
            f"Symbol: {symbol}\n"
            f"PnL: ${pnl:.2f}\n"
            f"Reason: {reason}\n"
            f"Time: {datetime.now(timezone.utc).strftime('%H:%M:%S')}"
        )
        
        await self.send_message(message)
    
    async def _on_position_liquidated(self, event: TradingEvent, data: Dict[str, Any]) -> None:
        """Likidasyonda bildirim"""
        if not self.config.notify_liquidation:
            return
        
        symbol = data['symbol']
        
        message = (
            "💀 **LIKİDASYON**\n"
            f"Symbol: {symbol}\n"
            f"Time: {datetime.now(timezone.utc).strftime('%H:%M:%S')}\n"
            "Pozisyon tamamen kapatıldı!"
        )
        
        await self.send_message(message)
    
    async def _on_drawdown_warning(self, event: TradingEvent, data: Dict[str, Any]) -> None:
        """Drawdown uyarısı"""
        if not self.config.notify_warnings:
            return
        
        daily_pnl_pct = data['daily_pnl_pct']
        threshold = data['threshold']
        
        message = (
            "⚠️ **DRAWDOWN UYARISI**\n"
            f"Günlük kayıp: %{abs(daily_pnl_pct):.1f}\n"
            f"Uyarı seviyesi: %{threshold}\n"
            "Dikkatli olun!"
        )
        
        await self.send_message(message)
    
    async def _on_drawdown_critical(self, event: TradingEvent, data: Dict[str, Any]) -> None:
        """Kritik drawdown bildirim"""
        if not self.config.notify_warnings:
            return
        
        daily_pnl_pct = data['daily_pnl_pct']
        threshold = data['threshold']
        
        message = (
            "🛑 **KRİTİK DRAWDOWN**\n"
            f"Günlük kayıp: %{abs(daily_pnl_pct):.1f}\n"
            f"Kritik seviye: %{threshold}\n"
            "**BOT OTOMATİK DURDURULDU!**\n"
            "Tüm pozisyonlar kapatıldı."
        )
        
        await self.send_message(message)
    
    async def _on_bot_stopped(self, event: TradingEvent, data: Dict[str, Any]) -> None:
        """Bot durdurulduğunda bildirim"""
        scan_count = data.get('scan_count', 0)
        positions_opened = data.get('positions_opened', 0)
        
        message = (
            "⏹️ **BOT DURDURULDU**\n"
            f"Tarama sayısı: {scan_count}\n"
            f"Açılan pozisyon: {positions_opened}\n"
            f"Time: {datetime.now(timezone.utc).strftime('%H:%M:%S')}"
        )
        
        await self.send_message(message)
    
    # Command Handlers
    async def _handle_start(self, message: Message) -> None:
        """Start komutu"""
        welcome_message = (
            "👋 **ShortBot'a Hoşgeldiniz!**\n\n"
            "Bu bot kripto para short işlemleri yapar.\n"
            "Kullanılabilir komutlar:\n"
            "/status - Bot durumu\n"
            "/balance - Bakiye bilgisi\n"
            "/positions - Açık pozisyonlar\n"
            "/help - Tüm komutlar\n\n"
            "⚠️ Risk uyarısı: Trading risklidir!"
        )
        
        await message.reply(welcome_message, parse_mode="Markdown")
    
    async def _handle_status(self, message: Message) -> None:
        """Status komutu"""
        if not self.trade_engine:
            await message.reply("❌ Trade engine bağlı değil")
            return
        
        status = self.trade_engine.get_status()
        portfolio = status['portfolio']
        
        status_message = (
            f"📊 **Bot Durumu**\n"
            f"Durum: {status['state'].upper()}\n"
            f"Mod: {status['trading_mode'].upper()}\n"
            f"Çalışma süresi: {status['uptime']//60:.0f} dakika\n\n"
            f"💰 **Portföy**\n"
            f"Bakiye: ${portfolio['balance']:.2f}\n"
            f"Günlük PnL: ${portfolio['daily_pnl']:.2f}\n"
            f"Açık pozisyon: {portfolio['open_positions']}\n\n"
            f"📈 **İstatistik**\n"
            f"Tarama: {status['scan_count']}\n"
            f"Sinyal: {status['signals_generated']}\n"
            f"Pozisyon: {status['positions_opened']}"
        )
        
        await message.reply(status_message, parse_mode="Markdown")
    
    async def _handle_stop(self, message: Message) -> None:
        """Stop komutu"""
        if not self.trade_engine:
            await message.reply("❌ Trade engine bağlı değil")
            return
        
        await message.reply("🛑 Bot durduruluyor...")
        await self.trade_engine.stop()
        await message.reply("✅ Bot güvenli şekilde durduruldu")
    
    async def _handle_start_bot(self, message: Message) -> None:
        """Start bot komutu"""
        if not self.trade_engine:
            await message.reply("❌ Trade engine bağlı değil")
            return
        
        if self.trade_engine.running:
            await message.reply("ℹ️ Bot zaten çalışıyor")
            return
        
        await message.reply("🚀 Bot başlatılıyor...")
        await self.trade_engine.start()
        await message.reply("✅ Bot başarıyla başlatıldı")
    
    async def _handle_mode(self, message: Message) -> None:
        """Mode değiştirme komutu"""
        args = message.text.split()
        
        if len(args) < 2:
            await message.reply(
                "📝 Kullanım: /mode <demo|real>\n"
                f"Mevcut mod: {self.trade_engine.settings.trading_mode if self.trade_engine else 'Bilinmiyor'}"
            )
            return
        
        new_mode = args[1].lower()
        
        if new_mode not in ['demo', 'real']:
            await message.reply("❌ Geçersiz mod. Kullanın: demo veya real")
            return
        
        # Mod değişikliği için bot'un yeniden başlatılması gerekir
        await message.reply(
            f"⚠️ Mod değişikliği için bot yeniden başlatılmalı.\n"
            f"Mevcut mod: {self.trade_engine.settings.trading_mode if self.trade_engine else 'Bilinmiyor'}\n"
            f"İstenen mod: {new_mode}"
        )
    
    async def _handle_tp(self, message: Message) -> None:
        """Take profit değiştirme komutu"""
        args = message.text.split()
        
        if len(args) < 2:
            current_tp = self.trade_engine.settings.strategy.tp_percentage if self.trade_engine else 0
            await message.reply(f"📝 Kullanım: /tp <yüzde>\nMevcut TP: %{current_tp}")
            return
        
        try:
            new_tp = float(args[1])
            
            if new_tp < 1 or new_tp > 50:
                await message.reply("❌ TP %1-%50 arasında olmalı")
                return
            
            if self.trade_engine:
                self.trade_engine.settings.strategy.tp_percentage = new_tp
                await message.reply(f"✅ Take Profit %{new_tp} olarak ayarlandı")
            else:
                await message.reply("❌ Trade engine bağlı değil")
                
        except ValueError:
            await message.reply("❌ Geçersiz sayı formatı")
    
    async def _handle_balance(self, message: Message) -> None:
        """Bakiye komutu"""
        if not self.trade_engine:
            await message.reply("❌ Trade engine bağlı değil")
            return
        
        wallet = self.trade_engine.portfolio.wallet
        
        balance_message = (
            f"💰 **Bakiye Durumu**\n"
            f"Toplam: ${wallet.balance:.2f}\n"
            f"Kullanılabilir: ${wallet.available_balance:.2f}\n"
            f"Marjin: ${wallet.margin_balance:.2f}\n"
            f"Unrealized PnL: ${wallet.unrealized_pnl:.2f}\n\n"
            f"📊 **Günlük**\n"
            f"Başlangıç: ${wallet.daily_start_balance:.2f}\n"
            f"PnL: ${wallet.daily_pnl:.2f}\n"
            f"Getiri: %{wallet.daily_return_pct:.2f}\n"
            f"İşlem: {wallet.daily_trades}"
        )
        
        await message.reply(balance_message, parse_mode="Markdown")
    
    async def _handle_positions(self, message: Message) -> None:
        """Açık pozisyonlar komutu"""
        if not self.trade_engine:
            await message.reply("❌ Trade engine bağlı değil")
            return
        
        positions = self.trade_engine.portfolio.get_open_positions()
        
        if not positions:
            await message.reply("📈 Açık pozisyon bulunmuyor")
            return
        
        positions_text = "📊 **Açık Pozisyonlar**\n\n"
        
        for pos in positions:
            pnl_emoji = "🟢" if pos.unrealized_pnl > 0 else "🔴"
            
            positions_text += (
                f"{pnl_emoji} **{pos.symbol}**\n"
                f"Side: {pos.side}\n"
                f"Size: {pos.size}\n"
                f"Entry: ${pos.entry_price:.4f}\n"
                f"Mark: ${pos.mark_price:.4f}\n"
                f"PnL: ${pos.unrealized_pnl:.2f}\n"
                f"TP: ${pos.tp_price:.4f}\n\n"
            )
        
        await message.reply(positions_text, parse_mode="Markdown")
    
    async def _handle_help(self, message: Message) -> None:
        """Yardım komutu"""
        help_message = (
            "🤖 **ShortBot Komutları**\n\n"
            "📊 **Durum**\n"
            "/status - Bot durumu ve portföy\n"
            "/balance - Detaylı bakiye bilgisi\n"
            "/positions - Açık pozisyonlar\n\n"
            "⚙️ **Kontrol**\n"
            "/stop - Botu güvenli durdur\n"
            "/start_bot - Botu yeniden başlat\n"
            "/mode <demo|real> - Mod değiştir\n"
            "/tp <yüzde> - Take profit ayarla\n\n"
            "ℹ️ **Bilgi**\n"
            "/help - Bu yardım menüsü\n\n"
            "⚠️ **Uyarı**: Bu bot otomatik işlem yapar. "
            "Sadece kaybetmeyi göze alabileceğiniz miktarda kullanın!"
        )
        
        await message.reply(help_message, parse_mode="Markdown")
    
    # Public Methods
    async def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Mesaj gönder"""
        if not self.bot or not self.config.chat_id or not self.config.enabled:
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.config.chat_id,
                text=text,
                parse_mode=parse_mode
            )
            return True
            
        except TelegramAPIError as e:
            logger.error(f"Telegram mesaj gönderme hatası: {e}")
            return False
        except Exception as e:
            logger.error(f"Beklenmeyen Telegram hatası: {e}")
            return False
    
    async def send_daily_summary(self, summary_data: Dict[str, Any]) -> None:
        """Günlük özet gönder"""
        if not self.config.notify_daily_summary:
            return
        
        summary = (
            "📅 **Günlük Özet**\n\n"
            f"🎯 Tarama: {summary_data.get('scans', 0)}\n"
            f"⚡ Sinyal: {summary_data.get('signals', 0)}\n"
            f"📈 Pozisyon: {summary_data.get('positions', 0)}\n"
            f"💰 PnL: ${summary_data.get('pnl', 0):.2f}\n"
            f"📊 Getiri: %{summary_data.get('return_pct', 0):.2f}\n"
            f"🏆 Kazanan: {summary_data.get('wins', 0)}\n"
            f"❌ Kaybeden: {summary_data.get('losses', 0)}"
        )
        
        await self.send_message(summary) 