#!/usr/bin/env python3
"""TODO v3 的解析、檢查與開場清單。只用標準庫，Python 3.8 起。

用法：
  python todo_core.py index  [--config 設定檔]        寫出 todo_index.json，stdout 不印任何東西
  python todo_core.py lint   [--config 設定檔] [檔...]  印格式問題，有問題 exit 1
  python todo_core.py render [--config 設定檔]        印開場清單（10,000 字元內）

設定檔預設在 ${CLAUDE_CONFIG_DIR:-~/.claude}/todo.config.json，index 寫在同一個資料夾。
這支腳本只讀 TODO、計畫檔與 session_log，除了 index 不寫、不搬、不改任何檔。
"""
import fnmatch
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

INDEX_VERSION = 1
CONFIG_NAME = "todo.config.json"
INDEX_NAME = "todo_index.json"
DEFAULTS = {"home": None, "dueSoonDays": 7, "staleDays": 14, "maxFirstLine": 60,
            "wslPrefix": "/mnt", "planGlob": "計畫_*.md"}
RENDER_LIMIT = 10000
EXPIRY_SOON_DAYS = 3
WALK_MAX_FILES = 3000
SKIP_DIRS = {"備份", "歸檔", "node_modules", "__pycache__", "out"}

ITEM = re.compile(r"^[-*] \[ \]\s*(.+)$")
LIST_TOP = re.compile(r"^[-*] ")
CHILD = re.compile(r"^\s+[-*] ")
CHILD_TAG = re.compile(r"^\s+[-*] (\[[ xX]\]\s*)?\[(你決定|你|Claude|等外部)\]")
TAG = re.compile(r"^\[(你決定|你|Claude|等外部)\]\s*")
ANY_TAG = re.compile(r"^\[[^\]\s]{1,12}\]")
PAREN = re.compile(r"（([^（）]*)）")
FIELD_NAME = re.compile(r"^(期限|計畫|建|改)(?=[\s\d]|$)")
FIELD_ORDER = ["期限", "計畫", "建", "改"]
DATE = re.compile(r"^(\d{1,2})-(\d{1,2})$")
ANY_DATE = re.compile(r"(?<!\d)(\d{1,2})-(\d{1,2})(?!\d)")
TOUCHED_IN = re.compile(r"(?<!\d)(\d{1,2}-\d{1,2})[^，,；;]{0,6}?改")
MERGED = re.compile(r"併入[^）]*goal", re.I)
MERGED_PAREN = re.compile(r"（併入[^）]*）")
PATH_TOKEN = re.compile(r"[^\s`「」（）()，、；]+\.md")
BAD = re.compile(r"[\x00-\x09\x0b\x0c\x0e-\x1f\x7f-\x9f]")  # 含 Tab；換行不在內

STEP = re.compile(r"^[-*] \[( |x|X)\]\s*(.+)$")
STEP_MAX = 80
ENTRY = re.compile(r"^## (\d{4}-\d{2}-\d{2})")
NEXT_HEAD = re.compile(r"^(?:#{1,6}\s*)?(?:\*\*)?下一步(?:\*\*)?\s*[：:]?\s*(?:\*\*)?\s*(.*)$")
SECTION_HEAD = re.compile(r"^(\*\*[^*]+\*\*|#{1,6} |[^\s\-*#|>][^：:]{0,20}[：:]\s*$)")
FM_DUE = re.compile(r"^到期:\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)
FM_AFTER = re.compile(r"^到期後:\s*(.+?)\s*$", re.M)


# ---------- 路徑 ----------

def is_wsl(env=None):
    env = os.environ if env is None else env
    if env.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False


def to_wsl(path, prefix):
    """E:/x 在 WSL 裡換成 <prefix>/e/x；prefix 寫成 /mnt 或 /mnt/d 都可以。"""
    m = re.match(r"^([A-Za-z]):[\\/]?(.*)$", path)
    if not m:
        return path
    base = (prefix or "/mnt").rstrip("/")
    if re.search(r"/[A-Za-z]$", base):
        base = base[:-2]
    rest = m.group(2).replace("\\", "/")
    return "%s/%s/%s" % (base, m.group(1).lower(), rest) if rest else "%s/%s" % (base, m.group(1).lower())


def expand(path, env=None, wsl=None):
    """展開 ~、統一成正斜線；wsl 有值時把 Windows 磁碟路徑換成 WSL 路徑。"""
    env = os.environ if env is None else env
    p = str(path).strip()
    if p == "~" or p.startswith("~/") or p.startswith("~\\"):
        keys = ("USERPROFILE", "HOME") if os.name == "nt" else ("HOME", "USERPROFILE")
        home = next((env[k] for k in keys if env.get(k)), None) or str(Path.home())
        p = home.rstrip("/\\") + p[1:]
    p = p.replace("\\", "/")
    if wsl is not None:
        p = to_wsl(p, wsl)
    return p


def join(root, rel):
    rel = rel.replace("\\", "/")
    if re.match(r"^([A-Za-z]:)?/", rel) or rel.startswith("~"):
        return rel
    return root.rstrip("/") + "/" + rel


def norm_key(path):
    p = str(path).replace("\\", "/").rstrip("/")
    return p.lower() if os.name == "nt" or re.match(r"^[A-Za-z]:", p) else p


def config_dir(env=None):
    env = os.environ if env is None else env
    d = env.get("CLAUDE_CONFIG_DIR")
    return Path(expand(d, env)) if d else Path(expand("~/.claude", env))


# ---------- 設定檔 ----------

class ConfigMissing(Exception):
    pass


def load_config(path=None, env=None):
    """讀設定檔，補上預設值，專案路徑全部換成絕對路徑（已展開 ~ 與 WSL）。"""
    env = os.environ if env is None else env
    cfg = Path(expand(path, env)) if path else config_dir(env) / CONFIG_NAME
    try:
        raw = json.loads(cfg.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise ConfigMissing(str(cfg))
    conf = dict(DEFAULTS)
    conf.update({k: v for k, v in raw.items() if k != "projects"})
    wsl = conf["wslPrefix"] if is_wsl(env) else None
    projects = []
    for p in raw.get("projects", []):
        root = expand(p.get("root", "."), env, wsl)
        todo = p.get("todo", ["TODO.md"])
        if isinstance(todo, str):
            todo = [todo]
        projects.append({
            "name": str(p.get("name") or Path(root).name),
            "root": root,
            "todo": [expand(join(root, t), env, wsl) for t in todo],
            "log": expand(join(root, p["log"]), env, wsl) if p.get("log") else None,
            "skipDirs": [str(d) for d in p.get("skipDirs", [])],
        })
    conf["projects"] = projects
    conf["_path"] = str(cfg).replace("\\", "/")
    conf["_wsl"] = wsl
    if not conf.get("home") and projects:
        conf["home"] = projects[0]["name"]
    return conf


# ---------- 日期 ----------

def to_date(m, today, future_ok):
    """MM-DD 補上年份：期限可以在未來，建立日與修改日不會在未來。"""
    if not m:
        return None
    try:
        d = date(today.year, int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None
    if future_ok and (d - today).days < -180:
        d = d.replace(year=d.year + 1)
    if not future_ok and d > today:
        d = d.replace(year=d.year - 1)
    return d


def iso(d):
    return d.isoformat() if d else None


# ---------- TODO 第一行 ----------

def problem(file, line, kind, msg):
    return {"file": file, "line": line, "kind": kind, "msg": msg}


def plain(s):
    return s.replace("**", "").replace("`", "").strip()


def parse_line(body, today, max_first_line=60, plan_glob=DEFAULTS["planGlob"]):
    """解析一條頂層 `- [ ]` 的第一行，回傳 (item, [(kind, msg)])。

    先抽欄位名再逐種驗內容；格式壞了也盡量把能讀的值抽出來，不會整條丟掉。
    """
    probs = []
    tag = TAG.match(body)
    if tag:
        who, rest = tag.group(1), body[tag.end():]
    else:
        who, rest = "未分類", body
        bad = ANY_TAG.match(body)
        if bad:
            probs.append(("標籤不合法", "標籤 %s 不合法，只能用 [你]、[你決定]、[Claude]、[等外部]" % bad.group(0)))
        else:
            probs.append(("缺少標籤", "缺少 [誰] 標籤"))

    fields, order, spans = {}, [], []
    for m in PAREN.finditer(rest):
        name = FIELD_NAME.match(m.group(1))
        if not name:
            continue
        key = name.group(1)
        value = m.group(1)[name.end():].strip()
        spans.append(m.span())
        if key in fields:
            probs.append(("欄位重複", "欄位（%s）重複" % key))
            continue
        order.append(key)
        ok = bool(value) if key == "計畫" else bool(DATE.match(value)) and to_date(DATE.match(value), today, True) is not None
        if not ok:
            probs.append(("欄位括號格式不對", "欄位括號格式不對：%s，要寫成（%s %s）這樣" % (
                m.group(0), key, "計畫_第二章.md" if key == "計畫" else "10-24")))
        fields[key] = (value, ok)
    if order != sorted(order, key=FIELD_ORDER.index):
        probs.append(("欄位順序不對", "欄位順序要是 期限、計畫、建、改"))

    stripped = rest
    for a, b in reversed(spans):
        stripped = stripped[:a] + stripped[b:]
    stripped = stripped.strip()
    if len(stripped) > max_first_line:
        probs.append(("第一行太長", "第一行扣掉欄位括號 %d 字，超過 %d" % (len(stripped), max_first_line)))

    def date_of(key, future_ok):
        if key not in fields:
            return None
        value, ok = fields[key]
        m = DATE.match(value) if ok else ANY_DATE.search(value)
        return to_date(m, today, future_ok)

    due = date_of("期限", True)
    born = date_of("建", False)
    touched = date_of("改", False)
    if touched is None and "建" in fields and not fields["建"][1]:
        # v2 寫法「（建 10-13，10-19 改）」：把修改日也抽出來
        t = TOUCHED_IN.search(fields["建"][0])
        if t:
            touched = to_date(DATE.match(t.group(1)), today, False)
    if born is None:
        probs.append(("建立日解析不了", "缺少（建 MM-DD）" if "建" not in fields else "建立日解析不了"))

    refs = []
    if "計畫" in fields and fields["計畫"][0]:
        refs.append(fields["計畫"][0].strip("`"))
    for tok in PATH_TOKEN.findall(rest):
        name = tok.replace("\\", "/").rsplit("/", 1)[-1]
        if fnmatch.fnmatch(name, plan_glob) and tok not in refs:
            refs.append(tok)

    text = MERGED_PAREN.sub("", stripped)
    item = {
        "who": who,
        "text": plain(re.sub(r"\s{2,}", " ", text)),
        "due": iso(due),
        "born": iso(born),
        "touched": iso(touched),
        "planRefs": refs,
        "planField": "計畫" in fields,
        "merged": bool(MERGED.search(rest)),
        "raw": rest,
    }
    return item, probs


def parse_todo_text(text, today, max_first_line=60, path="", plan_glob=DEFAULTS["planGlob"], stale_days=14):
    """整份 TODO：只抽頂層 `- [ ]`，順便檢查子項與控制字元。回傳 (items, problems)。"""
    items, problems = [], []
    has_parent = False
    fence = False
    for n, line in enumerate(text.splitlines(), 1):
        if BAD.search(line):
            problems.append(problem(path, n, "控制字元", "含控制字元（Tab 或路徑裡的 \\t、\\r 被轉義）"))
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = ITEM.match(line)
        if m:
            item, probs = parse_line(m.group(1).strip(), today, max_first_line, plan_glob)
            last = max([d for d in (item["born"], item["touched"]) if d], default=None)
            item["stale"] = bool(last and (today - date.fromisoformat(last)).days > stale_days)
            item["file"] = path
            item["line"] = n
            items.append(item)
            problems += [problem(path, n, k, msg) for k, msg in probs]
            has_parent = True
        elif CHILD.match(line):
            if not has_parent:
                problems.append(problem(path, n, "子項上面沒有母條目", "子項上面沒有母條目"))
            elif CHILD_TAG.match(line):
                problems.append(problem(path, n, "子項不放標籤", "子項不放誰做的標籤，要拍板的事另開一條"))
        elif LIST_TOP.match(line):
            has_parent = True  # 已勾選或一般清單也算母條目
        elif line.strip():
            has_parent = False  # 標題或段落之後的縮排行沒有母條目
    return items, problems


def read_text(path):
    return Path(path).read_text(encoding="utf-8-sig", errors="replace")


def scan_file(path, today, conf):
    try:
        text = read_text(path)
    except OSError:
        return None, [problem(path, 0, "讀不到", "讀不到 %s（設定檔有列，但檔案不存在或打不開）" % path)]
    return parse_todo_text(text, today, conf["maxFirstLine"], path, conf["planGlob"], conf["staleDays"])


# ---------- goal 計畫 ----------

def front_matter(text):
    head = text.lstrip("\ufeff")[:4000]
    if not head.startswith("---"):
        return {}
    end = head.find("\n---", 3)
    block = head[3:end] if end > 0 else ""
    out = {}
    m = FM_DUE.search(block)
    if m:
        out["due"] = m.group(1)
    m = FM_AFTER.search(block)
    if m:
        after = BAD.sub("", m.group(1))
        after = re.sub(r"[*`#>]", "", after).strip()
        out["after"] = after[:60] + ("…" if len(after) > 60 else "")
    return out


def clip(s):
    return s[:STEP_MAX] + "…" if len(s) > STEP_MAX else s


def parse_plan(text):
    """goal 計畫檔：`# 計畫：…` 是標題，`## ` 一節，節內 `- [ ]`／`- [x]` 是步驟。

    程式碼區塊裡的不算；內文沒寫 /goal 的不當 goal 計畫，回傳 None。
    """
    if "/goal" not in text:
        return None
    title, cur, nxt, fence = "", None, None, False
    sections = []
    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence
        if fence:
            continue
        if not title and line.startswith("# "):
            title = re.sub(r"^計畫[：:]\s*", "", plain(line[2:]))
        if line.startswith("## "):
            cur = {"name": plain(line[3:]), "done": 0, "total": 0, "steps": []}
            sections.append(cur)
            continue
        m = STEP.match(line)
        if not m or cur is None:
            continue
        step = clip(plain(m.group(2)).split(" → ")[0])
        done = m.group(1) != " "
        cur["total"] += 1
        cur["steps"].append({"text": step, "isDone": done})
        if done:
            cur["done"] += 1
        elif nxt is None:
            nxt = "%s｜%s" % (re.sub(r"（.*$", "", cur["name"]), step)
    fm = front_matter(text)
    return {"title": title, "due": fm.get("due"), "sections": [s for s in sections if s["total"] > 0], "next": nxt}


def head_of(title):
    return re.sub(r"（.*$", "", title).strip()


# ---------- session_log ----------

def latest_next(text):
    """session_log 依標題日期取最新一筆的「下一步」；加粗與不加粗都認。"""
    lines = text.splitlines()
    entries = [(m.group(1), i) for i, l in enumerate(lines) for m in [ENTRY.match(l)] if m]
    if not entries:
        return None
    newest = max(e[0] for e in entries)
    start = next(i for d, i in entries if d == newest)
    steps, in_next = [], False
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        m = NEXT_HEAD.match(line)
        if m and not line.startswith("-"):
            in_next = True
            if m.group(1).strip():
                steps.append(plain(m.group(1)))
            continue
        if in_next and SECTION_HEAD.match(line):
            break
        s = re.match(r"^[-*] (.+)$", line)
        if in_next and s:
            steps.append(plain(s.group(1)))
    return {"title": plain(lines[start][3:]), "steps": steps}


# ---------- 走訪專案資料夾 ----------

def walk(root, plan_glob, skip=()):
    """找計畫檔（planGlob）與檔頭有「到期」的 .md。只讀前 4 KB，不改任何檔。"""
    plans, expiring = {}, []
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS and d not in skip]
        for f in filenames:
            if not f.lower().endswith(".md"):
                continue
            count += 1
            if count > WALK_MAX_FILES:
                return plans, expiring
            p = (dirpath.replace("\\", "/").rstrip("/") + "/" + f)
            if fnmatch.fnmatch(f, plan_glob):
                plans.setdefault(f, []).append(p)
            try:
                with open(p, "rb") as fh:
                    head = fh.read(4096).decode("utf-8", errors="ignore")
            except OSError:
                continue
            fm = front_matter(head)
            if fm.get("due"):
                expiring.append((p, fm))
    return plans, expiring


def resolve_plan(ref, todo_path, root, plans):
    ref = ref.replace("\\", "/")
    cands = []
    if re.match(r"^([A-Za-z]:)?/", ref):
        cands.append(ref)
    else:
        cands.append(todo_path.rsplit("/", 1)[0] + "/" + ref)
        cands.append(root.rstrip("/") + "/" + ref)
    for c in cands:
        if Path(c).is_file():
            return c
    found = plans.get(ref.rsplit("/", 1)[-1])
    return sorted(found, key=len)[0] if found else None


# ---------- index ----------

def build(conf, today, env=None):
    index = {"version": INDEX_VERSION, "generated": datetime.now().isoformat(timespec="seconds"),
             "today": today.isoformat(), "config": conf.get("_path"), "home": conf.get("home"),
             "dueSoonDays": conf["dueSoonDays"], "projects": [], "goals": [], "expiring": [], "problems": []}
    plan_cache, goal_refs = {}, []
    seen_exp = set()
    for p in conf["projects"]:
        plans, exp = walk(p["root"], conf["planGlob"], p["skipDirs"]) if Path(p["root"]).is_dir() else ({}, [])
        items = []
        for path in p["todo"]:
            got, probs = scan_file(path, today, conf)
            index["problems"] += probs
            for it in got or []:
                it["planPaths"] = []
                for ref in it["planRefs"]:
                    hit = resolve_plan(ref, path, p["root"], plans)
                    if hit:
                        it["planPaths"].append(hit)
                    elif it["planField"] and ref == it["planRefs"][0]:
                        index["problems"].append(problem(path, it["line"], "計畫檔找不到", "計畫檔找不到：%s" % ref))
                items.append(it)
        nxt = None
        if p["log"]:
            try:
                nxt = latest_next(read_text(p["log"]))
            except OSError:
                nxt = None
        index["projects"].append({"name": p["name"], "root": p["root"], "todo": p["todo"], "log": p["log"],
                                  "items": items, "next": nxt})
        for path, fm in exp:
            if norm_key(path) in seen_exp:
                continue
            seen_exp.add(norm_key(path))
            left = (date.fromisoformat(fm["due"]) - today).days
            if left <= EXPIRY_SOON_DAYS:
                index["expiring"].append({"project": p["name"], "path": path,
                                          "rel": path[len(p["root"].rstrip("/")) + 1:], "due": fm["due"],
                                          "left": left, "after": fm.get("after")})
        for it in items:
            for pp in it["planPaths"]:
                goal_refs.append((p["name"], it, pp))

    # 未完成條目引用、內文寫了 /goal、還有沒勾步驟的計畫才算進行中的 goal
    goals = {}
    for project, it, pp in goal_refs:
        key = norm_key(pp)
        if key not in plan_cache:
            try:
                body = parse_plan(read_text(pp))
            except OSError:
                body = None
            plan_cache[key] = body if body and any(s["done"] < s["total"] for s in body["sections"]) else None
        body = plan_cache[key]
        if body is None:
            continue
        g = goals.get(key)
        if g is None:
            g = goals[key] = {"id": key, "project": project, "file": pp.rsplit("/", 1)[-1], "path": pp,
                              "title": body["title"], "due": body["due"], "sections": body["sections"],
                              "next": body["next"]}
        if not body["due"] and it["due"] and (g["due"] is None or it["due"] < g["due"]):
            g["due"] = it["due"]  # 檔頭沒寫到期時，取引用它的條目裡最近的期限
    for proj in index["projects"]:
        for it in proj["items"]:
            hit = next((goals[norm_key(pp)]["id"] for pp in it["planPaths"] if norm_key(pp) in goals), None)
            if not hit and it["merged"]:
                hit = next((g["id"] for g in goals.values() if head_of(g["title"]) and head_of(g["title"]) in it["raw"]), None)
            it["goal"] = hit
            for k in ("planRefs", "planField", "planPaths", "raw"):
                it.pop(k, None)
    index["goals"] = sorted(goals.values(), key=lambda g: g["due"] or "9999")
    index["expiring"].sort(key=lambda e: e["left"])
    return index


def write_index(index, base):
    base.mkdir(parents=True, exist_ok=True)
    target = base / INDEX_NAME
    tmp = base / (INDEX_NAME + ".tmp")
    data = json.dumps(index, ensure_ascii=False, indent=1)
    tmp.write_text(data, encoding="utf-8")
    for _ in range(5):
        try:
            os.replace(str(tmp), str(target))
            return
        except OSError:
            pass
    target.write_text(data, encoding="utf-8")
    try:
        tmp.unlink()
    except OSError:
        pass


# ---------- 開場清單 ----------

GROUPS = [("你決定", "待你決定"), ("你", "你"), ("等外部", "等外部"), ("Claude", "Claude"), ("未分類", "未分類")]


def left_of(due, today):
    return (date.fromisoformat(due) - today).days if due else None


def mark(it, today):
    left = left_of(it["due"], today)
    if left is not None:
        tail = "已過期 %d 天" % -left if left < 0 else "剩 %d 天" % left
        return "［期限 %s，%s%s］" % (it["due"][5:], tail, "，待驗現況" if it["stale"] else "")
    return "［待驗現況］" if it["stale"] else ""


def project_of(cwd, projects):
    c = norm_key(cwd or "")
    best = None
    for p in projects:
        r = norm_key(p["root"])
        if c and (c == r or c.startswith(r + "/")) and (best is None or len(r) > len(norm_key(best["root"]))):
            best = p
    return best


def render(index, cwd=None):
    today = date.fromisoformat(index["today"])
    soon_days = index.get("dueSoonDays", 7)
    projects = index["projects"]
    cur = project_of(cwd, projects) or next((p for p in projects if p["name"] == index.get("home")), None) \
        or (projects[0] if projects else None)
    # 寫了「併入 … goal」又對到計畫的條目，只列在那份 goal 計畫底下，不在各專案重複列（跟側欄一致）
    def own(p):
        return [i for i in p["items"] if not (i.get("goal") and i.get("merged"))]
    out = ["=== 待辦（todo plugin）：%s 全列，依「誰要做」分組；其他專案只列條數與 %d 天內到期的 ===" % (
        cur["name"] if cur else "沒有專案", soon_days)]
    if cur:
        items = own(cur)
        moved = len(cur["items"]) - len(items)
        out.append("【%s】未完成 %d 條%s" % (cur["name"], len(items), "（另 %d 條已併入 goal 計畫，列在下面）" % moved if moved else ""))
        for who, label in GROUPS:
            group = [i for i in items if i["who"] == who]
            if not group:
                continue
            group.sort(key=lambda i: (i["due"] is None, i["due"] or ""))
            out.append("  〔%s〕" % label)
            out += ["- %s%s" % (i["text"], mark(i, today)) for i in group]
    goals = index.get("goals", [])
    if goals:
        out += ["", "【goal 計畫】進行中 %d 份" % len(goals)]
        for g in goals:
            done = sum(s["done"] for s in g["sections"])
            total = sum(s["total"] for s in g["sections"])
            due = "" if not g["due"] else "（到期 %s）" % g["due"][5:]
            out.append("- %s%s：已勾 %d/%d 步%s" % (g["title"], due, done, total,
                                                   "，接著做：" + g["next"] if g["next"] else ""))
            merged = [(p["name"], i) for p in projects for i in p["items"] if i.get("goal") == g["id"] and i.get("merged")]
            out += ["  - 併入：%s｜%s%s" % (n, i["text"], mark(i, today)) for n, i in merged]
    exp = index.get("expiring", [])
    if exp:
        out += ["", "【有效期檔案】3 天內到期或已過期（要延後就改檔頭的到期日；這裡只提醒，不搬檔）："]
        for name, rows in (("已過期", [e for e in exp if e["left"] < 0]), ("3 天內到期", [e for e in exp if e["left"] >= 0])):
            if rows:
                out.append("  〔%s〕" % name)
                for e in rows:
                    left = "過 %d 天" % -e["left"] if e["left"] < 0 else "剩 %d 天" % e["left"]
                    after = "；到期後：「%s」" % e["after"] if e.get("after") else ""
                    out.append("- %s｜%s（到期 %s，%s）%s" % (e["project"], e["rel"], e["due"][5:], left, after))
    others = [p for p in projects if p is not cur and own(p)]
    if others:
        out += ["", "【其他專案】未完成條數：" + "、".join("%s %d" % (p["name"], len(own(p))) for p in others)
                + "；%d 天內到期或已過期：" % soon_days]
        soon = [(p["name"], i) for p in others for i in own(p)
                if i["due"] and left_of(i["due"], today) <= soon_days]
        soon.sort(key=lambda x: x[1]["due"])
        out += ["- %s［%s］%s%s" % (n, dict(GROUPS).get(i["who"], i["who"]), i["text"], mark(i, today)) for n, i in soon] or ["- 沒有"]
    probs = index.get("problems", [])
    if probs:
        out += ["", "【TODO 格式】%d 條問題，跑 `python <plugin>/scripts/todo_core.py lint` 看明細" % len(probs)]
    return cap("\n".join(out))


def cap(text, limit=RENDER_LIMIT):
    if len(text) <= limit:
        return text
    lines = text.split("\n")
    kept, size = [], 0
    room = limit - 120
    for line in lines:
        if size + len(line) + 1 > room:
            break
        kept.append(line)
        size += len(line) + 1
    note = "…（超過 10,000 字元，後面 %d 行省略；完整清單看 /todo 或各專案的 TODO 檔）" % (len(lines) - len(kept))
    return "\n".join(kept + [note])


# ---------- 指令列 ----------

def emit(text):
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()


def parse_args(argv):
    cmd = argv[0] if argv else "index"
    rest, config, files = argv[1:], None, []
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--config" and i + 1 < len(rest):
            config = rest[i + 1]
            i += 2
            continue
        if config is None and a.lower().endswith(".json"):
            config = a
        else:
            files.append(a)
        i += 1
    return cmd, config, files


def lint_main(config, files):
    today = date.today()
    try:
        conf = load_config(config)
    except ConfigMissing:
        if not files:
            emit("找不到設定檔 %s\n" % (config or config_dir() / CONFIG_NAME))
            return 1
        conf = dict(DEFAULTS)
    except ValueError as e:
        emit("設定檔不是合法的 JSON：%s\n" % e)
        return 1
    problems = []
    if files:
        for f in files:
            problems += scan_file(expand(f), today, conf)[1]
    else:
        problems = build(conf, today)["problems"]
    lines = ["%s:%d %s" % (p["file"], p["line"], p["msg"]) for p in problems]
    emit("\n".join(lines + ["共 %d 條問題" % len(problems)]) + "\n" if problems else "0 條問題\n")
    return 1 if problems else 0


def main(argv=None):
    cmd, config, files = parse_args(sys.argv[1:] if argv is None else argv)
    if cmd == "lint":
        return lint_main(config, files)
    if cmd == "render":
        cwd = None
        try:
            if not sys.stdin.isatty():
                data = sys.stdin.read()
                cwd = json.loads(data).get("cwd") if data.strip() else None
        except (ValueError, OSError, AttributeError):
            cwd = None
        try:
            conf = load_config(config)
        except ConfigMissing as e:
            emit("todo plugin：還沒有設定檔 %s。打 /workflow-kit:setup 產生，或照 todo/README.md 手寫一份。\n" % e)
            return 0
        except ValueError as e:
            emit("todo plugin：設定檔不是合法的 JSON（%s），開場清單先略過。\n" % e)
            return 0
        emit(render(build(conf, date.today()), cwd or os.getcwd()) + "\n")
        return 0
    if cmd == "index":
        # stdout 一個字都不印：UserPromptSubmit 的 stdout 會進對話。失敗也 exit 0，不擋使用者送出。
        try:
            conf = load_config(config)
            write_index(build(conf, date.today()), config_dir())
        except ConfigMissing:
            pass
        except Exception as e:  # noqa: BLE001
            sys.stderr.write("todo_core index 失敗：%s\n" % e)
        return 0
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
