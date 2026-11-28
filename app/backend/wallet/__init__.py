from fastapi import APIRouter
from . import auth, profile, inbox, loans, recipients, transfers
from .runtime import WalletContext


def create_router(wallet):
    router = APIRouter(prefix="/api/khach")
    for feature in (auth, profile, inbox, loans, recipients, transfers):
        feature.register(router, wallet)
    return router


__all__ = ["WalletContext", "create_router"]
