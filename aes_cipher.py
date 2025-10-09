import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class AESCipher:
    def __init__(self, key: bytes = None):
        self.key = key or AESGCM.generate_key(bit_length=256)
        self.aesgcm = AESGCM(self.key)

    @staticmethod
    def generate_key() -> bytes:
        return AESGCM.generate_key(bit_length=256)

    @staticmethod
    def key_to_base64(key: bytes) -> str:
        return base64.b64encode(key).decode("utf-8")

    @staticmethod
    def key_from_base64(key_b64: str) -> bytes:
        return base64.b64decode(key_b64)

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        blob = nonce + ciphertext
        return base64.b64encode(blob).decode("utf-8")

    def decrypt(self, encrypted_b64: str) -> str:
        blob = base64.b64decode(encrypted_b64)
        nonce = blob[:12]
        ciphertext = blob[12:]
        plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")