"""
ShortBot Ana Giriş Noktası
PySide6 GUI ve komut satırı arayüzü
"""
import sys
import asyncio
import argparse
from pathlib import Path

# Proje kökünü sys.path'e ekle
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bot.utils.config import get_settings, BotSettings
from bot.utils.logger import get_logger

logger = get_logger("main")


def main():
    """Ana fonksiyon"""
    parser = argparse.ArgumentParser(description="ShortBot - Kripto Short İşlem Botu")
    parser.add_argument(
        "--mode", 
        choices=["gui", "cli", "demo"],
        default="gui",
        help="Çalışma modu (varsayılan: gui)"
    )
    parser.add_argument(
        "--config", 
        type=str,
        default="config.json",
        help="Konfigürasyon dosyası yolu"
    )
    parser.add_argument(
        "--trading-mode",
        choices=["demo", "real"],
        help="İşlem modu (demo/real)"
    )
    
    args = parser.parse_args()
    
    try:
        # Konfigürasyonu yükle
        if Path(args.config).exists():
            settings = BotSettings.load_from_file(args.config)
        else:
            settings = BotSettings()
            settings.save_to_file(args.config)
            print(f"Varsayılan konfigürasyon dosyası oluşturuldu: {args.config}")
        
        # Trading mode override
        if args.trading_mode:
            settings.trading_mode = args.trading_mode
            settings.save_to_file(args.config)
        
        logger.info(f"ShortBot başlatılıyor - mod: {args.mode}, trading: {settings.trading_mode}")
        
        if args.mode == "gui":
            run_gui(settings)
        elif args.mode == "cli":
            asyncio.run(run_cli(settings))
        elif args.mode == "demo":
            asyncio.run(run_demo(settings))
            
    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından durduruldu")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Kritik hata: {e}")
        sys.exit(1)


def run_gui(settings: BotSettings):
    """PySide6 GUI başlat"""
    try:
        from PySide6.QtCore import Qt
        from bot.ui.app import ShortBotApp
        import os
        
        # Windows'da high DPI desteği  
        from PySide6.QtCore import QCoreApplication
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # ShortBot uygulamasını başlat
        app = ShortBotApp(settings)
        
        logger.info("GUI modu başlatıldı")
        return app.run()
        
    except ImportError as e:
        print(f"GUI bağımlılıkları eksik: {e}")
        print("Gerekli paketler: pip install PySide6")
        print("Demo modunu deneyin: python main.py --mode demo")
        sys.exit(1)
    except Exception as e:
        logger.error(f"GUI başlatma hatası: {e}")
        print(f"GUI başlatma hatası: {e}")
        sys.exit(1)


async def run_cli(settings: BotSettings):
    """Komut satırı arayüzü"""
    print("=" * 50)
    print("ShortBot CLI")
    print("=" * 50)
    print(f"Trading Mode: {settings.trading_mode}")
    print(f"Demo Balance: ${settings.demo_balance}")
    print(f"Strategy: {settings.strategy.timeframe}, TP: {settings.strategy.tp_percentage}%")
    print("=" * 50)
    
    # TODO: TradeEngine'i import et ve başlat
    # from bot.core.engine import TradeEngine
    # from bot.core.demo_exchange import DemoExchange
    
    print("CLI modu henüz tamamlanmadı.")
    print("Demo modunu deneyin: python main.py --mode demo")


async def run_demo(settings: BotSettings):
    """Demo modu - tam işlevli test"""
    print("=" * 50)
    print("ShortBot Demo Modu")
    print("=" * 50)
    print(f"Başlangıç Bakiyesi: ${settings.demo_balance}")
    print(f"Pozisyon Büyüklüğü: ${settings.strategy.position_size_usd}")
    print(f"Take Profit: %{settings.strategy.tp_percentage}")
    print(f"Timeframe: {settings.strategy.timeframe}")
    print("=" * 50)
    
    try:
        from bot.core.engine import TradeEngine
        
        # TradeEngine başlat
        async with TradeEngine(settings) as engine:
            print("✓ Demo exchange bağlantısı kuruldu")
            
            # Event handler'lar ekle
            def on_position_opened(event, data):
                symbol = data['symbol']
                price = data['price']
                qty = data['quantity']
                print(f"🔴 SHORT AÇILDI: {symbol} @ ${price:.4f} (Qty: {qty:.6f})")
                
            def on_position_closed(event, data):
                symbol = data['symbol']
                pnl = data['pnl']
                reason = data['reason']
                emoji = "✅" if pnl > 0 else "❌"
                print(f"{emoji} KAPATILDI: {symbol} | PnL: ${pnl:.2f} | {reason}")
            
            def on_drawdown_warning(event, data):
                pnl_pct = data['daily_pnl_pct']
                print(f"⚠️  DRAWDOWN UYARISI: %{pnl_pct:.1f}")
            
            from bot.core.engine import TradingEvent
            engine.add_event_handler(TradingEvent.POSITION_OPENED, on_position_opened)
            engine.add_event_handler(TradingEvent.POSITION_CLOSED, on_position_closed)
            engine.add_event_handler(TradingEvent.DRAWDOWN_WARNING, on_drawdown_warning)
            
            # Engine'i başlat
            await engine.start()
            print("✓ İşlem motoru başlatıldı")
            print("\nDemo çalışıyor... (30 saniye)")
            print("CTRL+C ile durdurun\n")
            
            try:
                # 30 saniye çalıştır
                await asyncio.sleep(30)
                
            except KeyboardInterrupt:
                print("\n⏹️  Kullanıcı tarafından durduruldu")
            
            # Durum raporu
            status = engine.get_status()
            portfolio = status['portfolio']
            
            print("\n" + "=" * 50)
            print("DEMO RAPORU")
            print("=" * 50)
            print(f"Tarama Sayısı: {status['scan_count']}")
            print(f"Üretilen Sinyal: {status['signals_generated']}")
            print(f"Açılan Pozisyon: {status['positions_opened']}")
            print(f"Açık Pozisyon: {portfolio['open_positions']}")
            print(f"Güncel Bakiye: ${portfolio['balance']:.2f}")
            print(f"Günlük PnL: ${portfolio['daily_pnl']:.2f}")
            
            if portfolio['daily_pnl'] != 0:
                daily_return_pct = (portfolio['daily_pnl'] / settings.demo_balance) * 100
                print(f"Günlük Getiri: %{daily_return_pct:.2f}")
            
            print("=" * 50)
            print("✓ Demo başarıyla tamamlandı!")
            
    except KeyboardInterrupt:
        print("\n⏹️  Demo durduruldu")
    except Exception as e:
        logger.error(f"Demo hatası: {e}")
        print(f"❌ Demo hatası: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 