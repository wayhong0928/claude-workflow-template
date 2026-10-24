#!/usr/bin/env python3
"""PostToolUse（Edit|Write）hook：改到設定檔列的 TODO 檔時檢查格式。

只警告不擋：問題用 hook JSON 的 additionalContext 交給 Claude，永遠 exit 0。
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

MAX_SHOWN = 30


def main():
    try:
        import todo_core as core

        raw = sys.stdin.buffer.read().decode("utf-8-sig", errors="replace")
        payload = json.loads(raw) if raw.strip() else {}
        path = (payload.get("tool_input") or {}).get("file_path") or ""
        if not path:
            return
        conf = core.load_config()
        target = core.norm_key(core.expand(path, wsl=conf["_wsl"]))
        todos = {core.norm_key(t): t for p in conf["projects"] for t in p["todo"]}
        if target not in todos:
            return
        _, problems = core.scan_file(todos[target], date.today(), conf)
        if not problems:
            return
        shown = ["- 第 %d 行：%s" % (p["line"], p["msg"]) for p in problems[:MAX_SHOWN]]
        if len(problems) > MAX_SHOWN:
            shown.append("- 還有 %d 條，跑 todo_core.py lint 看全部" % (len(problems) - MAX_SHOWN))
        text = "TODO 格式檢查：%s 有 %d 條問題（只提醒，沒有擋下這次修改）。格式見 todo plugin 的 README。\n%s" % (
            todos[target], len(problems), "\n".join(shown))
        out = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text[:9500]}}
        sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
    except Exception as e:  # noqa: BLE001  任何錯都不能擋到使用者
        sys.stderr.write("todo_lint：%s\n" % e)


if __name__ == "__main__":
    main()
    sys.exit(0)
