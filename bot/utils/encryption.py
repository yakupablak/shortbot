"""
Şifreleme ve güvenli saklama sistemi
API anahtarları Windows Credentials Vault'ta şifrelenmiş olarak saklanır
"""
import base64
import os
from typing import Optional, Tuple

import keyring
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .logger import get_logger

logger = get_logger("encryption")


class CredentialsManager:
    """API anahtarlarının güvenli saklanması ve şifrelenmesi"""
    
    SERVICE_NAME = "ShortBot"
    SALT_KEY = "shortbot_salt"
    
    def __init__(self):
        self._fernet: Optional[Fernet] = None
        self._ensure_salt()
    
    def _ensure_salt(self) -> None:
        """Şifreleme için salt oluştur veya al"""
        try:
            salt = keyring.get_password(self.SERVICE_NAME, self.SALT_KEY)
            if not salt:
                # Yeni salt oluştur
                salt = base64.urlsafe_b64encode(os.urandom(16)).decode()
                keyring.set_password(self.SERVICE_NAME, self.SALT_KEY, salt)
                logger.info("Yeni şifreleme salt'ı oluşturuldu")
            
            self._salt = base64.urlsafe_b64decode(salt.encode())
            
        except Exception as e:
            logger.error(f"Salt oluşturulurken hata: {e}")
            # Fallback: geçici salt
            self._salt = b"shortbot_fallback"
    
    def _get_fernet(self) -> Fernet:
        """Fernet şifreleme anahtarını al"""
        if self._fernet is None:
            # Makine-specific anahtar oluştur
            password = f"shortbot_{os.getlogin()}_{os.environ.get('COMPUTERNAME', 'default')}".encode()
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self._salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            self._fernet = Fernet(key)
        
        return self._fernet
    
    def store_credentials(self, api_key: str, api_secret: str) -> bool:
        """API anahtarlarını şifreleyerek sakla"""
        try:
            fernet = self._get_fernet()
            
            # API anahtarlarını şifrele
            encrypted_key = fernet.encrypt(api_key.encode())
            encrypted_secret = fernet.encrypt(api_secret.encode())
            
            # Credentials Vault'ta sakla
            keyring.set_password(self.SERVICE_NAME, "api_key", 
                               base64.urlsafe_b64encode(encrypted_key).decode())
            keyring.set_password(self.SERVICE_NAME, "api_secret", 
                               base64.urlsafe_b64encode(encrypted_secret).decode())
            
            logger.info("API anahtarları güvenli şekilde saklandı")
            return True
            
        except Exception as e:
            logger.error(f"API anahtarları saklanırken hata: {e}")
            return False
    
    def load_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Şifrelenmiş API anahtarlarını yükle"""
        try:
            fernet = self._get_fernet()
            
            # Şifrelenmiş anahtarları al
            encrypted_key_b64 = keyring.get_password(self.SERVICE_NAME, "api_key")
            encrypted_secret_b64 = keyring.get_password(self.SERVICE_NAME, "api_secret")
            
            if not encrypted_key_b64 or not encrypted_secret_b64:
                return None, None
            
            # Base64 decode ve şifresini çöz
            encrypted_key = base64.urlsafe_b64decode(encrypted_key_b64.encode())
            encrypted_secret = base64.urlsafe_b64decode(encrypted_secret_b64.encode())
            
            api_key = fernet.decrypt(encrypted_key).decode()
            api_secret = fernet.decrypt(encrypted_secret).decode()
            
            logger.info("API anahtarları başarıyla yüklendi")
            return api_key, api_secret
            
        except Exception as e:
            logger.error(f"API anahtarları yüklenirken hata: {e}")
            return None, None
    
    def clear_credentials(self) -> bool:
        """Saklanan API anahtarlarını temizle"""
        try:
            keyring.delete_password(self.SERVICE_NAME, "api_key")
            keyring.delete_password(self.SERVICE_NAME, "api_secret")
            logger.info("API anahtarları temizlendi")
            return True
            
        except Exception as e:
            logger.error(f"API anahtarları temizlenirken hata: {e}")
            return False
    
    def has_credentials(self) -> bool:
        """Saklanan API anahtarlarının varlığını kontrol et"""
        try:
            key = keyring.get_password(self.SERVICE_NAME, "api_key")
            secret = keyring.get_password(self.SERVICE_NAME, "api_secret")
            return bool(key and secret)
        except:
            return False
    
    def validate_credentials(self, api_key: str, api_secret: str) -> bool:
        """API anahtarlarının formatını doğrula"""
        # Binance API key formatı: 64 karakter hex
        if len(api_key) != 64:
            return False
        
        try:
            int(api_key, 16)  # Hex olduğunu kontrol et
        except ValueError:
            return False
        
        # Secret key en az 32 karakter olmalı
        if len(api_secret) < 32:
            return False
        
        return True


# Global credentials manager
credentials_manager = CredentialsManager()


def store_api_credentials(api_key: str, api_secret: str) -> bool:
    """API anahtarlarını sakla - kısayol fonksiyon"""
    return credentials_manager.store_credentials(api_key, api_secret)


def load_api_credentials() -> Tuple[Optional[str], Optional[str]]:
    """API anahtarlarını yükle - kısayol fonksiyon"""
    return credentials_manager.load_credentials()


def clear_api_credentials() -> bool:
    """API anahtarlarını temizle - kısayol fonksiyon"""
    return credentials_manager.clear_credentials()


def has_api_credentials() -> bool:
    """API anahtarları var mı kontrol et - kısayol fonksiyon"""
    return credentials_manager.has_credentials()


def validate_api_credentials(api_key: str, api_secret: str) -> bool:
    """API anahtarlarını doğrula - kısayol fonksiyon"""
    return credentials_manager.validate_credentials(api_key, api_secret) 