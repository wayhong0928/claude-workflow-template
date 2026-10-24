"""SessionStart hook：把目前專案 session_log.md 的最新幾筆注入給 Claude。只用標準函式庫。

- 專案資料夾：先看 CLAUDE_PROJECT_DIR（Claude Code 給 hook 的環境變數），再退回目前工作目錄。
- 依序找 <專案>/session_log.md、<專案>/notes/session_log.md，找不到就安靜結束（用 plugin 裝、
  專案還沒有 session_log 時也是這樣）。
- 注入量：日期最新的 1 筆全文；第 2、3 筆只放標題加「下一步」段（舊格式找「剩什麼未完成」）。
- log 超過 80KB 而且真的有 7 天前的紀錄可搬時，加一行歸檔提醒。只看大小的話，最新 3 筆本身就不小，
  提醒會一直亮著卻做不到，每個 session 白付一次 token。
- 標題遺失檢查：同一個標題底下出現兩次以上「**做了什麼**」，或第一個標題之前就有，就提醒。
  不直接比總數，因為舊格式的紀錄沒有「做了什麼」段，比總數會一直誤報。

Fail-open：任何例外都安靜結束，不擋開場。
"""
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

HEAD_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})")
NEXT_RE = re.compile(r"^\s*(\*\*)?(下一步|剩什麼未完成)")
STOP_RE = re.compile(r"^(\*\*|---|## )")
DONE_RE = re.compile(r"^\s*\*\*做了什麼")
SIZE_LIMIT = 81920
ARCHIVE_DAYS = 7
KEEP = 3


def find_log(root):
    for p in (root / "session_log.md", root / "notes" / "session_log.md"):
        if p.is_file():
            return p
    return None


def blocks_of(lines):
    """[(start, end, date)]，end 含在內。"""
    starts = [(i, m.group(1)) for i, ln in enumerate(lines) for m in [HEAD_RE.match(ln)] if m]
    out = []
    for j, (s, d) in enumerate(starts):
        e = starts[j + 1][0] - 1 if j + 1 < len(starts) else len(lines) - 1
        out.append((s, e, d))
    return out


def newest(blocks, n=KEEP):
    """日期新的在前；同一天以檔內位置為次鍵，越上面越新。"""
    return sorted(blocks, key=lambda b: (-int(b[2].replace("-", "")), b[0]))[:n]


def summary(lines, block):
    s, e, _ = block
    seg = [lines[s]]
    nxt = next((x for x in range(s + 1, e + 1) if NEXT_RE.match(lines[x])), -1)
    if nxt >= 0:
        for x in range(nxt, min(e, nxt + 6) + 1):
            if x > nxt and STOP_RE.match(lines[x]):
                break
            seg.append(lines[x])
    return "\n".join(seg).rstrip() + "\n"


def build(log_path, today=None):
    today = today or date.today()
    lines = log_path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").split("\n")
    blocks = blocks_of(lines)
    if not blocks:
        content = "\n".join(lines)
        top = []
    else:
        top = newest(blocks)
        parts = ["\n".join(lines[top[0][0]:top[0][1] + 1])] + [summary(lines, b) for b in top[1:]]
        content = "\n".join(parts)

    size_note = ""
    if log_path.stat().st_size > SIZE_LIMIT and len(blocks) > KEEP:
        cutoff = (today - timedelta(days=ARCHIVE_DAYS)).isoformat()
        movable = [b for b in blocks if b[2] < cutoff and b not in top]
        if movable:
            script = Path(__file__).with_name("archive_session_log.py")
            py = os.environ.get("CLAUDE_PLUGIN_OPTION_PYTHON") or ("python" if os.name == "nt" else "python3")
            size_note = (f"\n[維護提醒] session_log.md 已超過 80KB，其中 {len(movable)} 筆早於 {cutoff}，可以歸檔。"
                         "歸檔只是把整段原文搬進 session_log_archive.md，不刪任何內容，最新 3 筆一律保留。"
                         f"執行：{py} \"{script}\"")

    suspects = []
    first = blocks[0][0] if blocks else len(lines)
    if any(DONE_RE.match(lines[x]) for x in range(first)):
        x = next(x for x in range(first) if DONE_RE.match(lines[x]))
        suspects.append(f"第 {x + 1} 行（第一個標題之前）")
    for s, e, _ in blocks:
        hits = [x for x in range(s + 1, e + 1) if DONE_RE.match(lines[x])]
        if len(hits) >= 2:
            suspects.append(f"第 {hits[1] + 1} 行（在「{lines[s]}」底下）")
    lost_note = ""
    if suspects:
        lost_note = (f"\n[標題遺失提醒] session_log 有 {len(suspects)} 處「做了什麼」前面少了 ## 標題，"
                     f"可能是加新紀錄時把下面一筆的標題弄掉了：{'；'.join(suspects)}。請對照備份或版本紀錄補回標題。")

    add_note = ""
    if os.environ.get("CLAUDE_PLUGIN_ROOT"):
        # plugin 裝法：腳本在 plugin 快取裡，每次升版路徑都會變，CLAUDE.md 寫不了固定路徑，所以在這裡給
        py = os.environ.get("CLAUDE_PLUGIN_OPTION_PYTHON") or "python"
        add_note = (f"\n新紀錄存成暫存檔後，用這行插到最上面："
                    f"{py} \"{Path(__file__).with_name('add_session_log.py')}\" \"{log_path}\" <暫存檔>")
    header = (f"=== SESSION LOG：最新 1 筆全文，前 2 筆只列標題與下一步（完整記錄在 {log_path}，需要時再讀檔）==="
              f"{add_note}{lost_note}{size_note}\n")
    return header + content


def main():
    try:
        root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        log_path = find_log(root)
        if not log_path:
            return
        out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": build(log_path)}}
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
    except Exception:
        return


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
