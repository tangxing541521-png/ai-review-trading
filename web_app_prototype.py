from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
USERS_PATH = PROJECT_ROOT / "users.json"
DISCLAIMER = "免责声明：本系统仅供学习研究和模拟验证，不构成投资建议；过往回测和模拟结果不代表未来收益。"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def read_json(path: Path, default):
    if not path.exists() or path.stat().st_size == 0:
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str)
    except Exception as exc:
        st.warning(f"读取文件失败：{path.name}，原因：{exc}")
        return pd.DataFrame()


def read_markdown(path: Path) -> str:
    if not path.exists() or path.stat().st_size == 0:
        return "暂无报告，请先运行每日交易员流程。"
    return path.read_text(encoding="utf-8", errors="ignore")


def latest_row(path: Path) -> dict:
    data = read_csv(path)
    if data.empty:
        return {}
    return data.iloc[-1].fillna("").to_dict()


def load_users() -> list[dict]:
    return read_json(USERS_PATH, [])


def is_active_member(user: dict) -> bool:
    if not user or not user.get("is_active"):
        return False
    level = user.get("membership_level")
    if level == "admin":
        return True
    if level != "member":
        return False
    try:
        expire = datetime.strptime(user.get("expire_date", ""), "%Y-%m-%d").date()
        return expire >= date.today()
    except Exception:
        return False


def is_admin(user: dict) -> bool:
    return bool(user and user.get("membership_level") == "admin" and user.get("is_active"))


def authenticate(username: str, password: str) -> dict | None:
    password_hash = hash_password(password)
    for user in load_users():
        if user.get("username") == username and user.get("password_hash") == password_hash:
            return user
    return None


def require_member(user: dict) -> bool:
    if is_active_member(user) or is_admin(user):
        return True
    st.info("请升级会员后查看完整内容。免费用户当前只能查看市场状态、风险等级和本地复盘入口。")
    return False


def run_script(args: list[str]) -> None:
    with st.spinner("脚本运行中，请等待终端输出完成..."):
        completed = subprocess.run(
            [sys.executable, "-u", "-X", "utf8", *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    st.code((completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else ""))
    if completed.returncode == 0:
        st.success("运行完成。")
    else:
        st.error(f"运行失败，错误码：{completed.returncode}")


def page_header(title: str) -> None:
    st.title(title)
    st.caption(DISCLAIMER)


def login_panel() -> dict:
    st.sidebar.header("用户登录")
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user:
        user = st.session_state.user
        st.sidebar.success(f"当前用户：{user['username']}（{user['membership_level']}）")
        if st.sidebar.button("退出登录"):
            st.session_state.user = None
            st.rerun()
        return user

    username = st.sidebar.text_input("用户名", value="free")
    password = st.sidebar.text_input("密码", type="password", value="free123")
    if st.sidebar.button("登录"):
        user = authenticate(username, password)
        if user and user.get("is_active"):
            st.session_state.user = user
            st.rerun()
        else:
            st.sidebar.error("用户名、密码错误，或账号未启用。")
    return {}


def dashboard(user: dict) -> None:
    page_header("首页仪表盘")
    validation = latest_row(PROJECT_ROOT / "forward_validation.csv")
    master = latest_row(PROJECT_ROOT / "market_master_signal.csv")
    risk = latest_row(PROJECT_ROOT / "risk_control_report.csv")
    account = latest_row(PROJECT_ROOT / "paper_account.csv")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("市场状态", validation.get("market_regime_final") or master.get("market_regime_final", "暂无"))
    col2.metric("是否允许交易", validation.get("allow_trade", "暂无"))
    col3.metric("风险等级", risk.get("risk_level", "暂无"))
    col4.metric("当前总资产", account.get("total_assets", "暂无"))

    st.subheader("本地运行")
    if st.button("运行本地实时复盘（Analysis Mode）"):
        run_script(["forward_test.py"])

    if is_active_member(user) or is_admin(user):
        if st.button("运行一键交易员模式（Trading Mode）"):
            run_script(["app_launcher.py", "--run-today"])
    else:
        st.info("一键交易员模式为会员功能。")


def market_status_page(user: dict) -> None:
    page_header("今日市场状态")
    validation = latest_row(PROJECT_ROOT / "forward_validation.csv")
    master = latest_row(PROJECT_ROOT / "market_master_signal.csv")
    risk = latest_row(PROJECT_ROOT / "risk_control_report.csv")

    st.write("当前市场周期：", master.get("cycle", "暂无"))
    st.write("市场最终状态：", validation.get("market_regime_final") or master.get("market_regime_final", "暂无"))
    st.write("是否允许交易：", validation.get("allow_trade", "暂无"))
    st.write("建议仓位：", validation.get("position_advice", "暂无"))
    st.write("风险等级：", risk.get("risk_level", "暂无"))

    if require_member(user):
        st.subheader("会员可见：推荐与龙头摘要")
        st.write("推荐股票：", validation.get("recommended_names", "暂无"))
        st.write("龙头股票：", validation.get("leader_names", "暂无"))


def review_report_page(user: dict) -> None:
    page_header("今日复盘报告")
    if not require_member(user):
        st.write("免费版仅显示市场状态摘要，不展示完整股票池、订单详情和完整报告。")
        return

    target_date = datetime.now().strftime("%Y%m%d")
    report_candidates = [
        PROJECT_ROOT / "final_report.md",
        PROJECT_ROOT / "reports" / "forward_test" / f"forward_report_{target_date}.md",
    ]
    for path in report_candidates:
        st.subheader(path.name)
        st.markdown(read_markdown(path))

    orders = read_csv(PROJECT_ROOT / "frozen_decisions" / f"orders_{target_date}.csv")
    if not orders.empty:
        st.subheader("冻结订单详情")
        st.dataframe(orders, use_container_width=True)
        st.download_button("导出冻结订单 CSV", orders.to_csv(index=False).encode("utf-8-sig"), file_name=f"orders_{target_date}.csv")


def paper_trading_page(user: dict) -> None:
    page_header("Paper Trading 账户")
    if not require_member(user):
        return

    account = read_csv(PROJECT_ROOT / "paper_account.csv")
    positions = read_csv(PROJECT_ROOT / "paper_positions.csv")
    trades = read_csv(PROJECT_ROOT / "paper_trades.csv")
    equity = read_csv(PROJECT_ROOT / "paper_equity_curve.csv")

    if not account.empty:
        latest = account.iloc[-1].fillna("")
        col1, col2, col3 = st.columns(3)
        col1.metric("总资产", latest.get("total_assets", ""))
        col2.metric("现金", latest.get("cash", ""))
        col3.metric("累计收益", f"{latest.get('cumulative_return', '')}%")

    st.subheader("当前持仓")
    st.dataframe(positions, use_container_width=True)
    st.subheader("交易记录")
    st.dataframe(trades, use_container_width=True)
    st.subheader("资金曲线")
    st.dataframe(equity.tail(20), use_container_width=True)
    if not equity.empty:
        st.line_chart(pd.to_numeric(equity["total_assets"], errors="coerce"))
        st.download_button("导出资金曲线 CSV", equity.to_csv(index=False).encode("utf-8-sig"), file_name="paper_equity_curve.csv")


def forward_validation_page(user: dict) -> None:
    page_header("Forward Validation 结果")
    if not require_member(user):
        return

    validation = read_csv(PROJECT_ROOT / "forward_validation.csv")
    st.dataframe(validation, use_container_width=True)
    if not validation.empty:
        st.download_button("导出 Forward Validation CSV", validation.to_csv(index=False).encode("utf-8-sig"), file_name="forward_validation.csv")
    st.subheader("验证报告")
    st.markdown(read_markdown(PROJECT_ROOT / "validation_report.md"))


def membership_page(user: dict) -> None:
    page_header("会员权限模拟")
    if not user:
        st.warning("请先登录。")
        return

    st.write("用户名：", user.get("username"))
    st.write("会员等级：", user.get("membership_level"))
    st.write("到期日期：", user.get("expire_date"))
    st.write("账号状态：", "启用" if user.get("is_active") else "停用")
    st.write("会员内容权限：", "可访问" if is_active_member(user) or is_admin(user) else "不可访问")

    if is_admin(user):
        st.subheader("管理员：本地用户列表")
        st.dataframe(pd.DataFrame(load_users()), use_container_width=True)
        st.subheader("管理员：系统文件状态")
        files = ["final_report.md", "validation_report.md", "paper_report.md", "forward_validation.csv", "paper_equity_curve.csv"]
        st.dataframe(pd.DataFrame([{"file": item, "exists": (PROJECT_ROOT / item).exists()} for item in files]), use_container_width=True)


def disclaimer_page() -> None:
    page_header("免责声明")
    st.markdown(
        """
本系统当前只作为本地学习研究工具、策略验证工具和模拟交易工具。

- 不构成投资建议。
- 不提供真实投顾服务。
- 不承诺收益。
- 不保证回测或模拟结果会在未来复现。
- 不接入券商接口。
- 不自动下单。
- 不控制任何第三方交易软件。

市场有风险，使用者应独立判断并自行承担风险。
"""
    )


def main() -> None:
    st.set_page_config(page_title="AI Review Trading 本地原型", layout="wide")
    user = login_panel()
    st.sidebar.markdown("---")
    st.sidebar.caption("测试账号：free/free123，member/member123，admin/admin123")

    pages = {
        "首页仪表盘": lambda: dashboard(user),
        "今日市场状态": lambda: market_status_page(user),
        "今日复盘报告": lambda: review_report_page(user),
        "Paper Trading 账户": lambda: paper_trading_page(user),
        "Forward Validation 结果": lambda: forward_validation_page(user),
        "会员权限模拟": lambda: membership_page(user),
        "免责声明页面": disclaimer_page,
    }
    choice = st.sidebar.radio("页面", list(pages.keys()))
    pages[choice]()


if __name__ == "__main__":
    main()
