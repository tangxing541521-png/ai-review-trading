from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
FROZEN_DIR = PROJECT_ROOT / "frozen_decisions"
DISCLAIMER = "仅供学习研究和模拟验证，不构成投资建议；新闻风险只做标记，不改变冻结交易决策。"

HIGH_KEYWORDS = ["立案", "调查", "退市", "暂停上市", "重大违法", "暴雷", "亏损扩大", "监管函", "处罚", "ST"]
MEDIUM_KEYWORDS = ["减持", "问询函", "诉讼", "仲裁", "解禁", "业绩预减", "业绩下滑", "担保", "质押"]


def _candidate_paths(target_date: str) -> list[Path]:
    names = [
        f"news_{target_date}.txt",
        f"news_{target_date}.md",
        f"news_{target_date}.csv",
        f"announcements_{target_date}.txt",
        f"announcements_{target_date}.md",
        f"announcements_{target_date}.csv",
    ]
    dirs = [
        PROJECT_ROOT / "news",
        PROJECT_ROOT / "announcements",
        PROJECT_ROOT / "data" / "news",
        PROJECT_ROOT / "data" / "announcements",
    ]
    return [folder / name for folder in dirs for name in names]


def _read_sources(target_date: str) -> tuple[str, list[str]]:
    chunks = []
    used = []
    for path in _candidate_paths(target_date):
        if path.exists() and path.stat().st_size > 0:
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
            used.append(str(path))
    return "\n".join(chunks), used


def evaluate_news_risk(target_date: str | None = None) -> dict:
    target_date = target_date or datetime.now().strftime("%Y%m%d")
    FROZEN_DIR.mkdir(parents=True, exist_ok=True)
    text, sources = _read_sources(target_date)
    high_hits = [word for word in HIGH_KEYWORDS if word in text]
    medium_hits = [word for word in MEDIUM_KEYWORDS if word in text]

    if high_hits:
        risk_level = "HIGH"
        reason = f"命中高风险关键词：{'、'.join(high_hits)}"
    elif medium_hits:
        risk_level = "MEDIUM"
        reason = f"命中中风险关键词：{'、'.join(medium_hits)}"
    elif sources:
        risk_level = "LOW"
        reason = "读取到新闻/公告，但未命中预设风险关键词。"
    else:
        risk_level = "LOW"
        reason = "未发现本地新闻/公告文件，默认仅标记为 LOW。"

    result = {
        "date": target_date,
        "risk_level": risk_level,
        "reason": reason,
        "sources": sources,
        "high_keywords": high_hits,
        "medium_keywords": medium_hits,
        "decision_effect": "MARK_ONLY_DO_NOT_CHANGE_ORDER",
        "disclaimer": DISCLAIMER,
    }
    out_path = FROZEN_DIR / f"news_risk_{target_date}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="新闻/公告风险标记引擎")
    parser.add_argument("--date", help="日期，格式 YYYYMMDD；默认今天")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = evaluate_news_risk(args.date)
    print(f"日期：{result['date']}")
    print(f"新闻风险等级：{result['risk_level']}")
    print(f"原因：{result['reason']}")
    print("说明：该结果只做风险标签，不改变任何冻结订单或仓位。")


if __name__ == "__main__":
    main()
