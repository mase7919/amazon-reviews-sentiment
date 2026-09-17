# Development notes — bugs & workarounds (for the final README)

These are notes from the build process, kept so the "bugs / issues" section of the
final README reflects what actually happened.

## Step 1
- `.env` initially contained a placeholder `*<your-api-key>` (the exact text I'd put
  in an instruction) instead of the real course key -> every call returned `401
  Unauthorized`. The user replaced it with the real key from the assignment notes
  and auth succeeded. Lesson: never echo a template placeholder as the value a
  user should copy without flagging it loudly.
- Env propagation: credentials the user exported in their own shell were NOT visible
  to this agent's subprocess (env does not propagate into an already-running
  process), so we adopted a git-ignored project-local `.env` and a `load_dotenv()`
  helper (real env vars still take precedence). `.env` remains untracked.

## Step 3 (dashboard)
- **Python f-string vs CSS brace collision**: CSS braces were parsed as format
  placeholders. Fixed by keeping the CSS in a separate plain (non-f) string and
  injecting it once via `{CSS}`.
- **Donut gradient literal**: because the donut's `conic-gradient` lived in the
  non-interpolated CSS string, `{correct}%` was emitted literally instead of the
  real `98%`. Caught by a static check (the `98%` needle was MISSING), moved the
  gradient to an inline style. Confirmed `98%` renders.
- Browser backend for `browser_*` never successfully launched its Chromium (kept
  reporting "Chromium is missing" even after `playwright install chromium` and
  `agent-browser install`; the daemon likely needs an app restart to re-detect).
  Validated rendering via the Hermes desktop preview pane instead.

## Step 4 (interactive filtering)
- **Preview-cache verification issue (IMPORTANT)**: after clicking "Mismatched" in
  the preview pane, `desktop_preview read` still returned "Showing 100 of 100" and
  all rows. The read method returns what behaves like a **cached initial snapshot**
  of the page text and does NOT reflect live DOM visibility changes. This looked
  like the filter was broken, but it was a tool limitation.
- **Workaround**: verified the shipped page's own inline script with **jsdom**
  (`runScripts:'dangerously'` + real `dispatchEvent` clicks). This confirmed ALL,
  CORRECT=98, MISMATCHED=2 (rows 18 & 99), combined filters, etc. The filter logic
  itself was correct; only the preview read was misleading.

## Step 5
- NRC lexicon: used EmoLex v0.92 from Saif Mohammad's official page; kept the
  original README/EULA/readme plus a LICENSE-NOTICE for attribution.
- **LLM emotion returned EMPTY content for all 100 calls.** Root cause: Qwen3.6 is
  a *reasoning* model that first emits a long `reasoning` (thinking) field and only
  then the final answer. The Step 5 classifier had set `max_tokens=60`, which the
  model exhausted during reasoning -> `content=None`, `finish_reason=length`, every
  row → "no JSON object found in response ''". Step 2 never capped `max_tokens`, so
  it was unaffected. Fix: removed the `max_tokens` cap from
  `classify_sentiment_emotion`; the response then completes with clean JSON
  (`{"sentiment":"POSITIVE","emotion":"joy"}`). The bad rows were cleared and the
  run done again. Lesson: don't cap max_tokens on a reasoning model.

## Misc
- Some review bodies contain literal HTML entities (e.g. `4&#34;`) from the source
  data; they show as-is in the dashboard table (data quirk, not a bug).
