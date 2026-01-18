import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import crud
from app.api.api_v1 import api_router
from app.api.deps import get_db_context
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.db import base  # noqa: F401
from app.db.session import engine


settings = get_settings()


def create_app() -> FastAPI:
    is_dev = settings.deploy_env.upper() == "DEV"

    # Logging setup (console + rotating file)
    setup_logging()
    app = FastAPI(
        title=settings.app_name,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json" if is_dev else None,
        docs_url="/docs" if is_dev else None,
        redoc_url="/redoc" if is_dev else None,
    )

    cors_origins = ["*"] if is_dev else settings.cors_origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False if is_dev else True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    base.Base.metadata.create_all(bind=engine)

    # seed default admin if not exists
    with get_db_context() as db:
        admin = crud.user.get_by_username(db, username=settings.default_admin_username)
        if not admin:
            from app.schemas.user import UserCreate

            crud.user.create(
                db,
                obj_in=UserCreate(
                    username=settings.default_admin_username,
                    email=None,
                    password=settings.default_admin_password,
                    is_active=True,
                    is_superuser=True,
                ),
            )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    if is_dev:
        logger = logging.getLogger(__name__)
        logger.info("Swagger UI: http://localhost:8000/docs  |  OpenAPI: %s/openapi.json", settings.api_v1_prefix)

    return app


app = create_app()
