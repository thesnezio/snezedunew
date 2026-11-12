# Putting the Lesson Library online (free)

Chosen host: **PythonAnywhere, free "Beginner" plan** (checked 30 Oct 2026).
- Why it fits:
  - free, with no card;
  - keeps files and the database between visits;
  - runs Python, which is all this app needs;
  - your own address: `https://<username>.pythonanywhere.com`.
- Limits of the free plan:
  - 512 MB of storage (the package is about 100 MB unpacked);
  - limited CPU per day;
  - one web app;
  - community support only.
- Renewal: free web apps must be renewed from the Web tab now and then. There is a button for it, and PythonAnywhere emails you before.
- Left out on purpose: the course books (*Ticket 1.pdf*, *Outlook.pdf*). They are copyrighted and too big for the free plan.

Other options checked:
- Render, Koyeb and Fly.io no longer offer a free tier that keeps a database.
- Oracle Cloud "Always Free" gives a whole server with 200 GB, but needs a card and more setup. Use it if the library outgrows 512 MB.

## Quick way (about 5 minutes)
1. Create the account (step 2 below) and confirm your email.
2. On PythonAnywhere: **Account** (top right) → **API token** tab → **Create a new API token**. Copy it.
3. On this computer, double-click **`Put online.bat`**. Type your username exactly as PythonAnywhere shows it (same capitals). Paste the token with a right-click and press Enter. The token shows on screen but is not saved. The EU or US server is found automatically.
4. The script makes the package, uploads it, creates the web app, writes the WSGI file, turns Force HTTPS on and reloads.
5. Open `https://USERNAME.pythonanywhere.com`. The first opening takes up to a minute while the library unpacks. Sign in with the same username and password as on this computer.

**Claude & Gemini online (no API credit):** your computer does the Claude and Gemini work for the online library.
1. On this computer, double-click **`SnezEdu helper.bat`**. The first time, your browser opens SnezEdu: sign in if asked and press **Connect this computer**. That's all: nothing to type (the address comes from `Put online.bat`, and the helper remembers the connection).
2. Leave the helper window open.
3. The AI features online now run on this computer:
   - **Ask SnezEdu chatbox:** runs via Google Gemini on your PC (authenticated via `agy`).
   - **Lesson Builders (Quizzes, Reviews, Boards, Homework):** run via Claude Code or Gemini according to your engine preferences. Boards come back with their full PNG render made by Edge on your PC.
   - While the computer is off, requests wait online and run when the helper starts again.
   - Only your own requests go to your computer. Colleagues never use your subscription unless you turn on sharing.
4. To start it with Windows: press Win+R, type `shell:startup`, and put a shortcut to `SnezEdu helper.bat` in that folder.
5. **Colleagues:** in Settings › Claude, the switch "Colleagues use my Claude too (testing)" lets colleagues use your helper. They can also use their own: "Download my SnezEdu helper" for their own PC.

(Settings › Claude also accepts a paid Claude API key, for later, e.g. for colleagues. You don't need one.)

**Uploading:**
- The package goes up in parts of about 8 MB. A part whose connection drops is sent again automatically.
- Leftover parts from an upload that did not finish are deleted first.
- When the library is already online, the script asks:
  - **Enter = quick update**: only the files changed since the last upload are sent; the online data (accounts, classes, progress) is kept;
  - **ALL = full update**: every file is sent again (if the site looks out of date); the online data is kept;
  - **YES = start from scratch**: the online folder is deleted first. Its database is first saved as `library-before-fresh-start-<date>.db` in your PythonAnywhere home folder.

**To update later**, double-click `Put online.bat` again. Only what changed goes up (it remembers what the last successful upload sent, in `_deploy/online-manifest.json`), and the **online database is kept**. The first update after 9 Nov 2026 sends everything once.

**Only screens or server code changed?** `Put online (1).bat` is even quicker: it sends just the changed app files (no lessons, no zips) and reloads the site. It cannot install new Python packages: use `Put online.bat` for that.

If something fails, the Web tab has an **Error log** link. Steps 1, 3 and 4 below are the same work done by hand.

## 1. Make the package (on this computer)
```
python make_deploy.py
```
It writes `_deploy\lesson-library-part-1.zip`, `-part-2.zip`, … (each under 100 MB).

## 2. Create the account
1. Go to https://www.pythonanywhere.com → **Pricing & signup** → **Create a Beginner account**.
2. Choose the username carefully: it becomes the address, e.g. `thesnezio` → `https://thesnezio.pythonanywhere.com`.

## 3. Upload and unpack
1. **Files** tab → **Upload a file**. Upload each zip from `_deploy\`.
2. **Consoles** tab → **Bash**, then type:
```
unzip -o lesson-library-part-1.zip && unzip -o lesson-library-part-2.zip && rm lesson-library-part-*.zip
```
   Add more parts to that command if there are any.

## 4. Create the web app
1. **Web** tab → **Add a new web app** → **Manual configuration** (not Flask or Django) → the newest **Python 3** offered.
2. On the Web tab, click the **WSGI configuration file** link. Replace all its content with the lines below, putting your username in the three places:
```python
import os, sys
os.environ["LIBRARY_HOSTS"] = "USERNAME.pythonanywhere.com"
os.environ["LIBRARY_HTTPS"] = "1"
sys.path.insert(0, "/home/USERNAME/lesson-library/app")
from wsgi import application  # noqa
```
3. On the Web tab, turn **Force HTTPS** on.
4. Click **Reload**, then open `https://USERNAME.pythonanywhere.com`. Sign in with the same username and password as on this computer.

## 5. Updating it later
- **Lessons changed on this computer:**
  1. Run `python make_deploy.py` again and upload the zips.
  2. Unzip, but **keep the online database**:
     `unzip -o lesson-library-part-1.zip -x lesson-library/library.db`
  3. Click **Reload** on the Web tab.
- **One main database:** the online library and the one on this computer each have their own database (classes, progress, notes, quizzes). Once you work online, treat the online one as the main one.
  - To copy it down: **Files** tab → `lesson-library/library.db` → Download.
  - Put it in the library folder while the app here is closed.
- **Backups online:** the app keeps the last 10 database backups in `lesson-library/_backups/db/`.

## Colleagues: sign-up
Each teacher has their own classes, timetable, planner, notes and quizzes. The lesson library is shared, and only you change it.
1. **E-mail (once):** in your Google account, turn on 2-Step Verification, then create an **app password** (Google Account › Security › App passwords). Online, in **Settings › Teachers › E-mail**, enter the Gmail address and that app password, then press **Send me a test**.
2. **Share the link** shown in Settings › Teachers: `https://USERNAME.pythonanywhere.com/login?signup`.
3. **Each colleague:**
   - signs up and confirms the e-mail;
   - lands on **Setup**: school, classes, timetable, first day of lessons;
   - can then use Today, the Timetable and the Planner.
4. **In Settings › Teachers you can:**
   - **give access** to a new teacher: until you do, they cannot sign in, even with a confirmed e-mail (so a student cannot sign up as a teacher);
   - confirm an account yourself (useful while e-mail is not set up);
   - turn an account off or on;
   - close sign-up.

## The SnezEdu app (Android APK)
SnezEdu installs like an app: its own icon, full screen, a navy splash screen, a bottom tab bar on phones, and students' covered lessons saved for revision without internet. The APK opens the online SnezEdu, so every `Put online.bat` update reaches it at once; a new APK is never needed for that.
1. Run `Put online.bat` (the app files must be online first).
2. Go to **pwabuilder.com**, type `https://thesnezio.pythonanywhere.com`, press **Start**, then **Package for stores › Android › Generate package**.
   - Package ID: `com.snezedu.app` · App name: `SnezEdu` · Signing key: **Create new**. Leave the rest as it is.
3. Download the zip and unzip it. Inside:
   - the `.apk` file: the app to send to students and teachers (WhatsApp, Drive…);
   - `assetlinks.json`: copy it into the library folder (next to `Put online.bat`) and run `Put online.bat` again. Without it, the app shows a thin address bar at the top;
   - the **signing key** (`signing.keystore` + `signing-key-info.txt`): keep both safe, e.g. on a USB key. They are needed to make the next version of the APK, and they cannot be made again.
4. Installing on a phone: open the `.apk`, allow "Install unknown apps" for WhatsApp/Files when Android asks, then **Install**.

Without the APK, anyone can also install SnezEdu from Chrome: open the site, menu **⋮ › Install app** (on iPhone: Safari › Share › Add to Home Screen).

## Changing lessons online
You can edit a worksheet or lesson plan online, in the lesson editor or by asking **Ask SnezEdu** (it proposes the change; press **Apply**).
- **Keep `SnezEdu helper.bat` open on your computer.** The change comes back to your computer by itself, the old file backed up first. For a lesson a class has covered, Claude then makes the new student copy, and the site gets it within a few minutes.
- If you changed the same file on your computer meanwhile, your computer's version is kept, and the online one is saved in `_backups\online-edits\`.
- `Put online.bat` brings back any online change the helper has not taken yet before uploading, so it never puts an old version back.

## Students
1. In **Settings › Students**, each class has a 6-character **class code**. Write it on the board, or press "Copy the sign-up link" (`/login?join=CODE`) and send it to the class.
2. Each student chooses **I am a student** and types the code, their first name, last name and a password. No e-mail is needed: SnezEdu gives them a username (e.g. `amine.idrissi`). If they forget their password, press **New password** next to their name.
3. They see only the lessons their class has already covered, colour-coded by skill, with the worksheets and boards, and their next quiz or test. Lesson plans and lessons still to come stay hidden.
4. **What they see** shows you the same page. **New code** stops the old code. You can also move, turn off or remove a student.
