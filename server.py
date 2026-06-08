import imaplib
import smtplib
import email
import os
import json
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from datetime import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load .env sitting next to this file (works regardless of the launcher's CWD)
load_dotenv(Path(__file__).resolve().parent / ".env")

# ── Config (all from env vars, never hardcoded) ──────────────────────────────
IMAP_HOST = "poczta.agh.edu.pl"
IMAP_PORT = 993
SMTP_HOST = "poczta.agh.edu.pl"
SMTP_PORT = 465

AGH_EMAIL    = os.environ["AGH_EMAIL"]        # e.g. your_id@student.agh.edu.pl
AGH_APP_PASS = os.environ["AGH_APP_PASS"]     # app password from AGH Webmail panel
MCP_TOKEN    = os.environ.get("MCP_TOKEN")    # optional; only used for future network hosting

# ── FastMCP app ──────────────────────────────────────────────────────────────
mcp = FastMCP(
    "agh-mail",
    instructions=(
        "Tools for reading and sending email via the AGH University mailbox. "
        "Always call get_unread_emails first for a morning briefing. "
        "Use get_email_body only when you need the full content of a specific message. "
        "Never send email without explicit user confirmation."
    ),
)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _decode_header_value(raw: str) -> str:
    """Decode RFC2047-encoded email headers to plain text."""
    parts = decode_header(raw or "")
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _connect_imap() -> imaplib.IMAP4_SSL:
    """Open an authenticated IMAP connection."""
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(AGH_EMAIL, AGH_APP_PASS)
    return conn


def _parse_envelope(msg: email.message.Message) -> dict:
    """Extract key headers from an email.message object."""
    return {
        "from":    _decode_header_value(msg.get("From", "")),
        "to":      _decode_header_value(msg.get("To", "")),
        "subject": _decode_header_value(msg.get("Subject", "(no subject)")),
        "date":    msg.get("Date", ""),
    }


def _get_text_body(msg: email.message.Message) -> str:
    """Extract plain-text body, falling back to HTML stripped of tags."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                return part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace"
                )
        # fallback: first HTML part
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                raw = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace"
                )
                return re.sub(r"<[^>]+>", "", raw)
    else:
        return msg.get_payload(decode=True).decode(
            msg.get_content_charset() or "utf-8", errors="replace"
        )
    return ""

# ── MCP Tools ────────────────────────────────────────────────────────────────

@mcp.tool()
def get_unread_emails(
    folder: str = "INBOX",
    max_results: int = 20,
) -> str:
    """
    Return a list of unread emails (sender, subject, date, short preview).
    Use this for the morning briefing. Default folder is INBOX.
    Returns JSON array of message objects with uid, from, subject, date, preview.
    """
    conn = _connect_imap()
    try:
        conn.select(folder, readonly=True)
        _, data = conn.search(None, "UNSEEN")
        uids = data[0].split()
        if not uids:
            return json.dumps({"count": 0, "messages": []})

        uids = uids[-max_results:]  # most recent N
        results = []
        for uid in reversed(uids):
            _, msg_data = conn.fetch(uid, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            envelope = _parse_envelope(msg)
            body = _get_text_body(msg)
            preview = body.strip()[:200].replace("\n", " ") if body else ""
            results.append({
                "uid":     uid.decode(),
                "from":    envelope["from"],
                "subject": envelope["subject"],
                "date":    envelope["date"],
                "preview": preview,
            })

        return json.dumps({"count": len(results), "messages": results}, ensure_ascii=False)
    finally:
        conn.logout()


@mcp.tool()
def get_email_body(uid: str, folder: str = "INBOX") -> str:
    """
    Fetch the full body of a specific email by its UID.
    Get the UID from get_unread_emails or search_emails first.
    Returns JSON with full headers and body text.
    """
    conn = _connect_imap()
    try:
        conn.select(folder, readonly=True)
        _, msg_data = conn.fetch(uid.encode(), "(RFC822)")
        if not msg_data or msg_data[0] is None:
            return json.dumps({"error": f"Message UID {uid} not found in {folder}"})
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        envelope = _parse_envelope(msg)
        body = _get_text_body(msg)
        return json.dumps({
            **envelope,
            "uid":  uid,
            "body": body,
        }, ensure_ascii=False)
    finally:
        conn.logout()


@mcp.tool()
def search_emails(
    sender: Optional[str] = None,
    subject: Optional[str] = None,
    since_date: Optional[str] = None,
    folder: str = "INBOX",
    max_results: int = 10,
) -> str:
    """
    Search emails by sender address, subject keyword, and/or date.
    since_date format: YYYY-MM-DD (e.g. '2025-09-01').
    Returns JSON array with uid, from, subject, date, preview.
    """
    conn = _connect_imap()
    try:
        conn.select(folder, readonly=True)

        criteria = []
        if sender:
            criteria.append(f'FROM "{sender}"')
        if subject:
            criteria.append(f'SUBJECT "{subject}"')
        if since_date:
            # IMAP date format: 01-Jan-2025
            dt = datetime.strptime(since_date, "%Y-%m-%d")
            imap_date = dt.strftime("%d-%b-%Y")
            criteria.append(f'SINCE {imap_date}')

        search_str = " ".join(criteria) if criteria else "ALL"
        _, data = conn.search(None, search_str)
        uids = data[0].split()

        if not uids:
            return json.dumps({"count": 0, "messages": []})

        uids = uids[-max_results:]
        results = []
        for uid in reversed(uids):
            _, msg_data = conn.fetch(uid, "(RFC822.HEADER)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            envelope = _parse_envelope(msg)
            results.append({
                "uid":     uid.decode(),
                "from":    envelope["from"],
                "subject": envelope["subject"],
                "date":    envelope["date"],
            })

        return json.dumps({"count": len(results), "messages": results}, ensure_ascii=False)
    finally:
        conn.logout()


@mcp.tool()
def mark_as_read(uid: str, folder: str = "INBOX") -> str:
    """
    Mark a specific email as read (sets the \\Seen flag).
    Call this after processing a message in the morning briefing.
    """
    conn = _connect_imap()
    try:
        conn.select(folder)
        conn.store(uid.encode(), "+FLAGS", "\\Seen")
        return json.dumps({"success": True, "uid": uid, "folder": folder})
    finally:
        conn.logout()


@mcp.tool()
def send_email(
    to: str,
    subject: str,
    body: str,
    reply_to_uid: Optional[str] = None,
) -> str:
    """
    Send an email from your AGH address.
    IMPORTANT: Only call this after the user has explicitly confirmed the content.
    reply_to_uid: if replying, provide the UID to set correct threading headers.
    """
    msg = MIMEMultipart("alternative")
    msg["From"]    = AGH_EMAIL
    msg["To"]      = to
    msg["Subject"] = subject

    # Fetch original subject for threading if replying
    if reply_to_uid:
        try:
            conn = _connect_imap()
            conn.select("INBOX", readonly=True)
            _, msg_data = conn.fetch(reply_to_uid.encode(), "(RFC822.HEADER)")
            orig = email.message_from_bytes(msg_data[0][1])
            msg_id = orig.get("Message-ID", "")
            if msg_id:
                msg["In-Reply-To"] = msg_id
                msg["References"]  = msg_id
            conn.logout()
        except Exception:
            pass  # threading headers are best-effort

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(AGH_EMAIL, AGH_APP_PASS)
        smtp.sendmail(AGH_EMAIL, to, msg.as_string())

    return json.dumps({
        "success": True,
        "from":    AGH_EMAIL,
        "to":      to,
        "subject": subject,
    })


@mcp.tool()
def get_folders() -> str:
    """
    List all IMAP folders in the AGH mailbox.
    Useful for finding where specific mail (spam, sent, etc.) lives.
    """
    conn = _connect_imap()
    try:
        _, folder_list = conn.list()
        folders = []
        for item in folder_list:
            parts = item.decode().split('"/"')
            name = parts[-1].strip().strip('"')
            folders.append(name)
        return json.dumps({"folders": folders})
    finally:
        conn.logout()


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # stdio mode for local use; for cloud deployment use SSE transport
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
