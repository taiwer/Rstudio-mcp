"""Configuration encryption and sensitive data protection."""

import base64
import json
import logging
import os
from typing import Dict, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


@dataclass
class EncryptedConfig:
    """Represents an encrypted configuration."""
    
    encrypted_data: str
    salt: str
    algorithm: str = "PBKDF2-Fernet"
    iterations: int = 100000


class ConfigEncryption:
    """Handles encryption and decryption of configuration data."""
    
    def __init__(self, password: Optional[str] = None):
        """Initialize config encryption.
        
        Args:
            password: Encryption password. If None, will try to get from environment
        """
        self.logger = logging.getLogger(__name__)
        self.password = password or self._get_password_from_env()
        
        if not self.password:
            raise ValueError("No encryption password provided")
    
    def _get_password_from_env(self) -> Optional[str]:
        """Get encryption password from environment variables.
        
        Returns:
            Password from environment or None
        """
        # Try multiple environment variable names
        env_vars = [
            'RSTUDIO_MCP_ENCRYPTION_KEY',
            'MCP_ENCRYPTION_KEY',
            'ENCRYPTION_PASSWORD'
        ]
        
        for var in env_vars:
            password = os.getenv(var)
            if password:
                return password
        
        return None
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password and salt.
        
        Args:
            password: Password string
            salt: Salt bytes
            
        Returns:
            Derived key bytes
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def encrypt_data(self, data: Union[Dict[str, Any], str]) -> EncryptedConfig:
        """Encrypt configuration data.
        
        Args:
            data: Data to encrypt (dict or string)
            
        Returns:
            Encrypted configuration object
        """
        try:
            # Convert data to JSON string if it's a dict
            if isinstance(data, dict):
                json_data = json.dumps(data, indent=2)
            else:
                json_data = str(data)
            
            # Generate random salt
            salt = os.urandom(16)
            
            # Derive key
            key = self._derive_key(self.password, salt)
            
            # Create Fernet cipher
            fernet = Fernet(key)
            
            # Encrypt data
            encrypted_bytes = fernet.encrypt(json_data.encode('utf-8'))
            
            # Encode to base64 for storage
            encrypted_data = base64.b64encode(encrypted_bytes).decode('ascii')
            salt_b64 = base64.b64encode(salt).decode('ascii')
            
            return EncryptedConfig(
                encrypted_data=encrypted_data,
                salt=salt_b64
            )
            
        except Exception as e:
            self.logger.error(f"Error encrypting data: {e}")
            raise
    
    def decrypt_data(self, encrypted_config: EncryptedConfig) -> Dict[str, Any]:
        """Decrypt configuration data.
        
        Args:
            encrypted_config: Encrypted configuration object
            
        Returns:
            Decrypted data as dictionary
        """
        try:
            # Decode salt and encrypted data
            salt = base64.b64decode(encrypted_config.salt.encode('ascii'))
            encrypted_bytes = base64.b64decode(encrypted_config.encrypted_data.encode('ascii'))
            
            # Derive key
            key = self._derive_key(self.password, salt)
            
            # Create Fernet cipher
            fernet = Fernet(key)
            
            # Decrypt data
            decrypted_bytes = fernet.decrypt(encrypted_bytes)
            json_data = decrypted_bytes.decode('utf-8')
            
            # Parse JSON
            return json.loads(json_data)
            
        except Exception as e:
            self.logger.error(f"Error decrypting data: {e}")
            raise
    
    def encrypt_file(self, input_file: Union[str, Path], 
                    output_file: Union[str, Path]) -> None:
        """Encrypt a configuration file.
        
        Args:
            input_file: Path to input file
            output_file: Path to output encrypted file
        """
        input_path = Path(input_file)
        output_path = Path(output_file)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        try:
            # Read input file
            with open(input_path, 'r', encoding='utf-8') as f:
                data = f.read()
            
            # Encrypt data
            encrypted_config = self.encrypt_data(data)
            
            # Write encrypted file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'encrypted_data': encrypted_config.encrypted_data,
                    'salt': encrypted_config.salt,
                    'algorithm': encrypted_config.algorithm,
                    'iterations': encrypted_config.iterations
                }, f, indent=2)
            
            self.logger.info(f"Encrypted file: {input_path} -> {output_path}")
            
        except Exception as e:
            self.logger.error(f"Error encrypting file: {e}")
            raise
    
    def decrypt_file(self, input_file: Union[str, Path], 
                    output_file: Union[str, Path]) -> None:
        """Decrypt a configuration file.
        
        Args:
            input_file: Path to encrypted input file
            output_file: Path to output decrypted file
        """
        input_path = Path(input_file)
        output_path = Path(output_file)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        try:
            # Read encrypted file
            with open(input_path, 'r', encoding='utf-8') as f:
                encrypted_data = json.load(f)
            
            # Create encrypted config object
            encrypted_config = EncryptedConfig(
                encrypted_data=encrypted_data['encrypted_data'],
                salt=encrypted_data['salt'],
                algorithm=encrypted_data.get('algorithm', 'PBKDF2-Fernet'),
                iterations=encrypted_data.get('iterations', 100000)
            )
            
            # Decrypt data
            decrypted_data = self.decrypt_data(encrypted_config)
            
            # Write decrypted file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                if isinstance(decrypted_data, dict):
                    json.dump(decrypted_data, f, indent=2)
                else:
                    f.write(str(decrypted_data))
            
            self.logger.info(f"Decrypted file: {input_path} -> {output_path}")
            
        except Exception as e:
            self.logger.error(f"Error decrypting file: {e}")
            raise
    
    def load_encrypted_config(self, config_file: Union[str, Path]) -> Dict[str, Any]:
        """Load and decrypt a configuration file.
        
        Args:
            config_file: Path to encrypted configuration file
            
        Returns:
            Decrypted configuration data
        """
        config_path = Path(config_file)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                encrypted_data = json.load(f)
            
            # Check if file is encrypted
            if 'encrypted_data' in encrypted_data and 'salt' in encrypted_data:
                # File is encrypted
                encrypted_config = EncryptedConfig(
                    encrypted_data=encrypted_data['encrypted_data'],
                    salt=encrypted_data['salt'],
                    algorithm=encrypted_data.get('algorithm', 'PBKDF2-Fernet'),
                    iterations=encrypted_data.get('iterations', 100000)
                )
                
                return self.decrypt_data(encrypted_config)
            else:
                # File is not encrypted, return as-is
                return encrypted_data
                
        except Exception as e:
            self.logger.error(f"Error loading encrypted config: {e}")
            raise
    
    def save_encrypted_config(self, config_data: Dict[str, Any], 
                             config_file: Union[str, Path]) -> None:
        """Save configuration data in encrypted format.
        
        Args:
            config_data: Configuration data to save
            config_file: Path to save encrypted configuration
        """
        config_path = Path(config_file)
        
        try:
            # Encrypt data
            encrypted_config = self.encrypt_data(config_data)
            
            # Save encrypted file
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'encrypted_data': encrypted_config.encrypted_data,
                    'salt': encrypted_config.salt,
                    'algorithm': encrypted_config.algorithm,
                    'iterations': encrypted_config.iterations
                }, f, indent=2)
            
            self.logger.info(f"Saved encrypted config: {config_path}")
            
        except Exception as e:
            self.logger.error(f"Error saving encrypted config: {e}")
            raise
    
    def is_file_encrypted(self, config_file: Union[str, Path]) -> bool:
        """Check if a configuration file is encrypted.
        
        Args:
            config_file: Path to configuration file
            
        Returns:
            True if file is encrypted, False otherwise
        """
        config_path = Path(config_file)
        
        if not config_path.exists():
            return False
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return 'encrypted_data' in data and 'salt' in data
            
        except Exception:
            return False
    
    def change_password(self, old_password: str, new_password: str,
                       config_file: Union[str, Path]) -> None:
        """Change encryption password for a configuration file.
        
        Args:
            old_password: Current password
            new_password: New password
            config_file: Path to configuration file
        """
        config_path = Path(config_file)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        try:
            # Create decryption instance with old password
            old_encryption = ConfigEncryption(old_password)
            
            # Load and decrypt with old password
            decrypted_data = old_encryption.load_encrypted_config(config_path)
            
            # Create encryption instance with new password
            new_encryption = ConfigEncryption(new_password)
            
            # Save with new password
            new_encryption.save_encrypted_config(decrypted_data, config_path)
            
            self.logger.info(f"Changed encryption password for: {config_path}")
            
        except Exception as e:
            self.logger.error(f"Error changing password: {e}")
            raise
    
    @staticmethod
    def generate_password(length: int = 32) -> str:
        """Generate a random password for encryption.
        
        Args:
            length: Password length
            
        Returns:
            Random password string
        """
        import secrets
        import string
        
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def setup_environment_key(key_name: str = "RSTUDIO_MCP_ENCRYPTION_KEY") -> str:
        """Set up encryption key in environment.
        
        Args:
            key_name: Environment variable name
            
        Returns:
            Generated encryption key
        """
        # Generate new key
        key = ConfigEncryption.generate_password(32)
        
        # Set in environment
        os.environ[key_name] = key
        
        print(f"Generated encryption key and set {key_name}")
        print(f"Key: {key}")
        print(f"Add this to your environment: export {key_name}='{key}'")
        
        return key