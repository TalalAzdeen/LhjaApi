from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
import base64
import os
import uuid
import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from azure.storage.blob import BlobServiceClient
from sqlitedb import CompanyDB

DB_FILE = "db.json"

class CompanyCreate(BaseModel):
    name: str
    license_number: str
    employees:int = 0
    services:str = ""

class CompanyUpdate(BaseModel):
    name:str
    license_number:str
    employees:int
    services:str

class CompanyData(BaseModel):
    key_service: str
    company_name: str
    license: str
    employees: int
    services: list[str]
    subscription_type: str = "free"
    max_requests: int = 10
    current_requests: int = 0

class EncryptionKeyRequest(BaseModel):
    encryption_key: str

class UserHandler:
    CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=lhjaspcev15204396534;AccountKey=vbGXAI8Fqix/bV15xFfkU3pzgs9wCav0IRy9Vv0gVjh0s3sAZV1oLi3NgMC6fG6MsvhMg7/VohUC+AStizl4zg==;EndpointSuffix=core.windows.net"
    CONTAINER_NAME = "soundsaudi"
    AZURE_TTS_ENDPOINT = "https://lahja-dev-resource.cognitiveservices.azure.com/openai/deployments/LAHJA-V1/audio/speech?api-version=2025-03-01-preview"
    AZURE_CHAT_ENDPOINT = "https://lahja-dev-resource.cognitiveservices.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"

    def __init__(self):
        self.router = APIRouter()
        self.db_json = self.load_db()
        self.db = CompanyDB()
        self.db.create_table() 

        @self.router.post("/companies/")
        def create_company(company: CompanyCreate):
            company_id = self.db.add_company(
                name=company.name,
                license_number=company.license_number,
                employees=company.employees,
                services=company.services
            )
            return {"company_id": company_id, "message": "Company created successfully"}

        def create_company(company: CompanyCreate):
            company_id = self.db.add_company(
                name=company.name,
                license_number=company.license_number,
                employees=company.employees,
                services=company.services
            )
            return {"company_id": company_id, "message": "Company created successfully"}

        @self.router.put("/companies/{company_id}")
        def update_company(company_id: str, company: CompanyUpdate):
            success = self.db.update_company(company_id, company.dict(exclude_none=True))
            if not success:
                raise HTTPException(status_code=404, detail="Company not found")
            return {"message": "Company updated successfully"}

        @self.router.delete("/companies/{company_id}")
        def delete_company(company_id: str):
            success = self.db.delete_company(company_id)
            if not success:
                raise HTTPException(status_code=404, detail="Company not found")
            return {"message": "Company deleted successfully"}

        @self.router.get("/companies/search/")
        def search_companies(column: str, keyword: str):
            results = self.db.search_company(column, keyword)
            return {"results": results}    
        @self.router.post("/add-company/")
        def add_company(company_info: CompanyData):
            encrypted_item = self.encrypt_json(company_info.dict())
            self.append_to_db(encrypted_item)
            return {"encryption_key": encrypted_item["encryption_key"]}
        @self.router.get("/companies")
        def get_all_companies():
            companies = company_db.select("Company")
            return {"companies": companies}
        @self.router.post("/get-company/")
        def get_company(data: EncryptionKeyRequest):
            found_item = next((item for item in self.db_json["encrypted_data_list"] if item["encryption_key"] == data.encryption_key), None)
            if not found_item:
                raise HTTPException(status_code=404, detail="Company not found")
            decrypted_data = self.decrypt_json(found_item["encrypted_token"], found_item["encryption_key"])
            return {"company_info": decrypted_data}

        @self.router.post("/ChatText2Text")
        def chat_text2text(message: str, key: str):
            if not self.check_subscription(key)["is_allowed"]:
                raise HTTPException(status_code=403, detail="Request limit exceeded")
            key_service = self.get_key_service_from_encryption_key(key)
            result = self.chat_with_gpt(message, key_service)
            #self.increment_request_count(key)
            return {"response": result}

        @self.router.post("/ChatText2Speech")
        def chat_text2speech(text: str, api_key: str, file_type: str = "wav", voice: str = "alloy"):
            if not self.check_subscription(api_key)["is_allowed"]:
                raise HTTPException(status_code=403, detail="Request limit exceeded")
            key_service = self.get_key_service_from_encryption_key(api_key)
            url = self.text_to_speech_and_upload(text, key_service, file_type, voice)
            #self.increment_request_count(api_key)
            return {"audio_url": url}

    def load_db(self):
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "encrypted_data_list" not in data:
                        data["encrypted_data_list"] = []
                    return data
            except:
                return {"encrypted_data_list": []}
        return {"encrypted_data_list": []}

    def save_db(self, db):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)

    def append_to_db(self, encrypted_item: dict):
        self.db_json["encrypted_data_list"].append(encrypted_item)
        self.save_db(self.db_json)

    def encrypt_json(self, data: dict) -> dict:
        plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
        key = AESGCM.generate_key(bit_length=256)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)
        return {"encrypted_token": base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8"),
                "encryption_key": base64.urlsafe_b64encode(key).decode("utf-8")}

    def decrypt_json(self, encrypted_token_b64: str, encryption_key_b64: str) -> dict:
        data = base64.urlsafe_b64decode(encrypted_token_b64)
        key = base64.urlsafe_b64decode(encryption_key_b64)
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
        return json.loads(plaintext.decode("utf-8"))

    def get_key_service_from_encryption_key(self, encryption_key: str) -> str:
        found_item = next((item for item in self.db_json["encrypted_data_list"] if item["encryption_key"] == encryption_key), None)
        if not found_item:
            raise HTTPException(status_code=404, detail="Invalid encryption key")
        decrypted_data = self.decrypt_json(found_item["encrypted_token"], found_item["encryption_key"])
        return decrypted_data.get("key_service", "")

    def check_subscription(self, encryption_key: str) -> dict:
        found_item = next((item for item in self.db_json["encrypted_data_list"] if item["encryption_key"] == encryption_key), None)
        if not found_item:
            raise HTTPException(status_code=404, detail="Invalid encryption key")
        decrypted_data = self.decrypt_json(found_item["encrypted_token"], found_item["encryption_key"])
        subscription_type = decrypted_data.get("subscription_type", "free")
        max_requests = decrypted_data.get("max_requests", 10)
        current_requests = decrypted_data.get("current_requests", 0)
        is_allowed = current_requests < max_requests
        return {"subscription_type": subscription_type, "max_requests": max_requests, "current_requests": current_requests, "is_allowed": is_allowed}

    def increment_request_count(self, encryption_key: str):
        found_item = next((item for item in self.db_json["encrypted_data_list"] if item["encryption_key"] == encryption_key), None)
        if not found_item:
            raise HTTPException(status_code=404, detail="Invalid encryption key")
        decrypted_data = self.decrypt_json(found_item["encrypted_token"], found_item["encryption_key"])
        decrypted_data["current_requests"] = decrypted_data.get("current_requests", 0) + 1
        encrypted_item = self.encrypt_json(decrypted_data)
        index = self.db_json["encrypted_data_list"].index(found_item)
        self.db_json["encrypted_data_list"][index] = encrypted_item
        self.save_db(self.db_json)

    def chat_with_gpt(self, text: str, api_key: str):
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        messages = [{"role": "system", "content": "انت مساعد ذكي باللهجة النجدية السعودية."},
                    {"role": "user", "content": text}]
        data = {"messages": messages, "max_tokens": 512, "temperature": 0.8, "top_p": 1, "model": "gpt-4o"}
        response = requests.post(self.AZURE_CHAT_ENDPOINT, json=data, headers=headers)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        return f"Error: {response.status_code}\n{response.text}"

    def text_to_speech_and_upload(self, text, api_key, file_type="wav", voice="alloy", speed=1.0):
        headers = {"Content-Type": "application/json", "api-key": api_key}
        data = {"model": "LAHJA-V1", "input": text, "voice": voice, "speed": speed}
        response = requests.post(self.AZURE_TTS_ENDPOINT, json=data, headers=headers)
        if response.status_code != 200:
            return {"error": response.text}
        audio_data = response.content
        unique_id = uuid.uuid4().hex
        filename = f"{unique_id}.{file_type}"
        blob_service_client = BlobServiceClient.from_connection_string(self.CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=self.CONTAINER_NAME, blob=filename)
        blob_client.upload_blob(audio_data, overwrite=True)
        return f"https://{blob_service_client.account_name}.blob.core.windows.net/{self.CONTAINER_NAME}/{filename}"

    def get_router(self):
        return self.router


