"""todo_core.py 的測試。直接跑：python todo/tests/test_todo_core.py

測試資料裡的 Tab 一律寫成 "\x09"，路徑一律用正斜線。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import todo_core as core  # noqa: E402

CORE = str(SCRIPTS / "todo_core.py")
LINT = str(SCRIPTS / "todo_lint.py")
TODAY = date(2026, 10, 18)
NL = "\n"


def kinds(problems):
    return [p["kind"] for p in problems]


class Tmp(unittest.TestCase):
    """每個測試一個暫存資料夾，當成設定資料夾兼專案根目錄。"""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="todo-test-"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, rel, text):
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def config(self, projects, **extra):
        conf = {"home": projects[0]["name"], "projects": projects}
        conf.update(extra)
        return self.write("todo.config.json", json.dumps(conf, ensure_ascii=False))

    def run_cli(self, *args, stdin=None):
        env = dict(os.environ)
        env["CLAUDE_CONFIG_DIR"] = str(self.dir)
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            [sys.executable, *args], input=stdin, capture_output=True, env=env,
            stdin=None if stdin is not None else subprocess.DEVNULL,
        )


# ---- GS3 附錄 B 的五個案例 ----

class AppendixB(Tmp):
    def test_bad_field_paren(self):
        items, probs = core.parse_todo_text(
            "- [ ] [你] 看對帳表（建 10-13，10-17 改：原訂週五）", TODAY)
        self.assertIn("欄位括號格式不對", kinds(probs))
        # 壞欄位照樣盡量解析進 index：建立日、修改日都抽得出來
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["born"], "2026-10-13")
        self.assertEqual(items[0]["touched"], "2026-10-17")
        self.assertEqual(items[0]["text"], "看對帳表")

    def test_child_right_under_heading(self):
        _, probs = core.parse_todo_text(NL.join(["## 待你決定", "", "  - AC-2 照 README 設定"]), TODAY)
        self.assertIn("子項上面沒有母條目", kinds(probs))

    def test_tab(self):
        _, probs = core.parse_todo_text("- [ ] [Claude] 改 mods\x09odo 的設定（建 10-13）", TODAY)
        self.assertIn("控制字元", kinds(probs))

    def test_bad_tag(self):
        items, probs = core.parse_todo_text("- [ ] [工作身分] 會議紀錄小幫手（建 10-05）", TODAY)
        self.assertIn("標籤不合法", kinds(probs))
        self.assertEqual(items[0]["who"], "未分類")
        self.assertTrue(items[0]["text"].startswith("[工作身分]"))

    def test_missing_todo_file(self):
        cfg = self.config([{"name": "示範", "root": str(self.dir), "todo": ["沒有這個檔.md"]}])
        conf = core.load_config(str(cfg))
        index = core.build(conf, TODAY)
        self.assertIn("讀不到", kinds(index["problems"]))
        r = self.run_cli(CORE, "lint", "--config", str(cfg))
        self.assertEqual(r.returncode, 1)
        self.assertIn("讀不到", r.stdout.decode("utf-8"))


# ---- 1.2 節的實際壞條目 ----

class RealBadItems(unittest.TestCase):
    def test_born_unparsable(self):
        _, probs = core.parse_todo_text("- [ ] [你] 甲（建 十月中）", TODAY)
        self.assertIn("建立日解析不了", kinds(probs))
        _, probs = core.parse_todo_text("- [ ] [你] 乙沒有建立日", TODAY)
        self.assertIn("建立日解析不了", kinds(probs))

    def test_first_line_too_long(self):
        _, probs = core.parse_todo_text("- [ ] [你] " + "字" * 61 + "（建 10-13）", TODAY)
        self.assertIn("第一行太長", kinds(probs))
        _, probs = core.parse_todo_text("- [ ] [你] " + "字" * 60 + "（期限 10-30）（建 10-13）", TODAY)
        self.assertNotIn("第一行太長", kinds(probs))
        _, probs = core.parse_todo_text("- [ ] [你] " + "字" * 61 + "（建 10-13）", TODAY, max_first_line=80)
        self.assertNotIn("第一行太長", kinds(probs))

    def test_orphan_child_and_tab_child(self):
        _, probs = core.parse_todo_text(NL.join(["# TODO", "\x09- 用 Tab 縮排、上面沒有母條目"]), TODAY)
        self.assertEqual(sorted(kinds(probs)), ["子項上面沒有母條目", "控制字元"])

    def test_child_after_parent_is_fine(self):
        text = NL.join(["- [ ] [你] 甲（建 10-13）", "  - 現況", "", "  - 空行之後仍算同一條的子項"])
        _, probs = core.parse_todo_text(text, TODAY)
        self.assertEqual(probs, [])

    def test_child_with_tag(self):
        _, probs = core.parse_todo_text(NL.join(["- [ ] [你] 甲（建 10-13）", "  - [Claude] 子項夾了標籤"]), TODAY)
        self.assertIn("子項不放標籤", kinds(probs))


class FirstLine(unittest.TestCase):
    def test_v3_line(self):
        items, probs = core.parse_todo_text(
            "- [ ] [你決定] 王小明的報告要不要改題目（期限 10-30）（計畫 計畫_甲.md）（建 10-01）（改 10-15）", TODAY)
        self.assertEqual(probs, [])
        i = items[0]
        self.assertEqual(i["who"], "你決定")
        self.assertEqual(i["text"], "王小明的報告要不要改題目")
        self.assertEqual(i["due"], "2026-10-30")
        self.assertEqual(i["born"], "2026-10-01")
        self.assertEqual(i["touched"], "2026-10-15")
        self.assertEqual(i["planRefs"], ["計畫_甲.md"])
        self.assertFalse(i["stale"])  # 改 10-15 離今天 3 天

    def test_only_top_level_unchecked(self):
        text = NL.join(["- [ ] [你] 甲（建 10-13）", "  - [ ] 子項不算", "- [x] [Claude] 做完的不算",
                        "- [ ] [Claude] 乙（建 09-27）", "* [ ] [等外部] 丙（建 10-17）"])
        items, _ = core.parse_todo_text(text, TODAY)
        self.assertEqual([i["who"] for i in items], ["你", "Claude", "等外部"])
        self.assertEqual([i["line"] for i in items], [1, 4, 5])
        self.assertTrue(items[1]["stale"])

    def test_explanatory_paren_allowed(self):
        _, probs = core.parse_todo_text("- [ ] [你] 讀第三章（附錄先跳過）（建 10-13）", TODAY)
        self.assertEqual(probs, [])
        _, probs = core.parse_todo_text("- [ ] [你] 讀第三章（建議先讀附錄）（建 10-13）", TODAY)
        self.assertEqual(probs, [])

    def test_field_order_and_duplicate(self):
        _, probs = core.parse_todo_text("- [ ] [你] 甲（建 10-13）（期限 10-30）", TODAY)
        self.assertIn("欄位順序不對", kinds(probs))
        _, probs = core.parse_todo_text("- [ ] [你] 甲（期限 10-30）（期限 10-31）（建 10-13）", TODAY)
        self.assertIn("欄位重複", kinds(probs))

    def test_year_guess(self):
        # 期限可以在明年初；建立日不會在未來
        items, _ = core.parse_todo_text("- [ ] [你] 甲（期限 01-05）（建 12-20）", TODAY)
        self.assertEqual(items[0]["due"], "2027-01-05")
        self.assertEqual(items[0]["born"], "2025-12-20")

    def test_code_fence_ignored(self):
        items, _ = core.parse_todo_text(NL.join(["```", "- [ ] [你] 範例不算（建 10-13）", "```"]), TODAY)
        self.assertEqual(items, [])

    def test_missing_tag(self):
        items, probs = core.parse_todo_text("- [ ] 沒標籤的（建 10-13）", TODAY)
        self.assertIn("缺少標籤", kinds(probs))
        self.assertEqual(items[0]["who"], "未分類")

    def test_display_text_drops_markup(self):
        items, _ = core.parse_todo_text("- [ ] [Claude] **改** `CLAUDE.md`（併入 10/24 goal 計畫 G3）（建 10-13）", TODAY)
        self.assertEqual(items[0]["text"], "改 CLAUDE.md")
        self.assertTrue(items[0]["merged"])


# ---- goal 計畫 ----

PLAN = NL.join([
    "---",
    "到期: 2026-10-24",
    "到期後: 收進備份",
    "---",
    "# 計畫：10/24 goal 計畫（第二章）",
    "- **目標**：用 /goal 跑完",
    "## 總覽",
    "| Goal | 內容 |",
    "## G1 統計（`stats` session）",
    "- [x] 1. 做完的",
    "- [ ] 2. 讀 `統計.md` 補缺漏 → 檢查：清單貼在對話。",
    "```",
    "- [ ] 程式碼區塊裡的不算",
    "```",
    "## G2 文獻",
    "- [ ] 1. 合派 verifier",
    "### 追加",
    "- [X] 2. 子節也算進 G2",
])


class Plans(Tmp):
    def test_parse_plan(self):
        p = core.parse_plan(PLAN)
        self.assertEqual(p["title"], "10/24 goal 計畫（第二章）")
        self.assertEqual(p["due"], "2026-10-24")
        self.assertEqual(p["sections"], [
            {"name": "G1 統計（stats session）", "done": 1, "total": 2,
             "steps": [{"text": "1. 做完的", "isDone": True}, {"text": "2. 讀 統計.md 補缺漏", "isDone": False}]},
            {"name": "G2 文獻", "done": 1, "total": 2,
             "steps": [{"text": "1. 合派 verifier", "isDone": False}, {"text": "2. 子節也算進 G2", "isDone": True}]},
        ])
        self.assertEqual(p["next"], "G1 統計｜2. 讀 統計.md 補缺漏")
        self.assertIsNone(core.parse_plan("# 計畫：沒寫那個指令" + NL + "## 一" + NL + "- [ ] 甲"))

    def test_goals_in_index(self):
        self.write("proj/docs/計畫_甲.md", PLAN)
        self.write("proj/計畫_做完.md", NL.join(["# 計畫：做完", "/goal", "## 一", "- [x] 甲"]))
        self.write("proj/TODO.md", NL.join([
            "- [ ] [Claude] 跑 goal（計畫 計畫_甲.md）（建 10-13）",
            "- [ ] [Claude] 精簡測試（併入 10/24 goal 計畫 G3）（建 10-13）",
            "- [ ] [Claude] 舊寫法照 `docs/計畫_甲.md` 跑（期限 10-30）（建 10-13）",
            "- [ ] [Claude] 做完的計畫（計畫 計畫_做完.md）（建 10-13）",
            "- [ ] [Claude] 找不到的計畫（計畫 計畫_沒有.md）（建 10-13）",
            "- [ ] [你] 沒關係的（建 10-13）",
        ]))
        conf = core.load_config(str(self.config([{"name": "示範", "root": str(self.dir / "proj"), "todo": ["TODO.md"]}])))
        index = core.build(conf, TODAY)
        self.assertEqual([g["title"] for g in index["goals"]], ["10/24 goal 計畫（第二章）"])
        g = index["goals"][0]
        self.assertEqual(g["file"], "計畫_甲.md")
        self.assertEqual(g["due"], "2026-10-24")  # 檔頭的到期，不是條目的期限
        self.assertEqual(g["project"], "示範")
        items = index["projects"][0]["items"]
        self.assertEqual([bool(i["goal"]) for i in items], [True, True, True, False, False, False])
        self.assertEqual([i["merged"] for i in items], [False, True, False, False, False, False])
        self.assertIn("計畫檔找不到", kinds(index["problems"]))


# ---- session_log 的下一步 ----

class NextStep(unittest.TestCase):
    def test_latest_by_date(self):
        log = NL.join([
            "# Session Log",
            "格式：`## YYYY-MM-DD | 主題`",
            "## 2026-10-18 | 舊的放上面",
            "**下一步**：",
            "- 舊的不該出現",
            "",
            "## 2026-10-19（晚上） | 新的一筆",
            "**做了什麼**：",
            "- 做了甲",
            "**下一步**：",
            "- 使用者：回 **五項** 決定",
            "- Claude：改 `CLAUDE.md`",
            "  - 縮排的不算",
            "**備註**：",
            "- 備註不算",
        ])
        self.assertEqual(core.latest_next(log), {
            "title": "2026-10-19（晚上） | 新的一筆",
            "steps": ["使用者：回 五項 決定", "Claude：改 CLAUDE.md"],
        })

    def test_plain_heading(self):
        log = NL.join(["## 2026-10-20 | 不加粗", "做了什麼：", "- 甲", "下一步：", "- 乙", "- 丙", "", "## 2026-10-01 | 更舊"])
        self.assertEqual(core.latest_next(log)["steps"], ["乙", "丙"])
        self.assertIsNone(core.latest_next("# 空的" + NL))

    def test_same_line(self):
        log = NL.join(["## 2026-10-20 | 同一行", "**下一步**：等使用者回覆"])
        self.assertEqual(core.latest_next(log)["steps"], ["等使用者回覆"])


# ---- 有效期檔案 ----

def snapshot(root):
    return sorted((str(p.relative_to(root)), p.stat().st_size, p.stat().st_mtime_ns)
                  for p in Path(root).rglob("*"))


class Expiring(Tmp):
    def test_due_soon_and_expired_untouched(self):
        today = date.today()
        soon = (today + timedelta(days=2)).isoformat()
        past = (today - timedelta(days=5)).isoformat()
        far = (today + timedelta(days=30)).isoformat()
        self.write("proj/TODO.md", "- [ ] [你] 甲（建 10-13）")
        self.write("proj/計畫_快到.md", NL.join(["---", "到期: " + soon, "到期後: 搬進 **備份**", "---", "# 快到"]))
        self.write("proj/sub/交接_過期.md", NL.join(["---", "到期: " + past, "---", "# 過期"]))
        self.write("proj/還早.md", NL.join(["---", "到期: " + far, "---"]))
        self.write("proj/備份/舊的.md", NL.join(["---", "到期: " + past, "---"]))
        self.config([{"name": "示範", "root": str(self.dir / "proj"), "todo": ["TODO.md"]}])
        before = snapshot(self.dir / "proj")

        r = self.run_cli(CORE, "index")
        self.assertEqual(r.returncode, 0, r.stderr)
        index = json.loads((self.dir / "todo_index.json").read_text(encoding="utf-8"))
        got = {e["rel"]: e["left"] for e in index["expiring"]}
        self.assertEqual(got, {"計畫_快到.md": 2, "sub/交接_過期.md": -5})
        after_text = [e["after"] for e in index["expiring"] if e["rel"] == "計畫_快到.md"][0]
        self.assertEqual(after_text, "搬進 備份")

        r = self.run_cli(CORE, "render")
        out = r.stdout.decode("utf-8")
        self.assertIn("已過期", out)
        self.assertIn("3 天內到期", out)
        self.assertIn("sub/交接_過期.md", out)
        self.assertEqual(snapshot(self.dir / "proj"), before)


# ---- 子指令的輸出 ----

class Commands(Tmp):
    def setUp(self):
        super().setUp()
        lines = ["- [ ] [你] 第 %d 條很長的待辦，用來把開場清單撐到超過上限（期限 10-30）（建 10-13）" % n for n in range(2000)]
        self.write("proj/TODO.md", NL.join(lines))
        self.write("proj/session_log.md", NL.join(["## 2026-10-17 | 一筆", "**下一步**：", "- 繼續"]))
        self.config([{"name": "示範", "root": str(self.dir / "proj"), "todo": ["TODO.md"], "log": "session_log.md"}])

    def test_index_prints_nothing(self):
        r = self.run_cli(CORE, "index")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(r.stdout), 0)
        index = json.loads((self.dir / "todo_index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(index["projects"][0]["items"]), 2000)
        self.assertEqual(index["projects"][0]["next"]["steps"], ["繼續"])

    def test_render_capped(self):
        r = self.run_cli(CORE, "render")
        out = r.stdout.decode("utf-8")
        self.assertEqual(r.returncode, 0)
        self.assertLessEqual(len(out), 10000)
        self.assertIn("超過 10,000 字元", out)

    def test_render_uses_cwd_from_hook_input(self):
        other = self.dir / "other"
        self.write("other/TODO.md", "- [ ] [Claude] 別的專案的事（建 10-13）")
        conf = json.loads((self.dir / "todo.config.json").read_text(encoding="utf-8"))
        conf["projects"].append({"name": "別的", "root": str(other), "todo": ["TODO.md"]})
        self.write("todo.config.json", json.dumps(conf, ensure_ascii=False))
        r = self.run_cli(CORE, "render", stdin=json.dumps({"cwd": str(other / "sub")}).encode("utf-8"))
        out = r.stdout.decode("utf-8")
        self.assertIn("【別的】未完成 1 條", out)
        self.assertIn("別的專案的事", out)

    def test_render_lists_merged_items_under_goal_only(self):
        self.write("proj/計畫_甲.md", NL.join(["# 計畫：甲計畫", "/goal 照做", "## 一", "- [ ] 第一步"]))
        self.write("proj/TODO.md", NL.join([
            "- [ ] [你] 星期六貼 /goal（計畫 計畫_甲.md）（建 10-13）",
            "- [ ] [Claude] 補三塊原理（併入星期六 goal）（計畫 計畫_甲.md）（建 10-13）",
            "- [ ] [Claude] 自己的事（建 10-13）"]))
        out = self.run_cli(CORE, "render").stdout.decode("utf-8")
        self.assertIn("【示範】未完成 2 條（另 1 條已併入 goal 計畫，列在下面）", out)
        self.assertEqual(out.count("補三塊原理"), 1)
        self.assertIn("  - 併入：示範｜補三塊原理", out)
        self.assertIn("星期六貼 /goal", out)

    def test_no_config(self):
        (self.dir / "todo.config.json").unlink()
        r = self.run_cli(CORE, "index")
        self.assertEqual((r.returncode, len(r.stdout)), (0, 0))
        self.assertFalse((self.dir / "todo_index.json").exists())
        r = self.run_cli(CORE, "render")
        self.assertIn("todo.config.json", r.stdout.decode("utf-8"))

    def test_lint_exit_codes(self):
        good = self.write("good.md", "- [ ] [你] 甲（建 10-13）")
        bad = self.write("bad.md", "- [ ] 乙")
        self.assertEqual(self.run_cli(CORE, "lint", str(good)).returncode, 0)
        r = self.run_cli(CORE, "lint", str(bad))
        self.assertEqual(r.returncode, 1)
        self.assertIn("bad.md:1", r.stdout.decode("utf-8"))


# ---- 設定檔 ----

class Config(Tmp):
    def test_tilde_and_wsl(self):
        env = {"HOME": "/home/wang", "USERPROFILE": "C:/Users/wang"}
        home = "C:/Users/wang" if os.name == "nt" else "/home/wang"
        self.assertEqual(core.expand("~/projects/my-thesis", env, wsl=None), home + "/projects/my-thesis")
        self.assertEqual(core.expand("~", env, wsl=None), home)
        self.assertEqual(core.expand("E:/x/y", env, wsl="/mnt"), "/mnt/e/x/y")
        self.assertEqual(core.to_wsl("E:/work/thesis", "/mnt"), "/mnt/e/work/thesis")
        self.assertEqual(core.to_wsl("E:/work/thesis", "/mnt/d"), "/mnt/e/work/thesis")
        self.assertEqual(core.to_wsl("C:/Users/wang", "/mnt/d"), "/mnt/c/Users/wang")
        self.assertEqual(core.to_wsl("/home/wang", "/mnt"), "/home/wang")

    def test_config_path_tilde(self):
        self.config([{"name": "示範", "root": str(self.dir), "todo": ["TODO.md"]}])
        env = {"HOME": str(self.dir), "USERPROFILE": str(self.dir)}
        conf = core.load_config("~/todo.config.json", env=env)
        self.assertEqual(conf["projects"][0]["name"], "示範")

    def test_project_root_tilde(self):
        self.write("proj/TODO.md", "- [ ] [你] 甲（建 10-13）")
        cfg = self.config([{"name": "示範", "root": "~/proj", "todo": ["TODO.md"]}])
        env = {"HOME": str(self.dir), "USERPROFILE": str(self.dir)}
        index = core.build(core.load_config(str(cfg), env=env), TODAY, env=env)
        self.assertEqual(len(index["projects"][0]["items"]), 1)
        self.assertEqual(index["problems"], [])


# ---- PostToolUse 入口 ----

class LintHook(Tmp):
    def setUp(self):
        super().setUp()
        self.todo = self.write("proj/TODO.md", "- [ ] 沒標籤（建 10-13）")
        self.other = self.write("proj/notes.md", "- [ ] 不是 TODO")
        self.config([{"name": "示範", "root": str(self.dir / "proj"), "todo": ["TODO.md"]}])

    def hook(self, path):
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {"file_path": path}}
        return self.run_cli(LINT, stdin=json.dumps(payload).encode("utf-8"))

    def test_warns_on_listed_todo(self):
        r = self.hook(str(self.todo))
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout.decode("utf-8"))
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIn("缺少", ctx)
        self.assertNotIn("decision", out)

    def test_backslash_path(self):
        r = self.hook(str(self.todo).replace("/", "\\") if os.name == "nt" else str(self.todo))
        self.assertIn(b"additionalContext", r.stdout)

    def test_ignores_other_files(self):
        r = self.hook(str(self.other))
        self.assertEqual((r.returncode, r.stdout), (0, b""))

    def test_bad_input_still_exit_0(self):
        r = self.run_cli(LINT, stdin=b"not json")
        self.assertEqual((r.returncode, r.stdout), (0, b""))


# ---- GitHub 選用功能：用假的 gh 執行器，不連網 ----

def fake_gh(calls, fail=None):
    """回傳假的 runner：記下每次的 args；fail 是 {第幾次: 例外}。"""
    def runner(args, timeout):
        calls.append(list(args))
        if fail and len(calls) in fail:
            raise fail[len(calls)]
        if args[0] == "search":
            return [{"number": 3, "title": "搜尋到的 %s" % args[1], "url": "https://github.com/o/r/issues/3",
                     "repository": {"nameWithOwner": "o/r"}, "updatedAt": "2026-10-18T00:00:00Z"}]
        return [{"number": 7, "title": "專案 %s" % args[0], "url": "https://github.com/o/r/%s/7" % args[0],
                 "updatedAt": "2026-10-18T00:00:00Z"}]
    return runner


class GithubTests(Tmp):
    def conf(self, enabled=True, repo="o/r", **gh):
        proj = {"name": "示範", "root": str(self.dir / "proj"), "todo": ["TODO.md"]}
        if repo:
            proj["github"] = repo
        extra = {"github": dict({"enabled": enabled}, **gh)} if enabled is not None else {}
        self.write("proj/TODO.md", "- [ ] [你] 做事（建 10-17）\n")
        return core.load_config(str(self.config([proj], **extra)), {"CLAUDE_CONFIG_DIR": str(self.dir)})

    def test_success_writes_cache_and_index_merges_it(self):
        calls = []
        conf = self.conf()
        self.assertTrue(core.gh_update(conf, self.dir, fake_gh(calls), datetime(2026, 10, 18, 9, 0)))
        self.assertEqual([c[:3] for c in calls[:3]], [["search", "issues", "--assignee=@me"], ["search", "prs", "--assignee=@me"],
                                                      ["search", "prs", "--review-requested=@me"]])
        self.assertIn("--json", calls[0])
        self.assertEqual(calls[3][:5], ["issue", "list", "-R", "o/r", "--state"])
        self.assertEqual(calls[4][:2], ["pr", "list"])
        cache = json.loads((self.dir / "gh_cache.json").read_text(encoding="utf-8"))
        self.assertEqual(cache["fetched"], "2026-10-18T09:00:00")
        self.assertIsNone(cache["error"])
        self.assertEqual(cache["mine"]["assigned"][0], {"number": 3, "title": "搜尋到的 issues",
                         "url": "https://github.com/o/r/issues/3", "updated": "2026-10-18T00:00:00Z", "repo": "o/r"})
        self.assertEqual(cache["repos"]["o/r"]["issues"][0]["title"], "專案 issue")
        idx = core.build(conf, TODAY, {"CLAUDE_CONFIG_DIR": str(self.dir)})
        self.assertEqual(idx["github"]["fetched"], "2026-10-18T09:00:00")
        self.assertEqual(idx["projects"][0]["github"], "o/r")
        self.assertEqual(len(idx["github"]["repos"]["o/r"]["prs"]), 1)
        out = core.render(idx, str(self.dir / "proj"))
        self.assertIn("【GitHub】我的 指派 issue 1、指派 PR 1、等我審 1", out)
        self.assertIn("- 示範｜o/r：issue 1、PR 1", out)

    def test_disabled_never_calls_gh_and_index_has_no_github_key(self):
        calls = []
        for conf in (self.conf(enabled=False), self.conf(enabled=None)):
            self.assertFalse(core.gh_update(conf, self.dir, fake_gh(calls)))
            idx = core.build(conf, TODAY, {"CLAUDE_CONFIG_DIR": str(self.dir)})
            self.assertNotIn("github", idx)
            self.assertNotIn("github", idx["projects"][0])
            self.assertNotIn("【GitHub】", core.render(idx))
        self.assertEqual(calls, [])
        self.assertFalse((self.dir / "gh_cache.json").exists())

    def test_gh_not_found_stops_after_first_call_and_records_error(self):
        calls = []
        err = core.GhError("找不到 gh 指令", True)
        core.gh_update(self.conf(), self.dir, fake_gh(calls, {1: err}))
        self.assertEqual(len(calls), 1)
        cache = json.loads((self.dir / "gh_cache.json").read_text(encoding="utf-8"))
        self.assertEqual(cache["error"], "找不到 gh 指令")
        self.assertEqual(cache["mine"]["assigned"], [])

    def test_real_runner_maps_missing_timeout_nonzero_and_bad_json(self):
        import subprocess as sp
        from unittest import mock

        with mock.patch.object(core.subprocess, "run", side_effect=FileNotFoundError()):
            with self.assertRaises(core.GhError) as c:
                core.run_gh(["x"])
            self.assertTrue(c.exception.fatal)
            self.assertIn("找不到 gh", str(c.exception))
        with mock.patch.object(core.subprocess, "run", side_effect=sp.TimeoutExpired("gh", 10)):
            with self.assertRaises(core.GhError) as c:
                core.run_gh(["x"])
            self.assertTrue(c.exception.fatal)
            self.assertIn("逾時", str(c.exception))
        bad = sp.CompletedProcess(["gh"], 4, b"", "gh auth login\n第二行".encode("utf-8"))
        with mock.patch.object(core.subprocess, "run", return_value=bad):
            with self.assertRaises(core.GhError) as c:
                core.run_gh(["x"])
            self.assertFalse(c.exception.fatal)
            self.assertEqual(str(c.exception), "gh 結束碼 4：gh auth login")
        junk = sp.CompletedProcess(["gh"], 0, b"<html>", b"")
        with mock.patch.object(core.subprocess, "run", return_value=junk):
            with self.assertRaisesRegex(core.GhError, "不是 JSON"):
                core.run_gh(["x"])

    def test_timeout_and_nonzero_through_gh_update_are_recorded(self):
        calls = []
        core.gh_update(self.conf(), self.dir, fake_gh(calls, {1: core.GhError("gh 逾時（10 秒）", True)}))
        self.assertEqual(len(calls), 1)
        self.assertEqual(json.loads((self.dir / "gh_cache.json").read_text(encoding="utf-8"))["error"], "gh 逾時（10 秒）")

    def test_nonzero_exit_on_one_repo_keeps_other_data(self):
        calls = []
        core.gh_update(self.conf(), self.dir, fake_gh(calls, {4: core.GhError("gh 結束碼 1：HTTP 404")}))
        cache = json.loads((self.dir / "gh_cache.json").read_text(encoding="utf-8"))
        self.assertEqual(len(calls), 5)  # 非致命：同一個 repo 的 PR 照樣試
        self.assertEqual(cache["error"], "gh 結束碼 1：HTTP 404")
        self.assertEqual(cache["repos"]["o/r"]["issues"], [])
        self.assertEqual(len(cache["repos"]["o/r"]["prs"]), 1)
        self.assertEqual(len(cache["mine"]["assigned"]), 1)

    def test_fresh_cache_skips_call_and_stale_or_changed_repo_refetches(self):
        conf = self.conf(ttlMinutes=10)
        t0 = datetime(2026, 10, 18, 9, 0)
        calls = []
        self.assertTrue(core.gh_update(conf, self.dir, fake_gh(calls), t0))
        n = len(calls)
        self.assertFalse(core.gh_update(conf, self.dir, fake_gh(calls), t0 + timedelta(minutes=9)))
        self.assertEqual(len(calls), n)
        self.assertTrue(core.gh_update(conf, self.dir, fake_gh(calls), t0 + timedelta(minutes=11)))
        self.assertEqual(len(calls), 2 * n)
        other = self.conf(repo="o/other")
        self.assertTrue(core.gh_update(other, self.dir, fake_gh(calls), t0 + timedelta(minutes=12)))

    def test_error_cache_is_also_fresh_so_a_missing_gh_is_not_retried_every_time(self):
        calls = []
        conf = self.conf()
        t0 = datetime(2026, 10, 18, 9, 0)
        core.gh_update(conf, self.dir, fake_gh(calls, {1: core.GhError("找不到 gh 指令", True)}), t0)
        self.assertFalse(core.gh_update(conf, self.dir, fake_gh(calls), t0 + timedelta(minutes=1)))
        self.assertEqual(len(calls), 1)

    def test_cli_gh_without_gh_installed_is_silent_and_index_stdout_stays_empty(self):
        self.conf()
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(self.dir), PATH=str(self.dir / "empty"), PYTHONIOENCODING="utf-8")
        for cmd in ("gh", "index"):
            r = subprocess.run([sys.executable, CORE, cmd], capture_output=True, env=env, stdin=subprocess.DEVNULL)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, b"", b""))
        cache = json.loads((self.dir / "gh_cache.json").read_text(encoding="utf-8"))
        self.assertEqual(cache["error"], "找不到 gh 指令")
        idx = json.loads((self.dir / "todo_index.json").read_text(encoding="utf-8"))
        self.assertEqual(idx["github"]["error"], "找不到 gh 指令")

    def test_index_without_cache_shows_never_fetched(self):
        conf = self.conf()
        idx = core.build(conf, TODAY, {"CLAUDE_CONFIG_DIR": str(self.dir)})
        self.assertIsNone(idx["github"]["fetched"])
        self.assertIn("【GitHub】還沒抓過", core.render(idx))

    def test_bad_repo_name_and_bad_ttl_fall_back(self):
        self.assertIsNone(core.github_repo("not a repo"))
        self.assertEqual(core.github_repo(" o/r "), "o/r")
        self.assertEqual(core.github_conf({"enabled": "yes", "ttlMinutes": -1}), {"enabled": False, "ttlMinutes": 10})
        self.assertEqual(core.github_conf({"enabled": True, "ttlMinutes": 30}), {"enabled": True, "ttlMinutes": 30})


if __name__ == "__main__":
    unittest.main(verbosity=2)
