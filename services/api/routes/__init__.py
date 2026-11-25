from .auth import router as auth_router
from .incidents import router as incidents_router
from .incident_manager import router as incident_manager_router
from .inventory import router as inventory_router
from .suppliers import router as suppliers_router
from .users import profiles_router, users_router

__all__ = ["auth_router", "incidents_router", "incident_manager_router", "inventory_router", "profiles_router", "suppliers_router", "users_router"]
