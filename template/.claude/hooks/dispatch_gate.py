"""PreToolUse hook（matcher: Agent）：派 subagent 前，確保本 session 叫用過 `dispatch-template` skill。

背景：派工模板只在「要派工」時用得到，常駐在規則檔裡等於每個 session 都付一次 context，
所以做成 `dispatch-template` skill 按需載入。問題是 skill 要被叫用才會載入，
忘記叫用就等於規則失效（派工三件套、回報合約、平行派工檢查清單全部不會出現在 prompt 裡，
而且失效是靜默的：派工照樣成功，只是品質默默變差）。這支 hook 就是補這個缺口。

刻意不攔的情況：
- `subagent_type: "fork"`——fork 會繼承主對話的完整 context，模板那套「它什麼都不知道，
  要給它目標／動機／驗收條件」的前提不成立。
- 呼叫 `dispatch-template` skill 本身（那正是我們要求的動作，由 skill_gate_flag_writer 記錄；
  使用者直接打 `/dispatch-template` 也算，走 UserPromptExpansion）。

刻意要攔的情況：內建的 Explore、Plan 等 subagent 也一樣要先載模板。它們同樣是從零開始的 context，
寫清楚目標與回報格式一樣有用；代價是進 plan mode 後第一次派工可能被擋一次，載入模板後就放行。

Fail-open：任何例外、任何判斷不確定的情況一律放行，不阻擋正常工作。

判斷規則：本 session 叫用過一次就算數，compact 後要重叫（判斷邏輯在 `gate_flags.py`）。
擋下的事件記進 gate_trial.log（action: deny，位置見 hook_state.py），方便事後檢討有沒有誤擋。
"""
import json
import sys

from gate_flags import log_block, skill_called_in_session

REQUIRED_SKILL = "dispatch-template"
GATE_NAME = "dispatch_gate"

# 繼承完整 context 的派工型態，不需要模板
EXEMPT_SUBAGENT_TYPES = {"fork"}


def allow():
    sys.exit(0)


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    sys.exit(0)


def main():
    try:
        if sys.platform == "win32":
            sys.stdin.reconfigure(encoding="utf-8")
        hook_input = json.load(sys.stdin)
    except Exception:
        return allow()

    try:
        if hook_input.get("tool_name", "") != "Agent":
            return allow()

        tool_input = hook_input.get("tool_input") or {}
        subagent = str(tool_input.get("subagent_type") or "").strip().lower()
        if subagent in EXEMPT_SUBAGENT_TYPES:
            return allow()

        session_id = hook_input.get("session_id", "unknown")
        if skill_called_in_session(session_id, REQUIRED_SKILL, hook_input.get("transcript_path")):
            return allow()

        label = subagent or "（未指定型別）"
        model = str(tool_input.get("model") or "（未帶 model）")
        desc = str(tool_input.get("description") or "")
        log_block(GATE_NAME, session_id, f"派 {label}｜model={model}｜{desc}")
        return deny(
            f"這次要派 {label} subagent，但本 session 還沒叫用過 {REQUIRED_SKILL} skill"
            f"（或叫用後發生過 compact）。派工三件套（目標與動機／驗收條件／回報格式）、"
            f"回報合約全文、平行派工前的四項檢查、多樣本評審怎麼確保真獨立，都在那個 skill 裡。"
            f"請先用 Skill 工具呼叫 {REQUIRED_SKILL}，再重試這次派工。"
        )
    except Exception:
        return allow()


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
