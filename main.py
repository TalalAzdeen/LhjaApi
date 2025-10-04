from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import gradio as gr
import os
import uvicorn

 
from encrypt import *

 
app = FastAPI(title="Company API with Gradio")

 
company_handler = UserHandler()
app.include_router(company_handler.get_router(), prefix="/company", tags=["Company"])

 
def greet(name):
    return f"مرحباً {name}! 👋"

gradio_app = gr.Interface(fn=greet, inputs="text", outputs="text", title="Gradio Demo")

 
app = gr.mount_gradio_app(app, gradio_app, path="/gradio")

 
@app.get("/")
async def root():
    return RedirectResponse(url="/gradio")

# تشغيل السيرفر على Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
