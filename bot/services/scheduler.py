"""
Zamanlayıcı Servisi
Günlük reset, periyodik görevler, zamanlanmış işlemler
"""
import asyncio
from datetime import datetime, time, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..utils.config import BotSettings
from ..utils.logger import get_logger

logger = get_logger("scheduler")


class SchedulerService:
    """Zamanlayıcı servisi"""
    
    def __init__(self, settings: BotSettings):
        self.settings = settings
        self.scheduler = AsyncIOScheduler(timezone=timezone.utc)
        self.is_running = False
        
        # Registered jobs
        self.jobs: Dict[str, Any] = {}
        
        # Event callbacks
        self.daily_reset_callbacks: List[Callable] = []
        self.hourly_callbacks: List[Callable] = []
        self.custom_callbacks: Dict[str, List[Callable]] = {}
    
    async def start(self) -> None:
        """Scheduler'ı başlat"""
        if self.is_running:
            logger.warning("Scheduler zaten çalışıyor")
            return
        
        logger.info("Scheduler başlatılıyor...")
        
        try:
            # Default job'ları ekle
            self._add_default_jobs()
            
            # Scheduler'ı başlat
            self.scheduler.start()
            self.is_running = True
            
            logger.info("Scheduler başlatıldı")
            
        except Exception as e:
            logger.error(f"Scheduler başlatma hatası: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Scheduler'ı kapat"""
        if not self.is_running:
            return
        
        logger.info("Scheduler kapatılıyor...")
        
        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Scheduler kapatıldı")
            
        except Exception as e:
            logger.error(f"Scheduler kapatma hatası: {e}")
    
    def _add_default_jobs(self) -> None:
        """Varsayılan job'ları ekle"""
        
        # Günlük reset - UTC 00:00
        self.add_daily_job(
            "daily_reset",
            self._daily_reset_task,
            hour=0,
            minute=0
        )
        
        # Saatlik maintenance
        self.add_interval_job(
            "hourly_maintenance", 
            self._hourly_maintenance_task,
            hours=1
        )
        
        # 5 dakikada bir health check
        self.add_interval_job(
            "health_check",
            self._health_check_task,
            minutes=5
        )
        
        # Log rotation - günde bir
        self.add_daily_job(
            "log_rotation",
            self._log_rotation_task,
            hour=2,
            minute=0
        )
    
    # Job Management Methods
    def add_daily_job(
        self, 
        job_id: str, 
        func: Callable, 
        hour: int = 0, 
        minute: int = 0,
        **kwargs
    ) -> None:
        """Günlük job ekle"""
        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            timezone=timezone.utc
        )
        
        job = self.scheduler.add_job(
            func,
            trigger,
            id=job_id,
            replace_existing=True,
            **kwargs
        )
        
        self.jobs[job_id] = job
        logger.info(f"Günlük job eklendi: {job_id} @ {hour:02d}:{minute:02d} UTC")
    
    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        **kwargs
    ) -> None:
        """Interval job ekle"""
        trigger = IntervalTrigger(
            seconds=seconds,
            minutes=minutes,
            hours=hours
        )
        
        job = self.scheduler.add_job(
            func,
            trigger,
            id=job_id,
            replace_existing=True,
            **kwargs
        )
        
        self.jobs[job_id] = job
        interval_str = f"{hours}h {minutes}m {seconds}s"
        logger.info(f"Interval job eklendi: {job_id} @ her {interval_str}")
    
    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        cron_expression: str,
        **kwargs
    ) -> None:
        """Cron expression ile job ekle"""
        # Cron expression parsing'i
        parts = cron_expression.split()
        
        if len(parts) == 5:
            minute, hour, day, month, day_of_week = parts
            
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=timezone.utc
            )
            
            job = self.scheduler.add_job(
                func,
                trigger,
                id=job_id,
                replace_existing=True,
                **kwargs
            )
            
            self.jobs[job_id] = job
            logger.info(f"Cron job eklendi: {job_id} @ {cron_expression}")
        else:
            logger.error(f"Geçersiz cron expression: {cron_expression}")
    
    def remove_job(self, job_id: str) -> bool:
        """Job'ı kaldır"""
        try:
            if job_id in self.jobs:
                self.scheduler.remove_job(job_id)
                del self.jobs[job_id]
                logger.info(f"Job kaldırıldı: {job_id}")
                return True
        except Exception as e:
            logger.error(f"Job kaldırma hatası [{job_id}]: {e}")
        
        return False
    
    def pause_job(self, job_id: str) -> bool:
        """Job'ı duraklat"""
        try:
            if job_id in self.jobs:
                self.scheduler.pause_job(job_id)
                logger.info(f"Job duraklatıldı: {job_id}")
                return True
        except Exception as e:
            logger.error(f"Job duraklama hatası [{job_id}]: {e}")
        
        return False
    
    def resume_job(self, job_id: str) -> bool:
        """Job'ı devam ettir"""
        try:
            if job_id in self.jobs:
                self.scheduler.resume_job(job_id)
                logger.info(f"Job devam ettirildi: {job_id}")
                return True
        except Exception as e:
            logger.error(f"Job devam ettirme hatası [{job_id}]: {e}")
        
        return False
    
    # Callback Management
    def add_daily_reset_callback(self, callback: Callable) -> None:
        """Günlük reset callback'i ekle"""
        self.daily_reset_callbacks.append(callback)
        logger.debug("Günlük reset callback eklendi")
    
    def add_hourly_callback(self, callback: Callable) -> None:
        """Saatlik callback ekle"""
        self.hourly_callbacks.append(callback)
        logger.debug("Saatlik callback eklendi")
    
    def add_custom_callback(self, event_name: str, callback: Callable) -> None:
        """Özel event callback'i ekle"""
        if event_name not in self.custom_callbacks:
            self.custom_callbacks[event_name] = []
        
        self.custom_callbacks[event_name].append(callback)
        logger.debug(f"Özel callback eklendi: {event_name}")
    
    # Default Task Methods
    async def _daily_reset_task(self) -> None:
        """Günlük reset görevi"""
        logger.info("Günlük reset görevi çalışıyor...")
        
        try:
            # Callback'leri çağır
            for callback in self.daily_reset_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback()
                    else:
                        callback()
                except Exception as e:
                    logger.error(f"Daily reset callback hatası: {e}")
            
            logger.info("Günlük reset tamamlandı")
            
        except Exception as e:
            logger.error(f"Günlük reset hatası: {e}")
    
    async def _hourly_maintenance_task(self) -> None:
        """Saatlik maintenance görevi"""
        logger.debug("Saatlik maintenance çalışıyor...")
        
        try:
            # Memory cleanup
            import gc
            gc.collect()
            
            # Callback'leri çağır
            for callback in self.hourly_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback()
                    else:
                        callback()
                except Exception as e:
                    logger.error(f"Hourly callback hatası: {e}")
            
            logger.debug("Saatlik maintenance tamamlandı")
            
        except Exception as e:
            logger.error(f"Saatlik maintenance hatası: {e}")
    
    async def _health_check_task(self) -> None:
        """Health check görevi"""
        logger.debug("Health check çalışıyor...")
        
        try:
            # Memory usage kontrol
            import psutil
            memory_percent = psutil.virtual_memory().percent
            
            if memory_percent > 80:
                logger.warning(f"Yüksek memory kullanımı: %{memory_percent:.1f}")
            
            # Disk usage kontrol
            disk_percent = psutil.disk_usage('/').percent
            if disk_percent > 90:
                logger.warning(f"Disk alanı yetersiz: %{disk_percent:.1f}")
            
        except ImportError:
            # psutil yoksa atlat
            pass
        except Exception as e:
            logger.error(f"Health check hatası: {e}")
    
    async def _log_rotation_task(self) -> None:
        """Log rotation görevi"""
        logger.debug("Log rotation çalışıyor...")
        
        try:
            # Log dosyalarını kontrol et ve eski dosyaları sil
            from pathlib import Path
            log_dir = Path("logs")
            
            if log_dir.exists():
                # 30 günden eski log dosyalarını sil
                cutoff_date = datetime.now() - timedelta(days=30)
                
                for log_file in log_dir.glob("*.log*"):
                    if log_file.stat().st_mtime < cutoff_date.timestamp():
                        try:
                            log_file.unlink()
                            logger.debug(f"Eski log dosyası silindi: {log_file}")
                        except:
                            pass
            
        except Exception as e:
            logger.error(f"Log rotation hatası: {e}")
    
    # Utility Methods
    def trigger_custom_event(self, event_name: str, *args, **kwargs) -> None:
        """Özel event'i tetikle"""
        if event_name in self.custom_callbacks:
            for callback in self.custom_callbacks[event_name]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(*args, **kwargs))
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Custom event callback hatası [{event_name}]: {e}")
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Job durumunu al"""
        try:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                return {
                    'id': job.id,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger),
                    'func': job.func.__name__
                }
        except Exception as e:
            logger.error(f"Job status alma hatası [{job_id}]: {e}")
        
        return None
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Tüm job'ları listele"""
        jobs_list = []
        
        for job_id in self.jobs:
            job_status = self.get_job_status(job_id)
            if job_status:
                jobs_list.append(job_status)
        
        return jobs_list
    
    def is_job_running(self, job_id: str) -> bool:
        """Job çalışıyor mu kontrol et"""
        return job_id in self.jobs and self.jobs[job_id].next_run_time is not None
    
    # Time utility methods
    @staticmethod
    def next_trading_day() -> datetime:
        """Sonraki trading günü (Pazartesi-Cuma)"""
        now = datetime.now(timezone.utc)
        
        # Hafta sonu kontrolü
        if now.weekday() == 5:  # Cumartesi
            return now + timedelta(days=2)
        elif now.weekday() == 6:  # Pazar
            return now + timedelta(days=1)
        else:
            return now + timedelta(days=1)
    
    @staticmethod
    def market_hours() -> tuple[time, time]:
        """Piyasa saatleri (kripto 24/7 ama reference için)"""
        return time(9, 30), time(16, 0)  # NYSE hours in UTC
    
    def add_market_hours_job(
        self,
        job_id: str,
        func: Callable,
        start_hour: int = 9,
        start_minute: int = 30,
        end_hour: int = 16,
        end_minute: int = 0
    ) -> None:
        """Piyasa saatlerinde çalışan job ekle"""
        # Market açılışında
        self.add_daily_job(
            f"{job_id}_start",
            func,
            hour=start_hour,
            minute=start_minute
        )
        
        # Market kapanışında (isteğe bağlı stop fonksiyonu varsa)
        if hasattr(func, 'stop'):
            self.add_daily_job(
                f"{job_id}_stop", 
                func.stop,
                hour=end_hour,
                minute=end_minute
            )
    
    def schedule_one_time_job(
        self,
        job_id: str,
        func: Callable,
        run_time: datetime,
        **kwargs
    ) -> None:
        """Tek seferlik job planla"""
        job = self.scheduler.add_job(
            func,
            'date',
            run_date=run_time,
            id=job_id,
            replace_existing=True,
            **kwargs
        )
        
        self.jobs[job_id] = job
        logger.info(f"Tek seferlik job planlandı: {job_id} @ {run_time}")
    
    def get_next_reset_time(self) -> datetime:
        """Sonraki günlük reset zamanı"""
        now = datetime.now(timezone.utc)
        next_reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return next_reset 