from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
from .database import get_user_history

app = FastAPI()

# Configuração CORS (Permitir tudo para desenvolvimento local/ngrok)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoint de API
@app.get("/api/history/{user_id}")
async def history(user_id: int):
    data = get_user_history(user_id)
    if not data:
        return {"error": "Sem dados"}
    return data

# Rota Especial para o Index
@app.get("/")
async def read_index():
    # Retorna o HTML principal
    return FileResponse('app/web/index.html')

# Servir arquivos estáticos (JS, CSS, Imagens)
# Montado em /static para não conflitar, ou na raiz se preferir
if os.path.exists("app/web"):
    app.mount("/static", StaticFiles(directory="app/web"), name="static")
