"""Make the upload package for hosting the Lesson Library online (see DEPLOY.md).

Writes _deploy\\lesson-library-part-N.zip, each under 95 MB (PythonAnywhere accepts files up to 100 MB).
Left out: the course books (copyright, and too big for a free plan), backups, _to_delete, Claude skills,
Windows launchers and caches. The database is copied without anyone's sign-in sessions.
Run:  python make_deploy.py
Quick update: python make_deploy.py --changed  packs only the files that differ from _deploy/online-manifest.json
(what the last successful upload sent; upload_pythonanywhere.py writes it), and no database (the online one is kept).
"""
import hashlib
import json
import sqlite3
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_deploy"
LIMIT = 95 * 1024 * 1024
MANIFEST = OUT / "online-manifest.json"      # {file: sha1} of what is online (saved after a successful upload)
NEW_MANIFEST = OUT / "manifest-new.json"     # this package's list; becomes MANIFEST once the upload worked
SKIP_DIRS = {"_backups", "_to_delete", "_deploy", "_quiz_jobs", "_board_jobs", "_chat", "_relay", "_calfile", "_ttfile", ".claude", "skills", "__pycache__", ".git"}
SKIP_FILES = {"Ticket 1.pdf", "Outlook.pdf", "library.db",          # course books; the database is added separately
              "_helper.json", "_helper_site.txt", "_pa_login.json"}                   # the SnezEdu helper's address and token (this PC only)
SKIP_EXT = {".bat", ".ps1", ".saving", ".pyc"}
KEEP = {"skills/quiz-creation/tools/ref/Reading_U2.html",          # the test template's shell (app/tests.py)
        # online, Claude works through the API with these skills as instructions (app/ai.py) and the board fonts
        "skills/quiz-creation/SKILL.md", "skills/quiz-creation/models/tests/Quiz1_CC_Units1-2_filled.html",
        "skills/review-creation/SKILL.md", "skills/board-layout/SKILL.md",
        "skills/lesson-challenges/SKILL.md", "skills/homework-sheet/SKILL.md",   # Anticipated challenges, Homework builder
        "skills/review-creation/models/ECRIF.html",   # "Make plan" for reviews (app/plans.py)
        "skills/board-layout/fonts/patrick-hand-latin-400-normal.woff2", "skills/board-layout/fonts/kalam-latin-700-normal.woff2"}


def files():
    for p in sorted(ROOT.rglob("*")):
        rel = p.relative_to(ROOT)
        if rel.as_posix() in KEEP or p.is_file() and not (set(rel.parts) & SKIP_DIRS) and p.name not in SKIP_FILES and p.suffix.lower() not in SKIP_EXT:
            yield p, rel.as_posix()


def clean_db():
    """A copy of library.db without sign-in sessions or a Claude API key."""
    OUT.mkdir(exist_ok=True)
    dst = OUT / "library.db"
    src, out = sqlite3.connect(ROOT / "library.db"), sqlite3.connect(dst)
    src.backup(out)
    src.close()
    out.execute("DELETE FROM auth_sessions")
    out.execute("DELETE FROM meta WHERE key IN ('anthropic_key', 'relay_token_hash', 'relay_seen', 'mail_password')")   # set online, never shipped
    if out.execute("SELECT 1 FROM sqlite_master WHERE name = 'user_tokens'").fetchone():   # e-mail links (from migration 9)
        out.execute("DELETE FROM user_tokens")
    out.commit()
    out.execute("VACUUM")
    out.close()
    return dst


def sha1(p):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(limit=LIMIT, changed=False):
    """limit: the most bytes (before compression) per zip; upload_pythonanywhere.py asks for small parts.
    changed: only the files that are new or different since the last successful upload (no database)."""
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("lesson-library-part-*.zip"):
        old.unlink()  # earlier packages made by this script
    every = list(files())
    now = {arc: sha1(p) for p, arc in every}
    NEW_MANIFEST.write_text(json.dumps(now, indent=0), encoding="utf-8")
    online = {}
    if changed:
        try:
            online = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            print("No record of the last upload yet: everything goes up this time (only the changes next time).")
            changed = False
    if changed:
        items = [(p, arc) for p, arc in every if online.get(arc) != now[arc]]
        print(f"{len(items)} of {len(every)} files changed since the last upload.")
        if not items:
            print("Nothing to upload.")
            return 0
    else:
        items = every + [(clean_db(), "library.db")]
    part, size, z, made = 0, 0, None, []
    for p, arc in items:
        s = p.stat().st_size
        if z is None or size + s > limit:
            if z:
                z.close()
            part += 1
            size = 0
            name = OUT / f"lesson-library-part-{part}.zip"
            z = zipfile.ZipFile(name, "w", zipfile.ZIP_DEFLATED, compresslevel=6)
            made.append(name)
        z.write(p, f"lesson-library/{arc}")
        size += s
    if z:
        z.close()
    (OUT / "library.db").unlink(missing_ok=True)
    for m in made:
        print(f"{m.relative_to(ROOT)}  {m.stat().st_size / 1048576:.1f} MB")
    print(f"{len(items)} files. Upload these zips, then follow DEPLOY.md.")


if __name__ == "__main__":   # python make_deploy.py [--part-mb N] [--changed]
    mb = sys.argv[sys.argv.index("--part-mb") + 1] if "--part-mb" in sys.argv else None
    sys.exit(main(int(mb) * 1024 * 1024 if mb else LIMIT, "--changed" in sys.argv))
