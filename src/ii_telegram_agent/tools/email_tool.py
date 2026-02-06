"""
Email Tool - Gmail integration for email triage and management.

Supports:
- Reading unread emails
- Sending emails
- Email triage (categorization, priority)
- Inbox summary
"""

import base64
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional

from .base import Tool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


@dataclass
class Email:
    """Represents an email message."""
    id: str
    thread_id: str
    subject: str
    sender: str
    recipient: str
    date: str
    snippet: str
    body: str = ""
    labels: list[str] = None
    is_unread: bool = False

    def __post_init__(self):
        if self.labels is None:
            self.labels = []


class GmailClient:
    """Gmail API client wrapper."""

    def __init__(self, credentials_path: Optional[str] = None):
        self.credentials_path = credentials_path or os.getenv(
            "GMAIL_CREDENTIALS_PATH",
            str(Path.home() / ".ii-telegram-agent" / "gmail_credentials.json")
        )
        self.token_path = str(Path(self.credentials_path).parent / "gmail_token.json")
        self._service = None
        self._initialized = False

    def _get_service(self):
        """Get or create Gmail API service."""
        if self._service:
            return self._service

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build

            creds = None

            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                elif os.path.exists(self.credentials_path):
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                    with open(self.token_path, "w") as token:
                        token.write(creds.to_json())
                else:
                    raise FileNotFoundError(
                        f"Gmail credentials not found at {self.credentials_path}. "
                        "Please set up Gmail API credentials."
                    )

            self._service = build("gmail", "v1", credentials=creds)
            self._initialized = True
            return self._service

        except ImportError:
            raise ImportError(
                "Gmail dependencies not installed. "
                "Run: pip install google-auth-oauthlib google-api-python-client"
            )

    def is_configured(self) -> bool:
        """Check if Gmail is configured."""
        return os.path.exists(self.credentials_path) or os.path.exists(self.token_path)

    def get_unread_emails(self, max_results: int = 10) -> list[Email]:
        """Get unread emails from inbox."""
        service = self._get_service()
        
        results = service.users().messages().list(
            userId="me",
            q="is:unread",
            maxResults=max_results,
        ).execute()

        messages = results.get("messages", [])
        emails = []

        for msg in messages:
            email_data = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            ).execute()

            headers = {h["name"]: h["value"] for h in email_data.get("payload", {}).get("headers", [])}

            emails.append(Email(
                id=msg["id"],
                thread_id=msg.get("threadId", ""),
                subject=headers.get("Subject", "(No Subject)"),
                sender=headers.get("From", ""),
                recipient=headers.get("To", ""),
                date=headers.get("Date", ""),
                snippet=email_data.get("snippet", ""),
                labels=email_data.get("labelIds", []),
                is_unread="UNREAD" in email_data.get("labelIds", []),
            ))

        return emails

    def get_inbox_summary(self, hours: int = 24) -> dict:
        """Get a summary of inbox activity."""
        service = self._get_service()
        
        unread = service.users().messages().list(
            userId="me",
            q="is:unread",
            maxResults=100,
        ).execute()

        total_unread = unread.get("resultSizeEstimate", 0)
        
        recent = service.users().messages().list(
            userId="me",
            q=f"newer_than:{hours}h",
            maxResults=100,
        ).execute()

        recent_count = recent.get("resultSizeEstimate", 0)

        important = service.users().messages().list(
            userId="me",
            q="is:unread is:important",
            maxResults=10,
        ).execute()

        important_count = len(important.get("messages", []))

        return {
            "total_unread": total_unread,
            "recent_emails": recent_count,
            "important_unread": important_count,
        }

    def send_email(self, to: str, subject: str, body: str) -> dict:
        """Send an email."""
        service = self._get_service()

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        result = service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()

        return result

    def mark_as_read(self, message_id: str) -> bool:
        """Mark an email as read."""
        service = self._get_service()
        
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()
        
        return True

    def archive_email(self, message_id: str) -> bool:
        """Archive an email (remove from inbox)."""
        service = self._get_service()
        
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["INBOX"]},
        ).execute()
        
        return True


_gmail_client: Optional[GmailClient] = None


def get_gmail_client() -> GmailClient:
    """Get or create Gmail client singleton."""
    global _gmail_client
    if _gmail_client is None:
        _gmail_client = GmailClient()
    return _gmail_client


async def check_email_handler(max_results: int = 5) -> ToolResult:
    """Check for unread emails."""
    try:
        client = get_gmail_client()
        
        if not client.is_configured():
            return ToolResult(
                success=False,
                error="Gmail is not configured. Please set up Gmail API credentials."
            )
        
        emails = client.get_unread_emails(max_results)
        
        if not emails:
            return ToolResult(success=True, output="No unread emails.")
        
        output_lines = [f"**{len(emails)} Unread Email(s):**\n"]
        for email in emails:
            output_lines.append(
                f"- **{email.subject}**\n"
                f"  From: {email.sender}\n"
                f"  {email.snippet[:100]}..."
            )
        
        return ToolResult(success=True, output="\n".join(output_lines))
    
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def inbox_summary_handler(hours: int = 24) -> ToolResult:
    """Get inbox summary."""
    try:
        client = get_gmail_client()
        
        if not client.is_configured():
            return ToolResult(
                success=False,
                error="Gmail is not configured. Please set up Gmail API credentials."
            )
        
        summary = client.get_inbox_summary(hours)
        
        output = f"""**Inbox Summary (last {hours} hours):**
- Total unread: {summary['total_unread']}
- New emails: {summary['recent_emails']}
- Important unread: {summary['important_unread']}"""
        
        return ToolResult(success=True, output=output)
    
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def send_email_handler(to: str, subject: str, body: str) -> ToolResult:
    """Send an email."""
    try:
        client = get_gmail_client()
        
        if not client.is_configured():
            return ToolResult(
                success=False,
                error="Gmail is not configured. Please set up Gmail API credentials."
            )
        
        result = client.send_email(to, subject, body)
        
        return ToolResult(
            success=True,
            output=f"Email sent successfully to {to}. Message ID: {result.get('id', 'unknown')}"
        )
    
    except Exception as e:
        return ToolResult(success=False, error=str(e))


def create_email_tools() -> list[Tool]:
    """Create email-related tools."""
    check_email = Tool(
        name="check_email",
        description="Check for unread emails in Gmail inbox. Returns a summary of recent unread messages.",
        parameters=[
            ToolParameter(
                name="max_results",
                param_type="integer",
                description="Maximum number of emails to return (default: 5)",
                required=False,
            ),
        ],
        handler=check_email_handler,
    )

    inbox_summary = Tool(
        name="inbox_summary",
        description="Get a summary of Gmail inbox activity including unread count and important emails.",
        parameters=[
            ToolParameter(
                name="hours",
                param_type="integer",
                description="Time period to summarize in hours (default: 24)",
                required=False,
            ),
        ],
        handler=inbox_summary_handler,
    )

    send_email = Tool(
        name="send_email",
        description="Send an email via Gmail.",
        parameters=[
            ToolParameter(
                name="to",
                param_type="string",
                description="Recipient email address",
                required=True,
            ),
            ToolParameter(
                name="subject",
                param_type="string",
                description="Email subject line",
                required=True,
            ),
            ToolParameter(
                name="body",
                param_type="string",
                description="Email body content",
                required=True,
            ),
        ],
        handler=send_email_handler,
    )

    return [check_email, inbox_summary, send_email]