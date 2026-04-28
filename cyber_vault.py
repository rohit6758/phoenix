import hashlib
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

# 🔑 Generate a strong 32-byte key (Exact ga ammayi JS lo chesinatte)
key_hash = hashlib.sha256(b"my_super_secret_key").digest()
SECRET_KEY = key_hash[:32]

# 🔐 Encrypt function
def encrypt_code(text: str) -> str:
    # Generate random 16-byte IV
    iv = os.urandom(16)
    
    # AES-256-CBC setup
    cipher = Cipher(algorithms.AES(SECRET_KEY), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # Padding (JavaScript automatically adds padding, Python lo manam explicit ga ivvali)
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(text.encode('utf-8')) + padder.finalize()
    
    # Encrypt
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
    # Return exactly in her format: "iv_hex:ciphertext_hex"
    return iv.hex() + ":" + ciphertext.hex()

# 🔓 Decrypt function
def decrypt_code(encrypted_text: str) -> str:
    parts = encrypted_text.split(":")
    
    if len(parts) != 2:
        raise ValueError("Invalid encrypted format")
        
    iv = bytes.fromhex(parts[0])
    ciphertext = bytes.fromhex(parts[1])
    
    # Decrypt setup
    cipher = Cipher(algorithms.AES(SECRET_KEY), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    
    padded_data = decryptor.update(ciphertext) + decryptor.finalize()
    
    # Unpad
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    decrypted_data = unpadder.update(padded_data) + unpadder.finalize()
    
    return decrypted_data.decode('utf-8')