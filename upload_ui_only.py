"""Quick update: uploads only the app files that CHANGED since the last quick update (screens, server code, the record
book / grading sheet / report templates), then reloads the site. No lessons, no zips, no database change.
Uses the login saved in _pa_login.json. What was sent is remembered in _deploy/quick_upload_state.json.
  python upload_ui_only.py          only the changed files
  python upload_ui_only.py --all    every app file again (after Put online.bat from another folder, or if in doubt)
It cannot install Python packages: after a new tool needs one (pypdf, openpyxl, pillow), run Put online.bat once."""
import hashlib
import json
import sys
from pathlib import Path

import upload_pythonanywhere as pa

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "_deploy" / "quick_upload_state.json"
TEMPLATES = ["tools/record-book/English Record Book.html", "tools/grading-sheets/Grading sheet template.docx",
             "tools/grading-sheets/logo.png", "tools/reports/cheating.docx", "tools/reports/disruption.docx",
             "tools/reports/logo.png",
             # the skills the site gives Claude as instructions (app/ai.py), so skill updates go online too
             "skills/quiz-creation/SKILL.md", "skills/review-creation/SKILL.md", "skills/board-layout/SKILL.md",
             "skills/lesson-challenges/SKILL.md", "skills/homework-sheet/SKILL.md",
             "skills/review-creation/models/ECRIF.html"]   # "Make plan" for reviews (app/plans.py)


def app_files():
    """Every app module and interface file (not app/ui/brand: the logos uploaded on the site stay as they are)."""
    out = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "app").glob("*.py"))
    out += sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "app" / "ui").iterdir() if p.is_file())
    return out + [t for t in TEMPLATES if (ROOT / t).is_file()]


def digest(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def main():
    saved = json.loads((ROOT / "_pa_login.json").read_text(encoding="utf-8"))
    user = str(saved["username"]).strip()
    token = "".join(ch for ch in str(saved["token"]) if ch.isalnum())
    state = {}
    if "--all" not in sys.argv:
        try:
            state = json.loads(STATE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
    files = app_files()
    todo = [f for f in files if state.get(f) != digest(f)]
    if not todo:
        print("Nothing changed since the last quick update. (Use --all to send everything again.)")
        return
    if not state:
        print("First quick update (or --all): every app file is sent once; next time only the changed ones.")
    for eu in (False, True):
        api = pa.Api(user, token, eu)
        st, _ = api.call("GET", "webapps/")
        if st == 200:
            break
    else:
        sys.exit("PythonAnywhere refused the saved login.")
    domain = f"{user.lower()}.{'eu.' if eu else ''}pythonanywhere.com"
    print(f"{len(todo)} of {len(files)} files changed:")
    STATE.parent.mkdir(exist_ok=True)
    for name in todo:
        print(f"  uploading {name} ...")
        api.upload(f"/home/{user}/lesson-library/{name}", (ROOT / name).read_bytes())
        state[name] = digest(name)
        STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")   # saved after each file: a cut connection resumes
    st, out = api.call("POST", f"webapps/{domain}/reload/")
    print("Reloaded." if st == 200 else f"Reload failed ({st}): {out}")
    print(f"Done. Open https://{domain} and refresh (Ctrl+F5, or clear the site data on the phone).")


if __name__ == "__main__":
    main()
