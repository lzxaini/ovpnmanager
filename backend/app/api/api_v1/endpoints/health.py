from fastapi import APIRouter

router = APIRouter()


@router.get("/live")
def liveness() -> dict[str, str]:
    # 存活探针：返回静态 ok
    return {"status": "ok"}


@router.get("/ready")
def readiness() -> dict[str, str]:
    # 就绪探针：可扩展检查 DB、证书工具等
    return {"status": "ok"}
