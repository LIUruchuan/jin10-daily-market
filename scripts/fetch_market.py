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


def fetch_sector_data() -> list[dict]:
    """获取板块当日行情"""
    results = []
    import akshare as ak
    today = date.today().strftime("%Y%m%d")

    for code, name in SECTOR_CODES:
        try:
            df = ak.stock_board_industry_hist_em(symbol=name, period="daily", start_date=today, end_date=today, adjust="")
            if df is not None and not df.empty:
                row = df.iloc[0] if len(df) > 0 else df.iloc[-1]
                results.append({
                    "name": name,
                    "code": code,
                    "close": float(row.get("收盘", 0)),
                    "pct_change": float(row.get("涨跌幅", 0)),
                })
        except Exception as e:
            print(f"[WARN] 板块 {name} 获取失败: {e}")
    return results


def update_market_csv(indices: list[dict], sectors: list[dict]):
    """追加一行行情数据到 CSV"""
    beijing = datetime.now(timezone(timedelta(hours=8)))
    date_str = beijing.strftime("%Y-%m-%d")

    is_new = not MARKET_CSV.exists()
    with open(MARKET_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            header = ["date"]
            for idx in indices:
                header.append(f"{idx['name']}_close")
                header.append(f"{idx['name']}_pct")
            for sec in sectors:
                header.append(f"{sec['name']}_close")
                header.append(f"{sec['name']}_pct")
            writer.writerow(header)

        row = [date_str]
        for idx in indices:
            row.append(idx.get("close", ""))
            row.append(idx.get("pct_change", ""))
        for sec in sectors:
            row.append(sec.get("close", ""))
            row.append(sec.get("pct_change", ""))
        writer.writerow(row)

    print(f"[SAVED] market_history.csv 追加: {date_str}")


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
        sectors = fetch_sector_data()
        print(f"  · 板块: {len(sectors)} 个")
        for sec in sorted(sectors, key=lambda x: x.get("pct_change", 0), reverse=True):
            signal = "↑" if sec.get("pct_change", 0) > 0 else "↓"
            print(f"    {sec['name']}: {signal}{sec['pct_change']:.2f}%")
    except Exception as e:
        print(f"  · 板块获取异常: {e}")
        sectors = []

    # 保存 JSON 快照
    beijing = datetime.now(timezone(timedelta(hours=8)))
    date_str = beijing.strftime("%Y-%m-%d")
    snapshot = {"date": date_str, "indices": indices, "sectors": sectors}
    with open(MARKET_DIR / f"{date_str}_market.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    update_market_csv(indices, sectors)

    print("\n== 完成 ==")


if __name__ == "__main__":
    main()
