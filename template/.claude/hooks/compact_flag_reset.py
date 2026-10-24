"""PostCompact hook：compact 之後，刪掉這個 session 的 skill flag，派工前要重新叫用 dispatch-template。

為什麼要重叫：compact 時 Claude Code 會把叫用過的 skill 重新接在摘要後面，但每個 skill 只留開頭
5,000 tokens（官方 skills 文件 "Skill content lifecycle"），後段可能被截掉；官方疑難排解也建議
compact 後重新叫用 skill，內容才會完整回來。

PostCompact 在手動 `/compact`（matcher manual）和自動壓縮（matcher auto，含對話太長時的自動壓縮與
閒置自動壓縮 idle compaction）之後都會觸發，所以不必讀 transcript 找 compact 的痕跡。

輸入帶 agent_id 時是 subagent 自己的對話被壓縮，主對話的 skill 內容沒受影響，不刪。

Fail-open：任何例外都安靜結束；刪不掉 flag 的話，閘門就照舊放行。
"""
import json
import sys

from hook_state import state_dir

FLAGS_DIR = state_dir() / "skill_gate_flags"


def main():
    try:
        if sys.platform == "win32":
            sys.stdin.reconfigure(encoding="utf-8")
        hook_input = json.load(sys.stdin)
    except Exception:
        return
    if hook_input.get("agent_id"):
        return
    session_id = hook_input.get("session_id")
    if not session_id:
        return
    prefix = f"{session_id}__"
    try:
        for p in FLAGS_DIR.iterdir():
            if p.name.startswith(prefix) and p.name.endswith(".flag"):
                try:
                    p.unlink()
                except Exception:
                    pass
    except Exception:
        pass


if __name__ == "__main__":
    main()
