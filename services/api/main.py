"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routes import auth_router, incidents_router, incident_manager_router, inventory_router, profiles_router, suppliers_router, users_router
from routes.seed import seed_suppliers


@asynccontextmanager
async def lifespan(_: FastAPI):
	"""Ensure the supplier directory has its initial records on first startup."""
	seed_suppliers()
	yield


app = FastAPI(title="HealthCore Digital API", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(request: Request, exc: RequestValidationError):
	if request.url.path.startswith("/api/incident-manager"):
		errors = [
			{key: value for key, value in error.items() if key in {"loc", "msg", "type"}}
			for error in exc.errors()
		]
		return JSONResponse(status_code=422, content={"detail": errors})
	return await request_validation_exception_handler(request, exc)


app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:3002", "http://127.0.0.1:3002", "http://localhost:3000", "http://127.0.0.1:3000"],
	allow_credentials=True,
	allow_methods=["*"] ,
	allow_headers=["*"],
)
app.include_router(incidents_router)
app.include_router(incident_manager_router)
app.include_router(inventory_router)
app.include_router(suppliers_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)
