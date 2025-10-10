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
from sqlitedb import *
from aes_cipher import AESCipher

 
class Options(BaseModel):
    text_deployment_name: str
    api_version: str  
    base_url: str 
   
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
class SessionCreate(BaseModel):
    company_id: str
    token: str
    status:str= "Active"
    total_orders:int= 0
    used_orders:int= 0

class TextData(BaseModel):
    text: str
class SessionUpdate(BaseModel):
    used_orders:int
 
class EncryptionKeyRequest(BaseModel):
    encryption_key: str

class UserHandler:
    CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=lhjaspcev15204396534;AccountKey=vbGXAI8Fqix/bV15xFfkU3pzgs9wCav0IRy9Vv0gVjh0s3sAZV1oLi3NgMC6fG6MsvhMg7/VohUC+AStizl4zg==;EndpointSuffix=core.windows.net"
    CONTAINER_NAME = "soundsaudi"
    AZURE_TTS_ENDPOINT = "https://lahja-dev-resource.cognitiveservices.azure.com/openai/deployments/LAHJA-V1/audio/speech?api-version=2025-03-01-preview"
    AZURE_CHAT_ENDPOINT = "https://lahja-dev-resource.cognitiveservices.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"

    def __init__(self):
        self.router = APIRouter()
       
        self.db = CompanyDB("LhjaAPIDb.db")
        self.db1 = SessionDB("LhjaAPIDb.db")
        self.db1.create_table()
        self.cipher = AESCipher()
        
        @self.router.post("/sessions/")
        def create_session(session: SessionCreate):
            session_id = self.db1.add_session(
                company_id=session.company_id,
                token= session.token,
                status=session.status,
                total_orders=session.total_orders,
                used_orders=session.used_orders
            )
            
            return {"session_id": session_id, "message": "Session created successfully"}

         
        @self.router.put("/sessions/{session_id}")
        def update_used_orders(session_id: str, session: SessionUpdate):
            if session.used_orders is None:
                raise HTTPException(status_code=400, detail="used_orders required")
            success = self.db1.update_used_orders(session_id, session.used_orders)
            if not success:
                raise HTTPException(status_code=400, detail="Cannot update UsedOrders")
            return {"message": "UsedOrders updated successfully"}

     
        @self.router.get("/sessions/search/")
        def search_sessions(column: str, keyword: str):
            results = self.db1.search_session(column, keyword)
        
        @self.router.get("/sessions")
        def get_all_sessions(): 
            companies =self.db1.select("Sessions")
            return {"Sessions": companies}


            return {"results": results}
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
        
        @self.router.get("/companies")
        def get_all_companies():
            companies =self.db.select("Company")
            return {"companies": companies}
        
        @self.router.post("/ChatText2Text2")
        def chat_text2text2(message: str,Customize_the_dialect:str,token:str,options:Options):
            
            result = self.chat_with_gpt(message,token)
            return {"response": result}
        @self.router.post("/ChatText2Text3")
        def chat_text2text3(message: str,Customize_the_dialect:str,token:str,options:Options):
            decrypted = self.cipher.decrypt(token)
            key = self.db1.search_session("SessionId", decrypted)

            result = self.chat_with_gpt(message,key)
            
            return {"response": result}
        @self.router.post("/ChatText2Text")
        def chat_text2text(message: str, key: str):
             
            result = self.chat_with_gpt(message, key_service)
            #self.increment_request_count(key)
            return {"response": result}

        @self.router.post("/ChatText2Speech")
        def chat_text2speech(text: str, api_key: str, file_type: str = "wav", voice: str = "alloy"):
              
            url = self.text_to_speech_and_upload(text, api_key, file_type, voice)
            #self.increment_request_count(api_key)
            return {"audio_url": url}
        
        @self.router.post("/encrypt")
        def encrypt_text(data: TextData):
            encrypted =self.cipher.encrypt(data.text)
            key_b64 = AESCipher.key_to_base64(self.cipher.key)
            return {"encrypted": encrypted, "key": key_b64}
        
        @self.router.post("/decrypt")
        def decrypt_text(data: TextData):
            try:
                decrypted = self.cipher.decrypt(data.text)
                return {"decrypted": decrypted}
            except Exception as e:
                return {"error": str(e)}
    

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


