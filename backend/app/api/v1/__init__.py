from fastapi import APIRouter

from . import admin, attack, auth, game, me, places, raid, scan, verify

router = APIRouter()
router.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
router.include_router(me.router, prefix="/v1/me", tags=["me"])
router.include_router(places.router, prefix="/v1", tags=["places"])
router.include_router(scan.router, prefix="/v1", tags=["scan"])
router.include_router(verify.router, prefix="/v1", tags=["verify"])
router.include_router(game.router, prefix="/v1", tags=["game"])
router.include_router(raid.router, prefix="/v1", tags=["raid"])
router.include_router(attack.router, prefix="/v1", tags=["attack"])
router.include_router(admin.router, prefix="/v1/admin", tags=["admin"])

__all__ = ["router"]
