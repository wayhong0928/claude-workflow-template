"""install.py 的測試（只用標準函式庫）。

用法：python tests/test_install.py
每個情境都在暫存資料夾裡建一個假專案，實際執行 install.py，檢查檔案與 settings.json。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.py"
HAS_PS = bool(shutil.which("powershell") if os.name == "nt" else shutil.which("pwsh"))

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def run(target, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(INSTALL), str(target), *args],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    return r.returncode, r.stdout + r.stderr


def settings(target):
    return json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))


def our_count(s):
    n = 0
    for groups in s.get("hooks", {}).values():
        for g in groups:
            for h in g.get("hooks", []):
                if any(k in " ".join(h.get("args", [])) for k in ("/.claude/hooks/", "/.claude/session-log-kit/")):
                    n += 1
    return n


def snapshot(d):
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file()}


def new_project(base, name):
    p = base / name
    p.mkdir()
    return p


def main():
    base = Path(tempfile.mkdtemp(prefix="cwt-test-"))
    try:
        # 1. 空資料夾、裝 session_log
        p = new_project(base, "empty")
        if HAS_PS:
            code, out = run(p, "--session-log")
            check("空專案安裝成功", code == 0, out)
            check("hook 檔都在", all((p / ".claude/hooks" / n).exists() for n in
                  ("dispatch_gate.py", "gate_flags.py", "skill_gate_flag_writer.py", "context_guard.py", "ctrl_char_stop.py")))
            check("規則檔在 .claude/rules", (p / ".claude/rules/dispatch-and-verify.md").exists())
            check("session-log-kit 在 .claude 底下", (p / ".claude/session-log-kit/sessionstart_log.ps1").exists())
            s = settings(p)
            check("settings 有 6 個 hook", our_count(s) == 6, json.dumps(s, ensure_ascii=False))
            check("SessionStart 指到 .claude/session-log-kit",
                  "/.claude/session-log-kit/sessionstart_log.ps1" in json.dumps(s))
            cm = (p / "CLAUDE.md").read_text(encoding="utf-8")
            check("新建 CLAUDE.md 含接力說明", "claude-workflow-template:start" in cm and "【" in cm)
            check("建了 session_log.md、TODO.md", (p / "session_log.md").exists() and (p / "TODO.md").exists())
            check("不在 git repo 就不碰 .gitignore", not (p / ".gitignore").exists())
            check("專案根目錄只多出預期的東西",
                  sorted(x.name for x in p.iterdir()) == [".claude", "CLAUDE.md", "TODO.md", "session_log.md"],
                  str(sorted(x.name for x in p.iterdir())))
            r = subprocess.run([sys.executable, str(p / ".claude/hooks/tests/run_tests.py")],
                               capture_output=True, text=True, encoding="utf-8",
                               env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            check("裝好的 hook 測試全過", r.returncode == 0, r.stdout[-300:])

            # 2. 重跑不重複
            before = snapshot(p)
            code, out = run(p, "--session-log")
            after = snapshot(p)
            check("重跑成功", code == 0, out)
            check("重跑後 settings 仍是 6 個 hook", our_count(settings(p)) == 6)
            check("重跑後 CLAUDE.md 接力說明只有一段",
                  (p / "CLAUDE.md").read_text(encoding="utf-8").count("claude-workflow-template:start") == 1)
            check("重跑不改任何檔案、不產生備份", before == after,
                  str(set(after) ^ set(before)))
        else:
            print("SKIP 空專案＋session_log（這台電腦沒有 PowerShell）")

        # 3. 既有 settings、CLAUDE.md、git repo，不裝 session_log
        p = new_project(base, "existing")
        (p / ".git").mkdir()
        (p / ".claude").mkdir()
        user_hook = {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}
        (p / ".claude/settings.json").write_text(json.dumps(
            {"model": "sonnet", "hooks": {"PreToolUse": [user_hook]}}, indent=2), encoding="utf-8")
        (p / "CLAUDE.md").write_text("# 我的專案\n\n原本的內容。\n", encoding="utf-8")
        (p / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        code, out = run(p, "--no-session-log")
        check("既有專案安裝成功", code == 0, out)
        s = settings(p)
        check("保留使用者的其他設定", s.get("model") == "sonnet")
        check("保留使用者自己的 hook", user_hook in s["hooks"]["PreToolUse"])
        check("加了 5 個 hook、沒有 SessionStart", our_count(s) == 5 and "SessionStart" not in s["hooks"])
        check("CLAUDE.md 沒被改", (p / "CLAUDE.md").read_text(encoding="utf-8") == "# 我的專案\n\n原本的內容。\n")
        check("沒建 session_log.md", not (p / "session_log.md").exists())
        gi = (p / ".gitignore").read_text(encoding="utf-8")
        check(".gitignore 保留原本、加上狀態檔", gi.startswith("node_modules/") and ".claude/hooks/gate_trial.log" in gi)
        backups = list((p / ".claude/backup").glob("workflow-template-*/.claude/settings.json"))
        check("settings.json 有備份", len(backups) == 1)

        # 4. 改裝 session_log：既有 CLAUDE.md 加段落
        if HAS_PS:
            code, out = run(p, "--session-log")
            cm = (p / "CLAUDE.md").read_text(encoding="utf-8")
            check("既有 CLAUDE.md 保留原文並加接力說明",
                  code == 0 and cm.startswith("# 我的專案\n\n原本的內容。") and "claude-workflow-template:start" in cm, out)
            check("改裝後 6 個 hook", our_count(settings(p)) == 6)

        # 5. 移除
        code, out = run(p, "--uninstall")
        s = settings(p)
        check("移除成功", code == 0, out)
        check("移除後只剩使用者的 hook", our_count(s) == 0 and s["hooks"]["PreToolUse"] == [user_hook], json.dumps(s))
        check("移除後其他設定還在", s.get("model") == "sonnet")
        check("移除後 hook 檔不在", not (p / ".claude/hooks/dispatch_gate.py").exists())
        check("移除後 CLAUDE.md 回到原文",
              (p / "CLAUDE.md").read_text(encoding="utf-8").rstrip() == "# 我的專案\n\n原本的內容。")
        check("移除後 .gitignore 回到原文", (p / ".gitignore").read_text(encoding="utf-8") == "node_modules/\n")

        # 6. settings.json 格式錯：什麼都不動
        p = new_project(base, "broken")
        (p / ".claude").mkdir()
        (p / ".claude/settings.json").write_text("{ 這不是 JSON", encoding="utf-8")
        before = snapshot(p)
        code, out = run(p, "--no-session-log")
        check("settings 格式錯就停", code != 0 and "JSON" in out, out)
        check("格式錯時沒動任何檔案", snapshot(p) == before)

        # 7. 預演不動檔案
        p = new_project(base, "dry")
        code, out = run(p, "--no-session-log", "--dry-run")
        check("預演成功且沒建任何檔案", code == 0 and not any(p.iterdir()), out)

        # 8. 不能裝進 template 自己
        code, out = run(ROOT, "--no-session-log", "--dry-run")
        check("拒絕裝進 template 本身", code != 0, out)

        # 9. CRLF 的 CLAUDE.md 保留換行格式
        if HAS_PS:
            p = new_project(base, "crlf")
            (p / "CLAUDE.md").write_bytes("# 專案\r\n\r\n內容\r\n".encode("utf-8"))
            code, out = run(p, "--session-log")
            raw = (p / "CLAUDE.md").read_bytes()
            check("CRLF 檔案寫回後仍是 CRLF", code == 0 and b"\n" not in raw.replace(b"\r\n", b""), out)

        # 10. 只有 AGENTS.md：新建的 CLAUDE.md 要匯入它，否則 Claude Code 會改讀 CLAUDE.md、不再讀 AGENTS.md
        p = new_project(base, "agents")
        (p / "AGENTS.md").write_text("# 給 coding agent 的說明\n", encoding="utf-8")
        code, out = run(p, "--no-session-log", "--dry-run")
        check("預演有說明會匯入 AGENTS.md", code == 0 and "@AGENTS.md" in out, out)
        code, out = run(p, "--no-session-log")
        cm = (p / "CLAUDE.md").read_text(encoding="utf-8")
        check("新建的 CLAUDE.md 第一行是 @AGENTS.md", code == 0 and cm.splitlines()[0] == "@AGENTS.md", cm[:80])
        check("AGENTS.md 沒被改", (p / "AGENTS.md").read_text(encoding="utf-8") == "# 給 coding agent 的說明\n")
        code, out = run(p, "--no-session-log")
        check("重跑不重複加 @AGENTS.md",
              code == 0 and (p / "CLAUDE.md").read_text(encoding="utf-8").count("@AGENTS.md") == 1, out)

        # 11. --protect：資料夾、檔案、專案外路徑寫成 permissions.deny 的 Edit 規則
        p = new_project(base, "protect")
        (p / "pdf").mkdir()
        (p / "data").mkdir()
        (p / "data" / "問卷原始檔.csv").write_text("a,b\n", encoding="utf-8")
        outside = new_project(base, "outside-data")
        (p / ".claude").mkdir()
        (p / ".claude/settings.json").write_text(json.dumps(
            {"permissions": {"deny": ["Read(./.env)"], "allow": ["Bash(ls *)"]}}), encoding="utf-8")
        code, out = run(p, "--no-session-log", "--protect", "pdf", "--protect", "data/問卷原始檔.csv",
                        "--protect", str(outside), "--dry-run")
        check("預演列出保護規則且沒改 settings", code == 0 and "Edit(/pdf/**)" in out and
              "allow" in (p / ".claude/settings.json").read_text(encoding="utf-8") and
              "Edit" not in (p / ".claude/settings.json").read_text(encoding="utf-8"), out)
        code, out = run(p, "--no-session-log", "--protect", "pdf", "--protect", "data/問卷原始檔.csv",
                        "--protect", str(outside))
        deny = settings(p).get("permissions", {}).get("deny", [])
        out_posix = outside.resolve().as_posix()
        if len(out_posix) > 1 and out_posix[1] == ":":
            out_posix = out_posix[0].lower() + out_posix[2:]
        want = ["Read(./.env)", "Edit(/pdf/**)", "Edit(/data/問卷原始檔.csv)", "Edit(//" + out_posix.lstrip("/") + "/**)"]
        check("資料夾、檔案、專案外路徑各一條規則，原本的 deny 保留在前", code == 0 and deny == want, str(deny))
        check("permissions 的其他設定保留", settings(p)["permissions"].get("allow") == ["Bash(ls *)"])
        code, out = run(p, "--no-session-log", "--protect", "pdf")
        check("重跑不重複加保護規則", code == 0 and settings(p)["permissions"]["deny"] == want,
              str(settings(p)["permissions"]["deny"]))
        before = snapshot(p)
        code, out = run(p, "--no-session-log", "--protect", "不存在的資料夾")
        check("--protect 路徑不存在就停、不動檔案", code != 0 and "找不到" in out and snapshot(p) == before, out)
        code, out = run(p, "--no-session-log", "--protect", ".")
        check("--protect 整個專案會被拒絕", code != 0 and snapshot(p) == before, out)
        code, out = run(p, "--uninstall")
        check("移除時保護規則留著", code == 0 and settings(p)["permissions"]["deny"] == want and "沒有動" in out, out)

        # 12. permissions.deny 格式錯：什麼都不動
        p = new_project(base, "bad-perms")
        (p / ".claude").mkdir()
        (p / ".claude/settings.json").write_text(json.dumps({"permissions": {"deny": "Edit(x)"}}), encoding="utf-8")
        before = snapshot(p)
        code, out = run(p, "--no-session-log")
        check("permissions.deny 不是陣列就停", code != 0 and "permissions" in out and snapshot(p) == before, out)
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print()
    print(f"{sum(results)}/{len(results)} 通過")
    return 0 if all(results) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
