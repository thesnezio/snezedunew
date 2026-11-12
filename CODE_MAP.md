# Code map: where to look first

Use this to open the fewest files. Find things by function name; line numbers change.
Do not read `PROJECT_NOTES.md` whole (about 30,000 tokens): list its headings with a search for `^## `, then read only the part you need.

## Big files: search them, do not read them whole
| File | Size | Holds |
|---|---|---|
| `app/ui/app.js` | 250 KB | all teacher screens |
| `app/server.py` | 188 KB | API, jobs, routes (`ROUTES`, `Handler`) |
| `app/ui/app.css` | 87 KB | styles |
| `app/ui/student.html` | 65 KB | student page |
| `app/tickets.py` | 49 KB | Practice and unit checkpoints |
| `app/db.py` | 48 KB | `MIGRATIONS` (append only), backups, seed data |
| `lessons.json` | 305 KB | lesson index: read this first for lesson questions |
| `index.html`, `search.json`, `library.db` | | generated or data: do not read |

## Find it by task
| Task | Start at |
|---|---|
| New API route | `ROUTES` in `app/server.py` |
| Database change | append to `MIGRATIONS` in `app/db.py` |
| Quiz made by AI | `api_quiz_auto`, `run_quiz_job`, `doc_request` in `app/server.py`; `app/quizzes.py`, `app/tests.py` |
| Review made by AI | `api_review_auto`, `run_review_job`, `doc_request`, `REVIEW_FIT` in `app/server.py`; `app/reviews.py` |
| Anticipated challenges | `app/challenges.py`; `api_challenges_make` in `app/server.py` |
| Boards / homework | `app/boards.py` / `app/homework.py` |
| Ask SnezEdu chat | `app/chat.py`, `app/CHAT_GUIDE.md`; `api_chat_send` in `app/server.py`; `app/ui/page-chat.js` |
| Which computer or key runs a request | `claude_route` in `app/server.py`; `submit` in `app/ai.py` |
| Requests waiting online | `app/relay.py` (`submit`, `next_job`, `done`, `cancel`, `RETAKE_MINUTES`) |
| Helper window on this PC | `app/helper.py` (`main`, `do_batch`, `do_chat`, `do_sync`, `run_live`, `send_answer`) |
| Gemini command and answer | `gemini_prompt`, `gemini_result`, `gemini_finished` in `app/chat.py` |
| Student pages and access | `student_page`, `Handler.student_route` in `app/server.py`; `build_student_worksheets.py` |
| Lessons rebuilt after an edit | `reindex`, `refresh_student_copies`, `sync_changes` in `app/server.py`; `build_index.py` |
| Record book tool / data in it | `app/recordbook.py`, `/recordbook` route in `app/server.py`, `tools/record-book/` |
| New school year from a PDF/Excel | `app/calfile.py`; `api_calfile_*` in `app/server.py`; `cfInner` in `app/ui/app.js` (Setup › Holidays) |
| Setup from a timetable file (AI draft) | `app/ttfile.py`; `api_ttfile_*` in `app/server.py`; `ttInner`, `ttApply` in `app/ui/app.js` (Setup › Timetable) |
| AI engine + model per tool | `CHOICES`, `chosen`, `cli_model` in `app/ai.py`; `ai_model` in `app/server.py`; `aiPick`, `aiModel` in `app/ui/app.js` |
| Morning / afternoon timing | `api_timing` in `app/server.py`; `suTiming`, `suStart`, `SU_AM`/`SU_PM` in `app/ui/app.js` |
| Grading sheets (Word/PDF/Excel) | `app/gradesheet.py`; `api_gs_*` in `app/server.py`; `gradeSheetsTab` in `app/ui/app.js`; template in `tools/grading-sheets/` |
| Reports (Word/PDF), Word to PDF | `app/reports.py`, `app/officepdf.py`; `api_reports_*` in `app/server.py`; `reportsTab` in `app/ui/app.js`; templates in `tools/reports/` |
| The one logo (Setup) | `suLogo` in `app/ui/app.js`; `custom_logo` in `app/gradesheet.py` |
| Upload to the site | `Put online.bat`, `make_deploy.py`, `upload_pythonanywhere.py`, `DEPLOY.md` |
| Tests | `tests/` |

## How an online AI request travels
Website page -> `app/server.py` -> `ai.submit` -> `relay.submit` (queued on the site) -> helper on this PC asks `relay/next` every 10 s -> `do_batch` runs Claude or Gemini in an empty temp folder -> `send_answer` posts `relay/done` -> the page shows the result.

Two limits to remember:
- The helper handles one request at a time, so the others wait behind it.
- The site allows one quiz or review job at a time. A request taken but never answered goes back to the queue after 20 minutes (`RETAKE_MINUTES`).

## Gemini (agy CLI) facts learned the hard way
- `agy -p` does not read stdin. Prompts of 25,000+ characters must use `--input-format stream-json --output-format stream-json`, with `{"event":"user","message":{"content":...}}` on stdin.
- agy can stay open after it has answered. Its final result line is the sign that it finished.
- Its tools cannot be switched off here. The no-tools sentence in the prompt is an instruction, not a lock.
- To see what a run really did: `%USERPROFILE%\.gemini\antigravity-cli\brain\<id>\.system_generated\logs\transcript.jsonl`, and `...\antigravity-cli\log\cli-*.log`. "You are not logged into Antigravity" at the start of a log is normal.

## After changing code
- Helper code (`helper.py`, `chat.py` as the helper uses it): restart `SnezEdu helper.bat`. The running window keeps the old code.
- Local app: restart `Start Library.bat`.
- Code that runs on the site: `Put online.bat`.
- Back up what you edit to `_backups\<date>-ai\`, and add a short section to `PROJECT_NOTES.md`.
