#!/usr/bin/env python3
"""
Server酱通知发送器（Markdown格式，微信可渲染链接/粗体）
用法: python3 send_notify.py <title_prefix> <summary_json_path>
"""
import sys
import json
import urllib.request
import os
from datetime import datetime, timezone, timedelta

SENDKEY = os.environ.get("SERVERCHAN_SENDKEY", "")
if not SENDKEY:
    print("[SKIP] No SERVERCHAN_SENDKEY in environment.")
    sys.exit(0)

title_prefix = sys.argv[1] if len(sys.argv) > 1 else "日报"
summary_path = sys.argv[2] if len(sys.argv) > 2 else "data/history/summary.json"

beijing = datetime.now(timezone(timedelta(hours=8)))
date_str = beijing.strftime("%Y-%m-%d")

# 读取通知内容（优先 Markdown notify_text，微信可渲染链接和格式）
text = "no data"
try:
    with open(summary_path, "r", encoding="utf-8") as f:
        d = json.load(f)
    # 优先 Markdown，回退 HTML
    text = d.get("notify_text") or d.get("notify_html") or text
    if not text.strip():
        print("[WARN] Empty notify content, skip notification.")
        sys.exit(0)
except FileNotFoundError:
    print(f"[WARN] summary.json not found: {summary_path}, skip notification.")
    sys.exit(0)
except Exception as e:
    print(f"[ERROR] Failed to read {summary_path}: {e}")
    sys.exit(1)

title = f"{title_prefix} ({date_str})"

# 发送通知
try:
    payload = json.dumps({"title": title, "desp": text}).encode("utf-8")
    req = urllib.request.Request(
        f"https://sctapi.ftqq.com/{SENDKEY}.send",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
    code = resp.get("code", -1)
    if code == 0:
        pushid = resp.get("data", {}).get("pushid", "?")
        print(f"Server酱 notified: pushid={pushid} desp_length={len(text)}")
    else:
        msg = resp.get("message", "unknown error")
        print(f"Server酱 failed: code={code} message={msg}")
        sys.exit(1)
except Exception as e:
    print(f"[ERROR] HTTP request failed: {e}")
    sys.exit(1)