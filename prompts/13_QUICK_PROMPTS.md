# Copy-paste helpers for common moments

## "It doesn't work" (paste error + 40 lines around it)
Given this error and code, list 3 ranked hypotheses (most likely first, one line each, cite the line).
Then output the fix for hypothesis #1 ONLY, as a complete file/function per RULES. Then a VERIFY command.

## "Explain this file before I change it"
Summarize this file in ≤10 bullets: purpose, public functions (name + params + return), what imports it
(guess and mark as GUESS), external calls, failure modes. No suggestions yet.

## "Split this task"
This task touches >4 files. Split it into ordered sub-tasks of ≤3 files each, with the verify command for
each and the dependency between them. Output only the list.

## "Sync the TS types"
Here is OUTPUT_SCHEMA (pydantic). Output the matching TypeScript interface for frontend/src/types/agents.ts.
Optional → `| null`, list → array, dict → Record<string, unknown>. Nothing else.

## "Write the migration"
Here is the SQLAlchemy model diff. Output supabase/migrations/0033_<name>.sql: idempotent (IF NOT EXISTS),
RLS enable + policies (select/insert/update/delete own rows by supabase_uid via auth.uid()), indexes,
and a DOWN section as comments.

## "Commit message"
From this diff, output one conventional commit: type(scope): imperative summary ≤72 chars, blank line,
3 bullets max of WHAT changed (not why), footer "Verify: <command>".

---

## How to actually run this (short version)
- Create D:\CareerCraft AI\prompts\ and save the 14 files above (00 through 13), plus copy HANDOFF.md as 99_HANDOFF_2026-09-06.md for reference.
- Do Phase 0 yourself with the model tonight — it is mostly .env alignment. Nothing else matters until /health is green and SSE doesn't crash.
- Phase 1 is a conversation, not code: get the inventory table, approve it, then move files.
- Phase 2 is the whole game. Spend the most effort here. Once resume-optimize works in a browser with live SSE and a PDF download, you have a template every other agent copies.
- Then loop 07 fourteen times, 08 fourteen times, running 10_REVIEWER after each. Fresh chat every time; paste 01 + 02 + the task + the real files.
- Small models drift over long chats — that's why the kit is "one narrow task, one verify command, one commit". If you follow that, output quality is limited by your verification loop, not by model size.
