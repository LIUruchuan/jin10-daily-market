#!/usr/bin/env python3
"""
金十数据日报生成器
汇总事件 + 行情数据，生成 Markdown 报告 + HTML 首页
"""

import os
import json
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

import requests

# ---------- 配置 ----------
BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
EVENTS_DIR = BASE_DIR / "data" / "events"
MARKET_DIR = BASE_DIR / "data" / "market"
HISTORY_DIR = BASE_DIR / "data" / "history"
REPORTS_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "x-app-id": "bVBF4FyRTn5NJF5n",
    "x-version": "1.0.0",
}


def load_latest_events() -> list[dict]:
    """加载最新的事件 JSON"""
    beijing = datetime.now(timezone(timedelta(hours=8)))
    date_str = beijing.strftime("%Y-%m-%d")
    path = EVENTS_DIR / f"{date_str}_events.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # 回退 yesterdays
    yesterday = (beijing - timedelta(days=1)).strftime("%Y-%m-%d")
    path2 = EVENTS_DIR / f"{yesterday}_events.json"
    if path2.exists():
        with open(path2, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_latest_market() -> dict:
    """加载最新的行情数据"""
    beijing = datetime.now(timezone(timedelta(hours=8)))
    date_str = beijing.strftime("%Y-%m-%d")
    path = MARKET_DIR / f"{date_str}_market.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"indices": [], "sectors": []}


def generate_markdown_report(events: list[dict], market: dict) -> str:
    """生成日报 Markdown"""
    beijing = datetime.now(timezone(timedelta(hours=8)))
    date_str = beijing.strftime("%Y-%m-%d")

    # 分类事件 by evidence tier
    strong_events = [e for e in events if e.get("evidence") == "strong"]
    medium_events = [e for e in events if e.get("evidence") == "medium"]
    weak_events = [e for e in events if e.get("evidence") == "weak"]

    # 统计板块出现频率
    sector_counts = Counter()
    for e in events:
        for s in e.get("sectors", "").split(","):
            if s.strip():
                sector_counts[s.strip()] += 1

    lines = [f"# 金十数据·每日要闻", "", f"**日期**: {date_str}", f"**数据源**: 金十 Flash API + akshare", "", "---", ""]

    # 高置信度事件（strong evidence）
    if strong_events:
        lines.append(f"## 高置信度事件 ({len(strong_events)}条)")
        lines.append("")
        for e in strong_events[:10]:
            lines.append(f"- **[{e.get('time', '')[:16]}]** {e.get('content', '')[:120]}")
            lines.append(f"  - 关联板块: {e.get('sectors', '综合')}")
            lines.append("")
    else:
        lines.append("## 高置信度事件")
        lines.append("")
        lines.append("今日无高置信度事件。")
        lines.append("")

    # 中等置信度事件
    if medium_events:
        lines.append(f"## 中等置信度事件 ({len(medium_events)}条)")
        lines.append("")
        for e in medium_events[:8]:
            lines.append(f"- [{e.get('time', '')[:16]}] {e.get('content', '')[:100]}")
        lines.append("")

    # 低置信度事件（弱信号——可能不具备参考价值）
    if weak_events:
        lines.append(f"## 弱信号 / 待验证 ({len(weak_events)}条)")
        lines.append("")
        lines.append("以下事件的证据来自社交媒体、传闻或分析师观点，仅供参考，需进一步核实。")
        lines.append("")
        for e in weak_events[:5]:
            lines.append(f"- [{e.get('time', '')[:16]}] {e.get('content', '')[:100]}")
        lines.append("")

    # 市场概况
    indices = market.get("indices", [])
    if indices:
        lines.append("## 📊 市场概况")
        lines.append("")
        lines.append("| 指数 | 收盘 | 涨跌幅 |")
        lines.append("|------|------|--------|")
        for idx in indices[:6]:
            signal = "🔴" if idx.get("pct_change", 0) > 0 else "🟢"
            lines.append(f"| {idx['name']} | {idx.get('close', 0):.0f} | {signal} {idx.get('pct_change', 0):+.2f}% |")
        lines.append("")

    # 板块涨跌
    sectors = market.get("sectors", [])
    if sectors:
        sorted_s = sorted(sectors, key=lambda x: x.get("pct_change", 0), reverse=True)
        lines.append("## 🏭 板块表现")
        lines.append("")
        lines.append(f"**📈 涨幅前三**")
        for s in sorted_s[:3]:
            lines.append(f"- {s['name']}: +{s.get('pct_change', 0):.2f}%")
        lines.append("")
        lines.append(f"**📉 跌幅前三**")
        for s in sorted_s[-3:]:
            lines.append(f"- {s['name']}: {s.get('pct_change', 0):.2f}%")
        lines.append("")

    # 板块热点统计
    if sector_counts:
        lines.append("## 📈 板块热点分布")
        lines.append("")
        top_sectors = sector_counts.most_common(5)
        for sector, count in top_sectors:
            lines.append(f"- **{sector}**: {count} 条相关事件")
        lines.append("")

    # 完整事件列表
    lines.append("## 📋 完整事件列表")
    lines.append("")
    lines.append(f"（共 {len(events)} 条，按时间倒序）")
    lines.append("")
    for e in events[:30]:
        tag = " 🔴重要" if e.get("important") == 1 else ""
        lines.append(f"- [{e.get('time', '')[:16]}]{tag} {e.get('content', '')[:100]}")

    if len(events) > 30:
        lines.append(f"\n*...还有 {len(events) - 30} 条事件*")

    lines.append("")
    lines.append("---")
    lines.append(f"*报告自动生成于 {beijing.strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")

    return "\n".join(lines)


def update_index_html():
    """更新 HTML 目录页"""
    beijing = datetime.now(timezone(timedelta(hours=8)))
    date_str = beijing.strftime("%Y-%m-%d")

    # 获取报告文件列表
    md_files = sorted(
        [f.name for f in REPORTS_DIR.glob("*.md") if f.name.endswith(".md")],
        reverse=True
    )[:20]

    # 加载最新市场数据用于首页展示
    market = load_latest_market()

    indices_str = json.dumps(market.get("indices", []), ensure_ascii=False)

    report_items = "\n".join([
        f'<li class="report-item"><a href="{f}">{f}</a></li>'
        for f in md_files
    ]) if md_files else '<li class="report-item">暂无报告</li>'

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>金十数据日报</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
h1 {{ color: #333; border-bottom: 2px solid #c0392b; padding-bottom: 10px; }}
.card {{ background: white; border-radius: 12px; padding: 20px; margin: 16px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.price-up {{ color: #e74c3c; font-weight: bold; }}
.price-down {{ color: #27ae60; font-weight: bold; }}
.report-list {{ list-style: none; padding: 0; }}
.report-item {{ background: white; margin: 6px 0; padding: 10px 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
.report-item a {{ color: #c0392b; text-decoration: none; }}
.report-item a:hover {{ text-decoration: underline; }}
.footer {{ margin-top: 30px; color: #aaa; font-size: 13px; text-align: center; }}
</style>
</head>
<body>
<h1>📰 金十数据 · 每日要闻与市场</h1>

<div class="card">
<h3>📊 最新市场数据 ({date_str})</h3>
<div id="marketTable"></div>
</div>

<div class="card">
<h3>📅 历史日报</h3>
<ul class="report-list">{report_items}</ul>
</div>

<div class="footer"><p>自动更新 · 每天 08:00 CST</p></div>

<script>
const indices = {indices_str};
let html = '<table style="width:100%;text-align:center;border-collapse:collapse;">';
html += '<tr style="background:#f0f0f0;"><th>指数</th><th>收盘价</th><th>涨跌幅</th></tr>';
indices.forEach(function(i) {{
  const css = i.pct_change > 0 ? "price-up" : "price-down";
  const signal = i.pct_change > 0 ? "&#9650;" : "&#9660;";
  html += '<tr><td>' + i.name + '</td><td>' + i.close.toFixed(0) + '</td><td class="' + css + '">' + signal + ' ' + i.pct_change.toFixed(2) + '%</td></tr>';
}});
html += '</table>';
document.getElementById('marketTable').innerHTML = html;
</script>
</body>
</html>'''

    with open(REPORTS_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[SAVED] reports/index.html")


def write_summary_json(events: list[dict], market: dict):
    """写入 data/summary.json 供 Workflow 通知使用，同时生成通知 HTML"""
    strong = [e for e in events if e.get("evidence") == "strong"]
    medium = [e for e in events if e.get("evidence") == "medium"]
    weak = [e for e in events if e.get("evidence") == "weak"]

    sector_counts = Counter()
    for e in events:
        for s in e.get("sectors", "").split(","):
            if s.strip():
                sector_counts[s.strip()] += 1

    top_sectors = [s for s, _ in sector_counts.most_common(3)]
    indices = market.get("indices", [])

    # 生成通知 HTML
    lines = []
    lines.append('<h3>金十数据日报</h3>')
    lines.append(f'<p><b>事件</b>: {len(events)}条 | 高置信度 {len(strong)} · 中 {len(medium)} · 弱 {len(weak)}</p>')

    # 优先展示 high-confidence events
    if strong:
        lines.append('<p style="color:#c0392b;"><b>重要事件:</b></p>')
        for e in strong[:3]:
            lines.append(f'<p style="margin:2px 0;font-size:13px;">· {e.get("content","")[:80]}</p>')

    if top_sectors:
        lines.append(f'<p><b>热点板块</b>: {", ".join(top_sectors)}</p>')

    if indices:
        idx = indices[0]
        pct = idx.get("pct_change", 0)
        color = "#e74c3c" if pct >= 0 else "#27ae60"
        lines.append(f'<p><b>{idx["name"]}</b>: <span style="color:{color};font-weight:bold;">{idx.get("close",0):.0f} ({pct:+.2f}%)</span></p>')

    lines.append('<br/><a href="https://liuruchuan.github.io/jin10-daily-market/">查看完整报告 →</a>')
    lines.append('<hr/><p style="color:#999;font-size:12px;">每日 08:00 自动推送</p>')

    outcome = {
        "total_events": len(events),
        "strong_events": len(strong),
        "medium_events": len(medium),
        "weak_events": len(weak),
        "top_sectors": top_sectors,
        "indices": indices,
        "notify_html": "\n".join(lines),
    }
    with open(HISTORY_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(outcome, f, ensure_ascii=False, indent=2)
    print("[SAVED] data/history/summary.json")


def main():
    print("=" * 50)
    print(f"生成日报: {datetime.now(timezone(timedelta(hours=8)))}")
    print("=" * 50)

    events = load_latest_events()
    market = load_latest_market()

    print(f"Events: {len(events)}, Indices: {len(market.get('indices',[]))}, Sectors: {len(market.get('sectors',[]))}")

    beijing = datetime.now(timezone(timedelta(hours=8)))
    date_str = beijing.strftime("%Y-%m-%d")

    report = generate_markdown_report(events, market)
    report_path = REPORTS_DIR / f"{date_str}-金十日报.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[SAVED] {report_path}")

    # 写入 summary JSON（供 Workflow 通知读取）
    write_summary_json(events, market)

    update_index_html()

    print("\n== 完成 ==")


if __name__ == "__main__":
    main()
