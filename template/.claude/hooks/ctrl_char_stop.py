"""Stop hook：回合結束時，掃本回合寫過的 .md／.json／.py，有控制字元就擋。

為什麼：用 Python 字串寫 Windows 路徑或長文時，\\r、\\b、\\a、\\202 被當成跳脫字元寫進檔案。
這種錯一再發生，寫成規則也擋不住，所以改成 hook。

找什麼：U+0000–001F（Tab、LF、CR 除外）、U+0080–009F、後面不是 LF 的孤立 CR。CRLF 檔不算。

哪些檔案：只看本回合 transcript 裡有證據的路徑，而且 mtime 晚於本回合開始——
- Write／Edit／NotebookEdit 的目標路徑；
- Bash／PowerShell 命令、以及本回合用 Write 寫出的 .py／.ps1 內容裡出現的完整絕對路徑。
命令裡用變數組出來的路徑抓不到，會漏檢；這支只求擋住常見情況，不保證全抓。

Fail-open：任何例外都放行。stop_hook_active 時放行，同一回合最多擋 2 次，避免卡死無人看管的 session。
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

EXTS = (".md", ".json", ".py")
WRITE_TOOLS = {"Write", "Edit", "NotebookEdit", "Bash", "PowerShell"}
MAX_BYTES = 2_000_000
MAX_HITS_PER_FILE = 5
MAX_BLOCKS_PER_TURN = 2
STATE_FILE = Path(__file__).with_name("ctrl_char_stop_state.json")

BAD = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x80-\x9f]|\r(?!\n)")
# 完整絕對路徑：C:\...、C:/...、/c/...，結尾是三種副檔名之一
PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|/[a-zA-Z]/)[^\"'`<>|\r\n*?]*?\.(?:md|json|py)(?![\w])", re.I)


def is_real_user_message(r) -> bool:
    """tool_result 的 type 也是 user，要排除，否則會把工具回傳誤當成回合開始。"""
    if r.get("type") != "user" or r.get("toolUseResult") is not None:
        return False
    content = (r.get("message") or {}).get("content")
    if isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return False
    return True


def to_windows(p: str) -> str:
    m = re.match(r"^/([a-zA-Z])/(.*)$", p)
    if m:
        p = f"{m.group(1)}:/{m.group(2)}"
    return p


def candidate_paths(records, start_idx, cwd):
    paths = set()
    for r in records[start_idx + 1:]:
        if r.get("type") != "assistant":
            continue
        tool_cwd = r.get("cwd") or cwd
        for block in ((r.get("message") or {}).get("content") or []):
            if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                continue
            name, inp = block.get("name"), block.get("input") or {}
            if name not in WRITE_TOOLS:
                continue
            texts = []
            if name in {"Write", "Edit", "NotebookEdit"}:
                target = inp.get("file_path") or inp.get("notebook_path")
                if isinstance(target, str) and target:
                    p = Path(target)
                    paths.add(str(p if p.is_absolute() else Path(tool_cwd) / p))
                    if target.lower().endswith((".py", ".ps1")):
                        texts += [inp.get(k) for k in ("content", "new_string")]
            else:
                texts.append(inp.get("command"))
            for t in texts:
                if isinstance(t, str):
                    for m in PATH_RE.finditer(t):
                        paths.add(to_windows(m.group(0).replace("\\\\", "\\")))
    return paths


def scan(path: Path):
    """回傳 [(行號, 碼位描述)]，最多 MAX_HITS_PER_FILE 筆。"""
    data = path.read_bytes()[:MAX_BYTES]
    text = data.decode("utf-8", errors="replace")
    hits = []
    for m in BAD.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        hits.append((line, f"U+{ord(m.group(0)[0]):04X}"))
        if len(hits) >= MAX_HITS_PER_FILE:
            break
    return hits


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    try:
        if sys.platform == "win32":
            sys.stdin.reconfigure(encoding="utf-8")
        hook_input = json.load(sys.stdin)
    except Exception:
        return
    try:
        if hook_input.get("stop_hook_active"):
            return
        tp = hook_input.get("transcript_path")
        if not tp or not Path(tp).is_file():
            return
        records = []
        with open(tp, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
        start_idx = max((i for i, r in enumerate(records) if is_real_user_message(r)), default=-1)
        if start_idx < 0:
            return
        ts = records[start_idx].get("timestamp")
        start_ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() if ts else time.time() - 3600
        cwd = hook_input.get("cwd") or os.getcwd()

        found = []
        for raw in sorted(candidate_paths(records, start_idx, cwd)):
            p = Path(raw)
            try:
                if (p.suffix.lower() not in EXTS or not p.is_file()
                        or p.stat().st_mtime < start_ts - 2):
                    continue
                hits = scan(p)
            except Exception:
                continue
            if hits:
                where = "、".join(f"第 {ln} 行 {cp}" for ln, cp in hits)
                found.append(f"{p}（{where}）")
        if not found:
            return

        session_id = hook_input.get("session_id", "unknown")
        key = f"{session_id}:{start_idx}"
        state = load_state()
        count = state.get(key, 0)
        if count >= MAX_BLOCKS_PER_TURN:
            return
        try:
            STATE_FILE.write_text(json.dumps({key: count + 1}), encoding="utf-8")
        except Exception:
            pass
        print(json.dumps({
            "decision": "block",
            "reason": ("這一回合寫過的檔案裡有控制字元，多半是 Python 字串把 Windows 路徑或長文的反斜線"
                       "當成跳脫字元（\\r、\\b、\\a、\\202 這類）：" + "；".join(found) +
                       "。請修好再結束：讀出該行，改用 Edit 寫回正確文字；長文用 Write 寫檔，不經 Python 字串。"),
        }, ensure_ascii=False))
    except Exception:
        return


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
