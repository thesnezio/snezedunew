# Lesson Library: project guide for Claude Code

Owner: Youssef Nejjar, teacher of English.
School: Lycée Taha Hussein (الثانوية التأهيلية طه حسين), Aïn Mdboune, Meknès-Fès region (Fès-Meknès). School year 2026-2027.
Timetable approved 26 Sept 2026.

## Start here (saves tokens)
- For code work, read `CODE_MAP.md` first: it says which file and function to open.
- Never read `PROJECT_NOTES.md`, `app/server.py` or `app/ui/app.js` whole. Search them, then read only the part you need. "Next three tasks" and the current state are in `PROJECT_NOTES.md` (search `^## Current state`).
- Last known good code: `_backups\2026-11-04-good-version\`.
- Delegate every repo search and test run to the Haiku 5.5 subagents (`search`, `grep`, `audit`) to keep the main context small.

## What this folder is
A library of ECRIF lesson plans and worksheets (self-contained, editable HTML), plus a platform that indexes them.

```
1st BAC\Unit N - Name\<n Skill>\Lesson Plan.html + Worksheet.html   (9 units, 53 lessons)
Common Core\Unit N - Name\<n Skill>\Lesson Plan.html + Worksheet.html   (9 units, 57 lessons)
1st BAC\Homework\*.pdf        Ticket 1.pdf and Outlook.pdf are the course books (do not index)
index.html                    the platform (single file, data embedded, works offline)
lessons.json                  the index (single source of truth for the platform)
skills\                      my three teaching skills (see below)
```

## My skills (run them by name)
The skill files are in `skills\<name>\SKILL.md`. On first run in Claude Code, copy that `skills` folder to `.claude\skills` so the slash commands work (I could not write to `.claude` from the web app). Until then, read the matching SKILL.md before doing that kind of task.
- `/unit-creation`: create a whole unit (one 55-minute plan + worksheet per lesson) from my book maps and saved model library.
- `/board-layout`: colourful editable whiteboard summary (PNG + editable HTML) for any lesson.
- `/unit-copybook-notes`: max-3-page colour summary of a whole unit for students' copybooks.
- `/quiz-creation`: a quiz or global test (/20, with answer key) from my own lessons, saved as HTML and in the app's Saved quizzes.
After creating or changing any lesson, rebuild the index (see Rules).

## My classes and timetable (2026-2027)
Weekly total shown on the official timetable: 21 h. Class codes are exactly as the school wrote them.

| Day | Time | Class | Room |
|---|---|---|---|
| Monday | 09:00-10:00 | 1BACSE1 | S1 |
| Monday | 10:00-11:00 | 1BACSE3 | S1 |
| Tuesday | 14:00-15:00 | TCSF6 | S15 |
| Tuesday | 15:00-16:00 | 1BACSE1 | S15 |
| Tuesday | 16:00-17:00 | TCSF2 | S15 |
| Tuesday | 17:00-18:00 | TCSF5 | S15 |
| Wednesday | 08:00-09:00 | TCSF5 | S9 |
| Wednesday | 09:00-10:00 | TCSF6 | S9 |
| Wednesday | 10:00-11:00 | 1BACSE3 | S9 |
| Wednesday | 11:00-12:00 | TCSF2 | S9 |
| Thursday | 16:00-17:00 | 1BACSE1 | Activities (الأنشطة), 1 h |
| Thursday | 17:00-18:00 | 1BACSE3 | Activities (الأنشطة), 1 h |
| Friday | 15:00-16:00 | TCSF5 | S10 |
| Friday | 16:00-17:00 | TCSF2 | S10 |
| Friday | 17:00-18:00 | TCSF6 | S10 |
| Saturday | none | | |

Classes taught: TCSF2, TCSF5, TCSF6 (Common Core) and 1BACSE1, 1BACSE3 (1st BAC).
Per week: every class has 3 sessions. "Activities" (الأنشطة) on Thursday is a room; those are normal lessons (corrected 30 Oct 2026).
Lessons started on 28 Sept 2026. The app (`Start Library.bat`) holds the live timetable, holidays, leave, exam plan and each class's position; read PROJECT_NOTES.md for how it works.
Use this for the planner, the "Today" screen and pacing checks. Ask me before assuming holidays or exam dates.

## Rules (always)
1. Never rewrite or restyle lesson HTML. Edit only the lines I ask for; back up the file first.
2. Save tokens: read `lessons.json` first, then open only the file you need. Strip `<script>`, `<style>` and base64 data before reading a lesson. Use scripts for bulk work.
3. Never delete files. Move them to `_to_delete\` and tell me.
4. The platform must work offline by double-clicking `index.html` and also upload unchanged to GitHub Pages (relative links only).
5. `lessons.json` is the single source of truth. A script (`build_index.py`) must regenerate it and `index.html`; never edit the index by hand.
6. Every lesson is 55 minutes and follows ECRIF. Keep my saved models and tools, as the skills describe.
7. Finish each session by updating `PROJECT_NOTES.md`: what exists, how to rebuild, open issues, next three tasks.

## Known issues (as of 30 Oct 2026)
- Fixed 30 Oct 2026: Common Core Unit 1 "1 Vocabulary" is now the real lesson (People, Titles & Greetings); the misspelled `Lesosn Plan.html` is gone.
- This folder (working copy) is the main library; `..\Worksheets - Lesson Plans` is the old backup.
- Early Unit 1 plans are about 2.6 MB each because of embedded script. Slim them only when I ask.

## Platform design (keep consistent)
Whiteboard white and marker navy. Skill colours: Vocabulary teal, Functions violet, Reading blue, Grammar orange, Writing pink. Fonts: Bricolage Grotesque + Figtree with system fallbacks. One strip of coloured tiles per unit. Calm, accessible, responsive to phone width, dark mode, Student view (worksheets only).

## Using the skills inside Claude Code
The skills were written for Claude's cloud workspace and mention paths like `/mnt/user-data/outputs/`. When you run them here, ignore those paths: save every result inside the matching lesson or unit folder on this computer (for example the board PNG + HTML next to `Lesson Plan.html`), then rebuild the index.
