"""session_log.md 歸檔：把 N 天前（預設 7）的舊紀錄搬進同資料夾的 session_log_archive.md。只用標準函式庫。

用法：python archive_session_log.py [session_log.md 的路徑] [--days 7]
      不給路徑時，依 CLAUDE_PROJECT_DIR 或目前資料夾找（同開場 hook）。

- 不論多舊，日期最新的 3 筆一律留著（跟開場注入量一致）。
- 不刪任何內容：整段原文搬進 session_log_archive.md，只是不再被開場注入。
- 窗口預設 7 天：天天寫的專案，窗口太長就永遠搬不動。
- 寫回時保留原本的換行（CRLF 或 LF），不加 BOM。BOM 會讓用 '^## ' 解析的工具漏掉第一筆。
"""
import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sessionstart_log import blocks_of, find_log, newest  # noqa: E402


def archive(log_path, days=7, today=None):
    today = today or date.today()
    raw = log_path.read_bytes()
    text = raw.decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    blocks = blocks_of(lines)
    if len(blocks) <= 3:
        return f"紀錄只有 {len(blocks)} 筆（3 筆以內），不需要歸檔。"
    cutoff = (today - timedelta(days=days)).isoformat()
    keep3 = newest(blocks)
    move = [b for b in blocks if b[2] < cutoff and b not in keep3]
    if not move:
        return f"沒有早於 {cutoff} 的紀錄可以歸檔（最新 3 筆一律保留）。"

    arc = log_path.with_name("session_log_archive.md")
    moved = nl.join(nl.join(lines[s:e + 1]) for s, e, _ in move)
    chunk = f"{nl}<!-- 歸檔於 {today.isoformat()}（來自 session_log.md，早於 {cutoff} 的紀錄）-->{nl}{moved}{nl}"
    with open(arc, "a" if arc.exists() else "w", encoding="utf-8", newline="") as f:
        if f.tell() == 0:
            f.write("# Session Log Archive" + nl)
        f.write(chunk)

    starts = {b[0] for b in move}
    kept = lines[:blocks[0][0]]
    for s, e, _ in blocks:
        if s not in starts:
            kept += lines[s:e + 1]
    with open(log_path, "w", encoding="utf-8", newline="") as f:
        f.write(nl.join(kept) + nl)
    return f"已歸檔 {len(move)} 筆（早於 {cutoff}）到 {arc}；log 留 {len(blocks) - len(move)} 筆。"


def main(argv=None):
    ap = argparse.ArgumentParser(description="把舊的 session_log 紀錄搬進 session_log_archive.md")
    ap.add_argument("log", nargs="?", help="session_log.md 的路徑")
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args(argv)
    log_path = Path(a.log) if a.log else find_log(Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()))
    if not log_path or not log_path.is_file():
        print("找不到 session_log.md，沒有動任何檔案。")
        return 0
    print(archive(log_path, a.days))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
