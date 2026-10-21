from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.datasets import router as datasets_router
from backend.app.api.chat import router as chat_router
from backend.app.api.chat_stream import router as chat_stream_router

app = FastAPI(
    title="Conversational Data Analysis API",
    description="Backend API for Chat-Based Multi-CSV Data Analysis",
    version="1.0.0",
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets_router)
app.include_router(chat_router)
app.include_router(chat_stream_router)

@app.get("/api/health")

def health_check():

    return {"status": "ok", "service": "data-analysis-backend", "version": "1.0.0"}
