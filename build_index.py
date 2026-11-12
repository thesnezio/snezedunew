"""Rebuild lessons.json, search.json and the data embedded in index.html from the lesson folders.

Run:  python build_index.py      (or double-click "Rebuild index.bat")
Lesson files are only read, never written. For each lesson the build reads the visible text of the
plan and worksheet (scripts, styles, toolbars and base64 images removed) and extracts:
topic, approach, objective, key words, key point and the stages with their steps and minutes.
lessons.json holds that summary; search.json holds each worksheet's full text for searching.
Both are embedded in index.html so the platform works offline.
"""
import datetime
import hashlib
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEVELS = {"1st BAC": "bac", "Common Core": "cc"}
PLAN, WS = "Lesson Plan.html", "Worksheet.html"
MINUTES = 55
ECRIF = ["Encounter", "Clarify", "Remember", "Internalize", "Fluently use"]
ECRIF_SKILLS = {"Vocabulary", "Grammar", "Functions"}
BLOCKS = {"data": "lessons.json", "search": "search.json"}  # <script id="..."> in index.html -> file


# ---------- visible text ----------

class _Text(HTMLParser):
    """Collect visible text, one line per block element, skipping scripts, controls and .no-print toolbars."""
    SKIP = {"script", "style", "noscript", "template", "head", "button", "select", "option", "svg"}
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
    BLOCK = {"p", "div", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "section", "header",
             "footer", "table", "ul", "ol", "article", "br", "label", "figcaption"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.out, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK:
            self.out.append("\n")
        if tag in self.VOID:
            return
        cls = (dict(attrs).get("class") or "").split()
        skip = tag in self.SKIP or "no-print" in cls or "fmtbar" in cls
        self.stack.append((tag, skip))
        self.skip += skip

    def handle_endtag(self, tag):
        if tag in self.BLOCK:
            self.out.append("\n")
        if all(t != tag for t, _ in self.stack):
            return
        while self.stack:
            t, skip = self.stack.pop()
            self.skip -= skip
            if t == tag:
                break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def read_html(path):
    """Return (<title>, visible text lines) of an HTML file."""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"<title>(.*?)</title>", raw, re.S | re.I)
    raw = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", " ", raw)
    raw = re.sub(r"data:[^\"')\s]{200,}", "", raw)  # base64 images
    p = _Text()
    p.feed(raw)
    p.close()
    lines = [re.sub(r"\s+", " ", x).strip() for x in "".join(p.out).split("\n")]
    return (html.unescape(m.group(1)).strip() if m else ""), [x for x in lines if x]


def text_hash(lines):
    return hashlib.md5("\n".join(lines).encode("utf-8")).hexdigest()


# ---------- content extraction ----------

TIME = re.compile(r"(\d+)(?:\s*[–-]\s*(\d+))?\s*min\b.*", re.I)


def parse_plan(lines):
    """Objective, duration and stages from a plan. A stage starts with: mark, name, 'Procedure / steps'."""
    starts = [i for i in range(len(lines) - 2) if lines[i + 2] == "Procedure / steps"]
    head = lines[:starts[0]] if starts else lines
    obj = ""
    for i, x in enumerate(head):
        if x.startswith("Objective"):
            obj = " ".join([x[len("Objective"):].strip()] + head[i + 1:]).strip()
            break
    m = re.search(r"Duration\s*(\d+)\s*min", " ".join(head))
    stages = []
    for n, s in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        stage = {"mark": lines[s], "name": lines[s + 1], "min": 0, "max": 0, "steps": []}
        for x in lines[s + 3:end]:
            if x == "Timing":
                continue
            t = TIME.fullmatch(x)
            if t:
                stage["min"] += int(t[1])
                stage["max"] += int(t[2] or t[1])
            elif not re.search(r"=\s*\d+\s*min", x):  # skip footers like "Pre 10 + ... = 55 min"
                stage["steps"].append(re.sub(r"^[➢•\-–]\s*", "", x))
        stages.append(stage)
    return obj, (int(m[1]) if m else None), stages


def parse_worksheet(title, lines, skill):
    """Topic, approach, key words and key point from a worksheet."""
    topic, approach = "", ""
    m = re.match(r".*?\b" + re.escape(skill) + r"\b[^:]*:\s*(.+)$", title, re.I)
    if m:
        topic = m[1]
    a = re.search(r"\(([^()]*)\)\s*$", topic or title)
    if a:
        approach = a[1]
        topic = topic[:a.start()].strip() if topic else topic
    if not topic and len(lines) > 1 and lines[0].lower().startswith(skill.lower()):
        topic = lines[1]  # heading under the skill label, e.g. "Society: generations & social problems"
    words = []
    for box in re.findall(r"\(\s*([^()]+?\s-\s[^()]+?)\s*\)", "\n".join(lines)):
        for w in box.split(" - "):
            w = w.strip()
            if w and len(w) <= 40 and w.lower() not in (x.lower() for x in words):
                words.append(w)
    point = ""
    for i, x in enumerate(lines):
        if x.startswith("Remember") and i + 1 < len(lines):
            rest = x[len("Remember"):].strip(" :")
            point = rest if len(rest) > 25 else lines[i + 1]  # a short label like "Remember: words that go together" -> next line
            if len(point) >= 15:  # skip "Remember" cells in the answer key's stage table
                break
            point = ""
    return topic, approach, words, point


def approach_from(stages):
    names = " ".join(s["name"].lower() for s in stages)
    if "encounter" in names:
        return "ECRIF"
    if "pre-reading" in names:
        return "PDP"
    if "guided writing" in names or "model" in names:
        return "Product"
    if "drafting" in names or "pre-writing" in names:
        return "Process"
    return ""


# ---------- scan ----------

def letters(name):
    """Sorted letters of a file name, so 'Lesosn Plan.html' matches 'Lesson Plan.html'."""
    return "".join(sorted(re.sub(r"[^a-z]", "", Path(name).stem.lower())))


def scan():
    lessons, search, texts = [], {}, {}
    for level, prefix in LEVELS.items():
        units = [(int(m[1]), m[2], d) for d in (ROOT / level).iterdir()
                 if d.is_dir() and (m := re.fullmatch(r"Unit (\d+) - (.+)", d.name))]
        for unit, unit_name, udir in sorted(units):
            rows = [(int(m[1]), m[2], d) for d in udir.iterdir()
                    if d.is_dir() and (m := re.fullmatch(r"(\d+) (.+)", d.name))]
            for no, label, ldir in sorted(rows):
                skill, _, part = label.partition(" - ")
                lid = f"{prefix}-u{unit}-l{no}"
                lesson = {
                    "id": lid, "level": level, "unit": unit,
                    "unitName": unit_name, "unitDir": udir.name, "no": no, "dir": ldir.name,
                    "skill": skill, "part": part, "label": label,
                    "plan": PLAN if (ldir / PLAN).is_file() else None,
                    "ws": WS if (ldir / WS).is_file() else None,
                    "flags": [],
                }
                for f in sorted(p.name for p in ldir.glob("*.html")):
                    for good, key in ((PLAN, "plan"), (WS, "ws")):
                        if f != good and letters(f) == letters(good):
                            if lesson[key] is None:
                                lesson[key] = f
                                msg = f"The file is misspelled “{f}”. Rename it to “{good}”."
                            else:
                                msg = f"A misspelled copy “{f}” is still in this folder next to “{good}”. Delete the misspelled one."
                            lesson["flags"].append({"sev": "warn", "type": "filename", "msg": msg})

                ptitle, plines = read_html(ldir / lesson["plan"]) if lesson["plan"] else ("", [])
                wtitle, wlines = read_html(ldir / lesson["ws"]) if lesson["ws"] else ("", [])
                objective, duration, stages = parse_plan(plines)
                topic, approach, words, point = parse_worksheet(wtitle or ptitle, wlines, skill)
                lesson.update({
                    "title": wtitle or ptitle, "topic": topic, "approach": approach or approach_from(stages),
                    "objective": objective, "words": words, "point": point,
                    "minutes": [sum(s["min"] for s in stages), sum(s["max"] for s in stages)],
                    "stages": stages,
                })
                check_timing(lesson, duration, bool(plines))
                lessons.append(lesson)
                search[lid] = " ".join(wlines)
                texts[lid] = {"plan": text_hash(plines) if plines else None, "ws": text_hash(wlines) if wlines else None}
    return lessons, search, texts


# ---------- health checks ----------

def check_timing(l, duration, has_plan):
    if not has_plan:
        return
    add = lambda sev, kind, msg: l["flags"].append({"sev": sev, "type": kind, "msg": msg})
    lo, hi = l["minutes"]
    if not l["stages"]:
        add("warn", "plan", "No stages with timings were found in the plan.")
        return
    if hi == 0:
        add("warn", "timing", "The plan has no timings.")
    elif not lo <= MINUTES <= hi:
        total = f"{lo} min" if lo == hi else f"{lo}–{hi} min"
        add("bad" if abs((lo if lo > MINUTES else hi) - MINUTES) > 5 else "warn", "timing",
            f"Stage timings add up to {total}, not {MINUTES} min.")
    if duration is not None and duration != MINUTES:
        add("warn", "timing", f"The plan header says {duration} min, not {MINUTES} min.")
    untimed = [s["name"] for s in l["stages"] if s["max"] == 0]
    if untimed and hi:
        add("warn", "timing", "No timing for: " + ", ".join(untimed) + ".")
    if not l["objective"]:
        add("warn", "plan", "The plan has no objective.")
    if l["skill"] in ECRIF_SKILLS:
        names = [s["name"].lower() for s in l["stages"]]
        missing = [p for p in ECRIF if not any(n.startswith(p.lower()[:6]) for n in names)]
        if missing:
            add("warn", "plan", "ECRIF stage missing: " + ", ".join(missing) + ".")


def flag_duplicates(lessons, texts):
    """Flag lessons whose plan and/or worksheet text is identical to another lesson's."""
    by_id = {l["id"]: l for l in lessons}
    groups = {}
    for l in lessons:
        for key in ("plan", "ws"):
            if texts[l["id"]][key]:
                groups.setdefault((key, texts[l["id"]][key]), []).append(l["id"])
    copies = {}  # lesson id -> {kind: original lesson id}
    for (key, _), ids in groups.items():
        if len(ids) < 2:
            continue
        # The original is the lesson whose worksheet title names its own skill.
        own = [i for i in ids if by_id[i]["skill"].lower() in by_id[i]["title"].lower()]
        original = own[0] if len(own) == 1 else None
        for i in ids:
            if i != original:
                copies.setdefault(i, {})[key] = original or next(j for j in ids if j != i)
    for i, kinds in copies.items():
        l = by_id[i]
        for orig in dict.fromkeys(kinds.values()):
            o = by_id[orig]
            what = " and ".join(n for k, n in (("plan", "lesson plan"), ("ws", "worksheet")) if kinds.get(k) == orig)
            where = o["label"] if o["level"] == l["level"] and o["unit"] == l["unit"] else f'{o["level"]} Unit {o["unit"]} {o["label"]}'
            src = f"“{o['title']}”, the {where} lesson" if o["title"] else f"the {where} lesson"
            both = " and " in what
            verb = "are identical copies" if both else "is an identical copy"
            missing = "lesson" if both else what
            l["flags"].append({"sev": "bad", "type": "duplicate", "msg": f"This {what} {verb} of {src}. The real {l['label']} {missing} for this unit is missing."})


def resources():
    res = []
    for level in LEVELS:
        for pdf in sorted((ROOT / level).glob("*.pdf")):
            res.append({"group": level, "name": f"{pdf.stem} (book)", "path": f"{level}/{pdf.name}"})
    for level in LEVELS:
        for pdf in sorted((ROOT / level / "Homework").glob("*.pdf")):
            name = re.sub(r"\s+", " ", re.sub(r"\s*—\s*Homework\s*", ": ", pdf.stem)).strip()
            res.append({"group": "Homework", "name": name, "path": f"{level}/Homework/{pdf.name}"})
    return res


# ---------- write ----------

def embed(page, block_id, data):
    """Replace (or add, after the data block) <script id=block_id type=application/json> in index.html."""
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    tag = re.compile(r'(<script id="' + block_id + r'" type="application/json">)(.*?)(</script>)', re.S)
    if tag.search(page):
        return tag.sub(lambda m: m[1] + blob + m[3], page, count=1)
    anchor = re.search(r'<script id="data" type="application/json">.*?</script>', page, re.S)
    if not anchor:
        raise SystemExit('index.html has no <script id="data" type="application/json"> block; nothing written to it.')
    new = f'\n<script id="{block_id}" type="application/json">{blob}</script>'
    return page[:anchor.end()] + new + page[anchor.end():]


def main(quiet=False):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    lessons, search, texts = scan()
    flag_duplicates(lessons, texts)
    data = {"levels": list(LEVELS), "lessons": lessons, "resources": resources(),
            "built": datetime.date.today().isoformat()}

    out = {"data": data, "search": search}
    for block_id, name in BLOCKS.items():
        (ROOT / name).write_text(json.dumps(out[block_id], indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")

    index = ROOT / "index.html"
    page = index.read_text(encoding="utf-8")
    for block_id in BLOCKS:
        page = embed(page, block_id, out[block_id])
    index.write_text(page, encoding="utf-8", newline="\n")

    if quiet:
        return
    for level in LEVELS:
        n = [l for l in lessons if l["level"] == level]
        print(f"{level}: {len({l['unit'] for l in n})} units, {len(n)} lessons")
    print(f"Resources: {len(data['resources'])}")
    flags = [(l, f) for l in lessons for f in l["flags"]]
    print(f"Health check: {len(flags)} issue(s)")
    for l, f in flags:
        print(f"  [{f['sev']}] {l['id']}: {f['msg']}")
    print("lessons.json, search.json and index.html rebuilt.")


if __name__ == "__main__":
    main()
