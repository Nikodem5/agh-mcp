# AGH Mail MCP Server

A small [MCP] server that lets **Claude** read and
send email from your AGH mailbox (`poczta.agh.edu.pl`) 

Ask Claude things like *"any new emails"* or *"reply to the professor saying I'll attend"*

> **Status:** Local use with **Claude Desktop** is fully supported and is what this
> README covers. Remote hosting (so it works in the Claude mobile/web app or Cowork)
> is not supported yet.

---

## Tools exposed

| Tool | What it does |
|---|---|
| `get_unread_emails` | List unread messages |
| `get_email_body` | Fetch the full body of one message |
| `search_emails` | Search by sender, subject, and/or date |
| `mark_as_read` | Mark a message as read |
| `send_email` | Send from your AGH address (only after you confirm) |
| `get_folders` | List all IMAP folders in the mailbox |

---

## Prerequisites

- Python 3.10 or newer
- An AGH mailbox at `poczta.agh.edu.pl`
- Claude Desktop installed

---

## Setup

### Step 1 - Generate an AGH app password

1. Log into <https://poczta.agh.edu.pl>
2. Go to **Ustawienia → Hasła do aplikacji**
3. Enter your password to authorize, give the new password a name
4. Copy the generated password (you'll only see it once)

### Step 2 - Clone and install

```bash
git clone https://github.com/Nikodem5/agh-mcp.git
cd agh-mcp
python -m venv .venv
(activate the virtual environment)
pip install -r requirements.txt
```

### Step 3 - Configure your credentials

Copy the example file and fill in your two values:

```bash
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
```

Edit `.env`:

```env
AGH_EMAIL=123456@student.agh.edu.pl
AGH_APP_PASS=the_app_password_from_step_1
```

### Step 4 - Connect it to Claude Desktop

Open your Claude Desktop config file (create it if it doesn't exist):

Add an entry pointing at the absolute path to `server.py`

```json
{
  "mcpServers": {
    "agh-mail": {
      "command": "python",
      "args": ["/absolute/path/to/agh-mcp/server.py"]
    }
  }
}
```

Fully quit and reopen Claude Desktop.

---

## Extending: "university agent" ideas

This is a foundation. Each new capability is just one Python function with an
`@mcp.tool()` decorator. Ideas:

- `get_calendar` — pull your AGH timetable from USOS
- `check_grades` — watch USOS for new grade entries
- `get_deadlines` — parse the UPeL e-learning platform for upcoming deadlines
- `search_library` — query the AGH library catalog

---

## Project structure

```
agh-mcp/
├── server.py                        # the MCP server (all tools live here)
├── requirements.txt                 # mcp + python-dotenv
├── .env.example                     # template — copy to .env and fill in
├── .env                             # your secrets (git-ignored, never committed)
├── .gitignore
├── cowork-skill-morning-briefing.md # optional daily-digest skill
└── README.md
```
