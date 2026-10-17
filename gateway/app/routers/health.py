from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["Health"])

@router.get("/health")
def get_health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "service": "HBK IT Monitoring Gateway"
    }
