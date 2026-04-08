from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from ui.routes import router as ui_router
from utils.db import init_db
from utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="Covestro Strategy Lab Enterprise", version="2.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key="change-this-secret-key")
app.mount("/static", StaticFiles(directory="ui/static"), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    logger.info("Application started and database initialized.")


app.include_router(ui_router)
