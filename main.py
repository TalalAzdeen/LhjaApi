from fastapi import FastAPI
import gradio as gr
from fastapi.responses import RedirectResponse
 
from  encrypt  import * 
 

app = FastAPI()
company_handler = UserHandler() 
app.include_router(company_handler.get_router(), prefix="/company", tags=["Company"])
 
