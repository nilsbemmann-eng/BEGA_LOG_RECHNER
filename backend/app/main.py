from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    audits,
    documents,
    emails,
    exports,
    extracted_fields,
    imports,
    routes,
    shipments,
    tariffs,
    tour_origin_mappings,
    tours,
)
from app.config import get_settings
from app.errors import register_exception_handlers

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Automatisierte Frachtpreispruefung fuer Spediteure (MVP)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(emails.router)
app.include_router(documents.router)
app.include_router(extracted_fields.router)
app.include_router(shipments.router)
app.include_router(routes.router)
app.include_router(audits.router)
app.include_router(tariffs.router)
app.include_router(imports.router)
app.include_router(exports.router)
app.include_router(tours.router)
app.include_router(tour_origin_mappings.router)


@app.get("/health", tags=["system"])
def health_check() -> dict:
    return {"status": "ok", "environment": settings.environment}
