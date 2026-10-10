"""PostToolUse hook (matcher: Skill) 與 UserPromptExpansion hook：記錄受管制的 skill 是否被呼叫過。

兩條路都要接：Claude 自己用 Skill 工具叫用時走 PostToolUse；使用者直接打 `/dispatch-template`
時不經過 Skill 工具，只會觸發 UserPromptExpansion（官方 hooks 文件："typing `/skillname`
directly bypasses `PreToolUse`. `UserPromptExpansion` fires on that direct path"）。

目前受管制者見 TRACKED_SKILLS：dispatch-template（派 subagent 前必讀，閘門是 dispatch_gate.py）。

每次呼叫受管制的 skill，就在 skill_gate_flags/ 底下寫一個以
「session_id + skill 裸名稱」命名的空檔案，檔案的 mtime 就是「最近一次呼叫時間」。
dispatch_gate.py（PreToolUse on Agent）透過 gate_flags.py 檢查這個檔案，決定要不要放行派工。

skill 若是從 plugin 安裝，Skill 工具實際呼叫時的 `tool_input.skill` 會是
"某plugin:dispatch-template"（plugin:skill 格式），與寫死的裸名稱對不上。
所以同時接受裸名稱與「任意前綴:裸名稱」，並一律用裸名稱寫檔，閘門用裸名稱查詢即可命中。

Fail-open：任何例外都直接放行，不影響正常呼叫。
"""
import sys
import json
from pathlib import Path

FLAGS_DIR = Path(__file__).parent / "skill_gate_flags"
TRACKED_SKILLS = {"dispatch-template"}


def normalize_skill_name(skill_name):
    """把 plugin 前綴形式（如 "my-plugin:dispatch-template"）正規化成裸名稱；不認得就回傳 None。"""
    if not skill_name:
        return None
    if skill_name in TRACKED_SKILLS:
        return skill_name
    if ":" in skill_name:
        bare = skill_name.rsplit(":", 1)[-1]
        if bare in TRACKED_SKILLS:
            return bare
    return None


def main():
    try:
        if sys.platform == "win32":
            sys.stdin.reconfigure(encoding="utf-8")
            sys.stdout.reconfigure(encoding="utf-8")
        hook_input = json.load(sys.stdin)
    except Exception:
        return

    if hook_input.get("hook_event_name") == "UserPromptExpansion":
        raw_name = hook_input.get("command_name")
    else:
        raw_name = (hook_input.get("tool_input") or {}).get("skill")
    skill_name = normalize_skill_name(raw_name)
    if skill_name is None:
        return

    session_id = hook_input.get("session_id", "unknown")

    try:
        FLAGS_DIR.mkdir(parents=True, exist_ok=True)
        flag_path = FLAGS_DIR / f"{session_id}__{skill_name}.flag"
        flag_path.write_text("", encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    main()
