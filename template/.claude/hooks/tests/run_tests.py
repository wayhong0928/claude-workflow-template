"""Hook regression tests (stdlib only).

Usage:
    python .claude/hooks/tests/run_tests.py [--hooks-dir DIR] [--override NAME=FILE ...]

How it works
- The hooks under test are the ones shipped in this repo: by default the parent folder of
  this tests/ folder (i.e. .claude/hooks/). Nothing under the real ~/.claude is read.
- Every hook is copied into a throw-away sandbox directory and run from there with
  subprocess, JSON on stdin, exactly like Claude Code does. State files, flag files and
  gate_trial.log all resolve relative to the hook's own __file__, so they land in the sandbox.
- HOME / USERPROFILE point at the sandbox too, so a hook that wrongly used Path.home()
  would also stay inside the sandbox (and the ctrl_char_stop test checks it did not).
- Before and after the run, the state files and logs next to the source hooks are hashed
  (SHA-256 + mtime); any difference makes the run fail.

--override NAME=FILE replaces one hook in the sandbox (used to prove the tests catch a
broken hook, e.g. --override dispatch_gate.py=/tmp/broken/dispatch_gate.py).
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

HOOK_FILES = [
    "hook_state.py", "gate_flags.py", "dispatch_gate.py", "skill_gate_flag_writer.py",
    "context_guard.py", "ctrl_char_stop.py",
]
STATE_NAMES = ("gate_trial.log", "ctrl_char_stop_state.json", "context_guard_state.json")

results = []  # bools


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if (detail and not ok) else ""))


# ---------- source-state fingerprint ----------
def state_files(hooks_dir):
    files = set()
    if hooks_dir.is_dir():
        for pat in ("*.log", "*_state.json"):
            files.update(hooks_dir.glob(pat))
        flags = hooks_dir / "skill_gate_flags"
        if flags.is_dir():
            files.update(p for p in flags.rglob("*") if p.is_file())
    # files that may not exist yet must still be watched
    for name in STATE_NAMES:
        files.add(hooks_dir / name)
    return sorted(files)


def fingerprint(hooks_dir):
    out = {}
    for p in state_files(hooks_dir):
        try:
            out[str(p)] = (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
        except FileNotFoundError:
            out[str(p)] = None
    return out


# ---------- helpers ----------
def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Sandbox:
    def __init__(self, hooks_src, overrides):
        self.root = Path(tempfile.mkdtemp(prefix="hooktest_"))
        self.hooks = self.root / "hooks"
        self.home = self.root / "home"
        self.work = self.root / "work"
        for d in (self.hooks, self.home, self.work):
            d.mkdir(parents=True, exist_ok=True)
        (self.hooks / "skill_gate_flags").mkdir()
        for name in HOOK_FILES:
            src = Path(overrides.get(name, hooks_src / name))
            if not src.is_file():
                raise SystemExit(f"hook not found: {src}")
            shutil.copy2(src, self.hooks / name)
        self.env = dict(os.environ, USERPROFILE=str(self.home), HOME=str(self.home),
                        PYTHONIOENCODING="utf-8")
        self.n = 0

    def sid(self):
        self.n += 1
        return f"test-session-{self.n}-{time.time_ns()}"

    def flag_path(self, sid, skill):
        return self.hooks / "skill_gate_flags" / f"{sid}__{skill}.flag"

    def flag(self, sid, skill, age_s=0):
        f = self.flag_path(sid, skill)
        f.write_text("x", encoding="utf-8")
        t = time.time() - age_s
        os.utime(f, (t, t))

    def run(self, hook, payload, env=None):
        r = subprocess.run([sys.executable, str(self.hooks / hook)],
                           input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                           capture_output=True, timeout=60, env=dict(self.env, **(env or {})),
                           cwd=str(self.work))
        return r.returncode, r.stdout.decode("utf-8", errors="replace").strip(), \
            r.stderr.decode("utf-8", errors="replace").strip()

    def transcript(self, records):
        # compact separators, like real transcripts (gate_flags looks for "subtype":"compact_boundary")
        p = self.work / f"t{time.time_ns()}.jsonl"
        p.write_text("\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":"))
                               for r in records), encoding="utf-8")
        return p

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


def decision(out):
    """Return the decision word from hook stdout, or '' when nothing/garbage was printed."""
    if not out:
        return ""
    try:
        j = json.loads(out)
    except Exception:
        return "?garbage"
    if j.get("decision"):
        return j["decision"]
    return (j.get("hookSpecificOutput") or {}).get("permissionDecision", "")


def user_rec(dt, text="請做事"):
    return {"type": "user", "timestamp": iso(dt), "message": {"role": "user", "content": text}}


def tool_use_rec(name, inp, cwd, dt):
    return {"type": "assistant", "cwd": str(cwd), "timestamp": iso(dt),
            "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu1", "name": name, "input": inp}]}}


def tool_result_rec(dt):
    return {"type": "user", "toolUseResult": {"ok": True}, "timestamp": iso(dt),
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu1", "content": "ok"}]}}


def usage_rec(tokens, sidechain=False):
    return {"type": "assistant", "isSidechain": sidechain, "timestamp": iso(datetime.now()),
            "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}],
                        "usage": {"input_tokens": 10, "cache_read_input_tokens": tokens - 10,
                                  "cache_creation_input_tokens": 0}}}


# ---------- test groups ----------
def agent_payload(sb, sid, subagent="general-purpose", tp=None, tool="Agent"):
    p = {"hook_event_name": "PreToolUse", "tool_name": tool, "session_id": sid,
         "cwd": str(sb.work),
         "tool_input": {"subagent_type": subagent, "model": "sonnet",
                        "description": "test", "prompt": "do it"}}
    if tp:
        p["transcript_path"] = str(tp)
    return p


def test_dispatch_gate(sb):
    rc, out, _ = sb.run("dispatch_gate.py", agent_payload(sb, sb.sid()))
    check("dispatch_gate: 未叫用 dispatch-template -> 擋", rc == 0 and decision(out) == "deny", out[:100])
    sid = sb.sid()
    sb.flag(sid, "dispatch-template")
    rc, out, _ = sb.run("dispatch_gate.py", agent_payload(sb, sid))
    check("dispatch_gate: 已叫用 -> 放", rc == 0 and out == "", out[:100])
    rc, out, _ = sb.run("dispatch_gate.py", agent_payload(sb, sb.sid(), "fork"))
    check("dispatch_gate: fork 免檢 -> 放", rc == 0 and out == "", out[:100])
    rc, out, _ = sb.run("dispatch_gate.py", agent_payload(sb, sb.sid(), tool="Bash"))
    check("dispatch_gate: 不是 Agent 工具 -> 放", rc == 0 and out == "", out[:100])

    now = datetime.now()
    compact = {"type": "system", "subtype": "compact_boundary", "timestamp": iso(now - timedelta(seconds=60))}
    sid = sb.sid()
    sb.flag(sid, "dispatch-template", age_s=120)  # flag older than the compact
    tp = sb.transcript([user_rec(now - timedelta(seconds=300)), compact])
    rc, out, _ = sb.run("dispatch_gate.py", agent_payload(sb, sid, tp=tp))
    check("dispatch_gate: 叫用後發生 compact -> 擋", rc == 0 and decision(out) == "deny", out[:100])
    sb.flag(sid, "dispatch-template", age_s=0)  # re-invoked after the compact
    rc, out, _ = sb.run("dispatch_gate.py", agent_payload(sb, sid, tp=tp))
    check("dispatch_gate: compact 後重新叫用 -> 放", rc == 0 and out == "", out[:100])


def test_flag_writer(sb):
    def skill(sid, name):
        return {"hook_event_name": "PostToolUse", "tool_name": "Skill", "session_id": sid,
                "tool_input": {"skill": name}}

    sid = sb.sid()
    rc, out, _ = sb.run("skill_gate_flag_writer.py", skill(sid, "dispatch-template"))
    check("skill_gate_flag_writer: 裸名稱 -> 寫 flag",
          rc == 0 and sb.flag_path(sid, "dispatch-template").is_file(), out[:100])
    sid = sb.sid()
    rc, out, _ = sb.run("skill_gate_flag_writer.py", skill(sid, "my-plugin:dispatch-template"))
    check("skill_gate_flag_writer: plugin:skill 格式 -> 用裸名稱寫 flag",
          rc == 0 and sb.flag_path(sid, "dispatch-template").is_file(), out[:100])
    sid = sb.sid()
    rc, out, _ = sb.run("skill_gate_flag_writer.py", skill(sid, "some-other-skill"))
    left = list((sb.hooks / "skill_gate_flags").glob(f"{sid}__*"))
    check("skill_gate_flag_writer: 未受管制的 skill -> 不寫", rc == 0 and not left, str(left))

    # 使用者直接打 /dispatch-template：不經 Skill 工具，走 UserPromptExpansion
    def expansion(sid, name):
        return {"hook_event_name": "UserPromptExpansion", "session_id": sid,
                "expansion_type": "slash_command", "command_name": name,
                "command_args": "", "prompt": f"/{name}"}

    sid = sb.sid()
    rc, out, _ = sb.run("skill_gate_flag_writer.py", expansion(sid, "dispatch-template"))
    check("skill_gate_flag_writer: 使用者打 /dispatch-template -> 寫 flag",
          rc == 0 and out == "" and sb.flag_path(sid, "dispatch-template").is_file(), out[:100])
    sid = sb.sid()
    rc, out, _ = sb.run("skill_gate_flag_writer.py", expansion(sid, "my-plugin:dispatch-template"))
    check("skill_gate_flag_writer: 使用者打 /plugin:dispatch-template -> 用裸名稱寫 flag",
          rc == 0 and sb.flag_path(sid, "dispatch-template").is_file(), out[:100])

    # end to end: writer then gate
    sid = sb.sid()
    sb.run("skill_gate_flag_writer.py", skill(sid, "dispatch-template"))
    rc, out, _ = sb.run("dispatch_gate.py", agent_payload(sb, sid))
    check("串接: Skill 叫用後 dispatch_gate 放行", rc == 0 and out == "", out[:100])


def test_context_guard(sb):
    def case(sid, records):
        payload = {"session_id": sid, "transcript_path": str(sb.transcript(records)),
                   "hook_event_name": "UserPromptSubmit", "prompt": "繼續"}
        return sb.run("context_guard.py", payload)

    rc, out, _ = case(sb.sid(), [usage_rec(50_000)])
    check("context_guard: 5 萬 -> 不提醒", rc == 0 and out == "", out[:100])
    sid = sb.sid()
    rc, out, _ = case(sid, [usage_rec(160_000)])
    ctx = ""
    try:
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        pass
    check("context_guard: 16 萬 -> 提醒一次", rc == 0 and "[context_guard]" in ctx, out[:100])
    rc, out, _ = case(sid, [usage_rec(170_000)])
    check("context_guard: 同一級再來 -> 不重複提醒", rc == 0 and out == "", out[:100])
    rc, out, _ = case(sid, [usage_rec(260_000)])
    check("context_guard: 跨到下一級 -> 再提醒", rc == 0 and "[context_guard]" in out, out[:100])
    rc, out, _ = case(sb.sid(), [usage_rec(40_000), usage_rec(500_000, sidechain=True)])
    check("context_guard: 只看主對話、不看 sidechain -> 不提醒", rc == 0 and out == "", out[:100])


def test_ctrl_char(sb):
    now = datetime.now()

    def case(name, data):
        f = sb.work / name
        f.write_bytes(data)
        recs = [user_rec(now - timedelta(seconds=30)),
                tool_use_rec("Write", {"file_path": str(f), "content": "x"}, sb.work, now),
                tool_result_rec(now)]
        payload = {"session_id": sb.sid(), "transcript_path": str(sb.transcript(recs)),
                   "cwd": str(sb.work), "hook_event_name": "Stop", "stop_hook_active": False}
        return sb.run("ctrl_char_stop.py", payload)

    rc, out, _ = case("bad.md", "路徑 C:".encode("utf-8") + b"\x08ackup\n")
    check("ctrl_char_stop: .md 含 \\x08 -> 擋", rc == 0 and decision(out) == "block", out[:100])
    check("ctrl_char_stop: 狀態檔寫在 hook 旁邊、不在家目錄",
          (sb.hooks / "ctrl_char_stop_state.json").is_file()
          and not (sb.home / ".claude" / "hooks" / "ctrl_char_stop_state.json").exists())
    rc, out, _ = case("good.md", "正常的中文內容\n第二行\n".encode("utf-8"))
    check("ctrl_char_stop: 正常中文 -> 放", rc == 0 and out == "", out[:100])
    rc, out, _ = case("crlf.md", "第一行\r\n第二行\r\n".encode("utf-8"))
    check("ctrl_char_stop: CRLF 換行 -> 放", rc == 0 and out == "", out[:100])

    # Bash 指令裡的絕對路徑（Windows 是 C:/...，Linux／macOS 是 /tmp/...、/Users/...）
    def bash_case(f, command):
        recs = [user_rec(now - timedelta(seconds=30)),
                tool_use_rec("Bash", {"command": command}, sb.work, now),
                tool_result_rec(now)]
        payload = {"session_id": sb.sid(), "transcript_path": str(sb.transcript(recs)),
                   "cwd": str(sb.work), "hook_event_name": "Stop", "stop_hook_active": False}
        return sb.run("ctrl_char_stop.py", payload)

    bad = b"x\x08y\n"
    f = sb.work / "bash_bad.md"
    f.write_bytes(bad)
    rc, out, _ = bash_case(f, f"printf 'x\\by' > {f.as_posix()}")
    check("ctrl_char_stop: Bash 指令裡的絕對路徑 -> 擋", rc == 0 and decision(out) == "block", out[:100])
    spaced = sb.work / "有 空白"
    spaced.mkdir(exist_ok=True)
    f = spaced / "bad.md"
    f.write_bytes(bad)
    rc, out, _ = bash_case(f, f"printf 'x\\by' > \"{f.as_posix()}\"")
    check("ctrl_char_stop: 引號包住、含空白與中文的路徑 -> 擋", rc == 0 and decision(out) == "block", out[:100])


def test_plugin_data(sb):
    """plugin 裝法：狀態寫進 CLAUDE_PLUGIN_DATA（跨更新保留），每個專案各一個子資料夾。"""
    data = sb.root / "plugin-data"
    projects = [sb.root / "proj-a", sb.root / "proj-b"]
    for d in [data] + projects:
        d.mkdir()
    envs = [{"CLAUDE_PLUGIN_DATA": str(data), "CLAUDE_PROJECT_DIR": str(p)} for p in projects]
    before = fingerprint(sb.hooks)

    sid = sb.sid()
    sb.run("skill_gate_flag_writer.py", {"hook_event_name": "PostToolUse", "tool_name": "Skill",
                                         "session_id": sid, "tool_input": {"skill": "dispatch-template"}},
           env=envs[0])
    flags = list(data.rglob(f"{sid}__dispatch-template.flag"))
    check("plugin: flag 寫進 CLAUDE_PLUGIN_DATA", len(flags) == 1, str(flags))
    rc, out, _ = sb.run("dispatch_gate.py", agent_payload(sb, sid), env=envs[0])
    check("plugin: 同一專案讀得到 flag -> 放", rc == 0 and out == "", out[:100])
    rc, out, _ = sb.run("dispatch_gate.py", agent_payload(sb, sb.sid()), env=envs[0])
    check("plugin: 沒叫用 -> 擋，log 寫進 CLAUDE_PLUGIN_DATA",
          decision(out) == "deny" and len(list(data.rglob("gate_trial.log"))) == 1, out[:100])

    now = datetime.now()
    for i, env in enumerate(envs):
        f = sb.work / f"plugin_bad_{i}.md"
        f.write_bytes(b"x\x08y\n")
        recs = [user_rec(now - timedelta(seconds=30)),
                tool_use_rec("Write", {"file_path": str(f), "content": "x"}, sb.work, now),
                tool_result_rec(now)]
        sb.run("ctrl_char_stop.py", {"session_id": sb.sid(), "transcript_path": str(sb.transcript(recs)),
                                     "cwd": str(sb.work), "hook_event_name": "Stop",
                                     "stop_hook_active": False}, env=env)
        sb.run("context_guard.py", {"session_id": sb.sid(), "hook_event_name": "UserPromptSubmit",
                                    "transcript_path": str(sb.transcript([usage_rec(160_000)])),
                                    "prompt": "繼續"}, env=env)
    for name in ("ctrl_char_stop_state.json", "context_guard_state.json"):
        found = list(data.rglob(name))
        check(f"plugin: 兩個專案各有自己的 {name}",
              len(found) == 2 and len({p.parent for p in found}) == 2, str(found))
    after = fingerprint(sb.hooks)
    check("plugin: hook 自己資料夾的狀態檔沒被動到", before == after,
          str([p for p in set(before) | set(after) if before.get(p) != after.get(p)]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hooks-dir", type=Path, default=HERE.parent)
    ap.add_argument("--override", action="append", default=[], metavar="NAME=FILE")
    a = ap.parse_args()

    hooks_dir = a.hooks_dir.resolve()
    overrides = {}
    for item in a.override:
        name, _, path = item.partition("=")
        overrides[name] = path

    before = fingerprint(hooks_dir)
    sb = Sandbox(hooks_dir, overrides)
    try:
        for fn in (test_dispatch_gate, test_flag_writer, test_context_guard, test_ctrl_char, test_plugin_data):
            fn(sb)
        # the sandbox, not the source hooks dir, must have received the block log
        log = sb.hooks / "gate_trial.log"
        check("隔離: 擋下事件的 log 寫進沙箱",
              log.is_file() and "deny" in log.read_text(encoding="utf-8"))
    finally:
        sb.cleanup()
    after = fingerprint(hooks_dir)

    changed = [p for p in before if before[p] != after[p]]
    check("隔離: 原始 hooks 資料夾的狀態檔與 log 前後一致（SHA-256 與 mtime）", not changed, str(changed))
    print(f"\n受測 hooks：{hooks_dir}")

    passed = sum(results)
    print(f"\n{passed}/{len(results)} 通過")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
