# AGH Morning Mail Briefing

## Purpose
Read new AGH university email every morning and produce a concise briefing,
flagging anything that needs action today.

## When to run
Trigger this skill at the start of each day, or when the user says
"check my uni mail", "morning briefing", "any new emails from AGH", etc.

## Steps

1. Call `get_unread_emails` with default settings (INBOX, max 20).

2. If count is 0, report: "No new emails in your AGH inbox." Stop.

3. For each message, classify it into one of:
   - 🔴 **Action needed** — deadlines, exam registration, payment, reply required
   - 🟡 **Worth reading** — announcements, schedule changes, professor updates
   - ⚪ **Low priority** — newsletters, automated notifications, mass emails

4. Present the briefing in this format:

---
**AGH Mail — [today's date] — [N] new messages**

🔴 Action needed (X)
- [Subject] from [Sender] — [one sentence why it needs action]

🟡 Worth reading (X)
- [Subject] from [Sender] — [one sentence summary]

⚪ Low priority (X) — skipped unless user asks

---

5. If any 🔴 item exists, ask: "Want me to open any of these in full?"

6. After presenting the briefing, call `mark_as_read` for all processed UIDs
   so they don't appear again tomorrow. Ask user to confirm before marking.

## Tone
Concise, neutral. Think daily digest, not essay. One sentence per email max
unless the user asks to open a specific one.

## Important rules
- Never call `send_email` without the user explicitly approving the full text.
- If an email body is needed to classify it, call `get_email_body` for that UID only.
- Subjects/senders may be in Polish — classify them the same way.
