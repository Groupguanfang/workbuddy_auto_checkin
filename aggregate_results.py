#!/usr/bin/env python3
"""合并 matrix 账号结果，生成 Actions Summary，并统一推送飞书。"""

import glob
import json
import os
import sys

from wb_auto import push_feishu


def load_results(root):
    accounts = []
    for path in sorted(glob.glob(os.path.join(root, "**", "result.json"), recursive=True)):
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            accounts.extend(payload.get("accounts") or [])
        except (OSError, ValueError) as e:
            print("读取结果失败 %s：%s" % (path, e), file=sys.stderr)
    return accounts


def expected_slots():
    raw = os.environ.get("WB_EXPECTED_SLOTS") or "[]"
    try:
        slots = json.loads(raw)
        return [int(slot) for slot in slots]
    except (TypeError, ValueError):
        return []


def missing_result(slot):
    name = os.environ.get("WB_ACCOUNT_NAME_%d" % slot) or "账号 %d" % slot
    return {
        "slot": slot,
        "name": name,
        "checkin": {"ok": False, "result": "MISSING", "report": "matrix job 未产出结果"},
        "buddy": {"result": "SKIPPED", "report": "未执行"},
        "checkin_line": "❌ matrix job 未产出结果",
        "buddy_line": "🐱 未执行",
        "overall_ok": False,
    }


def write_summary(path, accounts, push_ok, push_reason, overall_ok):
    with open(path, "w", encoding="utf-8") as f:
        f.write("### Buddy 加油站多账号汇总\n\n")
        f.write("| 账号 | 签到 | 猫猫旅行 |\n| --- | --- | --- |\n")
        for account in accounts:
            f.write("| %s | %s | %s |\n" % (
                account["name"].replace("|", "\\|"),
                account["checkin_line"].replace("|", "\\|"),
                account["buddy_line"].replace("|", "\\|"),
            ))
        push_line = "✅ 已推送到飞书" if push_ok else "❌ %s" % push_reason
        f.write("\n- 飞书推送：%s\n" % push_line)
        f.write("- 整体：%s\n" % ("全部账号签到已达成" if overall_ok else "部分账号签到未达成"))


def main():
    root = os.environ.get("WB_RESULTS_DIR") or "results"
    accounts = load_results(root)
    by_slot = {int(account.get("slot", 0)): account for account in accounts}
    for slot in expected_slots():
        if slot not in by_slot:
            by_slot[slot] = missing_result(slot)
    accounts = [by_slot[slot] for slot in sorted(by_slot)]
    if not accounts:
        print("没有找到任何账号结果", file=sys.stderr)
        return 1

    overall_ok = all(account.get("overall_ok") is True for account in accounts)
    webhook = os.environ.get("FEISHU_WEBHOOK")
    push_ok, push_reason = None, "未配置 FEISHU_WEBHOOK，本次不推送"
    if webhook:
        push_ok, push_reason = push_feishu(webhook, accounts, overall_ok)

    summary = os.environ.get("WB_SUMMARY_FILE")
    if summary:
        write_summary(summary, accounts, push_ok, push_reason, overall_ok)
    print(json.dumps({"accounts": accounts, "push": {"ok": push_ok, "reason": push_reason},
                      "overall_ok": overall_ok}, ensure_ascii=False))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
