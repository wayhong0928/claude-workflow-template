"""把一筆新紀錄插到 session_log.md 頂部，並檢查格式。

為什麼：讓 Claude 每次臨場寫腳本插入，常會把下一筆的標題弄掉，或被 Python 跳脫字元寫壞。
改成固定工具：內容先用 Write 存成暫存 .md，本腳本只負責插入與檢查。

用法：
    python add_session_log.py <session_log.md> <新紀錄.md> [--allow-long]

新紀錄.md 的內容：
    ## YYYY-MM-DD | 主題        （日期後可加括號，例如「YYYY-MM-DD（續）」）
    **做了什麼**：...
    **決定了什麼**：...
    **下一步**：...

檢查（任一不過就不寫入，結束碼 1）：
- 第一行是 `## YYYY-MM-DD...| 主題` 的標題，全文只有這一個 `## ` 標題
- 三段標籤都在
- 沒有控制字元（U+0000–001F 除 Tab／LF／CR、U+0080–009F、孤立的 CR）
- 內文（不含標題、不含空白）600 字內；要超過加 --allow-long
寫入後重讀，確認標題數剛好多 1、新標題是第一筆。保留原檔的換行（CRLF／LF）與 BOM。
"""
import re
import sys
from pathlib import Path

HEAD_RE = re.compile(r"^## \d{4}-\d{2}-\d{2}")
TITLE_RE = re.compile(r"^## \d{4}-\d{2}-\d{2}\S*\s*\|\s*\S")
BAD = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x80-\x9f]|\r(?!\n)")
LABELS = ("**做了什麼**", "**決定了什麼**", "**下一步**")
LIMIT = 600


def fail(msg):
    print(f"不寫入：{msg}")
    sys.exit(1)


def count_heads(lines):
    return sum(1 for ln in lines if HEAD_RE.match(ln))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    allow_long = "--allow-long" in sys.argv
    if len(args) != 2:
        fail("用法：python add_session_log.py <session_log.md> <新紀錄.md> [--allow-long]")
    log_path, entry_path = Path(args[0]), Path(args[1])
    if not log_path.exists():
        fail(f"找不到 {log_path}")

    entry_raw = entry_path.read_bytes().decode("utf-8-sig")
    m = BAD.search(entry_raw)
    if m:
        fail(f"新紀錄含控制字元 U+{ord(m.group()[0]):04X}（第 {entry_raw[:m.start()].count(chr(10)) + 1} 行），多半是 Python 字串裡的 \\b、\\r 被轉義")
    entry = entry_raw.replace("\r\n", "\n").strip("\n")
    elines = entry.split("\n")
    if not TITLE_RE.match(elines[0]):
        fail(f"第一行不是「## YYYY-MM-DD | 主題」：{elines[0][:60]}")
    if count_heads(elines) != 1 or sum(1 for ln in elines if ln.startswith("## ")) != 1:
        fail("新紀錄裡有不只一個 ## 標題")
    missing = [lb for lb in LABELS if lb not in entry]
    if missing:
        fail(f"缺段落：{'、'.join(missing)}")
    body_len = len(re.sub(r"\s", "", "\n".join(elines[1:])))
    if body_len > LIMIT and not allow_long:
        fail(f"內文 {body_len} 字，超過 {LIMIT}；精簡後重跑，或確定要保留就加 --allow-long")

    raw = log_path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    crlf = "\r\n" in text
    lines = text.replace("\r\n", "\n").split("\n")
    before = count_heads(lines)

    idx = next((i for i, ln in enumerate(lines) if HEAD_RE.match(ln)), None)
    if idx is None:  # 還沒有任何紀錄：接在檔頭說明之後
        head = "\n".join(lines).rstrip("\n")
        new_text = (head + "\n\n" if head else "") + entry + "\n"
    else:
        head = "\n".join(lines[:idx]).rstrip("\n")
        rest = "\n".join(lines[idx:])
        new_text = (head + "\n\n" if head else "") + entry + "\n\n" + rest

    out = new_text.replace("\n", "\r\n") if crlf else new_text
    log_path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + out.encode("utf-8"))

    check = log_path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").split("\n")
    after = count_heads(check)
    first = next(ln for ln in check if HEAD_RE.match(ln))
    if after != before + 1 or first != elines[0]:
        print(f"警告：寫入後檢查不符（標題 {before}→{after}，第一筆：{first[:60]}），請用 git diff 檢查")
        sys.exit(2)
    print(f"已插入：{elines[0]}（內文 {body_len} 字；標題 {before}→{after}）")


if __name__ == "__main__":
    main()
