from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .database import get_database_path, initialize_database
from .demo_data import seed_demo_data
from .modules import MODULES
from .repository import DataRepository


def create_app(db_path: Path | str | None = None) -> FastAPI:
    resolved_db_path = db_path or get_database_path()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        initialize_database(resolved_db_path)
        if os.getenv("ASHARE_DEMO_DATA", "").lower() in {"1", "true", "yes"}:
            seed_demo_data(resolved_db_path)
        yield

    app = FastAPI(title="A-Share Local Data Workbench API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_repository() -> DataRepository:
        return DataRepository(resolved_db_path)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "database": str(resolved_db_path)}

    @app.get("/api/modules")
    def modules() -> list[dict[str, object]]:
        return [
            {
                "id": module.id,
                "label": module.label,
                "layer": module.layer,
                "description": module.description,
                "status": module.status,
                "tables": list(module.tables),
            }
            for module in MODULES
        ]

    @app.get("/api/securities/search")
    def search_securities(
        q: str = "",
        limit: int = Query(default=20, ge=1, le=100),
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        return {"query": q, "rows": repository.search_securities(q, limit)}

    @app.get("/api/security/{symbol}/overview")
    def security_overview(
        symbol: str,
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        overview = repository.get_security_overview(symbol)
        if overview["security"] is None:
            raise HTTPException(status_code=404, detail=f"No local security found for {symbol.upper()}")
        return overview

    @app.get("/api/modules/{module_id}/data")
    def module_data(
        module_id: str,
        symbol: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        result = repository.get_module_data(module_id, symbol=symbol, limit=limit)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Unknown module: {module_id}")
        return result

    @app.get("/api/jobs")
    def jobs(
        limit: int = Query(default=50, ge=1, le=200),
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        return {"rows": repository.list_jobs(limit)}

    @app.get("/api/data-sources/status")
    def source_status(repository: DataRepository = Depends(get_repository)) -> dict[str, object]:
        return {"rows": repository.list_source_health()}

    return app


app = create_app()
