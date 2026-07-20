# Project Instructions for Claude Code

## Facebook Messenger code is frozen — ask before editing

All Facebook Messenger logic (webhook verification, HMAC signature checks,
Send API calls, FB Lite fallback handling, message dedup, `/webhook` and
`/chatbot/webhook` routes) lives in **`src/controllers/chat_controller.py`**.
This also includes the related launch/deploy scripts:
`scripts/RUN_FACEBOOK_BOT.ps1`, `scripts/START_FACEBOOK_BOT.bat`,
`config/chatbot.service`.

**Rule:** never edit any of those files without first explicitly asking the
user for permission in the conversation and getting an explicit yes. This
applies even when a task looks like it requires a change there — stop and
ask instead of proceeding. If the user says no or doesn't respond, do not
make the edit.

**Not covered by this rule:** *reading* or *importing* from
`chat_controller.py` (e.g. reusing the shared `_process_user_message(...)`
pipeline from a new module) is fine and does not require permission — only
edits/writes to the file itself do.

This rule is also enforced mechanically via a `permissions.ask` entry in
`.claude/settings.json` scoped to `src/controllers/chat_controller.py`.

## Language

All chatbot-facing replies (the bot's own output to end users) must be in
Bangla, never English.
