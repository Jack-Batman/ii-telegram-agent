"""
Calendar Tool - Google Calendar integration.

Supports:
- Listing upcoming events
- Creating events
- Getting daily schedule
- Finding free time slots
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .base import Tool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


@dataclass
class CalendarEvent:
    """Represents a calendar event."""
    id: str
    summary: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    description: Optional[str] = None
    attendees: list[str] = None
    is_all_day: bool = False

    def __post_init__(self):
        if self.attendees is None:
            self.attendees = []

    def format_time(self) -> str:
        """Format event time for display."""
        if self.is_all_day:
            return "All day"
        return f"{self.start.strftime('%H:%M')} - {self.end.strftime('%H:%M')}"

    def duration_minutes(self) -> int:
        """Get event duration in minutes."""
        return int((self.end - self.start).total_seconds() / 60)


class GoogleCalendarClient:
    """Google Calendar API client wrapper."""

    def __init__(self, credentials_path: Optional[str] = None):
        self.credentials_path = credentials_path or os.getenv(
            "GOOGLE_CREDENTIALS_PATH",
            str(Path.home() / ".ii-telegram-agent" / "google_credentials.json")
        )
        self.token_path = str(Path(self.credentials_path).parent / "calendar_token.json")
        self._service = None
        self._initialized = False

    def _get_service(self):
        """Get or create Calendar API service."""
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
                        f"Google credentials not found at {self.credentials_path}. "
                        "Please set up Google Calendar API credentials."
                    )

            self._service = build("calendar", "v3", credentials=creds)
            self._initialized = True
            return self._service

        except ImportError:
            raise ImportError(
                "Google Calendar dependencies not installed. "
                "Run: pip install google-auth-oauthlib google-api-python-client"
            )

    def is_configured(self) -> bool:
        """Check if Calendar is configured."""
        return os.path.exists(self.credentials_path) or os.path.exists(self.token_path)

    def _parse_event(self, event: dict) -> CalendarEvent:
        """Parse API event to CalendarEvent object."""
        start_data = event.get("start", {})
        end_data = event.get("end", {})

        is_all_day = "date" in start_data

        if is_all_day:
            start = datetime.fromisoformat(start_data["date"])
            end = datetime.fromisoformat(end_data["date"])
        else:
            start = datetime.fromisoformat(start_data.get("dateTime", "").replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_data.get("dateTime", "").replace("Z", "+00:00"))
            start = start.replace(tzinfo=None)
            end = end.replace(tzinfo=None)

        attendees = [a.get("email", "") for a in event.get("attendees", [])]

        return CalendarEvent(
            id=event.get("id", ""),
            summary=event.get("summary", "(No title)"),
            start=start,
            end=end,
            location=event.get("location"),
            description=event.get("description"),
            attendees=attendees,
            is_all_day=is_all_day,
        )

    def get_upcoming_events(
        self,
        max_results: int = 10,
        hours_ahead: int = 24,
    ) -> list[CalendarEvent]:
        """Get upcoming events."""
        service = self._get_service()

        now = datetime.utcnow().isoformat() + "Z"
        time_max = (datetime.utcnow() + timedelta(hours=hours_ahead)).isoformat() + "Z"

        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])
        return [self._parse_event(e) for e in events]

    def get_today_events(self) -> list[CalendarEvent]:
        """Get all events for today."""
        service = self._get_service()

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=today.isoformat() + "Z",
            timeMax=tomorrow.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])
        return [self._parse_event(e) for e in events]

    def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[list[str]] = None,
    ) -> CalendarEvent:
        """Create a new calendar event."""
        service = self._get_service()

        event_body = {
            "summary": summary,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        }

        if description:
            event_body["description"] = description
        if location:
            event_body["location"] = location
        if attendees:
            event_body["attendees"] = [{"email": email} for email in attendees]

        event = service.events().insert(calendarId="primary", body=event_body).execute()
        return self._parse_event(event)

    def get_free_slots(
        self,
        date: datetime,
        duration_minutes: int = 30,
        start_hour: int = 9,
        end_hour: int = 17,
    ) -> list[tuple[datetime, datetime]]:
        """Find free time slots on a given date."""
        events = self.get_today_events() if date.date() == datetime.now().date() else []

        work_start = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        work_end = date.replace(hour=end_hour, minute=0, second=0, microsecond=0)

        busy_times = [(e.start, e.end) for e in events if not e.is_all_day]
        busy_times.sort(key=lambda x: x[0])

        free_slots = []
        current = work_start

        for busy_start, busy_end in busy_times:
            if current + timedelta(minutes=duration_minutes) <= busy_start:
                free_slots.append((current, busy_start))
            current = max(current, busy_end)

        if current + timedelta(minutes=duration_minutes) <= work_end:
            free_slots.append((current, work_end))

        return free_slots


_calendar_client: Optional[GoogleCalendarClient] = None


def get_calendar_client() -> GoogleCalendarClient:
    """Get or create Calendar client singleton."""
    global _calendar_client
    if _calendar_client is None:
        _calendar_client = GoogleCalendarClient()
    return _calendar_client


async def get_calendar_handler(hours: int = 24, max_results: int = 10) -> ToolResult:
    """Get upcoming calendar events."""
    try:
        client = get_calendar_client()

        if not client.is_configured():
            return ToolResult(
                success=False,
                error="Google Calendar is not configured. Please set up Google Calendar API credentials."
            )

        events = client.get_upcoming_events(max_results, hours)

        if not events:
            return ToolResult(success=True, output="No upcoming events.")

        output_lines = [f"**Upcoming Events ({len(events)}):**\n"]
        for event in events:
            time_str = event.format_time()
            date_str = event.start.strftime("%b %d")
            output_lines.append(f"- **{event.summary}**\n  {date_str} {time_str}")
            if event.location:
                output_lines.append(f"  📍 {event.location}")

        return ToolResult(success=True, output="\n".join(output_lines))

    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def today_schedule_handler() -> ToolResult:
    """Get today's schedule."""
    try:
        client = get_calendar_client()

        if not client.is_configured():
            return ToolResult(
                success=False,
                error="Google Calendar is not configured."
            )

        events = client.get_today_events()
        today = datetime.now().strftime("%A, %B %d")

        if not events:
            return ToolResult(success=True, output=f"**{today}**\nNo events scheduled for today.")

        output_lines = [f"**{today} - {len(events)} event(s):**\n"]
        for event in events:
            time_str = event.format_time()
            output_lines.append(f"- {time_str}: **{event.summary}**")
            if event.location:
                output_lines.append(f"  📍 {event.location}")

        return ToolResult(success=True, output="\n".join(output_lines))

    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def create_event_handler(
    title: str,
    start_time: str,
    duration_minutes: int = 60,
    description: str = "",
    location: str = "",
) -> ToolResult:
    """Create a calendar event."""
    try:
        client = get_calendar_client()

        if not client.is_configured():
            return ToolResult(
                success=False,
                error="Google Calendar is not configured."
            )

        try:
            start = datetime.fromisoformat(start_time)
        except ValueError:
            return ToolResult(
                success=False,
                error="Invalid start_time format. Use ISO format: YYYY-MM-DDTHH:MM:SS"
            )

        end = start + timedelta(minutes=duration_minutes)

        event = client.create_event(
            summary=title,
            start=start,
            end=end,
            description=description if description else None,
            location=location if location else None,
        )

        return ToolResult(
            success=True,
            output=f"Created event: **{event.summary}**\n"
                   f"📅 {event.start.strftime('%Y-%m-%d %H:%M')} - {event.end.strftime('%H:%M')}"
        )

    except Exception as e:
        return ToolResult(success=False, error=str(e))


def create_calendar_tools() -> list[Tool]:
    """Create calendar-related tools."""
    get_calendar = Tool(
        name="get_calendar",
        description="Get upcoming calendar events. Shows events for the next specified hours.",
        parameters=[
            ToolParameter(
                name="hours",
                param_type="integer",
                description="Hours ahead to look for events (default: 24)",
                required=False,
            ),
            ToolParameter(
                name="max_results",
                param_type="integer",
                description="Maximum number of events to return (default: 10)",
                required=False,
            ),
        ],
        handler=get_calendar_handler,
    )

    today_schedule = Tool(
        name="today_schedule",
        description="Get today's full schedule. Shows all events for the current day.",
        parameters=[],
        handler=today_schedule_handler,
    )

    create_event = Tool(
        name="create_event",
        description="Create a new calendar event.",
        parameters=[
            ToolParameter(
                name="title",
                param_type="string",
                description="Event title/summary",
                required=True,
            ),
            ToolParameter(
                name="start_time",
                param_type="string",
                description="Event start time in ISO format (YYYY-MM-DDTHH:MM:SS)",
                required=True,
            ),
            ToolParameter(
                name="duration_minutes",
                param_type="integer",
                description="Event duration in minutes (default: 60)",
                required=False,
            ),
            ToolParameter(
                name="description",
                param_type="string",
                description="Event description",
                required=False,
            ),
            ToolParameter(
                name="location",
                param_type="string",
                description="Event location",
                required=False,
            ),
        ],
        handler=create_event_handler,
    )

    return [get_calendar, today_schedule, create_event]