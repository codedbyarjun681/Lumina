from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db
from routes import (
    chat,
    conversations,
    documents,
    memory,
    models,
    providers,
    quiz,
    settings,
    upload,
    workspace,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("Lumina backend started.")
    yield
    print("Lumina backend stopped.")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workspace.router)
app.include_router(conversations.router)
app.include_router(memory.router)
app.include_router(upload.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(settings.router)
app.include_router(models.router)
app.include_router(providers.router)
app.include_router(quiz.router)


@app.get("/")
def home():
    return {"message": "Lumina Backend Running"}