from fastapi import APIRouter

router = APIRouter(prefix="/api/automation", tags=["Automation"])

@router.get("/health")
def automation_health():
    return {"status": "ok", "service": "automation"}

@router.get("/jobs")
def list_jobs():
    return {"jobs": [], "count": 0}

@router.get("/webhooks")
def list_webhooks():
    return {"webhooks": [], "count": 0}
