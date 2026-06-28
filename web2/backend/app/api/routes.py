import jwt

from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.ai_decision_engine import build_ai_decision
from app.services.auth_service import authenticate_user, get_user_by_username
from app.services.auction_ai import build_auction_ai
from app.services.data_center import data_center
from app.services.decision_center import build_decision_center
from app.services.daily_ai_report import build_daily_ai_report
from app.services.mainline_engine import build_mainline_analysis
from app.services.market_brain import build_market_brain
from app.services.market_data_hub import build_market_data_hub
from app.services.pipeline_runner import get_pipeline_job, run_daily_pipeline
from app.services.pre_market_ai import build_pre_market_ai
from app.services.realtime_ai import build_realtime_ai
from app.services.report_service import (
    build_dashboard,
    read_disclaimer,
    read_final_report,
    read_frozen_orders,
    read_leaders,
    read_membership,
    read_paper_data,
    read_paper_report,
    read_strategy_judge,
    read_validation_report,
)
from app.services.trader_agent import build_trader_agent
from app.services.trade_script_engine import build_trade_script
from app.services.trading_plan_engine import build_trading_plan
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


router = APIRouter()
optional_bearer = HTTPBearer(auto_error=False)


def get_dev_user() -> dict:
    """本地开发调试用：临时关闭接口鉴权，统一返回 mock admin 用户。"""
    return {
        "username": "dev_admin",
        "membership_level": "admin",
        "expire_date": "2099-12-31",
        "is_active": True,
    }


def get_optional_user(credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer)) -> dict:
    """本地开发用可选认证：无 token 返回 mock admin；有 token 则按真实用户权限解析。"""
    if not credentials:
        return get_dev_user()
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.algorithm])
        username = payload.get("sub")
        user = get_user_by_username(username) if username else None
        return user if user and user.get("is_active") else get_dev_user()
    except Exception:
        return get_dev_user()


def _dump_model(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _envelope(current_user: dict, allowed: bool = True, data=None) -> dict:
    return {
        "success": True,
        "allowed": bool(allowed),
        "membership_level": current_user.get("membership_level", "admin"),
        "data": data if data is not None else {},
    }


def _pipeline_envelope(current_user: dict, result: dict) -> dict:
    return {
        "success": bool(result.get("success", False)),
        "allowed": True,
        "membership_level": current_user.get("membership_level", "admin"),
        "data": result,
    }


def _service_envelope(current_user: dict, payload: dict, data_key: str | None = None) -> dict:
    allowed = bool(payload.get("allowed", True))
    if data_key:
        data = payload.get(data_key, [])
    else:
        data = {
            key: value
            for key, value in payload.items()
            if key not in {"success", "allowed", "membership_level", "disclaimer", "message"}
        }
    return _envelope(current_user, allowed, data)


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "AI Review Trading Web2 API",
        "disclaimer": "本系统仅用于学习研究和模拟验证，不构成任何投资建议，不承诺收益，交易风险自担。",
    }


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = create_access_token({"sub": user["username"], "membership_level": user["membership_level"]})
    return LoginResponse(
        access_token=token,
        username=user["username"],
        membership_level=user["membership_level"],
        expire_date=user.get("expire_date", ""),
    )


@router.get("/dashboard")
def dashboard(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, _dump_model(build_dashboard(current_user)))


@router.get("/reports/final")
def final_report(current_user: dict = Depends(get_optional_user)) -> dict:
    payload = _dump_model(read_final_report(current_user))
    return _envelope(current_user, payload.get("allowed", True), {
        "title": payload.get("title", "最终日报"),
        "content": payload.get("content", ""),
        "disclaimer": payload.get("disclaimer", settings.disclaimer),
    })


@router.get("/paper/account")
def paper_account(current_user: dict = Depends(get_optional_user)) -> dict:
    payload = _dump_model(read_paper_report(current_user))
    return _envelope(current_user, payload.get("allowed", True), {
        "title": payload.get("title", "Paper Trading 账户"),
        "content": payload.get("content", ""),
        "disclaimer": payload.get("disclaimer", settings.disclaimer),
    })


@router.get("/paper/data")
def paper_data(current_user: dict = Depends(get_optional_user)) -> dict:
    return _service_envelope(current_user, read_paper_data(current_user))


@router.get("/validation")
def validation(current_user: dict = Depends(get_optional_user)) -> dict:
    payload = _dump_model(read_validation_report(current_user))
    return _envelope(current_user, payload.get("allowed", True), {
        "title": payload.get("title", "Forward Validation 验证结果"),
        "content": payload.get("content", ""),
        "disclaimer": payload.get("disclaimer", settings.disclaimer),
    })


@router.get("/leaders")
def leaders(current_user: dict = Depends(get_optional_user)) -> dict:
    return _service_envelope(current_user, read_leaders(current_user), "items")


@router.get("/frozen-orders")
def frozen_orders(current_user: dict = Depends(get_optional_user)) -> dict:
    return _service_envelope(current_user, read_frozen_orders(current_user))


@router.get("/strategy-judge")
def strategy_judge(current_user: dict = Depends(get_optional_user)) -> dict:
    return _service_envelope(current_user, read_strategy_judge(current_user))


@router.get("/membership")
def membership(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, read_membership(current_user))


@router.get("/disclaimer")
def disclaimer() -> dict:
    return {
        "success": True,
        "allowed": True,
        "membership_level": "anonymous",
        "data": read_disclaimer(),
    }


@router.get("/decision-center")
def decision_center(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, build_decision_center(current_user))


@router.get("/mainline")
def mainline(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, build_mainline_analysis(current_user))


@router.get("/daily-ai-report")
def daily_ai_report(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, build_daily_ai_report(current_user))


@router.get("/market-brain")
def market_brain(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, build_market_brain(current_user))


@router.get("/market-hub")
def market_hub(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, build_market_data_hub(current_user))


@router.get("/data-center/status")
def data_center_status(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, data_center.status())


@router.get("/trading-plan")
def trading_plan(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, build_trading_plan(current_user))


@router.get("/trade-script")
def trade_script(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, build_trade_script(current_user))


@router.get("/pre-market")
def pre_market(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, build_pre_market_ai(current_user))


@router.get("/auction-ai")
def auction_ai(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, build_auction_ai(current_user))


@router.get("/realtime-ai")
def realtime_ai(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, build_realtime_ai(current_user))


@router.get("/ai-decision")
def ai_decision(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, build_ai_decision(current_user))


@router.get("/trader-agent")
def trader_agent(current_user: dict = Depends(get_optional_user)) -> dict:
    return _envelope(current_user, True, build_trader_agent(current_user))


@router.post("/run-pipeline")
def run_pipeline(current_user: dict = Depends(get_optional_user)) -> dict:
    result = run_daily_pipeline()
    return _pipeline_envelope(current_user, result)


@router.get("/job-status/{job_id}")
def job_status(job_id: str, current_user: dict = Depends(get_optional_user)) -> dict:
    job = get_pipeline_job(job_id)
    if not job:
        return _envelope(
            current_user,
            True,
            {
                "job_id": job_id,
                "status": "failed",
                "progress": 0,
                "current_step": "任务不存在",
                "elapsed": 0,
                "message": "未找到该 Job，可能后端已重启或 job_id 不存在。",
                "steps": [],
            },
        )
    return _envelope(current_user, True, job)
