"""hook 的本機狀態（flag、計數、擋下事件的 log）放哪裡。

- 用 install.py 裝在專案裡：放 hook 腳本旁邊（.claude/hooks/），跟專案走。
- 用 plugin 裝：腳本在 plugin 快取裡，每次升版路徑都變，所以改放 CLAUDE_PLUGIN_DATA
  （官方：跨更新保留）。這個資料夾是所有專案共用的，底下再依專案路徑的雜湊分子資料夾，
  兩個專案的狀態檔才不會互相覆蓋。
"""
import hashlib
import os
from pathlib import Path


def state_dir():
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data:
        return Path(__file__).parent
    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    key = os.path.normcase(os.path.abspath(project))
    d = Path(data) / "state" / hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d
