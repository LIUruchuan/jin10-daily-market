#!/usr/bin/env python3
"""
金十数据 24小时新闻事件抓取
数据源: 金十 Flash API（免费公开接口）
"""

import os
import json
import csv
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# ---------- 配置 ----------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EVENTS_DIR = DATA_DIR / "events"
HISTORY_DIR = DATA_DIR / "history"
for d in [DATA_DIR, EVENTS_DIR, HISTORY_DIR]:
    d.mkdir(exist_ok=True)

JIN10_API = "https://flash-api.jin10.com/get_flash_list"
EVENTS_CSV = HISTORY_DIR / "events_history.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.jin10.com/",
    "x-app-id": "bVBF4FyRTn5NJF5n",
    "x-version": "1.0.0",
}

# 事件关键词 → 关联板块
SECTOR_KEYWORDS = {
    "央行|降息|加息|利率|逆回购|MLF|LPR|存款准备金": "银行",
    "芯片|半导体|光刻|AI|人工智能|英伟达|台积电|存储": "半导体",
    "新能源|光伏|锂电|储能|风电|电车|电池": "新能源",
    "房地产|楼市|房贷|土地|物业|房价": "房地产",
    "原油|油价|OPEC|成品油|石油|天然气": "能源",
    "黄金|白银|贵金属|金价|央行购金": "贵金属",
    "钢|铜|铝|煤炭|铁矿石|大宗商品": "大宗商品",
    "医药|医疗|药品|疫苗|生物": "医药",
    "汽车|新能源车|特斯拉|比亚迪|华为汽车": "汽车",
    "白酒|茅台|消费|零售|社零": "消费",
    "军工|国防|军事|武器": "军工",
    "券商|保险|银行|金融监管|基金": "金融",
    "游戏|传媒|电影|互联网|电商|社交": "互联网",
    "出口|进口|外贸|关税|贸易逆差": "出口贸易",
}


def classify_sector(content: str) -> list[str]:
    """根据内容关键词识别关联板块"""
    sectors = []
    for pattern, sector in SECTOR_KEYWORDS.items():
        if re.search(pattern, content):
            sectors.append(sector)
    return sectors if sectors else ["综合"]


def fetch_jin10_events(hours: int = 24) -> list[dict]:
    """获取金十过去 N 小时的事件"""
    all_events = []
    # 翻页抓取（每页最多 20 条）
    for page in range(5):  # 最多 100 条
        ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        params = {
            "channel": "-8200",
            "vip": "1",
            "max_time": "",
            "_": str(ts),
        }
        try:
            resp = requests.get(JIN10_API, params=params, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                break
            data = resp.json()
            items = data.get("data", [])
            if not items:
                break

            cutoff = datetime.now(timezone(timedelta(hours=8))) - timedelta(hours=hours)
            for item in items:
                try:
                    t = datetime.strptime(item["time"], "%Y-%m-%d %H:%M:%S")
                    t = t.replace(tzinfo=timezone(timedelta(hours=8)))
                except (ValueError, KeyError):
                    continue

                if t < cutoff:
                    continue

                content = item.get("data", {}).get("content", "")
                if not content:
                    continue

                # 过滤纯广告和VIP锁定内容
                if item.get("data", {}).get("lock"):
                    continue
                if item.get("data", {}).get("ad"):
                    continue
                if "正在直播" in content or "解锁VIP" in content:
                    continue

                sectors = classify_sector(content)
                all_events.append({
                    "id": item.get("id", ""),
                    "time": item["time"],
                    "content": content.strip(),
                    "important": item.get("important", 0),
                    "sectors": ",".join(sectors),
                    "has_market_data": "remark" in item and bool(item.get("remark")),
                })

            time.sleep(0.5)  # 礼貌限速

        except Exception as e:
            print(f"[WARN] API 请求失败: {e}")
            break

    # 去重
    seen = set()
    unique = []
    for e in all_events:
        if e["id"] not in seen:
            seen.add(e["id"])
            unique.append(e)

    print(f"[JIN10] 获取 {len(all_events)} 条原始事件，去重后 {len(unique)} 条")
    return unique


def save_events(events: list[dict]):
    """保存原始事件到 JSON 和累积到 CSV"""
    beijing = datetime.now(timezone(timedelta(hours=8)))
    date_str = beijing.strftime("%Y-%m-%d")

    # 保存原始 JSON
    json_path = EVENTS_DIR / f"{date_str}_events.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    print(f"[SAVED] {json_path} ({len(events)} events)")

    # 追加到累积 CSV
    is_new = not EVENTS_CSV.exists()
    with open(EVENTS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["date", "time", "content", "important", "sectors"])
        for e in events:
            # 检查今日是否已有同一 ID
            if not is_new:
                pass  # 简单追加，让 generate_report 去重
            writer.writerow([
                date_str,
                e["time"],
                e["content"],
                e["important"],
                e["sectors"],
            ])
    print(f"[SAVED] events_history.csv 追加 {len(events)} 条")


def main():
    print("=" * 50)
    print(f"金十事件抓取: {datetime.now(timezone(timedelta(hours=8)))}")
    print("=" * 50)

    events = fetch_jin10_events(hours=24)
    save_events(events)

    important = [e for e in events if e["important"] == 1]
    print(f"  · 重要事件: {len(important)} 条")
    for e in important[:5]:
        print(f"    [{e['time']}] {e['content'][:60]}... | 板块: {e['sectors']}")

    print("\n== 完成 ==")


if __name__ == "__main__":
    main()
