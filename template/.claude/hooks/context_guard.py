"""UserPromptSubmit hook：主對話 context 過大時，提醒 Claude 在段落點請使用者寫 log 後 /clear。

為什麼：用量的大宗是長 context 每一輪重讀。「記得在段落點 /clear」靠自律常常做不到，所以交給機制提醒。
/clear 只能由使用者下，Claude 能做的是在段落點提出來，並先把進度寫進 session_log／TODO。

判斷：讀本 session transcript 最後一筆主對話（非 sidechain）assistant 的 usage，
context = input + cache_read + cache_creation。
提醒節奏：到 THRESHOLD（15 萬）提醒一次，之後每多 STEP（10 萬）再提醒一次，同一級不重複；/clear 後 context 變小，
自然不再觸發。狀態存在 context_guard_state.json（位置見 hook_state.py）。
Fail-open：任何例外都靜默放行，不輸出。
"""
import json
import os
import sys
from pathlib import Path

from hook_state import state_dir

THRESHOLD = 150_000
STEP = 100_000
TAIL_BYTES = 3_000_000
STATE_FILE = state_dir() / "context_guard_state.json"


def last_context_tokens(transcript_path):
    p = Path(transcript_path)
    size = p.stat().st_size
    with p.open("rb") as f:
        f.seek(max(0, size - TAIL_BYTES))
        chunk = f.read().decode("utf-8", errors="ignore")
    for line in reversed(chunk.splitlines()):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("type") != "assistant" or r.get("isSidechain"):
            continue
        u = (r.get("message") or {}).get("usage")
        if not u:
            continue
        return (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) \
            + (u.get("cache_creation_input_tokens") or 0)
    return 0


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    try:
        if len(state) > 200:  # 只留最近的 session
            state = dict(list(state.items())[-100:])
        STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def main():
    hook_input = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    tokens = last_context_tokens(hook_input["transcript_path"])
    if tokens < THRESHOLD:
        return
    level = (tokens - THRESHOLD) // STEP  # 0 = 15 萬級、1 = 25 萬級……
    sid = hook_input.get("session_id", "")
    state = load_state()
    if state.get(sid, -1) >= level:
        return
    state[sid] = level
    save_state(state)
    msg = (f"[context_guard] 目前主對話 context 約 {tokens // 1000}k tokens（門檻 {THRESHOLD // 1000}k）。"
           "先處理使用者這則訊息，不要中斷進行中的步驟；在下一個自然段落點（一件事做完、驗收過），"
           "把進度與下一步補進 session_log.md 與 TODO，然後請使用者下 /clear 接力。"
           "若使用者已說要繼續在這個 session 做，簡短帶過即可。")
    out = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": msg}}
    sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
