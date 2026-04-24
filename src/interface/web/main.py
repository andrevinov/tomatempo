from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from infrastructure.database import check_database_connection

templates = Jinja2Templates(directory="src/interface/web/templates")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    check_database_connection()
    yield


app = FastAPI(title="Tomatempo", lifespan=lifespan)


@app.get("/")
def read_root() -> str:
    return "Tomatempo is running"
