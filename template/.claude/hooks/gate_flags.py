"""dispatch_gate.py 用：判斷本 session 叫用過的 skill 還算不算數，並記錄擋下的事件。

規則：同一個 session 叫用過一次就算數；之後發生 compact 就要重叫。compact 後 skill 只留開頭
5,000 tokens，後段可能被截掉，重叫才會完整回來。
曾經試過「叫用後 N 分鐘內才算數」的時限，結果大部分被擋的都是同一個 session 稍早叫用過、
skill 內容其實還在對話裡的情況，所以改成現在這樣。

compact 的處理：PostCompact hook（compact_flag_reset.py）把該 session 的 flag 刪掉，這裡只看 flag
在不在，不讀 transcript。手動 /compact、自動壓縮、閒置自動壓縮都會觸發 PostCompact。

Fail-open：判斷時出任何例外，一律當作「算數」放行。
"""
import datetime
import json

from hook_state import state_dir

STATE_DIR = state_dir()
FLAGS_DIR = STATE_DIR / "skill_gate_flags"
GATE_LOG = STATE_DIR / "gate_trial.log"  # 擋下的事件，方便事後檢討有沒有誤擋


def skill_called_in_session(session_id, skill):
    """本 session 叫用過 skill，而且之後沒有 compact（flag 還在），就回傳 True。"""
    try:
        return (FLAGS_DIR / f"{session_id}__{skill}.flag").exists()
    except Exception:
        return True


def log_block(gate, session_id, detail):
    """把擋下的事件記一行。寫檔失敗不影響判斷。"""
    try:
        record = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "gate": gate,
            "session": session_id,
            "detail": str(detail)[:300],
            "action": "deny",
            "verdict": "",  # 檢討時人工填：該擋／誤擋
        }
        with open(GATE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass
