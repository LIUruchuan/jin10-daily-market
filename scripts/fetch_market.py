#!/usr/bin/env python3
"""
A 股市场行情数据抓取
数据源: akshare（免费开源金融数据接口）
"""

import os
import sys
import json
import csv
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

# ---------- 配置 ----------
BASE_DIR = Path(__file__).resolve().parent.parent
MARKET_DIR = BASE_DIR / "data" / "market"
HISTORY_DIR = BASE_DIR / "data" / "history"
for d in [MARKET_DIR, HISTORY_DIR]:
    d.mkdir(exist_ok=True)

MARKET_CSV = HISTORY_DIR / "market_history.csv"
SECTOR_CSV = HISTORY_DIR / "sector_ranking_history.csv"

# 追踪的主要指数
INDEX_CODES = [
    ("000001.SH", "上证指数"),
    ("399001.SZ", "深证成指"),
    ("399006.SZ", "创业板指"),
    ("000688.SH", "科创50"),
    ("000016.SH", "上证50"),
    ("000300.SH", "沪深300"),
]

# 10个热门板块（用东方财富板块代码）
SECTOR_CODES = [
    ("BK0463", "半导体"),
    ("BK0477", "新能源"),
    ("BK0445", "银行"),
    ("BK0473", "汽车"),
    ("BK0447", "房地产开发"),
    ("BK0468", "医药商业"),
    ("BK0475", "军工"),
    ("BK0423", "互联网服务"),
    ("BK0469", "酿酒"),
    ("BK0433", "电力"),
]


def fetch_index_data() -> list[dict]:
    """获取主要指数当日行情"""
    results = []
    import akshare as ak
    for code, name in INDEX_CODES:
        try:
            # 使用 stock_zh_index_daily_em 获取日频数据
            df = ak.stock_zh_index_daily_em(symbol=code)
            if df is not None and not df.empty:
                row = df.iloc[-1]  # 最新一天
                results.append({
                    "name": name,
                    "code": code,
                    "close": float(row["close"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "pct_change": float(row.get("pct_chg", 0)),
                })
        except Exception as e:
            print(f"[WARN] {name}({code}) 获取失败: {e}")
    return results


def fetch_sector_data() -> dict:
    """获取当日动态板块排行（涨幅前10 + 跌幅前10）"""
    result = {"top_gainers": [], "top_losers": [], "raw": []}
    import akshare as ak
    try:
        # 概念板块实时行情（动态获取全量）
        df = ak.stock_board_concept_name_em()
        if df is not None and not df.empty:
            # 列: 排名,板块名称,板块代码,最新价,涨跌额,涨跌幅,总市值,换手率,上涨家数,下跌家数,领涨股票,领涨股票-涨跌幅
            for _, row in df.iterrows():
                name = str(row.get("板块名称", ""))
                code = str(row.get("板块代码", ""))
                pct = float(row.get("涨跌幅", 0))
                price = float(row.get("最新价", 0))
                lead = str(row.get("领涨股票", ""))
                if name and code:
                    result["raw"].append({
                        "name": name,
                        "code": code,
                        "pct_change": pct,
                        "close": price,
                        "lead_stock": lead,
                    })

            # 按涨跌幅排序
            result["raw"].sort(key=lambda x: x["pct_change"], reverse=True)
            result["top_gainers"] = result["raw"][:10]
            result["top_losers"] = result["raw"][-10:]
            result["top_losers"].reverse()  # 跌幅最大的在前
    except Exception as e:
        print(f"[WARN] 动态板块排行获取失败: {e}")

    return result


def update_market_csv(indices: list[dict], sector_data: dict):
    """追加指数行情到 CSV，板块排行存另一张表"""
    beijing = datetime.now(timezone(timedelta(hours=8)))
    date_str = beijing.strftime("%Y-%m-%d")

    # 指数 CSV
    is_new = not MARKET_CSV.exists()
    with open(MARKET_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            header = ["date"]
            for idx in indices:
                header.append(f"{idx['name']}_close")
                header.append(f"{idx['name']}_pct")
            writer.writerow(header)
        row = [date_str]
        for idx in indices:
            row.append(idx.get("close", ""))
            row.append(idx.get("pct_change", ""))
        writer.writerow(row)

    # 板块排行 CSV（动态字段）
    top_gainers = sector_data.get("top_gainers", []) if sector_data else []
    top_losers = sector_data.get("top_losers", []) if sector_data else []

    is_new_sec = not SECTOR_CSV.exists()
    with open(SECTOR_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new_sec:
            writer.writerow(["date", "rank", "type", "name", "pct_change", "lead_stock"])
        for i, sec in enumerate(top_gainers):
            writer.writerow([date_str, i+1, "gain", sec["name"], sec["pct_change"], sec.get("lead_stock", "")])
        for i, sec in enumerate(top_losers):
            writer.writerow([date_str, i+1, "loss", sec["name"], sec["pct_change"], sec.get("lead_stock", "")])

    print(f"[SAVED] market_history.csv + sector_ranking_history.csv 追加: {date_str}")


def main():
    print("=" * 50)
    print(f"市场行情抓取: {datetime.now(timezone(timedelta(hours=8)))}")
    print("=" * 50)

    try:
        indices = fetch_index_data()
        print(f"  · 指数: {len(indices)} 个")
        for idx in indices:
            signal = "↑" if idx.get("pct_change", 0) > 0 else "↓"
            print(f"    {idx['name']}: {idx['close']:.0f} ({signal}{abs(idx['pct_change']):.2f}%)")
    except Exception as e:
        print(f"  · 指数获取异常: {e}")
        indices = []

    try:
        sector_data = fetch_sector_data()
        top = sector_data.get("top_gainers", [])
        bottom = sector_data.get("top_losers", [])
        print(f"  · 动态板块排行: 涨幅TOP10 + 跌幅TOP10")

        print("  📈 涨幅前3:")
        for sec in top[:3]:
            lead = sec.get("lead_stock", "")
            lead_str = f" (领涨: {lead})" if lead else ""
            print(f"    {sec['name']}: +{sec['pct_change']:.2f}%{lead_str}")
        print("  📉 跌幅前3:")
        for sec in bottom[:3]:
            print(f"    {sec['name']}: {sec['pct_change']:.2f}%")
    except Exception as e:
        print(f"  · 板块获取异常: {e}")
        sector_data = {"top_gainers": [], "top_losers": []}

    # 保存 JSON 快照
    beijing = datetime.now(timezone(timedelta(hours=8)))
    date_str = beijing.strftime("%Y-%m-%d")

    # 格式化 sectors 给 generate_report 用
    sectors_for_report = []
    for sec in (sector_data.get("top_gainers", []) + sector_data.get("top_losers", [])):
        sectors_for_report.append({"name": sec["name"], "pct_change": sec["pct_change"]})

    snapshot = {"date": date_str, "indices": indices, "sectors": sectors_for_report, "sector_detail": sector_data}
    with open(MARKET_DIR / f"{date_str}_market.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    update_market_csv(indices, sector_data)

    print("\n== 完成 ==")


if __name__ == "__main__":
    main()
