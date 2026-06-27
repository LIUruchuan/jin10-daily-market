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
    "原油|油价|OPEC|OPEC+|成品油|石油|天然气|能源": "能源",
    "黄金|白银|贵金属|金价|央行购金": "贵金属",
    "钢|铜|铝|煤炭|铁矿石|大宗商品": "大宗商品",
    "医药|医疗|药品|疫苗|生物": "医药",
    "汽车|新能源车|特斯拉|比亚迪|华为汽车": "汽车",
    "白酒|茅台|消费|零售|社零": "消费",
    "军工|国防|军事|武器|导弹|战机|舰艇|冲突|伊朗|以色列|加沙|哈马斯|也门|胡塞": "军工",
    "券商|保险|银行|金融监管|基金": "金融",
    "游戏|传媒|电影|互联网|电商|社交": "互联网",
    "出口|进口|外贸|关税|贸易逆差|制裁": "出口贸易",
    "美联储|美元|美联储|非农|CPI|通胀|美股": "金融",
    "港口|航运|集装箱|运费|海运|红海|苏伊士": "港口航运",
    "核电|核能|铀": "电力",
    "粮食|小麦|玉米|大豆|农产品|化肥": "农牧",
}

# 证据分级规则（Serenity evidence ladder）
# strong: 官方数据/央行操作/交易所公告
# medium: 正规财经媒体/行业数据
# weak: KOL/社交/传闻/分析观点
STRONG_PATTERNS = [
    r"(?:公布|发布|出炉).*?(?:GDP|CPI|PPI|PMI|社融|M2|进出口|贸易|零售|工业增加值)",
    r"(?:央行|人民银行|美联储|欧央行).*?(?:逆回购|MLF|LPR|降息|加息|降准|利率)",
    r"(?:交易所|证监会|上交所|深交所).*?(?:公告|问询|监管)",
    r"(?:国家统计局|财政部|商务部|发改委|工信部).*?(?:数据|发布|通知)",
    r"(?:公司|集团).*?(?:公告|披露|发布).*?(?:财报|年报|季报|业绩)",
    r"(?:初请|非农|CPI|GDP|PMI).*?(?:数据|报告)",
]

MEDIUM_PATTERNS = [
    r"(?:据.*?(?:报道|消息|获悉|了解))",
    r"(?:研报|分析|预计|预测|展望)",
    r"(?:机构|分析师|经济学家).*?(?:表示|认为|指出)",
    r"(?:行业|产业).*?(?:数据|报告|统计)",
]

WEAK_PATTERNS = [
    r"(?:传闻|消息人士|知情人士|市场传言)",
    r"(?:KOL|大V|博主|网友|热议)",
    r"(?:猜测|可能|或将|疑似)",
    r"(?:情绪|恐慌|狂欢|炒作)",
]


def classify_sector(content: str) -> list[str]:
    """根据内容关键词识别关联板块"""
    sectors = []
    for pattern, sector in SECTOR_KEYWORDS.items():
        if re.search(pattern, content):
            sectors.append(sector)
    return sectors if sectors else ["综合"]


def classify_evidence(content: str) -> str:
    """按 Serenity evidence ladder 给事件分级: strong / medium / weak"""
    for pat in STRONG_PATTERNS:
        if re.search(pat, content):
            return "strong"
    for pat in MEDIUM_PATTERNS:
        if re.search(pat, content):
            return "medium"
    for pat in WEAK_PATTERNS:
        if re.search(pat, content):
            return "weak"
    return "medium"  # 默认中等


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
                evidence = classify_evidence(content)
                # important 标记的事件自动升级到 strong
                if item.get("important", 0) == 1 and evidence != "strong":
                    evidence = "strong"
                all_events.append({
                    "id": item.get("id", ""),
                    "time": item["time"],
                    "content": content.strip(),
                    "important": item.get("important", 0),
                    "sectors": ",".join(sectors),
                    "evidence": evidence,
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
            writer.writerow(["date", "time", "content", "important", "sectors", "evidence"])
        for e in events:
            writer.writerow([
                date_str,
                e["time"],
                e["content"],
                e["important"],
                e["sectors"],
                e.get("evidence", "medium"),
            ])
    print(f"[SAVED] events_history.csv 追加 {len(events)} 条")


def main():
    print("=" * 50)
    print(f"金十事件抓取: {datetime.now(timezone(timedelta(hours=8)))}")
    print("=" * 50)

    events = fetch_jin10_events(hours=24)
    save_events(events)

    strong = [e for e in events if e.get("evidence") == "strong"]
    medium = [e for e in events if e.get("evidence") == "medium"]
    weak = [e for e in events if e.get("evidence") == "weak"]
    print(f"  · 事件分级: strong={len(strong)} medium={len(medium)} weak={len(weak)}")
    for e in strong[:5]:
        print(f"    [strong] [{e['time']}] {e['content'][:60]}...")

    print("\n== 完成 ==")


if __name__ == "__main__":
    main()
