"""Student copies of the worksheets: filled in, colour-coded, static (for SnezEdu's student page).

    python build_student_worksheets.py covered [--db library.db …] [--jobs 4]
                                                         the usual way: copies for the lessons some class has
                                                         covered, new or changed since their copy (run by itself
                                                         every 30 minutes by the app on this computer, and by
                                                         Put online.bat with the online database too)
    python build_student_worksheets.py extract [ids…]     the blanks of each worksheet, numbered (to _students/work/)
    python build_student_worksheets.py answer [--jobs 4] [--redo] [ids…]
                                                         Claude Code solves them from the worksheet itself (the
                                                         answer key on page 3 only helps where it still matches:
                                                         the teacher may change a worksheet and keep the old key)
                                                         into _students/answers/<id>.json
    python build_student_worksheets.py build [ids…]       writes _students/<id>.html

A student copy is pages 1 and 2 of the worksheet (page 3, the teacher's answer key, is left out), with every blank
filled in, the editing bars, buttons and scripts removed, nothing editable, and pages that grow so every answer shows.
Answers are in the lesson's skill colour; in Grammar and Functions lessons the target language is colour-coded
(subject, verb, helping verb, key words, expressions), with a colour key on page 1.
A copy is made only once a class has covered the lesson, so later changes to a lesson are in its copy; a lesson changed
after its copy was made is done again. Until its filled copy exists, a covered lesson shows a static copy without the
answers (_students/plain/). The lesson files themselves are only read, never changed.
"""
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_students"
WORK, ANSWERS, PLAIN = OUT / "work", OUT / "answers", OUT / "plain"
VERSION = 3   # 2: Grammar and Functions answers carry the colour tags; 3: answers solved from the worksheet itself
#               (the answer key only helps): older answers are done again when their lesson is covered
COLOUR_SKILLS = {"Grammar", "Functions"}
# the target language's colours (Grammar and Functions): tag → (class, colour, name in the colour key)
TAGS = {"s": ("Subject", "#1d4ed8"), "a": ("Helping verb / negative", "#7c3aed"), "v": ("Verb", "#dc2626"),
        "k": ("Key words", "#15803d"), "f": ("Expressions", "#c2185b")}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
BLOCK = {"div", "section", "p", "li", "ul", "ol", "tr", "table", "thead", "tbody", "h1", "h2", "h3", "h4", "h5", "h6",
         "header", "footer", "figure", "figcaption", "label", "blockquote"}
# the controls of the editable worksheet: never in a student copy
CONTROL_CLASSES = {"no-print", "fmtbar", "linectl", "tblctl", "imgbtn", "frmbtn", "imgdel", "drophint", "toolbar", "lctl"}
# the answers' colour: the lesson's skill, a shade darker than on the platform so small text stays readable
SKILL_INK = {"Vocabulary": ("#0b7a6e", "#e3f5f2"), "Functions": ("#5b3fd6", "#ece8ff"), "Reading": ("#1d56c8", "#e6eeff"),
             "Grammar": ("#b85a06", "#fff0e0"), "Writing": ("#b8235f", "#fde8f0")}


# ---------- a small HTML tree that writes back exactly what it read (raw tags, entities kept)
class El:
    def __init__(self, tag, raw, attrs):
        self.tag, self.raw, self.attrs, self.kids, self.end, self.parent = tag, raw, dict(attrs), [], "", None

    def cls(self):
        return set((self.attrs.get("class") or "").split())

    def style(self):
        return (self.attrs.get("style") or "").replace(" ", "").lower()


class Raw:
    def __init__(self, s):
        self.raw, self.parent = s, None


class Tree(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.root = El("#root", "", {})
        self.stack = [self.root]
        self.feed(text)
        self.close()

    def add(self, node):
        node.parent = self.stack[-1]
        self.stack[-1].kids.append(node)

    def handle_starttag(self, tag, attrs):
        el = El(tag, self.get_starttag_text(), attrs)
        self.add(el)
        if tag not in VOID:
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        self.add(El(tag, self.get_starttag_text(), attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack[i].end = f"</{tag}>"
                del self.stack[i:]
                return
        # a stray end tag: dropped

    def handle_data(self, d):
        self.add(Raw(d))

    def handle_entityref(self, name):
        self.add(Raw(f"&{name};"))

    def handle_charref(self, name):
        self.add(Raw(f"&#{name};"))

    def handle_comment(self, d):
        self.add(Raw(f"<!--{d}-->"))

    def handle_decl(self, d):
        self.add(Raw(f"<!{d}>"))

    def unknown_decl(self, d):
        self.add(Raw(f"<![{d}]>"))

    def handle_pi(self, d):
        self.add(Raw(f"<?{d}>"))


def out(node):
    if isinstance(node, Raw):
        return node.raw
    return node.raw + "".join(out(k) for k in node.kids) + node.end


def walk(node):
    yield node
    if isinstance(node, El):
        for k in node.kids:
            yield from walk(k)


def text(node):
    if isinstance(node, Raw):
        return "" if node.raw.startswith("<") else html.unescape(node.raw)
    if node.tag in ("script", "style"):
        return ""
    return "".join(text(k) for k in node.kids)


LEADERS = re.compile(r"_{3,}|\.{4,}|…{2,}")   # typed blanks: ______ or ........


def empty(el):
    """No visible text (typed ____ lines count as empty) and nothing to see inside: a blank to write on."""
    if LEADERS.sub("", text(el)).replace("\xa0", "").strip():
        return False
    return not any(isinstance(n, El) and (n.tag in ("img", "svg", "input", "textarea", "video", "canvas") or "imgslot" in n.cls()
                                          or "background-image" in n.style()) for n in walk(el) if n is not el)


def pages(tree):
    return [n for n in walk(tree.root) if isinstance(n, El) and n.tag == "section" and "page" in n.cls()]


def strip_controls(tree):
    """Remove the editing bars, buttons, scripts and file pickers; make everything static."""
    def keep(n):
        if not isinstance(n, El):
            return True
        if n.tag in ("script", "button", "select", "textarea") or (n.tag == "input" and n.attrs.get("type") == "file"):
            return False
        return not (n.cls() & CONTROL_CLASSES or n.attrs.get("id") == "framePanel")
    for n in list(walk(tree.root)):
        if isinstance(n, El):
            n.kids = [k for k in n.kids if keep(k)]
            n.raw = re.sub(r'\s+(contenteditable|spellcheck|onclick|onchange|oninput|draggable)="[^"]*"', "", n.raw)
            if n.tag == "body":
                n.raw = re.sub(r'\s+style="[^"]*"', "", n.raw)


def split_typed_blanks(page):
    """A ______ typed inside a sentence becomes its own blank (an underlined gap). A line made only of ____ stays one
    blank as a whole (see empty())."""
    for el in [n for n in walk(page) if isinstance(n, El)]:
        if el.tag in ("script", "style") or not LEADERS.sub("", text(el)).replace("\xa0", "").strip():
            continue
        kids = []
        for k in el.kids:
            if isinstance(k, Raw) and not k.raw.startswith("<") and LEADERS.search(k.raw):
                for part in re.split(r"(_{3,}|\.{4,}|…{2,})", k.raw):
                    if not part:
                        continue
                    if LEADERS.fullmatch(part):
                        g = El("span", '<span class="gap typed">', {"class": "gap typed"})
                        g.end, g.kids, g.parent = "</span>", [], el
                        kids.append(g)
                    else:
                        r = Raw(part)
                        r.parent = el
                        kids.append(r)
            else:
                kids.append(k)
        el.kids = kids


def find_blanks(page):
    """The places to write in, in reading order: underlined gaps, empty table cells, writing lines and boxes."""
    found = []

    def visit(el):
        inner = False
        for k in el.kids:
            if isinstance(k, El) and visit(k):
                inner = True
        if inner or el.tag not in ("span", "div", "td", "p", "li", "b", "i", "u"):
            return inner
        st, cl = el.style(), el.cls()
        if not empty(el) or "height:0" in st or "imgslot" in cl:
            return False
        line = "border-bottom" in st or "gap" in cl or "ruled" in cl or "box" in cl or "min-height" in st or "border:" in st
        cell = el.tag == "td" and el.parent is not None and any(isinstance(a, El) and a.tag == "tbody" for a in ancestors(el))
        if line or cell:
            found.append(el)
            return True
        return False
    visit(page)
    return found


def ancestors(el):
    p = el.parent
    while p is not None:
        yield p
        p = p.parent


def render(node, ids):
    """Pages as plain text for Claude: one line per block, table cells split by |, each blank as [[n]]."""
    if isinstance(node, Raw):
        return "" if node.raw.startswith("<") else html.unescape(node.raw)
    if node in ids:
        return f" [[{ids[node]}]] "
    if node.tag in ("script", "style") or (node.tag == "footer"):
        return ""
    if node.tag == "br":
        return "\n"
    inner = "".join(render(k, ids) for k in node.kids)
    if node.tag in ("td", "th"):
        return " | " + inner.strip()
    if node.tag in BLOCK:
        return "\n" + inner + "\n"
    return inner


def tidy(s):
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n[ \n]*", "\n", s)
    return s.strip()


def lessons(ids=None):
    j = json.loads((ROOT / "lessons.json").read_text(encoding="utf-8"))
    out_ = []
    for l in j["lessons"]:
        f = ROOT / l["level"] / l["unitDir"] / l["dir"] / (l["ws"] or "")
        if l["ws"] and f.is_file() and (not ids or l["id"] in ids):
            out_.append((l, f))
    return out_


def parse(f):
    tree = Tree(f.read_text(encoding="utf-8", errors="replace"))
    strip_controls(tree)
    ps = pages(tree)
    key = next((p for p in ps if re.search(r"answer key|teacher copy", text(p), re.I)), ps[2] if len(ps) > 2 else None)
    keep = [p for p in ps if p is not key][:2]
    for p in keep:
        split_typed_blanks(p)
    blanks = [b for p in keep for b in find_blanks(p)]
    return tree, ps, key, keep, blanks


# ---------- 1. extract
def extract(l, f):
    tree, ps, key, keep, blanks = parse(f)
    ids = {b: i + 1 for i, b in enumerate(blanks)}
    body = "\n\n".join(f"===== PAGE {n + 1} =====\n" + tidy(render(p, ids)) for n, p in enumerate(keep))
    keytext = tidy(render(key, {})) if key else "(no answer key)"
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / f"{l['id']}.txt").write_text(f"{body}\n\n===== TEACHER'S ANSWER KEY (page 3) =====\n{keytext}\n", encoding="utf-8")
    return len(blanks)


# ---------- 2. answer (Claude Code fills the blanks)
PROMPT = """You fill in an English-class worksheet so that students can revise from it. It is a {level} {skill} lesson
(Moroccan high school, Unit {unit}: {unit_name}). Below are the worksheet's two student pages as text, each blank to fill
written as [[n]], then the teacher's answer key.

Return ONLY a JSON object, no other text:
{{"blanks": {{"1": "…", "2": "…", …}}, "extra": {{"A": "…"}}}}

THE WORKSHEET IS THE SOURCE OF TRUTH. The teacher often changes the worksheet (new sentences, other words, other
names, another order, a new exercise) and keeps the old answer key. So:
- Solve every exercise yourself from the worksheet as it is now: its instructions, sentences, dialogue, reading
  text, word bank, examples, table and Remember box. The answer must fit the sentence printed on the page.
- Use the answer key only as a help, and only where it clearly matches the exercise as it is now (same sentence,
  same numbering). When the key and the page disagree, the page wins: answer what the page asks.

Rules:
- Give an answer for EVERY [[n]]: only the words that go in that blank (not the whole sentence), exactly as a student
  would write them there, correct for the sentence on the page (grammar, word bank, reading text).
- When there is no single answer (open questions, a partner's answers, "accept any", free writing, a
  writing box or several writing lines), write a short, correct model answer that a good student of this level would
  write, in simple English that fits the worksheet's topic and characters. For several numbered writing lines, one
  sentence per line. For a big writing box, a model paragraph (a short letter, e-mail, paragraph…) of the length the
  task asks for, at most about 120 words.
- Use "" only for a blank that is not an answer (Name, Class, Date, Score, Mark, a teacher's signature…).
- "extra": for an exercise that has NO [[n]] but still has answers (circle, underline, tick, match, number, choose,
  true/false written elsewhere, order the pictures…), its exercise letter → the answers in one short line
  (e.g. "1 c · 2 a · 3 b" or "Verbs: get up, starts, do"). Leave "extra" empty when every exercise has blanks.
- Keep the worksheet's spelling, names and facts. Do not add explanations.
{colour}
{material}
"""
COLOUR = """
COLOUR CODING (this is a {skill} lesson, so students see the target language in colour):
- Inside your answers (blanks and extra), wrap the target language in these tags, and only the words that belong:
  <s>…</s> subject · <v>…</v> main verb (in the form the lesson teaches) · <a>…</a> helping verb, modal, be or
  negative (do, does, don't, is, are, will, can, have, has, not…) · <k>…</k> key words of the point taught (time
  expressions, prepositions, articles, quantifiers, linkers, question words, comparatives…) · <f>…</f> a functional
  expression the lesson teaches (e.g. <f>I'd rather</f>, <f>That sounds interesting!</f>, <f>Would you like</f>…).
  Use only the tags that fit this lesson; other words stay untagged. Example: "<s>She</s> <a>doesn't</a> <v>play</v>
  sports <k>on Mondays</k>." A one-word blank is tagged too: "<a>Does</a>".
- Also return "highlight": up to 30 examples of the target language ALREADY PRINTED on the pages (dialogue, model
  text, examples, tables, the Remember box), each as ["exact text as printed", "the same text with tags"]. Copy the
  printed text character for character (2 to 8 words, inside one sentence); the tagged version must have exactly the
  same words. So the JSON is {{"blanks": {{…}}, "extra": {{…}}, "highlight": [["…", "…"], …]}}.
"""


# ---------- the lesson's card on the student page: a short goal and the whole target language in 2-4 coloured lines
CARDS = OUT / "cards"
CARD_PROMPT = """You write the revision card of an English lesson for Moroccan high-school students ({level}, Unit {unit}:
{unit_name}, a {skill} lesson). Students see it on their page, with the lesson's worksheet, to prepare quizzes and exams.

Return ONLY a JSON object: {{"goal": "…", "points": ["…", "…"]}}

- "goal": what the student can do after this lesson, in at most 10 easy words, starting with a verb
  (e.g. "Talk about your daily routine", "Write an informal letter to a friend").
- "points": 2 to 4 short lines (at most about 14 words each) that sum up ALL the target language of the lesson, so a
  student can revise from the card alone. Grammar: the form and the rule, each with a tiny example. Functions: the
  expressions, grouped by what they do. Vocabulary: the key words, grouped by meaning. Reading: the reading skill and
  the key words of the text. Writing: the layout or steps of the text and its useful phrases.
- Colour-code with these tags, only around the words that matter: <s>…</s> subject · <a>…</a> helping verb, modal,
  be or negative (do, does, don't, is, will, can…) · <v>…</v> main verb form · <k>…</k> key words (vocabulary, time
  words, prepositions, linkers, question words, text parts) · <f>…</f> expressions to use. Example:
  "<s>He/She/It</s> + <v>verb-s</v>: <s>She</s> <v>plays</v>." or "Prefer: <f>I'd rather…</f> · <f>I prefer… to…</f>".
- Simple English, the lesson's own words and examples, no explanations in another language.

The lesson's objective: {objective}
Its Remember point: {point}
Its key words: {words}

{material}
"""


def card_source(l):
    """What the card is made from (the lesson's data in lessons.json): a new card when it changes."""
    keep = {k: l.get(k) for k in ("topic", "objective", "words", "point", "stages", "title")}
    return __import__("hashlib").sha1(json.dumps(keep, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def card_ok(l):
    p = CARDS / f"{l['id']}.json"
    return p.is_file() and json.loads(p.read_text(encoding="utf-8")).get("source") == card_source(l)


def card_one(l, f):
    extract(l, f)
    pages = (WORK / f"{l['id']}.txt").read_text(encoding="utf-8").split("===== TEACHER'S ANSWER KEY")[0]
    prompt = CARD_PROMPT.format(level=l["level"], unit=l["unit"], unit_name=l["unitName"], skill=l["skill"],
                                objective=l.get("objective") or "-", point=l.get("point") or "-",
                                words=", ".join(l.get("words") or []) or "-", material="The worksheet:\n" + pages[:9000])
    try:
        a = ask(l, prompt)
        goal, points = str(a.get("goal") or "").strip(), [str(x).strip() for x in a.get("points") or [] if str(x).strip()][:4]
        if not goal or not points:
            return "card FAILED: empty"
        CARDS.mkdir(parents=True, exist_ok=True)
        (CARDS / f"{l['id']}.json").write_text(json.dumps({"id": l["id"], "source": card_source(l), "goal": goal, "points": points},
                                                          ensure_ascii=False, indent=1), encoding="utf-8")
        return "card made"
    except Exception as e:  # noqa: BLE001 - tried again on the next pass
        return f"card FAILED: {e}"


def card_for(lid, data):
    """The card to show for a lesson (the server): {goal, points} when it was made from the lesson as it is now."""
    p = CARDS / f"{lid}.json"
    if not p.is_file():
        return None
    c = json.loads(p.read_text(encoding="utf-8"))
    return {"goal": c["goal"], "points": c["points"]} if c.get("source") == card_source(data) else None


def claude_exe():
    return shutil.which("claude") or shutil.which("claude.cmd") or "claude"


def ask(l, prompt):
    with tempfile.TemporaryDirectory() as tmp:   # outside the library: no project files or instructions are read
        r = subprocess.run([claude_exe(), "-p", "--output-format", "text"], input=prompt, capture_output=True,
                           text=True, encoding="utf-8", cwd=tmp, timeout=600)
    m = re.search(r"\{.*\}", r.stdout, re.S)
    if not m:
        raise RuntimeError(f"no JSON in the answer: {r.stdout[:300]} {r.stderr[:300]}")
    return json.loads(m.group(0))


LOCK = threading.Lock()


SEEN = {}   # path -> (mtime, size, fingerprint): a worksheet is read again only when it changes on disk


def stamp(f):
    """The worksheet's fingerprint (its content, so it stays the same when the library is unpacked online)."""
    st = f.stat()
    got = SEEN.get(str(f))
    if not got or got[:2] != (st.st_mtime, st.st_size):
        got = (st.st_mtime, st.st_size, __import__("hashlib").sha1(f.read_bytes()).hexdigest()[:16])
        SEEN[str(f)] = got
    return got[2]


def saved(lid, f):
    """The saved answers of a lesson, if they were made from the worksheet as it is now. Answers saved before the
    worksheet's date was recorded count as current when they are newer than the worksheet."""
    p = ANSWERS / f"{lid}.json"
    if not p.is_file():
        return None
    a = json.loads(p.read_text(encoding="utf-8"))
    if "source" not in a and p.stat().st_mtime >= f.stat().st_mtime:
        a["source"] = stamp(f)
        p.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    return a if a.get("source") == stamp(f) else None


def up_to_date(l, f):
    a = saved(l["id"], f)
    return bool(a) and a.get("v", 1) >= VERSION


def material_of(lid):
    p = WORK / f"{lid}.txt"
    return __import__("hashlib").sha1(p.read_bytes()).hexdigest()[:16] if p.is_file() else None


def refresh_one(l, f, quick=False):
    """A covered lesson whose copy is missing or out of date (e.g. the teacher just edited it). When the edit left the
    exercises, the blanks and the answer key as they were (a picture, a title, the layout…), the answers are kept and
    the copy is simply made again: no Claude needed. Otherwise Claude fills the worksheet again (not with quick)."""
    p = ANSWERS / f"{l['id']}.json"
    if p.is_file():
        a = json.loads(p.read_text(encoding="utf-8"))
        before = a.get("material") or material_of(l["id"])   # the blanks and key the answers were made from
        extract(l, f)
        if before and before == material_of(l["id"]) and a.get("v", 1) >= VERSION:
            a.update(source=stamp(f), material=before)
            p.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
            return "same exercises: answers kept"
    if quick:
        return "waits for Claude (exercises changed)"
    return answer_one(l, f, redo=True)


def answer_one(l, f, redo=False):
    dst = ANSWERS / f"{l['id']}.json"
    if dst.exists() and not redo:
        return "kept"
    n = extract(l, f)
    material = (WORK / f"{l['id']}.txt").read_text(encoding="utf-8")
    colour = COLOUR.format(skill=l["skill"]) if l["skill"] in COLOUR_SKILLS else ""
    prompt = PROMPT.format(level=l["level"], skill=l["skill"], unit=l["unit"], unit_name=l["unitName"], material=material, colour=colour)
    last = None
    for _ in range(2):
        try:
            a = ask(l, prompt)
            missing = [i for i in range(1, n + 1) if str(i) not in (a.get("blanks") or {})]
            if missing and last is None:
                last = f"missing blanks {missing[:10]}"
                prompt += f"\n\nYour last answer missed the blanks {missing}. Answer every [[n]] from 1 to {n}."
                continue
            ANSWERS.mkdir(parents=True, exist_ok=True)
            dst.write_text(json.dumps({"id": l["id"], "skill": l["skill"], "v": VERSION, "source": stamp(f), "count": n,
                                       "material": material_of(l["id"]),
                                       "blanks": a.get("blanks") or {}, "extra": a.get("extra") or {},
                                       "highlight": a.get("highlight") or []}, ensure_ascii=False, indent=1), encoding="utf-8")
            return f"{n} blanks" + (f" ({len(missing)} still missing)" if missing else "")
        except Exception as e:  # noqa: BLE001 - one retry, then report
            last = str(e)
    return f"FAILED: {last}"


# ---------- 3. build
STYLE = """<style data-student>
  /* SnezEdu student copy: static, filled in, every page grows to show everything */
  body{{padding-top:0!important}}
  .page{{height:auto!important;min-height:297mm;overflow:visible!important}}
  .ans{{color:{ink};font-weight:700;font-style:normal;background:{bg};border-radius:2px;padding:0 1.5px;
        -webkit-box-decoration-break:clone;box-decoration-break:clone;text-transform:none;letter-spacing:0}}
  .ans-block{{display:block;white-space:pre-line;font-weight:600;line-height:1.55;text-align:left}}
  .ans-note{{border-left:3pt solid {ink};background:{bg};color:{ink};font-weight:700;padding:1.2mm 2.4mm;font-size:9.4pt;margin:1mm 0}}
  .ans-note b{{font-family:Archivo,'Segoe UI',sans-serif;font-size:7.8pt;letter-spacing:.08em;text-transform:uppercase;margin-right:2mm}}
  {tags}
  .ckey{{display:flex;flex-wrap:wrap;gap:1.2mm 3.5mm;align-items:center;border:.7pt dashed #9aa5b1;border-radius:2mm;padding:1.4mm 2.6mm;
         font-family:Archivo,'Segoe UI',sans-serif;font-size:8.4pt}}
  .ckey b{{font-size:7.6pt;letter-spacing:.08em;text-transform:uppercase;color:#555}}
  .ckey span{{font-weight:700}}
  .imgslot{{cursor:default!important}}
  @media print{{.page{{box-shadow:none;margin:0}}}}
</style>"""
HEIGHT = re.compile(r"(?<![-\w])(height|max-height)\s*:\s*[^;\"]+;?", re.I)
TAG_RX = re.compile(r"&lt;(/?)([svakf])&gt;")


def unfix_heights(el, page):
    """The blank and its parents up to the page lose any fixed height, so a longer answer pushes the lines down."""
    for n in [el, *ancestors(el)]:
        if n is page:
            break
        if not isinstance(n, El) or n.tag in ("tr", "table"):
            continue
        m = re.search(r'style="([^"]*)"', n.raw)
        if m and HEIGHT.search(m.group(1)):
            n.raw = n.raw.replace(m.group(0), f'style="{HEIGHT.sub("", m.group(1))}"')


def fmt(v, used):
    """An answer as HTML: escaped, with its colour tags (<s>…</s> …) turned into coloured spans when they are well made."""
    e = html.escape(v, quote=False)
    tagged = TAG_RX.sub(lambda m: "</span>" if m.group(1) else f'<span class="c-{m.group(2)}">', e)
    opens = re.findall(r'<span class="c-(\w)">', tagged)
    if len(opens) != tagged.count("</span>"):
        return TAG_RX.sub("", e)
    used.update(opens)
    return tagged


def plain_text(v):
    return re.sub(r"</?[svakf]>", "", v)


def highlight(keep, pairs, used):
    """Colour the target language already printed on the pages (e.g. the dialogue): each exact text found in a text
    node (not in an answer) becomes its tagged version. Texts that are not found as they are, or whose tagged version
    has other words, are left alone."""
    done = 0
    for pair in pairs or []:
        if not (isinstance(pair, list) and len(pair) == 2):
            continue
        plain, tagged = str(pair[0]), str(pair[1])
        if len(plain.strip()) < 2 or plain_text(tagged) != plain:
            continue
        for p in keep:
            for n in list(walk(p)):
                if not isinstance(n, Raw) or n.raw.startswith("<") or n.parent is None or n.parent.tag in ("script", "style", "h1", "title"):
                    continue
                if any(isinstance(a, El) and ("ans" in a.cls() or "c-" in (a.attrs.get("class") or "")) for a in ancestors(n)):
                    continue
                t = html.unescape(n.raw)
                i = t.find(plain)
                if i < 0:
                    continue
                # three nodes: the text before, the coloured part (markup: never matched again), the text after
                # (still plain text, so another example in the same sentence can be coloured too)
                parts = [Raw(html.escape(t[:i], quote=False)), Raw(f'<span class="hl-t">{fmt(tagged, used)}</span>'),
                         Raw(html.escape(t[i + len(plain):], quote=False))]
                kids = n.parent.kids
                at = kids.index(n)
                for q in parts:
                    q.parent = n.parent
                kids[at:at + 1] = [q for q in parts if q.raw]
                done += 1
    return done


def write_copy(lid, skill, f, a, dst):
    """The static copy of a worksheet: pages 1-2, no controls; with the answers a (None: without answers)."""
    tree, ps, key, keep, blanks = parse(f)
    for p in ps:
        if p not in keep:
            p.parent.kids.remove(p)
    filled = notes = marks = 0
    used = set()
    if a:
        for i, b in enumerate(blanks, 1):
            v = str((a.get("blanks") or {}).get(str(i)) or "").strip()
            if not v:
                continue
            filled += 1
            big = "\n" in v or len(plain_text(v)) > 90 or b.tag == "div" and ("ruled" in b.cls() or "min-height" in b.style())
            r = Raw(f'<span class="ans{" ans-block" if big else ""}">{fmt(v, used)}</span>')
            r.parent, b.kids = b, [r]
            unfix_heights(b, next(p for p in keep if p in ancestors(b)))
        for letter, v in (a.get("extra") or {}).items():
            v = str(v or "").strip()
            lab = next((n for p in keep for n in walk(p) if isinstance(n, El) and n.tag in ("span", "b", "strong")
                        and re.fullmatch(rf"\s*{re.escape(letter.strip(' .'))}\s*[.)]?\s*", text(n))), None)
            if not v or lab is None:
                continue
            row = lab.parent
            box = Raw(f'<div class="ans-note"><b>Answers</b>{fmt(v, used)}</div>')
            box.parent = row.parent
            row.parent.kids.insert(row.parent.kids.index(row) + 1, box)
            notes += 1
        if skill in COLOUR_SKILLS:
            marks = highlight(keep, a.get("highlight"), used)
    if used and keep:   # the colour key, at the top of page 1 (under its header)
        page1 = keep[0]
        head = next((k for k in page1.kids if isinstance(k, El) and k.tag == "header"), None)
        ck = Raw('<div class="ckey"><b>Colour key</b>' + "".join(f'<span class="c-{t}">{TAGS[t][0]}</span>' for t in TAGS if t in used) + "</div>")
        ck.parent = page1
        page1.kids.insert(page1.kids.index(head) + 1 if head else 0, ck)
    ink, bg = SKILL_INK.get(skill, ("#14213d", "#eef1f6"))
    if skill in COLOUR_SKILLS:   # the colours speak for the target language; the rest of an answer stays dark
        ink = "#1f2937"
    tags = "".join(f".c-{t}{{color:{c}!important;font-weight:800}}" for t, (_, c) in TAGS.items())
    doc = out(tree.root)
    doc = re.sub(r"</head>", lambda m: STYLE.format(ink=ink, bg=bg, tags=tags) + "</head>", doc, count=1, flags=re.I)
    doc = re.sub(r"<title>(.*?)</title>", lambda m: f"<title>{html.escape(short_title(lid) or m.group(1))}</title>", doc, count=1, flags=re.S | re.I)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(doc, encoding="utf-8")
    return filled, len(blanks), notes, marks


def short_title(lid):
    """The tab name of a copy, as server.page_title: "Unit 2 · Grammar · The present simple"."""
    l = next((x for x, _ in lessons({lid})), None)
    if not l:
        return None
    topic = str(l.get("topic") or "").strip()
    return f"Unit {l['unit']} · {l['skill']}" + (" · " + topic[:1].upper() + topic[1:] if l["skill"] in ("Grammar", "Functions", "Writing") and topic else "")


def build_one(l, f):
    a = saved(l["id"], f)
    if not a:
        return "FAILED: no answers for the worksheet as it is now: run covered (or answer --redo)"
    filled, n, notes, marks = write_copy(l["id"], l["skill"], f, a, OUT / f"{l['id']}.html")
    if n != a.get("count", n):
        return f"FAILED: the worksheet changed ({n} blanks, {a.get('count')} answered): run answer --redo"
    a["built"] = a["source"]   # the copy on disk matches these answers and this worksheet
    (ANSWERS / f"{l['id']}.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"{filled}/{n} blanks filled, {notes} answer lines" + (f", {marks} colour marks" if marks else "")


def copy_for(lid, ws_rel):
    """The student copy to show for a covered lesson (a path in the library): the filled copy when it was made from
    the worksheet as it is now; otherwise a static copy without the answers, made here and then (no Claude needed)."""
    f = ROOT / ws_rel if ws_rel else None
    if not f or not f.is_file():
        return ws_rel
    a = saved(lid, f)
    if a and a.get("built") == a["source"] and (OUT / f"{lid}.html").is_file():
        return f"_students/{lid}.html"
    plain, mark = PLAIN / f"{lid}.html", PLAIN / f"{lid}.src"
    if not plain.is_file() or not mark.is_file() or mark.read_text() != stamp(f):
        with LOCK:
            write_copy(lid, "", f, None, plain)
            mark.write_text(stamp(f))
    return f"_students/plain/{lid}.html"


def covered(dbs):
    """Every lesson covered by a class in these databases (this computer's and, from Put online, the online one)."""
    sys.path.insert(0, str(ROOT / "app"))
    import db
    import server
    ids = set()
    for p in dbs:
        if not Path(p).is_file():
            continue
        db.DB = Path(p)
        try:
            with db.session() as c:
                ids |= server.all_covered(c)
        except Exception as e:  # noqa: BLE001 - an older database: skip it
            print(f"{p}: cannot read the classes ({e})")
    return ids


def main(argv):
    cmd = argv[0] if argv else "covered"
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 4
    ids = {x for x in argv[1:] if re.fullmatch(r"(cc|bac)-u\d+-l\d+", x)}
    if cmd == "covered":
        dbs = [argv[i + 1] for i, x in enumerate(argv) if x == "--db" and i + 1 < len(argv)] or [str(ROOT / "library.db")]
        ids = covered(dbs)
        todo = [x for x in lessons(ids) if not up_to_date(*x)] if ids else []
        print(f"{len(ids)} lessons covered; {len(todo)} student copies to make or redo", flush=True)
    elif cmd == "refresh":   # these lessons now (the helper, after an online edit of a covered lesson)
        todo = [x for x in lessons(ids) if not up_to_date(*x)] if ids else []
        if not todo and ids:
            print("already up to date: " + ", ".join(sorted(ids)) + " (blanks filled)")
    else:
        todo = lessons(ids)
    if cmd == "extract":
        for l, f in todo:
            print(l["id"], extract(l, f), "blanks")
    if cmd in ("answer", "covered", "refresh"):
        def one(x):
            r = (refresh_one(*x, quick="--quick" in argv) if cmd in ("covered", "refresh")
                 else answer_one(*x, redo="--redo" in argv))
            with LOCK:
                print(f"{x[0]['id']}: {r}", flush=True)
        with ThreadPoolExecutor(jobs) as pool:
            list(pool.map(one, todo))
    if cmd in ("build", "covered", "refresh"):
        for l, f in todo:
            if saved(l["id"], f):
                print(f"{l['id']}: {build_one(l, f)}", flush=True)
    if cmd in ("covered", "refresh", "cards") and "--quick" not in argv:   # the cards of the student page (Claude)
        cards = [x for x in lessons(ids) if not card_ok(x[0])] if ids else []

        def card(x):
            r = card_one(*x)
            with LOCK:
                print(f"{x[0]['id']}: {r}", flush=True)
        with ThreadPoolExecutor(jobs) as pool:
            list(pool.map(card, cards))


if __name__ == "__main__":
    main(sys.argv[1:])