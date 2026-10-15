# Conquistador - Project Rules for Claude

## What this project is

A Python/pygame quiz game where players buzz in to answer questions and claim
regions on a map. Questions and answers are game content.

## Protecting answers and content

- Never print, log, or display correct answers in code, comments, debug output,
  or test output that could be committed.
- Questions and answers live only in `data/questions.json`. Do not copy answer
  values into Python source files, README files, or commit messages.
- Do not generate or add new questions without flagging them for human review.
  Mark any AI-written questions with `"reviewed": false` until the owner approves.

## Secrets and credentials

- Never write API keys, tokens, passwords, or `.env` contents into any file.
- If a secret appears in the code or terminal output, stop and tell the owner
  instead of committing it.
- Do not modify `.gitignore` to un-ignore `.env`, `*.key`, or `secrets/`.

## Git and GitHub

- Never run `git push --force`, `git reset --hard` on shared branches, or
  delete branches without asking first.
- Do not push directly to `main`. Create a feature branch and tell the owner
  to open a pull request.
- Before every commit, run `git status` and `git diff --staged` and confirm
  no unexpected files (large binaries, `__pycache__/`, `.env`, local saves)
  are included.
- Do not commit files listed in `.gitignore`. If a file should be ignored
  and isn't, add it to `.gitignore` and tell the owner.
- Write commit messages that describe the change without revealing answers
  or question text.

## Code changes

- Keep the game loop, rendering, and question logic in separate modules.
- Do not add network calls, telemetry, or auto-update code without asking.
  LAN-only networking for rooms is approved (TCP 5555 for the game, UDP 5556
  for room discovery). No internet calls.
- The host (`net/server.py`) is authoritative: only it holds answers and judges
  them. Clients receive questions without the `answer` field.
- Do not change the answer-checking logic to accept answers from the client
  in a way that could be spoofed without explaining the change first.

## Before finishing a task

- Run the game and any tests to confirm nothing is broken.
- Summarize what changed and list any files that need owner review.
