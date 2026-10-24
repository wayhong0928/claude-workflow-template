"""dispatch_gate.py 用：判斷本 session 叫用過的 skill 還算不算數，並記錄擋下的事件。

規則：同一個 session 叫用過一次就算數；之後若發生 compact（skill 內容可能被摘要掉），要重叫。
曾經試過「叫用後 N 分鐘內才算數」的時限，結果大部分被擋的都是同一個 session 稍早叫用過、
skill 內容其實還在對話裡的情況，所以改成現在這樣。

compact 的判斷：transcript 裡最後一筆 `"subtype":"compact_boundary"` 的時間晚於 flag 的時間。
compact 後 session_id 與 transcript 檔不變。

Fail-open：讀不到 flag 時間、transcript 或解析失敗，一律當作「算數」放行。
"""
import datetime
import json
from pathlib import Path

from hook_state import state_dir

STATE_DIR = state_dir()
FLAGS_DIR = STATE_DIR / "skill_gate_flags"
GATE_LOG = STATE_DIR / "gate_trial.log"  # 擋下的事件，方便事後檢討有沒有誤擋
COMPACT_MARKER = b'"subtype":"compact_boundary"'


def last_compact_epoch(transcript_path):
    """transcript 裡最後一次 compact 的時間（epoch 秒）；沒有 compact 或讀不到就回傳 None。"""
    try:
        data = Path(transcript_path).read_bytes()
    except Exception:
        return None
    pos = data.rfind(COMPACT_MARKER)
    if pos < 0:
        return None
    start = data.rfind(b"\n", 0, pos) + 1
    end = data.find(b"\n", pos)
    line = data[start:end if end >= 0 else len(data)]
    try:
        ts = json.loads(line.decode("utf-8"))["timestamp"]
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def skill_called_in_session(session_id, skill, transcript_path):
    """本 session 叫用過 skill，且之後沒有 compact，就回傳 True。"""
    try:
        flag = FLAGS_DIR / f"{session_id}__{skill}.flag"
        if not flag.exists():
            return False
        if not transcript_path:
            return True
        compact = last_compact_epoch(transcript_path)
        return compact is None or flag.stat().st_mtime >= compact
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
