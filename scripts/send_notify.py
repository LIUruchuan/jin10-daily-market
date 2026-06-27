#!/usr/bin/env python3
"""
Server酱通知发送器
用法: python3 notify.py <title_prefix> <summary_json_path>
将 summary.json 中的 notify_html 转为纯文本后发送（微信不支持HTML渲染）
"""
import sys
import json
import re
import urllib.request
import os
from datetime import datetime, timezone, timedelta

SENDKEY = os.environ.get("SERVERCHAN_SENDKEY", "")
if not SENDKEY:
    print("No SERVERCHAN_SENDKEY, skip.")
    sys.exit(0)

title_prefix = sys.argv[1] if len(sys.argv) > 1 else "日报"
summary_path = sys.argv[2] if len(sys.argv) > 2 else "data/summary.json"

beijing = datetime.now(timezone(timedelta(hours=8)))
date_str = beijing.strftime("%Y-%m-%d")

# 读取通知内容（优先 Markdown，回退 HTML→纯文本）
text = "no data"
try:
    with open(summary_path, "r", encoding="utf-8") as f:
        d = json.load(f)
        # 优先读 notify_text（Markdown格式，链接可点击）
        text = d.get("notify_text") or d.get("notify_html", text)
except Exception as e:
    print(f"[WARN] Failed to read summary.json: {e}")

title = f"{title_prefix} ({date_str})"
payload = json.dumps({"title": title, "desp": text}).encode("utf-8")

req = urllib.request.Request(
    f"https://sctapi.ftqq.com/{SENDKEY}.send",
    data=payload,
    headers={"Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
resp = json.loads(urllib.request.urlopen(req).read().decode())
if resp.get("code") == 0:
    print(f"Server酱 notified: {resp['data']['pushid']}")
else:
    print(f"Server酱 failed: {resp}")
