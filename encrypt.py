from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import json
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DB_FILE = "db.json"


class CompanyData(BaseModel):
    key_service: str
    company_name: str
    license: str
    employees: int
    services: List[str]


class EncryptionKeyRequest(BaseModel):
    encryption_key: str


class EncryptedItem(BaseModel):
    encrypted_token: str
    encryption_key: str


class CompanyHandler:
    """
    Handles company data encryption, storage, and API endpoints.
    """

    def __init__(self):
        self.router = APIRouter()
        self.db_json = self.load_db()

        # --------- API Routes ----------
        @self.router.post("/add-company/", summary="Add a new company")
        def add_company(company_info: CompanyData):
            """
            Encrypt and store a new company. Returns the encryption key.
            """
            try:
                encrypted_item = self.encrypt_json(company_info.dict())
                self.append_to_db(encrypted_item)
                return {"encryption_key": encrypted_item["encryption_key"]}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to add company: {str(e)}")

        @self.router.post("/get-company/", summary="Retrieve company info by encryption key")
        def get_company(data: EncryptionKeyRequest):
            """
            Retrieve and decrypt company info by encryption key.
            """
            found_item = next(
                (item for item in self.db_json["encrypted_data_list"] if item["encryption_key"] == data.encryption_key),
                None
            )
            if not found_item:
                raise HTTPException(status_code=404, detail="Company not found")
            try:
                decrypted_data = self.decrypt_json(found_item["encrypted_token"], found_item["encryption_key"])
                return {"company_info": decrypted_data}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Decryption failed: {str(e)}")

    # --------- Database Methods ----------
    def load_db(self):
        """
        Load database from DB_FILE. Returns default structure if file missing or corrupted.
        """
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "encrypted_data_list" not in data:
                        data["encrypted_data_list"] = []
                    return data
            except (json.JSONDecodeError, IOError):
                # File corrupted or unreadable
                return {"encrypted_data_list": []}
        return {"encrypted_data_list": []}

    def save_db(self, db):
        """
        Save database to DB_FILE.
        """
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise RuntimeError(f"Failed to save database: {str(e)}")

    def append_to_db(self, encrypted_item: dict):
        """
        Add a new encrypted item to the database and persist it.
        """
        self.db_json["encrypted_data_list"].append(encrypted_item)
        self.save_db(self.db_json)

    # --------- Encryption / Decryption ----------
    def encrypt_json(self, data: dict) -> dict:
        """
        Encrypt a dictionary using AES-GCM 256-bit and return encrypted token + key.
        """
        try:
            plaintext = json.dumps(data, ensure_ascii=False).encode('utf-8')
            key = AESGCM.generate_key(bit_length=256)
            aesgcm = AESGCM(key)
            nonce = os.urandom(12)
            ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)
            return {
                "encrypted_token": base64.urlsafe_b64encode(nonce + ciphertext).decode('utf-8'),
                "encryption_key": base64.urlsafe_b64encode(key).decode('utf-8')
            }
        except Exception as e:
            raise RuntimeError(f"Encryption failed: {str(e)}")

    def decrypt_json(self, encrypted_token_b64: str, encryption_key_b64: str) -> dict:
        """
        Decrypt AES-GCM encrypted token using the provided encryption key.
        """
        try:
            data = base64.urlsafe_b64decode(encrypted_token_b64)
            key = base64.urlsafe_b64decode(encryption_key_b64)
            nonce = data[:12]
            ciphertext = data[12:]
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
            return json.loads(plaintext.decode('utf-8'))
        except Exception as e:
            raise RuntimeError(f"Decryption failed: {str(e)}")

    def get_router(self):
        """
        Return FastAPI router for inclusion.
        """
        return self.router

