"""FastAPI backend for the conventional AyurMitra website."""
from pathlib import Path
from typing import Literal
import json
import os
import urllib.request
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

from app.service import search_project
from app.language import detect_language, translator
from app.core import dataset_status
from app.knowledge_graph import graph_summary, search_knowledge_graph

WEB = ROOT / 'web'
app = FastAPI(title='AyurMitra', description='Source-grounded Ayurveda multilingual RAG research prototype', version='1.1.0')
app.mount('/static', StaticFiles(directory=str(WEB)), name='static')

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    category: Literal["general", "herbs", "disease"] = "general"
    answer_mode: Literal["ollama", "extractive"] = "extractive"
    output_language: Literal["auto", "english", "hindi", "kannada", "tamil", "telugu"] = "auto"

@app.get('/', include_in_schema=False)
def home(): 
    return FileResponse(WEB / 'index.html')

@app.get('/api/health')
def health():
    model = os.environ.get('AYURMITRA_OLLAMA_MODEL', '').strip()
    ollama_available = False
    model_available = False
    try:
        with urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=1.5) as response:
            installed = json.loads(response.read().decode('utf-8')).get('models', [])
        ollama_available = True
        model_available = any(
            item.get('name', '').split(':')[0] == model.split(':')[0]
            for item in installed
        ) if model else False
    except Exception:
        pass
    return {
        'status': 'ok', 
        'app': 'AyurMitra', 
        'version': '1.1.0', 
        'translation_enabled': translator.enabled,
        'ollama_model_configured': bool(model),
        'ollama_server_available': ollama_available,
        'ollama_model_available': model_available,
        'ollama_timeout_seconds': float(os.environ.get('AYURMITRA_OLLAMA_TIMEOUT_SECONDS', '45')),
        'answer_generation': 'Source-first answers with a labeled Ollama fallback when no direct local answer is available',
        'dense_retrieval': 'opt-in via AYURMITRA_ENABLE_DENSE=1; BM25 + TF-IDF is the default'
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

@app.get('/api/knowledge-graph/search')
def knowledge_graph_search(q: str = Query(min_length=1, max_length=120), limit: int = Query(default=20, ge=1, le=50)):
    return search_knowledge_graph(q, limit)

@app.post('/api/search')
def search(request: SearchRequest):
    try: 
        # Pass the answer_mode to the service
        return search_project(
            request.query, request.category, request.answer_mode, request.output_language
        )
    except ValueError as exc: 
        raise HTTPException(status_code=400, detail=str(exc)) from exc
