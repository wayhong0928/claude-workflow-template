"""把 claude-workflow-template 裝進一個專案，或從專案移除。只用 Python 標準函式庫。

用法：
  python install.py <專案資料夾> [--session-log | --no-session-log] [--dry-run]
  python install.py <專案資料夾> --uninstall [--dry-run]

安裝會做的事：
  - 把 template/.claude/ 底下的 hook、skill、agent、規則檔複製到 <專案>/.claude/
  - 把 hook 設定合併進 <專案>/.claude/settings.json（原本的設定保留，只加這個 template 的幾項）
  - 專案沒有 CLAUDE.md 就建一份；裝 session_log 時在 CLAUDE.md 結尾加一段接力說明
  - 裝 session_log 時，專案沒有 session_log.md、TODO.md 就各建一份
  - 專案在 git repo 裡時，在 .gitignore 加上 hook 產生的本機狀態檔
被覆蓋或修改的既有檔案，先備份到 <專案>/.claude/backup/workflow-template-<時間>/。
重複執行不會重複加設定；--dry-run 只列出會做什麼，不動任何檔案。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    # 輸出一律 UTF-8：被 Claude Code、Codex 這類工具接走輸出時，中文 Windows 預設的 cp950 會變亂碼
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
TPL = HERE / "template"
MIN_PY = (3, 8)

CORE_FILES = [
    ".claude/hooks/dispatch_gate.py",
    ".claude/hooks/gate_flags.py",
    ".claude/hooks/skill_gate_flag_writer.py",
    ".claude/hooks/context_guard.py",
    ".claude/hooks/ctrl_char_stop.py",
    ".claude/hooks/tests/run_tests.py",
    ".claude/skills/dispatch-template/SKILL.md",
    ".claude/agents/verifier.md",
    ".claude/rules/dispatch-and-verify.md",
]
SESSION_LOG_FILES = [
    ".claude/session-log-kit/add_session_log.py",
    ".claude/session-log-kit/sessionstart_log.ps1",
    ".claude/session-log-kit/archive_session_log.ps1",
    ".claude/session-log-kit/README.md",
]
# hook 執行時在 .claude/hooks/ 產生的本機狀態，移除時一併刪掉
STATE_PATHS = [
    ".claude/hooks/skill_gate_flags",
    ".claude/hooks/gate_trial.log",
    ".claude/hooks/context_guard_state.json",
    ".claude/hooks/ctrl_char_stop_state.json",
    ".claude/hooks/__pycache__",
]
# settings.json 裡哪些 hook 是這個 template 加的：看 args 有沒有指到這幾支腳本
OUR_SCRIPTS = [
    "/.claude/hooks/dispatch_gate.py",
    "/.claude/hooks/skill_gate_flag_writer.py",
    "/.claude/hooks/context_guard.py",
    "/.claude/hooks/ctrl_char_stop.py",
    "/.claude/session-log-kit/sessionstart_log.ps1",
]
MARK_START = "<!-- claude-workflow-template:start -->"
MARK_END = "<!-- claude-workflow-template:end -->"
GITIGNORE_HEADER = "# claude-workflow-template：hook 產生的本機狀態與安裝備份"
GITIGNORE_LINES = [
    ".claude/hooks/skill_gate_flags/",
    ".claude/hooks/gate_trial.log",
    ".claude/hooks/*_state.json",
    ".claude/hooks/__pycache__/",
    ".claude/backup/",
]


class InstallError(Exception):
    pass


# ---------- 環境偵測 ----------

def find_python():
    """回傳 hook 要用的 Python 指令名稱（python／python3／py），找不到回傳 None。
    用名稱不用絕對路徑：專案資料夾可能同步到別台電腦，絕對路徑會失效。"""
    candidates = ["python", "python3"] + (["py"] if os.name == "nt" else [])
    for name in candidates:
        exe = shutil.which(name)
        if not exe:
            continue
        try:
            r = subprocess.run(
                [exe, "-c", "import sys; print(sys.version_info[:2] >= %r)" % (MIN_PY,)],
                capture_output=True, text=True, timeout=30,
            )
        except Exception:
            continue
        # Windows 的 Microsoft Store 假捷徑會回傳非 0，這裡自然被略過
        if r.returncode == 0 and r.stdout.strip() == "True":
            return name
    return None


def find_powershell():
    if os.name == "nt" and shutil.which("powershell"):
        return "powershell"
    if shutil.which("pwsh"):
        return "pwsh"
    return None


def in_git_repo(path):
    for p in [path] + list(path.parents):
        if (p / ".git").exists():
            return True
    return False


# ---------- 文字檔讀寫（保留原本的換行格式） ----------

def read_text(p):
    return p.read_text(encoding="utf-8-sig")


def newline_of(p):
    if p.exists() and b"\r\n" in p.read_bytes():
        return "\r\n"
    return "\n"


def write_text(p, text, nl="\n"):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace("\r\n", "\n").replace("\n", nl))


# ---------- settings.json ----------

def load_settings(p):
    if not p.exists():
        return {}
    try:
        text = read_text(p)
    except UnicodeDecodeError:
        raise InstallError(f"{p} 不是 UTF-8 編碼，沒有動任何檔案。請先把它存成 UTF-8 再執行。")
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise InstallError(f"{p} 的 JSON 格式有錯（第 {e.lineno} 行），沒有動任何檔案。請先修好再執行。")
    if not isinstance(data, dict):
        raise InstallError(f"{p} 最外層不是物件（{{...}}），沒有動任何檔案。")
    if "hooks" in data and not isinstance(data["hooks"], dict):
        raise InstallError(f"{p} 的 \"hooks\" 不是物件，沒有動任何檔案。")
    return data


def is_ours(hook):
    if not isinstance(hook, dict):
        return False
    parts = [str(hook.get("command", ""))] + [str(a) for a in (hook.get("args") or [])]
    blob = " ".join(parts).replace("\\", "/")
    return any(s in blob for s in OUR_SCRIPTS)


def strip_ours(hooks):
    out = {}
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            out[event] = groups
            continue
        kept = []
        for g in groups:
            if isinstance(g, dict) and isinstance(g.get("hooks"), list):
                remain = [h for h in g["hooks"] if not is_ours(h)]
                if g["hooks"] and not remain:
                    continue
                if len(remain) != len(g["hooks"]):
                    g = dict(g, hooks=remain)
            kept.append(g)
        if kept or not groups:
            out[event] = kept
    return out


def add_ours(hooks, defs, py, ps):
    for event, groups in defs.items():
        for g in groups:
            g = json.loads(json.dumps(g))
            for h in g["hooks"]:
                if h.get("command") == "python":
                    h["command"] = py
                elif h.get("command") == "powershell":
                    h["command"] = ps
            hooks.setdefault(event, []).append(g)
    return hooks


def merged_settings(current, session_log, py, ps):
    new = json.loads(json.dumps(current))
    hooks = strip_ours(new.get("hooks", {}))
    add_ours(hooks, json.loads(read_text(TPL / "hooks-core.json")), py, ps)
    if session_log:
        add_ours(hooks, json.loads(read_text(TPL / "hooks-session-log.json")), py, ps)
    new["hooks"] = hooks
    return new


def dump_settings(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


# ---------- CLAUDE.md ----------

def session_log_block(py):
    return "\n".join([
        MARK_START,
        "## 接力：session_log 與 TODO",
        "",
        "- 開場時 hook 會注入 `session_log.md` 最新 1 筆全文，以及前 2 筆的標題與下一步。先用 1 到 2 句話報告上次進度與待辦，再處理指令。",
        f"- 每完成一段有意義的工作，把新紀錄存成暫存檔，再跑 `{py} .claude/session-log-kit/add_session_log.py session_log.md <暫存檔>` 插到最上面。格式見 `.claude/session-log-kit/README.md`。",
        "- 還沒做的事寫在 `TODO.md`，做完就整條刪掉。",
        MARK_END,
        "",
    ])


def find_claude_md(target):
    for rel in ("CLAUDE.md", ".claude/CLAUDE.md"):
        if (target / rel).exists():
            return target / rel
    return None


def remove_block(text):
    s = text.find(MARK_START)
    e = text.find(MARK_END)
    if s < 0 or e < s:
        return text
    e += len(MARK_END)
    while e < len(text) and text[e] in "\r\n":
        e += 1
    head = text[:s].rstrip("\r\n")
    return (head + "\n" if head else "") + text[e:]


# ---------- 主流程 ----------

class Plan:
    def __init__(self, target, dry_run):
        self.target = target
        self.dry_run = dry_run
        base = target / ".claude" / "backup" / ("workflow-template-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        self.backup_dir, n = base, 2
        while self.backup_dir.exists():  # 同一秒內跑兩次也不覆蓋前一次的備份
            self.backup_dir, n = base.with_name(f"{base.name}-{n}"), n + 1
        self.lines = []
        self.backed_up = False

    def say(self, msg):
        self.lines.append(msg)
        print(("（預演）" if self.dry_run else "") + msg)

    def backup(self, p):
        rel = p.relative_to(self.target)
        if self.dry_run:
            return
        dst = self.backup_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if p.is_dir():
            shutil.copytree(p, dst)
        else:
            shutil.copy2(p, dst)
        self.backed_up = True


def check_target(target):
    if not target.is_dir():
        raise InstallError(f"找不到資料夾：{target}")
    if target == HERE or HERE in target.parents:
        raise InstallError("目標資料夾是 template 本身（或在它裡面）。請指定你自己的專案資料夾。")
    if not TPL.is_dir():
        raise InstallError(f"找不到 {TPL}。請在下載下來的 template 資料夾裡執行 install.py，不要只複製這支檔案。")


def install(target, session_log, dry_run):
    check_target(target)
    py = find_python()
    if not py:
        raise InstallError("找不到 Python 3.8 以上的指令（試過 python、python3、py）。hook 需要它，請先安裝 Python。")
    in_git = in_git_repo(target)
    ps = find_powershell()
    if session_log is None:
        session_log = not in_git
        why = "專案不在 git repo 裡" if session_log else "專案在 git repo 裡，進度可以看 git log"
        if session_log and not ps:
            session_log = False
            why = "專案不在 git repo 裡，但這台電腦沒有 PowerShell"
        print(f"session_log：{'裝' if session_log else '不裝'}（{why}；要改請加 --session-log 或 --no-session-log）")
    if session_log and not ps:
        raise InstallError("session_log 的開場注入要用 PowerShell，這台電腦找不到 powershell 或 pwsh。"
                           "macOS／Linux 請先裝 PowerShell 7，或改用 --no-session-log。")
    settings_path = target / ".claude" / "settings.json"
    current = load_settings(settings_path)  # 格式有錯會在這裡停，什麼都還沒動

    plan = Plan(target, dry_run)
    print(f"專案資料夾：{target}")
    print(f"hook 用的 Python 指令：{py}" + (f"；PowerShell 指令：{ps}" if session_log else ""))

    # 1. 檔案
    files = CORE_FILES + (SESSION_LOG_FILES if session_log else [])
    counts = {"new": 0, "replace": 0, "same": 0}
    for rel in files:
        src, dst = TPL / rel, target / rel
        if dst.exists():
            if dst.read_bytes() == src.read_bytes():
                counts["same"] += 1
                continue
            plan.say(f"覆蓋 {rel}（舊檔先備份）")
            plan.backup(dst)
            counts["replace"] += 1
        else:
            counts["new"] += 1
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    plan.say(f"複製檔案到 .claude/：新增 {counts['new']}、覆蓋 {counts['replace']}、內容相同略過 {counts['same']}")

    # 2. settings.json
    new = merged_settings(current, session_log, py, ps)
    if new == current and settings_path.exists():
        plan.say(".claude/settings.json：已經是最新，沒改")
    else:
        if settings_path.exists():
            plan.backup(settings_path)
            plan.say(".claude/settings.json：加入這個 template 的 hook，原本的設定保留")
        else:
            plan.say(".claude/settings.json：新建")
        if not dry_run:
            write_text(settings_path, dump_settings(new), newline_of(settings_path))

    # 3. CLAUDE.md
    cmd = find_claude_md(target)
    block = session_log_block(py) if session_log else ""
    if cmd is None:
        # 有 CLAUDE.md 之後，Claude Code 就不再自動讀 AGENTS.md（官方 memory 文件的 AGENTS.md 一節），
        # 所以專案原本有 AGENTS.md 時，新建的 CLAUDE.md 第一行用 @AGENTS.md 把它匯入
        agents_md = (target / "AGENTS.md").exists()
        if agents_md:
            plan.say("CLAUDE.md：新建，第一行用 @AGENTS.md 匯入你原本的 AGENTS.md"
                     "（有了 CLAUDE.md，Claude Code 就不會自動讀 AGENTS.md）；裡面有【】空格要填")
        else:
            plan.say("CLAUDE.md：新建（裡面有【】空格要填）")
        if not dry_run:
            body = read_text(TPL / "CLAUDE.md.template").rstrip("\n") + "\n"
            if agents_md:
                body = "@AGENTS.md\n\n" + body
            if block:
                body += "\n" + block
            write_text(target / "CLAUDE.md", body)
    else:
        text = read_text(cmd)
        rel = cmd.relative_to(target).as_posix()
        stripped = remove_block(text)
        wanted = (stripped.rstrip("\r\n") + "\n\n" + block) if block else stripped
        if wanted.replace("\r\n", "\n") == text.replace("\r\n", "\n"):
            plan.say(f"{rel}：沒改")
        else:
            plan.backup(cmd)
            plan.say(f"{rel}：{'在結尾加上接力說明' if block else '拿掉之前加的接力說明'}（舊檔先備份）")
            if not dry_run:
                write_text(cmd, wanted, newline_of(cmd))

    # 4. session_log.md、TODO.md
    if session_log:
        for name in ("session_log.md", "TODO.md"):
            if (target / name).exists():
                plan.say(f"{name}：已經有了，沒動")
            else:
                plan.say(f"{name}：新建")
                if not dry_run:
                    write_text(target / name, read_text(TPL / (name + ".template")))

    # 5. .gitignore
    if in_git:
        gi = target / ".gitignore"
        existing = read_text(gi).splitlines() if gi.exists() else []
        missing = [l for l in GITIGNORE_LINES if l not in existing]
        if missing:
            plan.say(f".gitignore：加上 {len(missing)} 行 hook 狀態檔")
            if not dry_run:
                text = read_text(gi) if gi.exists() else ""
                if text and not text.endswith("\n"):
                    text += "\n"
                if GITIGNORE_HEADER not in existing:
                    text += ("\n" if text else "") + GITIGNORE_HEADER + "\n"
                text += "\n".join(missing) + "\n"
                write_text(gi, text, newline_of(gi))

    print()
    if dry_run:
        print("預演結束，沒有動任何檔案。拿掉 --dry-run 再跑一次就會正式安裝。")
        return
    if plan.backed_up:
        print(f"備份在：{plan.backup_dir.relative_to(target).as_posix()}/")
    print("安裝完成。接下來：")
    steps = [f"在專案資料夾跑 {py} .claude/hooks/tests/run_tests.py ，最後一行要是「25/25 通過」（前後數字一樣就是全過）"]
    if cmd is None:
        steps.append("打開 CLAUDE.md，把【】填完（也可以請 Claude 一題一題問你）")
    steps.append("關掉正在跑的 Claude Code，在專案資料夾重新打 claude，再打 /hooks 確認看得到這幾個 hook")
    for i, s in enumerate(steps, 1):
        print(f"  {i}. {s}")


def uninstall(target, dry_run):
    check_target(target)
    settings_path = target / ".claude" / "settings.json"
    current = load_settings(settings_path)
    plan = Plan(target, dry_run)
    print(f"專案資料夾：{target}")

    if settings_path.exists():
        new = json.loads(json.dumps(current))
        if "hooks" in new:
            new["hooks"] = strip_ours(new["hooks"])
            if not new["hooks"]:
                del new["hooks"]
        if new != current:
            plan.backup(settings_path)
            plan.say(".claude/settings.json：拿掉這個 template 的 hook，其他設定保留")
            if not dry_run:
                write_text(settings_path, dump_settings(new), newline_of(settings_path))

    moved = 0
    for rel in CORE_FILES + SESSION_LOG_FILES:
        p = target / rel
        if p.exists():
            plan.backup(p)
            moved += 1
            if not dry_run:
                p.unlink()
    plan.say(f"移除 .claude/ 裡這個 template 的檔案 {moved} 個（先備份）")
    for rel in STATE_PATHS:
        p = target / rel
        if p.exists() and not dry_run:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    if not dry_run:
        for rel in (".claude/hooks/tests", ".claude/hooks", ".claude/skills/dispatch-template",
                    ".claude/skills", ".claude/agents", ".claude/rules", ".claude/session-log-kit"):
            p = target / rel
            if p.is_dir() and not any(p.iterdir()):
                p.rmdir()

    cmd = find_claude_md(target)
    if cmd is not None:
        text = read_text(cmd)
        stripped = remove_block(text)
        if stripped != text:
            plan.backup(cmd)
            plan.say(f"{cmd.relative_to(target).as_posix()}：拿掉接力說明那段，其他內容不動")
            if not dry_run:
                write_text(cmd, stripped, newline_of(cmd))

    gi = target / ".gitignore"
    if gi.exists():
        lines = read_text(gi).splitlines()
        kept = [l for l in lines if l not in GITIGNORE_LINES and l != GITIGNORE_HEADER]
        if kept != lines:
            plan.say(".gitignore：拿掉安裝時加的幾行")
            if not dry_run:
                write_text(gi, "\n".join(kept).rstrip("\n") + "\n", newline_of(gi))

    print()
    if dry_run:
        print("預演結束，沒有動任何檔案。")
        return
    print("移除完成。CLAUDE.md、session_log.md、TODO.md 是你的內容，沒有刪；不需要的話自己刪。")
    if plan.backed_up:
        print(f"備份在：{plan.backup_dir.relative_to(target).as_posix()}/（確定不要了可以整個刪掉）")


def main(argv=None):
    ap = argparse.ArgumentParser(description="把 claude-workflow-template 裝進專案，或從專案移除。")
    ap.add_argument("project", help="你的專案資料夾")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--session-log", dest="session_log", action="store_true", default=None,
                   help="裝 session_log（開場自動接上次進度）")
    g.add_argument("--no-session-log", dest="session_log", action="store_false",
                   help="不裝 session_log")
    g.add_argument("--uninstall", action="store_true", help="移除這個 template 裝進去的東西")
    ap.add_argument("--dry-run", action="store_true", help="只列出會做什麼，不動任何檔案")
    a = ap.parse_args(argv)
    if sys.version_info[:2] < MIN_PY:
        print(f"需要 Python {MIN_PY[0]}.{MIN_PY[1]} 以上，你現在用的是 {sys.version.split()[0]}。", file=sys.stderr)
        return 1
    target = Path(a.project).expanduser().resolve()
    try:
        if a.uninstall:
            uninstall(target, a.dry_run)
        else:
            install(target, a.session_log, a.dry_run)
    except InstallError as e:
        print("沒有完成：" + str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
