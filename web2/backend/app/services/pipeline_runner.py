from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

from app.core.config import settings
from app.services.broker_center import build_broker_center
from app.services.daily_ai_report import build_daily_ai_report
from app.services.data_center import data_center
from app.services.data_sanitizer import sanitize_data
from app.services.decision_center import build_decision_center
from app.services.job_manager import job_manager
from app.services.mainline_engine import build_mainline_analysis
from app.services.market_brain import build_market_brain
from app.services.pipeline_health import run_pipeline_health_check
from app.services.quote_sync import sync_latest_quotes_for_trading_date
from app.services.trader_agent import build_trader_agent


# One Click Review 的固定阶段。只允许调整编排和健康检查，不在这里新增策略逻辑。
PIPELINE_STAGES = {
    "PREFLIGHT": "preflight health check",
    "SANITIZE": "sanitize dirty data",
    "RUN_MAIN": "run main.py",
    "QUOTE_SYNC": "sync latest quotes",
    "LEDGER_REPLAY": "trades replay rebuild",
    "DATA_CENTER": "refresh data center",
    "MARKET_BRAIN": "refresh Market Brain",
    "MAINLINE": "refresh Mainline",
    "AI_REPORT": "refresh AI Report",
    "DECISION_CENTER": "refresh Decision Center",
    "TRADER_AGENT": "refresh Trader Agent",
    "BROKER_CENTER": "refresh Broker Center",
    "FINAL_HEALTH": "final health check",
}


def run_daily_pipeline() -> dict:
    job = job_manager.create_job()
    thread = threading.Thread(target=_run_pipeline_job, args=(job["job_id"],), daemon=True)
    thread.start()
    return {"success": True, "status": "queued", "job_id": job["job_id"]}


def get_pipeline_job(job_id: str) -> dict | None:
    return job_manager.get_job(job_id)


def _run_pipeline_job(job_id: str) -> None:
    root = settings.project_root
    system_user = {"membership_level": "admin", "username": "pipeline", "is_active": True}
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"pipeline_{job_id}_stdout.log"
    stderr_path = log_dir / f"pipeline_{job_id}_stderr.log"
    command = [sys.executable, "-X", "utf8", "main.py"]
    step_results: list[dict] = []
    start = time.perf_counter()

    try:
        _step(job_id, step_results, PIPELINE_STAGES["PREFLIGHT"], 5, lambda: run_pipeline_health_check(system_user))
        _step(job_id, step_results, PIPELINE_STAGES["SANITIZE"], 10, lambda: sanitize_data(dry_run=False))
        main_result = _run_main(job_id, command, root, stdout_path, stderr_path, step_results)
        if not main_result.get("success"):
            _finish_failed(job_id, step_results, main_result)
            return

        latest_date = _latest_report_date(root)
        quote_status = _step(
            job_id,
            step_results,
            PIPELINE_STAGES["QUOTE_SYNC"],
            55,
            lambda: sync_latest_quotes_for_trading_date(latest_date, root),
        )
        rebuild_result = _step(
            job_id,
            step_results,
            PIPELINE_STAGES["LEDGER_REPLAY"],
            60,
            lambda: _rebuild_paper_ledger(root, latest_date),
        )
        _step(job_id, step_results, PIPELINE_STAGES["DATA_CENTER"], 65, lambda: data_center.get_latest_context())
        _step(job_id, step_results, PIPELINE_STAGES["MARKET_BRAIN"], 70, lambda: build_market_brain(system_user))
        _step(job_id, step_results, PIPELINE_STAGES["MAINLINE"], 75, lambda: build_mainline_analysis(system_user))
        _step(job_id, step_results, PIPELINE_STAGES["AI_REPORT"], 80, lambda: build_daily_ai_report(system_user))
        _step(job_id, step_results, PIPELINE_STAGES["DECISION_CENTER"], 84, lambda: build_decision_center(system_user))
        _step(job_id, step_results, PIPELINE_STAGES["TRADER_AGENT"], 88, lambda: build_trader_agent(system_user))
        _step(job_id, step_results, PIPELINE_STAGES["BROKER_CENTER"], 92, lambda: build_broker_center(system_user))
        final_health = _step(job_id, step_results, PIPELINE_STAGES["FINAL_HEALTH"], 96, lambda: run_pipeline_health_check(system_user))

        elapsed = round(time.perf_counter() - start, 2)
        summary = {
            "elapsed": elapsed,
            "latest_report_date": latest_date,
            "quote_sync_status": quote_status.get("quote_sync_status", ""),
            "ledger_source": "trades replay",
            "ledger_consistent": final_health.get("ledger_consistent", False),
            "total_assets": rebuild_result.get("total_assets", ""),
            "health_score": final_health.get("health_score", 0),
            "final_status": final_health.get("status", ""),
            "steps": step_results,
        }
        _append_pipeline_log(root, job_id, "completed", summary)
        job_manager.finish_job(job_id, _format_summary(summary))
    except Exception:
        tb = traceback.format_exc()
        _append_pipeline_log(root, job_id, "exception", {"traceback": tb, "steps": step_results})
        job_manager.fail_job(job_id, tb)


def _step(job_id: str, step_results: list[dict], name: str, progress: int, fn):
    start = time.perf_counter()
    job_manager.update_job(job_id, status="running", progress=progress, current_step=name, message=f"Running: {name}")
    try:
        result = fn()
        elapsed = round(time.perf_counter() - start, 2)
        item = {"name": name, "status": "ok", "time": elapsed, "message": _safe_json(result)}
        step_results.append(item)
        job_manager.update_job(job_id, status="running", progress=progress, current_step=name, message=item["message"])
        return result if isinstance(result, dict) else {"result": result}
    except Exception:
        elapsed = round(time.perf_counter() - start, 2)
        tb = traceback.format_exc()
        item = {"name": name, "status": "failed", "time": elapsed, "message": tb}
        step_results.append(item)
        job_manager.update_job(job_id, status="running", progress=progress, current_step=name, message=tb)
        raise


def _run_main(job_id: str, command: list[str], root: Path, stdout_path: Path, stderr_path: Path, step_results: list[dict]) -> dict:
    start = time.perf_counter()
    job_manager.update_job(job_id, status="running", progress=20, current_step="run main.py", message="Running main.py")
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
        "w", encoding="utf-8", errors="replace"
    ) as stderr_file:
        process = subprocess.Popen(command, cwd=root, stdout=stdout_file, stderr=stderr_file, text=True)
        completed_by_outputs = False
        timed_out = False
        while process.poll() is None:
            elapsed = time.perf_counter() - start
            if elapsed >= 20 and (
                _pipeline_outputs_ready(root, time.strftime("%Y%m%d"))
                or _pipeline_outputs_ready(root, _latest_report_date(root))
            ):
                completed_by_outputs = True
                job_manager.update_job(
                    job_id,
                    status="running",
                    progress=50,
                    current_step="main.py outputs ready",
                    message="main.py outputs are ready; terminating stale child processes and continuing.",
                )
                _terminate_process_tree(process)
                break
            if elapsed >= 180:
                if _pipeline_outputs_ready(root, time.strftime("%Y%m%d")) or _pipeline_outputs_ready(root, _latest_report_date(root)):
                    completed_by_outputs = True
                    job_manager.update_job(
                        job_id,
                        status="running",
                        progress=50,
                        current_step="main.py outputs ready",
                        message="main.py outputs are ready; terminating stale child processes and continuing.",
                    )
                    _terminate_process_tree(process)
                    break
                timed_out = True
                _terminate_process_tree(process)
                break
            progress, step = _progress_for_elapsed(elapsed)
            job_manager.update_job(job_id, status="running", progress=progress, current_step=step, message=f"main.py running {elapsed:.0f}s")
            time.sleep(2)

    stdout = _read_text(stdout_path)
    stderr = _read_text(stderr_path)
    elapsed = round(time.perf_counter() - start, 2)
    result = {
        "success": process.returncode == 0 or completed_by_outputs,
        "returncode": process.returncode,
        "completed_by_outputs": completed_by_outputs,
        "timed_out": timed_out,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout": stdout,
        "stderr": stderr,
        "traceback": _extract_traceback(stdout, stderr),
    }
    step_results.append({"name": "run main.py", "status": "ok" if result["success"] else "failed", "time": elapsed, "message": _main_message(result)})
    job_manager.update_job(job_id, status="running", progress=50, current_step="run main.py", message=_main_message(result))
    _append_pipeline_log(root, job_id, "main.py", result)
    return result


def _finish_failed(job_id: str, step_results: list[dict], main_result: dict) -> None:
    message = _main_message(main_result)
    if main_result.get("traceback"):
        message += "\n\nTRACEBACK:\n" + main_result["traceback"]
    job_manager.fail_job(job_id, message)


def _format_summary(summary: dict) -> str:
    lines = [
        "One Click Review completed.",
        f"health_score={summary.get('health_score')}",
        f"final_status={summary.get('final_status')}",
        f"latest_report_date={summary.get('latest_report_date')}",
        f"ledger_source={summary.get('ledger_source')}",
        f"ledger_consistent={summary.get('ledger_consistent')}",
        f"quote_sync_status={summary.get('quote_sync_status')}",
        f"total_assets={summary.get('total_assets')}",
    ]
    return "\n".join(lines)


def _main_message(result: dict) -> str:
    if result.get("completed_by_outputs"):
        text = "main.py outputs are ready; stale child processes were terminated after required files were generated.\n"
        text += f"raw_returncode={result.get('returncode')}\n"
        if result.get("traceback"):
            text += result["traceback"]
        else:
            text += (result.get("stderr") or result.get("stdout") or "")[-4000:]
        return text
    text = f"main.py returncode={result.get('returncode')}\n"
    if result.get("traceback"):
        text += result["traceback"]
    else:
        text += (result.get("stderr") or result.get("stdout") or "")[-4000:]
    return text


def _progress_for_elapsed(elapsed: float) -> tuple[int, str]:
    if elapsed < 20:
        return 25, "main.py: downloading quotes"
    if elapsed < 60:
        return 32, "main.py: scoring"
    if elapsed < 120:
        return 40, "main.py: reports"
    return 48, "main.py: still running"


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_traceback(stdout: str, stderr: str) -> str:
    combined = stdout + "\n" + stderr
    marker = "Traceback (most recent call last):"
    index = combined.find(marker)
    return combined[index:] if index >= 0 else ""


def _pipeline_outputs_ready(root: Path, target_date: str) -> bool:
    if not target_date:
        return False
    paths = [
        root / "data" / "raw" / f"daily_quotes_{target_date}.csv",
        root / "data" / "processed" / f"trend_core_pool_{target_date}.csv",
        root / "reports" / "daily" / f"daily_report_{target_date}.md",
        root / "portfolio" / "positions.csv",
        root / "portfolio" / "equity_curve.csv",
    ]
    if not all(path.exists() and path.stat().st_size > 0 for path in paths):
        return False
    return all(_file_has_date(path, target_date) for path in paths)


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=8)
    except Exception:
        process.kill()


def _file_has_date(path: Path, target_date: str) -> bool:
    try:
        return target_date in path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return False


def _latest_report_date(root: Path) -> str:
    candidates: list[str] = []
    for pattern in ["reports/daily/daily_report_*.md", "data/processed/trend_core_pool_*.csv", "data/raw/daily_quotes_*.csv"]:
        paths = sorted(root.glob(pattern))
        if paths:
            digits = "".join(ch for ch in paths[-1].stem if ch.isdigit())
            if len(digits) >= 8:
                candidates.append(digits[-8:])
    return candidates[0] if candidates else time.strftime("%Y%m%d")


def _rebuild_paper_ledger(root: Path, latest_date: str) -> dict:
    module_path = root / "ledger_rebuilder.py"
    spec = importlib.util.spec_from_file_location("ledger_rebuilder", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load ledger_rebuilder.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.rebuild_ledger(root, latest_date)


def _safe_json(value) -> str:
    import json

    try:
        return json.dumps(value, ensure_ascii=False, default=str)[-4000:]
    except Exception:
        return str(value)[-4000:]


def _append_pipeline_log(root: Path, job_id: str, event: str, payload: dict) -> None:
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} | job_id={job_id} | event={event}\n{_safe_json(payload)}\n\n"
    with (log_dir / "pipeline.log").open("a", encoding="utf-8", errors="replace") as file:
        file.write(line)
