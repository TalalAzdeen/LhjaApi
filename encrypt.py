from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import requests
import json
import os
import base64
import uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from azure.storage.blob import BlobServiceClient

DB_FILE = "db.json"


class CompanyData(BaseModel):
    key_service: str
    company_name: str
    license: str
    employees: int
    services: List[str]


class EncryptionKeyRequest(BaseModel):
    encryption_key: str


class UserHandler:
    """
    Integrated handler for chat, TTS, and company data encryption API endpoints.
    """

    CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=lhjaspcev15204396534;AccountKey=vbGXAI8Fqix/bV15xFfkU3pzgs9wCav0IRy9Vv0gVjh0s3sAZV1oLi3NgMC6fG6MsvhMg7/VohUC+AStizl4zg==;EndpointSuffix=core.windows.net"
    CONTAINER_NAME = "soundsaudi"
    AZURE_TTS_ENDPOINT = "https://lahja-dev-resource.cognitiveservices.azure.com/openai/deployments/LAHJA-V1/audio/speech?api-version=2025-03-01-preview"
    AZURE_CHAT_ENDPOINT = "https://lahja-dev-resource.cognitiveservices.azure.com/openai/deployments/LAHJA-V1/chat/completions?api-version=2025-03-01-preview"

    def __init__(self):
        self.router = APIRouter()
        self.db_json = self.load_db()

        # --------- Company API ----------
        @self.router.post("/add-company/")
        def add_company(company_info: CompanyData):
            encrypted_item = self.encrypt_json(company_info.dict())
            self.append_to_db(encrypted_item)
            return {"encryption_key": encrypted_item["encryption_key"]}

        @self.router.post("/get-company/")
        def get_company(data: EncryptionKeyRequest):
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

        # --------- Chat API ----------
        @self.router.post("/ChatText2Text")
        def chat_text2text(message: str, key: str = ""):
            return self.chat_with_gpt(message, key)

        # --------- Text-to-Speech API ----------
        @self.router.post("/ChatText2Speech")
        def chat_text2speech(text: str, api_key: str, file_type: str = "wav", voice: str = "alloy"):
            return self.text_to_speech_and_upload(text, api_key, file_type, voice)

    # --------- Database Methods ----------
    def load_db(self):
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "encrypted_data_list" not in data:
                        data["encrypted_data_list"] = []
                    return data
            except (json.JSONDecodeError, IOError):
                return {"encrypted_data_list": []}
        return {"encrypted_data_list": []}

    def save_db(self, db):
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise RuntimeError(f"Failed to save database: {str(e)}")

    def append_to_db(self, encrypted_item: dict):
        self.db_json["encrypted_data_list"].append(encrypted_item)
        self.save_db(self.db_json)

    # --------- Encryption / Decryption ----------
    def encrypt_json(self, data: dict) -> dict:
        plaintext = json.dumps(data, ensure_ascii=False).encode('utf-8')
        key = AESGCM.generate_key(bit_length=256)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)
        return {
            "encrypted_token": base64.urlsafe_b64encode(nonce + ciphertext).decode('utf-8'),
            "encryption_key": base64.urlsafe_b64encode(key).decode('utf-8')
        }

    def decrypt_json(self, encrypted_token_b64: str, encryption_key_b64: str) -> dict:
        data = base64.urlsafe_b64decode(encrypted_token_b64)
        key = base64.urlsafe_b64decode(encryption_key_b64)
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
        return json.loads(plaintext.decode('utf-8'))

    # --------- Chat Methods ----------
    def chat_with_gpt(self, text: str, api_key: str):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "انت مساعد ذكي اسمه (لهجة)، مطور من قبل شركة (أسس الذكاء الرقمي). "
                    "رد دايمًا باللهجة النجدية السعودية. "
                    "خلك مختصر وواضح."
                )
            },
            {"role": "user", "content": text}
        ]
        data = {
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1,
            "model": "gpt-4o"
        }
        response = requests.post(self.AZURE_CHAT_ENDPOINT, json=data, headers=headers)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return f"Error: {response.status_code}\n{response.text}"

    # --------- Text-to-Speech Methods ----------
    def text_to_speech_and_upload(self, text, api_key, file_type="wav", voice="alloy", speed=1.0):
        try:
            headers = {"Content-Type": "application/json", "api-key": api_key}
            data = {"model": "LAHJA-V1", "input": text, "voice": voice, "speed": speed}
            response = requests.post(self.AZURE_TTS_ENDPOINT, json=data, headers=headers)
            if response.status_code != 200:
                raise Exception(f"TTS Error: {response.text}")

            audio_data = response.content
            unique_id = uuid.uuid4().hex
            filename = f"{unique_id}.{file_type}"

            blob_service_client = BlobServiceClient.from_connection_string(self.CONNECTION_STRING)
            blob_client = blob_service_client.get_blob_client(container=self.CONTAINER_NAME, blob=filename)
            blob_client.upload_blob(audio_data, overwrite=True)
            blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{self.CONTAINER_NAME}/{filename}"
            return blob_url
        except Exception as e:
            return {"error": str(e)}

    # --------- Router Getter ----------
    def get_router(self):
        return self.router


