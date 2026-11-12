"""Put the Lesson Library online on PythonAnywhere, or update it there (see DEPLOY.md).

Does steps 3-4 of DEPLOY.md through the PythonAnywhere API:
  1. makes the package (make_deploy.py) and uploads the zips to your home folder;
  2. writes the web app's WSGI file, which unpacks new zips when the app starts and keeps the online database;
  3. creates the web app the first time, turns Force HTTPS on and reloads it.
Needs your username and an API token (Account page > API token). The token is asked for and never saved.
The EU or US server is found automatically (--eu only changes which one is tried first).
When the library is already online it asks: update (keep the online data) or start from scratch (--fresh: delete
the online folder first; its database is copied next to it beforehand). Leftover zips are always removed first.
Run:  python upload_pythonanywhere.py USERNAME          (add --eu if your account is on eu.pythonanywhere.com)
"""
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PART_MB = 12   # zip parts this size or smaller (before compression): big uploads to PythonAnywhere get cut off
PYTHONS = ["python313", "python312", "python311", "python310"]   # newest first; the first one the host accepts is used

WSGI = '''# Written by upload_pythonanywhere.py; running that script again replaces this file.
import os, sys, zipfile
from pathlib import Path

HOME = Path("/home/{user}")
APP = HOME / "lesson-library"
for z in sorted(HOME.glob("lesson-library-part-*.zip")):
    claim = z.with_suffix(".unpacking")
    try:
        z.rename(claim)             # only one worker unpacks each zip
    except OSError:
        continue
    with zipfile.ZipFile(claim) as zf:
        for m in zf.infolist():
            if m.filename == "lesson-library/library.db" and (APP / "library.db").exists():
                continue            # keep the online database (classes, progress, notes, quizzes)
            zf.extract(m, HOME)
    claim.unlink()

for _pkg, _mod in (("anthropic", "anthropic"), ("pypdf", "pypdf"), ("openpyxl", "openpyxl"), ("pillow", "PIL")):   # the Claude API package (Settings > Claude) and the PDF reader (Setup > new school year from a file), installed once
    try:
        __import__(_mod)
    except ImportError:
        try:                        # never stops the library from starting: only these options need them
            import subprocess, site, importlib
            subprocess.run([f"python{{sys.version_info[0]}}.{{sys.version_info[1]}}", "-m", "pip", "install", "--user", "--quiet", _pkg],
                           timeout=240)
            importlib.invalidate_caches()
            site.addsitedir(site.getusersitepackages())
        except Exception:
            pass

os.environ["LIBRARY_HOSTS"] = "{domain}"
os.environ["LIBRARY_HTTPS"] = "1"
sys.path.insert(0, str(APP / "app"))
from wsgi import application  # noqa
'''


def mb(n):
    return f"{n / 1048576:.1f} MB"


class Sending:
    """The bytes of one upload, read by the connection piece by piece: draws a progress bar while they go out
    (this part, and the whole package)."""
    def __init__(self, data, label, before=0, total=None):
        self.data, self.pos, self.label = data, 0, label
        self.before, self.total = before, total or len(data)
        self.t0 = self.drawn = time.time()

    def read(self, n=-1):
        chunk = self.data[self.pos:] if n is None or n < 0 else self.data[self.pos:self.pos + n]
        self.pos += len(chunk)
        if time.time() - self.drawn > 0.2 or self.pos >= len(self.data):
            self.draw()
        return chunk

    def draw(self):
        self.drawn = time.time()
        part = self.pos / max(1, len(self.data))
        sent = self.before + self.pos
        speed = self.pos / max(0.1, time.time() - self.t0)
        left = (self.total - sent) / speed if speed > 0 else 0
        bar = "#" * int(part * 24) + "-" * (24 - int(part * 24))
        sys.stdout.write(f"\r  {self.label} [{bar}] {part:4.0%}  {mb(self.pos)}/{mb(len(self.data))}"
                         f"  | all: {sent / self.total:4.0%}  {speed / 1024:5.0f} KB/s  ~{int(left // 60)} min {int(left % 60):02d} s left ")
        sys.stdout.flush()


class Api:
    def __init__(self, user, token, eu):
        self.base = f"https://{'eu' if eu else 'www'}.pythonanywhere.com/api/v0/user/{user}/"
        self.token = token

    def call(self, method, path, data=None, body=None, ctype=None):
        headers = {"Authorization": f"Token {self.token}"}
        if data is not None:
            body, ctype = urllib.parse.urlencode(data).encode(), "application/x-www-form-urlencoded"
        if ctype:
            headers["Content-Type"] = ctype
        if isinstance(body, Sending):   # sent piece by piece (progress bar), so its length is given up front
            headers["Content-Length"] = str(len(body.data))
        req = urllib.request.Request(self.base + path, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                raw = r.read()
                return r.status, json.loads(raw) if raw.strip().startswith((b"{", b"[")) else raw
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def upload(self, remote, data, tries=5, label=None, before=0, total=None):
        """POST files/path/<remote> as multipart form data (field "content"). PythonAnywhere sometimes drops a
        connection during an upload, so each file is tried again a few times, waiting a little longer each time.
        With a label, a progress bar shows (before/total: bytes already sent and in all, for the overall %)."""
        b = uuid.uuid4().hex
        body = (f"--{b}\r\nContent-Disposition: form-data; name=\"content\"; filename=\"f\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{b}--\r\n".encode()
        for n in range(1, tries + 1):
            try:
                st, out = self.call("POST", "files/path" + urllib.parse.quote(remote),
                                    body=Sending(body, label, before, total) if label else body,
                                    ctype=f"multipart/form-data; boundary={b}")
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as ex:
                st, out = None, getattr(ex, "reason", ex)
            if label:
                print()   # end the progress line
            if st in (200, 201):
                return
            if st is not None and st < 500 and st != 429:
                sys.exit(f"Upload of {remote} failed ({st}): {out}")
            if n < tries:
                wait = 10 * n
                for s in range(wait, 0, -1):
                    sys.stdout.write(f"\r  the connection dropped ({out}); trying again in {s:2d} s ({n}/{tries - 1}) ")
                    sys.stdout.flush()
                    time.sleep(1)
                print()
        sys.exit(f"Upload of {remote} failed {tries} times ({out}). Check the internet connection and run Put online.bat again.")

    def exists(self, remote):
        st, _ = self.call("GET", "files/path" + urllib.parse.quote(remote))
        return st == 200

    def delete(self, remote):
        st, out = self.call("DELETE", "files/path" + urllib.parse.quote(remote))
        return st in (200, 204), out

    def clear_old_parts(self, user):
        """Remove zips left by an earlier upload that did not finish, so only this package is unpacked."""
        st, listing = self.call("GET", f"files/path/home/{user}/")
        if st != 200 or not isinstance(listing, dict):
            return
        for name in listing:
            if name.startswith("lesson-library-part-") and name.endswith((".zip", ".unpacking")):
                self.call("DELETE", "files/path" + urllib.parse.quote(f"/home/{user}/{name}"))


def pull_online_edits(api, folder):
    """Lessons changed online (editor, Ask SnezEdu) that the SnezEdu helper has not brought here yet: they are put on
    this computer first (same rules as the helper: a file changed here too is kept, the online one saved aside), so
    this upload never brings the old version back. The online requests are then marked done."""
    st, listing = api.call("GET", "files/path" + urllib.parse.quote(folder + "_relay/"))
    if st != 200 or not isinstance(listing, dict):
        return
    sys.path.insert(0, str(ROOT / "app"))
    import helper   # apply_online_edit
    jobs = []
    for name in listing:
        if name.startswith("relay_") and name.endswith(".json") and not name.endswith(".result.json"):
            st, d = api.call("GET", "files/path" + urllib.parse.quote(folder + "_relay/" + name))
            if st == 200 and isinstance(d, dict) and d.get("kind") == "sync" and d.get("status") in ("queued", "taken"):
                jobs.append(d)
    if not jobs:
        return
    print(f"\nLessons changed online, brought to this computer first ({len(jobs)}):")
    for d in sorted(jobs, key=lambda d: d.get("created", "")):
        state = helper.apply_online_edit(d["sync"], log=print)
        print(f"  {d['sync']['file']}: {state}")
        d["status"] = "answered"   # the student copy is made below, with the other covered lessons
        api.upload(folder + "_relay/" + d["id"] + ".json", json.dumps(d, ensure_ascii=False).encode("utf-8"))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    saved = {}
    try:   # _pa_login.json (this PC only, never uploaded, never committed): {"username": "...", "token": "..."}
        saved = json.loads((ROOT / "_pa_login.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if not args and saved.get("username"):
        args = [str(saved["username"])]
    if not args:
        sys.exit(__doc__)
    user = args[0].strip()          # the API path is case-sensitive: keep the username exactly as on PythonAnywhere
    if saved.get("token") and str(saved.get("username", "")).strip() == user:
        token = "".join(ch for ch in str(saved["token"]) if ch.isalnum())
        print(f"Using the username and token saved in _pa_login.json ({user}).")
    else:
        print("Paste the API token with a right-click (or Ctrl+V), then press Enter. It shows here but is not saved.")
        token = "".join(ch for ch in input("API token: ") if ch.isalnum())   # drops spaces, quotes and stray Ctrl+V characters
    if len(token) != 40:
        print(f"Note: the token has {len(token)} letters/digits; PythonAnywhere tokens usually have 40.")

    tried = []
    for eu in (["--eu" in sys.argv] + ["--eu" not in sys.argv]):  # the region asked for first, then the other one
        api = Api(user, token, eu)
        st, apps = api.call("GET", "webapps/")
        tried.append(f"{'eu' if eu else 'www'}.pythonanywhere.com: {st}")
        if st == 200:
            break
    else:
        sys.exit("PythonAnywhere refused the token (" + "; ".join(tried) + ").\nCheck:\n"
                 f"  - the username is exactly '{user}', with the same capitals as on PythonAnywhere (top right when signed in);\n"
                 f"  - the token is the one shown under Account > API token (token {token[:4]}...{token[-4:]});\n"
                 "  - if in doubt, click 'Create a new API token' there and use the new one.")
    if eu != ("--eu" in sys.argv):
        print(f"Your account is on {'eu' if eu else 'www'}.pythonanywhere.com; using that.")
    domain = f"{user.lower()}.{'eu.' if eu else ''}pythonanywhere.com"

    folder = f"/home/{user}/lesson-library/"
    fresh, quick = "--fresh" in sys.argv, "--all" not in sys.argv
    if not fresh and api.exists(folder):
        print("\nThe library is already online. Three choices:\n"
              "  Enter  = QUICK UPDATE: send only the files changed since the last upload, KEEP the online data.\n"
              "  ALL    = FULL UPDATE: send every file again (if the site looks out of date), KEEP the online data.\n"
              "  YES    = START FROM SCRATCH: delete everything online first, the online database too (a copy is kept).")
        choice = input("Your choice (Enter, ALL or YES): ").strip().upper()
        fresh, quick = choice == "YES", quick and choice not in ("ALL", "YES")
    quick = quick and not fresh and api.exists(folder)
    if fresh and api.exists(folder):
        keep = f"/home/{user}/library-before-fresh-start-{time.strftime('%Y%m%d-%H%M%S')}.db"
        st, data = api.call("GET", "files/path" + urllib.parse.quote(folder + "library.db"))
        if st == 200 and isinstance(data, bytes):
            api.upload(keep, data)   # the online database is kept as a single file next to the library, just in case
            print(f"Online database copied to {keep}")
        print("Deleting the old online library (can take a minute)...")
        done, out = api.delete(folder)
        if not done or api.exists(folder):
            sys.exit(f"Could not delete {folder} ({out}). Delete it in the Files tab of PythonAnywhere, then run this again.")
        print("  deleted.")

    if not fresh:
        pull_online_edits(api, folder)

    # the students' copies of the lessons covered so far, here or online (the online database is read, not changed)
    print("\n[0/4] Student copies of the lessons covered so far (filled in with Claude Code)...")
    dbs = ["--db", str(ROOT / "library.db")]
    if not fresh:
        st, data = api.call("GET", "files/path" + urllib.parse.quote(folder + "library.db"))
        if st == 200 and isinstance(data, bytes):
            online = ROOT / "_deploy" / "online-library.db"
            online.parent.mkdir(exist_ok=True)
            online.write_bytes(data)
            dbs += ["--db", str(online)]
    r = subprocess.run([sys.executable, str(ROOT / "build_student_worksheets.py"), "covered", "--jobs", "4", *dbs])
    if r.returncode:
        print("  (some student copies could not be made now; students see those lessons without the answers until the next time)")

    print("\n[1/4] Making the package" + (" (only what changed since the last upload)..." if quick else " (in small parts, easier to upload)..."))
    subprocess.run([sys.executable, str(ROOT / "make_deploy.py"), "--part-mb", str(PART_MB), *(["--changed"] if quick else [])], check=True)
    api.clear_old_parts(user)
    parts = sorted((ROOT / "_deploy").glob("lesson-library-part-*.zip"), key=lambda p: int(re.search(r"(\d+)\.zip$", p.name)[1]))
    if not parts:   # a quick update with nothing changed: the site stays as it is
        print("\nThe site is already up to date: nothing to upload.")
        return
    total, sent, t0 = sum(p.stat().st_size for p in parts), 0, time.time()
    print(f"\n[2/4] Uploading {len(parts)} parts, {mb(total)} in all:")
    for i, z in enumerate(parts, start=1):
        api.upload(f"/home/{user}/{z.name}", z.read_bytes(), label=f"part {i}/{len(parts)}", before=sent, total=total)
        sent += z.stat().st_size
    print(f"  all {len(parts)} parts uploaded in {int((time.time() - t0) // 60)} min {int((time.time() - t0) % 60)} s.")
    print("\n[3/4] Setting up the web app...")

    if not any(a.get("domain_name") == domain for a in apps):
        for py in PYTHONS:
            st, out = api.call("POST", "webapps/", {"domain_name": domain, "python_version": py})
            if st in (200, 201):
                print(f"Web app created: {domain} ({py})")
                break
        else:
            sys.exit(f"Could not create the web app ({st}): {out}")
    wsgi_file = f"/var/www/{domain.replace('.', '_')}_wsgi.py"
    api.upload(wsgi_file, WSGI.format(user=user, domain=domain).encode())
    st, out = api.call("PATCH", f"webapps/{domain}/", {"force_https": "true"})
    if st != 200:
        print(f"Note: could not turn Force HTTPS on ({st}); turn it on in the Web tab.")
    print("  reloading...")
    st, out = api.call("POST", f"webapps/{domain}/reload/")
    if st != 200:
        sys.exit(f"Reload failed ({st}): {out}\nOpen the Web tab and click Reload; the error log is linked there.")
    (ROOT / "_helper_site.txt").write_text(f"https://{domain}", encoding="utf-8")   # SnezEdu helper.bat finds the site by itself
    new = ROOT / "_deploy" / "manifest-new.json"   # what is online now: the next quick update sends only what differs
    if new.exists():
        new.replace(ROOT / "_deploy" / "online-manifest.json")
    print("\n[4/4] Starting the site (its first start unpacks the library)...")
    if wait_for_site(f"https://{domain}/login"):
        print(f"\nDone. Open https://{domain} and sign in with the same username and password as on this computer.")
    else:
        print(f"\nThe site did not answer yet. Open https://{domain} in a minute; if it shows an error, "
              "the Web tab of PythonAnywhere has an Error log link.")


def wait_for_site(url, minutes=4):
    """Open the sign-in page until it answers (the first visit unpacks the parts), with a running clock."""
    t0, spin = time.time(), "|/-\\"
    while time.time() - t0 < minutes * 60:
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                if r.status == 200:
                    print(f"\r  the site answers ({int(time.time() - t0)} s).          ")
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            pass
        for _ in range(5):
            sys.stdout.write(f"\r  waiting {spin[int(time.time()) % 4]} {int(time.time() - t0)} s ")
            sys.stdout.flush()
            time.sleep(1)
    print()
    return False


if __name__ == "__main__":
    main()
