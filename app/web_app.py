"""FastAPI backend for the conventional AyurMitra website."""
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

from app.service import search_project
from app.language import detect_language, translator
from app.core import dataset_status
from app.knowledge_graph import graph_summary

WEB = ROOT / 'web'
app = FastAPI(title='AyurMitra', description='Source-grounded Ayurveda multilingual RAG research prototype', version='1.1.0')
app.mount('/static', StaticFiles(directory=str(WEB)), name='static')

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    category: Literal["general", "herbs", "disease"] = "general"
    answer_mode: Literal["ollama", "extractive"] = "ollama"  # <-- ADDED THIS LINE

@app.get('/', include_in_schema=False)
def home(): 
    return FileResponse(WEB / 'index.html')

@app.get('/api/health')
def health():
    return {
        'status': 'ok', 
        'app': 'AyurMitra', 
        'version': '1.1.0', 
        'translation_enabled': translator.enabled,
        'ollama_model_configured': bool(__import__('os').environ.get('AYURMITRA_OLLAMA_MODEL', '').strip()),
        'answer_generation': 'Ollama local model if AYURMITRA_OLLAMA_MODEL is set; otherwise extractive grounded RAG',
        'dense_retrieval': 'optional sentence-transformers; BM25 + TF-IDF fallback always available'
    }

@app.get('/api/status')
def status(): 
    return {'datasets': dataset_status(), 'translation_enabled': translator.enabled}

@app.post('/api/language')
def language(request: SearchRequest): 
    return detect_language(request.query)

@app.get('/api/knowledge-graph')
def knowledge_graph(): 
    return graph_summary()

@app.post('/api/search')
def search(request: SearchRequest):
    try: 
        # Pass the answer_mode to the service
        return search_project(request.query, request.category, request.answer_mode) 
    except ValueError as exc: 
        raise HTTPException(status_code=400, detail=str(exc)) from exc