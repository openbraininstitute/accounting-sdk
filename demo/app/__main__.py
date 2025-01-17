"""Main entry point."""

import logging
import os

import uvicorn

logging.basicConfig(level=logging.INFO)
uvicorn.run(
    "app.api:app",
    host=os.getenv("UVICORN_HOST", "127.0.0.1"),
    port=int(os.getenv("UVICORN_PORT", "8000")),
)
