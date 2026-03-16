"""TraceCtrl Engine — FastAPI entrypoint."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from engine.scheduler import start_scheduler, stop_scheduler
from engine.api.routes import topology, system, sessions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="TraceCtrl Engine",
    version="0.1.0",
    description="Intelligence Engine for TraceCtrl agentic AI security observability",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router, prefix="/api/v1")
app.include_router(topology.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
