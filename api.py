import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from bot import handle_chat_turn

app = FastAPI(
    title="Sports Court Booking AI Assistant API",
    description="سرویس هوش مصنوعی چت‌بات رزرو سالن‌های ورزشی (مبتنی بر RAG و LLM)",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

user_sessions: dict[str, list] = {}

class ChatRequest(BaseModel):
    session_id: str = "default_user"
    message: str

@app.get("/")
def serve_ui():
    """نمایش صفحه گرافیکی چت‌بات در آدرس اصلی سرور"""
    ui_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(ui_path):
        return FileResponse(ui_path)
    return {"message": "فایل index.html یافت نشد. به /docs مراجعه کنید."}

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="متن پیام نمی‌تواند خالی باشد.")
    
    if req.session_id not in user_sessions:
        user_sessions[req.session_id] = []
        
    try:
        result = handle_chat_turn(req.message, user_sessions[req.session_id])
        return {
            "status": "success",
            "session_id": req.session_id,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))