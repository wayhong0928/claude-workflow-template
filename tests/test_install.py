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
# 在 Claude Code session 裡跑時，CLAUDE_PLUGIN_DATA、CLAUDE_PROJECT_DIR 這類變數會讓 hook 把狀態寫到沙箱外，跑 install.py 和 hook 的子行程不帶 CLAUDE* 變數
BASE_ENV = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def run(target, *args):
    env = dict(BASE_ENV, PYTHONIOENCODING="utf-8")
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
        code, out = run(p, "--session-log")
        check("空專案安裝成功", code == 0, out)
        check("hook 檔都在", all((p / ".claude/hooks" / n).exists() for n in
              ("dispatch_gate.py", "gate_flags.py", "skill_gate_flag_writer.py", "context_guard.py",
               "ctrl_char_stop.py", "compact_flag_reset.py")))
        check("規則檔在 .claude/rules", (p / ".claude/rules/dispatch-and-verify.md").exists())
        check("session-log-kit 在 .claude 底下", (p / ".claude/session-log-kit/sessionstart_log.py").exists())
        s = settings(p)
        check("settings 有 7 個 hook", our_count(s) == 7, json.dumps(s, ensure_ascii=False))
        check("SessionStart 指到 .claude/session-log-kit",
              "/.claude/session-log-kit/sessionstart_log.py" in json.dumps(s))
        check("PostCompact 指到 compact_flag_reset.py",
              "/.claude/hooks/compact_flag_reset.py" in json.dumps(s.get("hooks", {}).get("PostCompact")))
        cm = (p / "CLAUDE.md").read_text(encoding="utf-8")
        check("新建 CLAUDE.md 含接力說明", "claude-workflow-template:start" in cm and "【" in cm)
        check("建了 session_log.md、TODO.md", (p / "session_log.md").exists() and (p / "TODO.md").exists())
        check("不在 git repo 就不碰 .gitignore", not (p / ".gitignore").exists())
        check("專案根目錄只多出預期的東西",
              sorted(x.name for x in p.iterdir()) == [".claude", "CLAUDE.md", "TODO.md", "session_log.md"],
              str(sorted(x.name for x in p.iterdir())))
        r = subprocess.run([sys.executable, str(p / ".claude/hooks/tests/run_tests.py")],
                           capture_output=True, text=True, encoding="utf-8",
                           env=dict(BASE_ENV, PYTHONIOENCODING="utf-8"))
        check("裝好的 hook 測試全過", r.returncode == 0, r.stdout[-300:])

        # 2. 重跑不重複
        before = snapshot(p)
        code, out = run(p, "--session-log")
        after = snapshot(p)
        check("重跑成功", code == 0, out)
        check("重跑後 settings 仍是 7 個 hook", our_count(settings(p)) == 7)
        check("重跑後 CLAUDE.md 接力說明只有一段",
              (p / "CLAUDE.md").read_text(encoding="utf-8").count("claude-workflow-template:start") == 1)
        check("重跑不改任何檔案、不產生備份", before == after,
              str(set(after) ^ set(before)))

        # 2b. session-log-kit：插入、擋格式、歸檔都保留原本的換行（LF）
        kit = p / ".claude/session-log-kit"
        log = p / "session_log.md"

        def kit_run(script, *args):
            r = subprocess.run([sys.executable, str(kit / script), *map(str, args)], capture_output=True,
                               env=dict(BASE_ENV, CLAUDE_PROJECT_DIR=str(p)))
            return r.returncode, r.stdout.decode("utf-8", errors="replace")

        for i, day in enumerate(("2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05")):
            entry = base / f"entry{i}.md"
            entry.write_bytes(f"## {day} | 第 {i} 筆\n\n**做了什麼**：\n- 事\n\n**決定了什麼**：\n- 決定\n\n"
                              f"**下一步**：\n- 下一步 {i}\n".encode("utf-8"))
            code, out = kit_run("add_session_log.py", log, entry)
        text = log.read_text(encoding="utf-8")
        check("add_session_log：連插 5 筆，最新的在最上面", code == 0 and text.count("\n## 2020-") == 5 and
              text.find("## 2020-01-05") < text.find("## 2020-01-01"), out)
        before = log.read_bytes()
        bad = base / "bad_entry.md"
        bad.write_bytes("## 沒有日期的標題\n\n**做了什麼**：\n- 事\n".encode("utf-8"))
        code, out = kit_run("add_session_log.py", log, bad)
        check("add_session_log：格式不對就不寫入、結束碼 1", code == 1 and "不寫入" in out and
              log.read_bytes() == before, out)
        code, out = kit_run("archive_session_log.py")
        arc = p / "session_log_archive.md"
        check("archive_session_log：舊紀錄搬走、留最新 3 筆", code == 0 and arc.is_file() and
              log.read_text(encoding="utf-8").count("\n## 2020-") == 3 and
              arc.read_text(encoding="utf-8").count("## 2020-") == 2, out)
        check("session_log 套件寫回後仍是 LF", b"\r\n" not in log.read_bytes() + arc.read_bytes())
        crlf = base / "crlf_log.md"
        crlf.write_bytes(log.read_bytes().replace(b"\n", b"\r\n"))
        code, out = kit_run("add_session_log.py", crlf, base / "entry0.md")
        check("add_session_log：CRLF 的 log 寫回後仍是 CRLF",
              code == 0 and b"\n" not in crlf.read_bytes().replace(b"\r\n", b""), out)
        for f in (log, arc):  # 還原成剛裝好的樣子，下面的移除測試要用
            f.unlink()
        shutil.copy2(ROOT / "template/session_log.md.template", log)

        # 2c. 剛裝好、沒改過的專案移除後回到空資料夾（只剩 .claude/ 裡的備份與空 settings）
        code, out = run(p, "--uninstall")
        left = sorted(x.name for x in p.iterdir())
        check("沒改過的範本 CLAUDE.md、session_log.md、TODO.md 移除時刪掉（有備份）",
              code == 0 and left == [".claude"] and
              len(list((p / ".claude/backup").glob("workflow-template-*/CLAUDE.md"))) >= 1, out + str(left))
        check("沒有 .gitignore 的專案，移除訊息不提 .gitignore", ".gitignore" not in out, out)
        p = new_project(base, "edited")
        run(p, "--session-log")
        with open(p / "TODO.md", "a", encoding="utf-8") as f:
            f.write("- 我自己加的待辦\n")
        code, out = run(p, "--uninstall")
        check("改過的 TODO.md 移除時留著", code == 0 and (p / "TODO.md").is_file() and
              not (p / "session_log.md").exists(), out)
        # 3. 既有 settings、CLAUDE.md、git repo，不裝 session_log
        p = new_project(base, "existing")
        (p / ".git").mkdir()
        (p / ".claude").mkdir()
        user_hook = {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}
        (p / ".claude/settings.json").write_text(json.dumps(
            {"model": "sonnet", "hooks": {"PreToolUse": [user_hook]}}, indent=2), encoding="utf-8")
        (p / "CLAUDE.md").write_text("# 我的專案\n\n原本的內容。\n", encoding="utf-8")
        (p / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        settings_before = (p / ".claude/settings.json").read_bytes()
        code, out = run(p, "--no-session-log")
        check("既有專案安裝成功", code == 0, out)
        s = settings(p)
        check("保留使用者的其他設定", s.get("model") == "sonnet")
        check("保留使用者自己的 hook", user_hook in s["hooks"]["PreToolUse"])
        check("加了 6 個 hook、沒有 SessionStart", our_count(s) == 6 and "SessionStart" not in s["hooks"])
        check("CLAUDE.md 沒被改", (p / "CLAUDE.md").read_text(encoding="utf-8") == "# 我的專案\n\n原本的內容。\n")
        check("沒建 session_log.md", not (p / "session_log.md").exists())
        gi = (p / ".gitignore").read_text(encoding="utf-8")
        check(".gitignore 保留原本、加上狀態檔", gi.startswith("node_modules/") and ".claude/hooks/gate_trial.log" in gi)
        check("安裝訊息說明 .gitignore 加的是狀態檔與安裝備份", "安裝備份" in out, out)
        backups = list((p / ".claude/backup").glob("workflow-template-*/.claude/settings.json"))
        check("settings.json 有備份", len(backups) == 1)
        gi_backup = list((p / ".claude/backup").glob("workflow-template-*/.gitignore"))
        check(".gitignore 改之前有備份", len(gi_backup) == 1 and
              gi_backup[0].read_text(encoding="utf-8") == "node_modules/\n", str(gi_backup))

        # 4. 改裝 session_log：既有 CLAUDE.md 加段落
        code, out = run(p, "--session-log")
        cm = (p / "CLAUDE.md").read_text(encoding="utf-8")
        check("既有 CLAUDE.md 保留原文並加接力說明",
              code == 0 and cm.startswith("# 我的專案\n\n原本的內容。") and "claude-workflow-template:start" in cm, out)
        check("改裝後 7 個 hook", our_count(settings(p)) == 7)

        # 5. 移除
        trial = p / ".claude/hooks/gate_trial.log"
        trial.write_text('{"gate": "dispatch_gate", "verdict": "誤擋"}\n', encoding="utf-8")
        code, out = run(p, "--uninstall")
        s = settings(p)
        check("移除成功", code == 0, out)
        check("移除後只剩使用者的 hook", our_count(s) == 0 and s["hooks"]["PreToolUse"] == [user_hook], json.dumps(s))
        check("移除後其他設定還在", s.get("model") == "sonnet")
        check("移除後 hook 檔不在", not (p / ".claude/hooks/dispatch_gate.py").exists())
        check("移除後 CLAUDE.md 回到原文",
              (p / "CLAUDE.md").read_text(encoding="utf-8").rstrip() == "# 我的專案\n\n原本的內容。")
        gi = (p / ".gitignore").read_text(encoding="utf-8")
        check("移除後 .gitignore 留原文，備份資料夾還在所以 .claude/backup/ 那行留著",
              gi.startswith("node_modules/\n") and ".claude/backup/" in gi and "gate_trial.log" not in gi, gi)
        check("移除後 settings.json 和安裝前位元組相同（不重新排版）",
              (p / ".claude/settings.json").read_bytes() == settings_before)
        check("gate_trial.log 刪掉前有備份", not trial.exists() and any(
              "誤擋" in b.read_text(encoding="utf-8")
              for b in (p / ".claude/backup").glob("workflow-template-*/.claude/hooks/gate_trial.log")))
        if shutil.which("git"):
            r = subprocess.run(["git", "init", "-q", str(p)], capture_output=True)
            r = subprocess.run(["git", "-C", str(p), "status", "--porcelain", "--untracked-files=all"],
                               capture_output=True, text=True, encoding="utf-8")
            check("移除後 git 看不到備份資料夾", r.returncode == 0 and ".claude/backup" not in r.stdout, r.stdout)

        # 5b. git repo、安裝前沒有 .gitignore；專案原本就有自己的 .claude/rules/dispatch-and-verify.md
        p = new_project(base, "git-no-gitignore")
        (p / ".git").mkdir()
        (p / ".claude/rules").mkdir(parents=True)
        (p / ".claude/rules/dispatch-and-verify.md").write_text("# 我自己的規則\n", encoding="utf-8")
        run(p, "--no-session-log")
        code, out = run(p, "--uninstall")
        gi = p / ".gitignore"
        check("移除後 .gitignore 不是空檔：留著標題和 .claude/backup/",
              gi.is_file() and (gi.read_text(encoding="utf-8").strip().splitlines() or [""])[-1] == ".claude/backup/",
              gi.read_text(encoding="utf-8") if gi.exists() else "沒有 .gitignore")
        check("留著 .claude/backup/ 那行時，移除訊息提醒刪備份時一起拿掉", "那兩行也可以一起拿掉" in out, out)
        check("移除時指出原本那份規則檔在哪個備份",
              code == 0 and "workflow-template-" in out and ".claude/rules/dispatch-and-verify.md" in out.split("舊版")[-1],
              out)
        p = new_project(base, "gitignore-only-ours")
        (p / ".git").mkdir()
        (p / ".gitignore").write_text("# claude-workflow-template：hook 產生的本機狀態與安裝備份\n"
                                      ".claude/hooks/gate_trial.log\n.claude/backup/\n", encoding="utf-8")
        code, out = run(p, "--uninstall")
        check(".gitignore 只剩安裝時加的幾行、也沒有備份 -> 刪掉，不留空檔",
              code == 0 and not (p / ".gitignore").exists(), out)

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

        # 13. 已經用 plugin 裝了：兩條裝法並存會讓 hook 跑兩次，要停下說明
        for fname in ("settings.json", "settings.local.json"):
            p = new_project(base, "plugin-" + fname)
            (p / ".claude").mkdir()
            (p / ".claude" / fname).write_text(json.dumps(
                {"enabledPlugins": {"workflow-kit@workflow-kit": True}}), encoding="utf-8")
            before = snapshot(p)
            code, out = run(p, "--no-session-log")
            check(f"{fname} 已啟用 plugin 就停、不動檔案",
                  code != 0 and "plugin" in out and snapshot(p) == before, out)
        p = new_project(base, "plugin-disabled")
        (p / ".claude").mkdir()
        (p / ".claude/settings.json").write_text(json.dumps(
            {"enabledPlugins": {"workflow-kit@workflow-kit": False}}), encoding="utf-8")
        code, out = run(p, "--no-session-log")
        check("plugin 設成停用時照常安裝", code == 0, out)

        # 14. 舊版裝過 .ps1：重裝時收掉（先備份）、settings 換成 Python 版；開場 hook 實跑一次
        p = new_project(base, "legacy-ps1")
        kit = p / ".claude/session-log-kit"
        kit.mkdir(parents=True)
        for n in ("sessionstart_log.ps1", "archive_session_log.ps1"):
            (kit / n).write_text("# old\n", encoding="utf-8")
        old_hook = {"hooks": [{"type": "command", "command": "powershell", "args": [
            "-NoProfile", "-File", "${CLAUDE_PROJECT_DIR}/.claude/session-log-kit/sessionstart_log.ps1"]}]}
        (p / ".claude/settings.json").write_text(json.dumps({"hooks": {"SessionStart": [old_hook]}}), encoding="utf-8")
        code, out = run(p, "--session-log")
        s = json.dumps(settings(p))
        check("舊 .ps1 收掉且有備份", code == 0 and not (kit / "sessionstart_log.ps1").exists() and
              len(list((p / ".claude/backup").glob("workflow-template-*/.claude/session-log-kit/*.ps1"))) == 2, out)
        check("SessionStart 換成 Python 版、舊的拿掉", ".ps1" not in s and "sessionstart_log.py" in s, s)
        (p / "session_log.md").write_text("# log\n\n## 2026-10-02 | 舊\n\n**下一步**：\n- 舊的\n\n"
                                          "## 2026-10-03 | 新\n\n**做了什麼**：\n- 新的\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(kit / "sessionstart_log.py")], capture_output=True,
                           env=dict(BASE_ENV, CLAUDE_PROJECT_DIR=str(p)))
        ctx = json.loads(r.stdout.decode("utf-8") or "{}").get("hookSpecificOutput", {}).get("additionalContext", "")
        check("開場 hook 先放日期最新的全文、再放舊的標題與下一步",
              0 < ctx.find("## 2026-10-03 | 新") < ctx.find("## 2026-10-02 | 舊") and "- 新的" in ctx and "- 舊的" in ctx,
              ctx[:300])
        r = subprocess.run([sys.executable, str(kit / "sessionstart_log.py")], capture_output=True,
                           env=dict(BASE_ENV, CLAUDE_PROJECT_DIR=str(base / "no-such-project")))
        check("沒有 session_log.md 就安靜結束", r.returncode == 0 and r.stdout == b"", r.stdout[:200])

        # 15. --todo：選用，開場清單與 TODO 格式檢查（腳本正本在 todo/scripts/，這裡只複製）
        todo_files = ("todo_core.py", "todo_lint.py")

        def todo_hooks(s):
            found = []
            for event, groups in s.get("hooks", {}).items():
                for g in groups:
                    for h in g.get("hooks", []):
                        a = " ".join(h.get("args", []))
                        if "/.claude/todo/" in a:
                            found.append((event, g.get("matcher"), a, h.get("command")))
            return found

        p = new_project(base, "no-extras")
        code, out = run(p, "--no-session-log")
        check("沒給 --todo：沒有 .claude/todo、settings 沒有 todo hook、輸出不提 todo",
              code == 0 and not (p / ".claude/todo").exists() and not todo_hooks(settings(p))
              and "todo" not in out.lower() and our_count(settings(p)) == 6, out)

        p = new_project(base, "todo-on")
        code, out = run(p, "--no-session-log", "--todo")
        check("--todo 安裝成功", code == 0, out)
        check("--todo：兩支腳本複製到 .claude/todo 且與 todo/scripts 的正本相同",
              all((p / ".claude/todo" / n).is_file() and
                  (p / ".claude/todo" / n).read_bytes() == (ROOT / "todo/scripts" / n).read_bytes()
                  for n in todo_files))
        th = todo_hooks(settings(p))
        check("--todo：SessionStart 跑 todo_core.py render",
              any(e == "SessionStart" and a.endswith("/.claude/todo/todo_core.py render") for e, m, a, c in th), str(th))
        check("--todo：PostToolUse（Edit|Write）跑 todo_lint.py",
              any(e == "PostToolUse" and m == "Edit|Write" and a.endswith("/.claude/todo/todo_lint.py")
                  for e, m, a, c in th), str(th))
        check("--todo：只加這兩個 hook，沒有 UserPromptSubmit 與 index", len(th) == 2 and
              all(e in ("SessionStart", "PostToolUse") for e, m, a, c in th) and "index" not in json.dumps(th), str(th))
        check("--todo：hook 的 Python 指令名跟其他 hook 一致",
              {c for e, m, a, c in th} == {settings(p)["hooks"]["PreToolUse"][0]["hooks"][0]["command"]}, str(th))
        check("--todo：原本的 core hook 還在", our_count(settings(p)) >= 6)
        before = snapshot(p)
        code, out = run(p, "--no-session-log", "--todo")
        check("--todo 重跑不重複加 hook、不改任何檔案", code == 0 and len(todo_hooks(settings(p))) == 2
              and snapshot(p) == before, out)

        # 15b. 預演不寫檔，但列出動作
        p = new_project(base, "todo-dry")
        code, out = run(p, "--no-session-log", "--todo", "--dry-run")
        check("--todo --dry-run：沒建任何檔案、有列出 todo 的動作",
              code == 0 and not any(p.iterdir()) and ".claude/todo" in out and "todo_core.py" in out, out)

        # 15c. 移除：乾淨，settings 回到安裝前
        p = new_project(base, "todo-uninstall")
        (p / ".claude").mkdir()
        (p / ".claude/settings.json").write_text(json.dumps({"model": "sonnet"}, indent=4), encoding="utf-8")
        orig = (p / ".claude/settings.json").read_bytes()
        run(p, "--no-session-log", "--todo")
        (p / ".claude/todo/__pycache__").mkdir()
        (p / ".claude/todo/__pycache__/x.pyc").write_bytes(b"x")
        code, out = run(p, "--uninstall", "--dry-run")
        check("--uninstall --dry-run 列出 todo 檔且沒刪", code == 0 and (p / ".claude/todo/todo_core.py").exists()
              and "todo" in out, out)
        code, out = run(p, "--uninstall")
        check("--uninstall：todo 腳本與資料夾移除、hook 拿掉",
              code == 0 and not (p / ".claude/todo").exists() and not todo_hooks(settings(p)), out)
        check("--uninstall：settings.json 與安裝前位元組相同", (p / ".claude/settings.json").read_bytes() == orig)
        check("--uninstall：todo 腳本有備份", all(
              list((p / ".claude/backup").glob("workflow-template-*/.claude/todo/" + n)) for n in todo_files))

        # 15d. git repo：--todo 才多一行 pycache 的 .gitignore，移除時拿掉
        p = new_project(base, "todo-git")
        (p / ".git").mkdir()
        run(p, "--no-session-log")
        gi_off = (p / ".gitignore").read_text(encoding="utf-8")
        run(p, "--no-session-log", "--todo")
        gi_on = (p / ".gitignore").read_text(encoding="utf-8")
        check("--todo：.gitignore 多 .claude/todo/__pycache__/，沒給時沒有",
              ".claude/todo/__pycache__/" in gi_on and ".claude/todo/" not in gi_off, gi_on)
        run(p, "--uninstall")
        check("移除後 .gitignore 沒有 todo 那行",
              ".claude/todo/__pycache__/" not in (p / ".gitignore").read_text(encoding="utf-8"))

        # 15e. 用 --uninstall 搭 --todo 不合理
        code, out = run(new_project(base, "todo-bad"), "--uninstall", "--todo")
        check("--uninstall 不能搭 --todo", code != 0, out)
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print()
    print(f"{sum(results)}/{len(results)} 通過")
    return 0 if all(results) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
