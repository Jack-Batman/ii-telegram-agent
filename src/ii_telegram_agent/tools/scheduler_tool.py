"""
Scheduler Tool - Set reminders, schedule tasks, and manage cron jobs.

Provides natural language interface for scheduling tasks.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from .base import Tool, ToolParameter, ToolResult
from ..scheduler import Scheduler, ReminderManager, ScheduledTask, TaskType

logger = logging.getLogger(__name__)

_scheduler: Optional[Scheduler] = None
_reminder_manager: Optional[ReminderManager] = None


def get_scheduler() -> Scheduler:
    """Get or create Scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler


def get_reminder_manager() -> ReminderManager:
    """Get or create ReminderManager singleton."""
    global _reminder_manager
    if _reminder_manager is None:
        _reminder_manager = ReminderManager()
    return _reminder_manager


async def set_reminder_handler(
    message: str,
    time_expression: str,
) -> ToolResult:
    """Set a reminder using natural language time."""
    try:
        scheduler = get_scheduler()
        
        parsed_time = scheduler.parse_natural_time(time_expression)
        
        if not parsed_time:
            try:
                parsed_time = datetime.fromisoformat(time_expression)
            except ValueError:
                return ToolResult(
                    success=False,
                    error=f"Could not parse time: '{time_expression}'. "
                          f"Try formats like 'in 30 minutes', 'tomorrow at 9am', or ISO format."
                )
        
        task = scheduler.add_reminder(message, parsed_time - datetime.now())
        
        time_str = parsed_time.strftime("%Y-%m-%d %H:%M")
        return ToolResult(
            success=True,
            output=f"⏰ **Reminder set!**\n"
                   f"- **Message:** {message}\n"
                   f"- **Time:** {time_str}\n"
                   f"- **ID:** {task.id}"
        )
        
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def list_reminders_handler() -> ToolResult:
    """List all pending reminders and scheduled tasks."""
    try:
        scheduler = get_scheduler()
        tasks = scheduler.list_tasks(enabled_only=True)
        
        if not tasks:
            return ToolResult(success=True, output="No scheduled tasks or reminders.")
        
        output_lines = [f"**Scheduled Tasks ({len(tasks)}):**\n"]
        
        for task in tasks:
            type_emoji = {
                TaskType.REMINDER: "⏰",
                TaskType.CRON: "🔄",
                TaskType.DAILY_BRIEFING: "📰",
                TaskType.HEARTBEAT: "💓",
                TaskType.ONE_TIME: "📌",
            }.get(task.task_type, "📋")
            
            next_run = task.next_run.strftime("%Y-%m-%d %H:%M") if task.next_run else "Not scheduled"
            
            output_lines.append(
                f"{type_emoji} **{task.name}** (ID: {task.id})\n"
                f"   Next: {next_run}\n"
                f"   Message: {task.message[:50]}{'...' if len(task.message) > 50 else ''}"
            )
        
        return ToolResult(success=True, output="\n".join(output_lines))
        
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def cancel_reminder_handler(task_id: str) -> ToolResult:
    """Cancel a scheduled task or reminder."""
    try:
        scheduler = get_scheduler()
        
        if scheduler.remove_task(task_id):
            return ToolResult(success=True, output=f"✅ Removed task: {task_id}")
        else:
            return ToolResult(success=False, error=f"Task not found: {task_id}")
        
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def add_cron_task_handler(
    name: str,
    message: str,
    cron_expression: str,
    active_hours_start: int = 0,
    active_hours_end: int = 24,
) -> ToolResult:
    """Add a recurring cron task."""
    try:
        scheduler = get_scheduler()
        
        try:
            from croniter import croniter
            croniter(cron_expression)
        except Exception:
            return ToolResult(
                success=False,
                error=f"Invalid cron expression: '{cron_expression}'. "
                      f"Format: minute hour day month weekday (e.g., '0 9 * * *' for 9am daily)"
            )
        
        active_hours = None
        if active_hours_start != 0 or active_hours_end != 24:
            active_hours = (active_hours_start, active_hours_end)
        
        task = scheduler.add_cron_task(
            name=name,
            message=message,
            cron_expression=cron_expression,
            active_hours=active_hours,
        )
        
        return ToolResult(
            success=True,
            output=f"🔄 **Cron task added!**\n"
                   f"- **Name:** {name}\n"
                   f"- **Schedule:** {cron_expression}\n"
                   f"- **Next run:** {task.next_run.strftime('%Y-%m-%d %H:%M') if task.next_run else 'TBD'}\n"
                   f"- **ID:** {task.id}"
        )
        
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def setup_daily_briefing_handler(
    hour: int = 8,
    minute: int = 0,
    custom_message: str = "",
) -> ToolResult:
    """Set up or update the daily briefing."""
    try:
        scheduler = get_scheduler()
        
        if hour < 0 or hour > 23:
            return ToolResult(success=False, error="Hour must be between 0 and 23")
        if minute < 0 or minute > 59:
            return ToolResult(success=False, error="Minute must be between 0 and 59")
        
        task = scheduler.add_daily_briefing(
            hour=hour,
            minute=minute,
            message=custom_message if custom_message else None,
        )
        
        return ToolResult(
            success=True,
            output=f"📰 **Daily briefing set!**\n"
                   f"- **Time:** {hour:02d}:{minute:02d} every day\n"
                   f"- **ID:** {task.id}\n\n"
                   f"I'll send you a briefing with weather, calendar, and news each morning."
        )
        
    except Exception as e:
        return ToolResult(success=False, error=str(e))


def create_scheduler_tools() -> list[Tool]:
    """Create scheduler-related tools."""
    set_reminder = Tool(
        name="set_reminder",
        description="Set a reminder for a specific time. Supports natural language like 'in 30 minutes', 'tomorrow at 9am', etc.",
        parameters=[
            ToolParameter(
                name="message",
                param_type="string",
                description="The reminder message",
                required=True,
            ),
            ToolParameter(
                name="time_expression",
                param_type="string",
                description="When to remind (e.g., 'in 30 minutes', 'tomorrow at 9am', 'at 3pm')",
                required=True,
            ),
        ],
        handler=set_reminder_handler,
    )

    list_reminders = Tool(
        name="list_reminders",
        description="List all scheduled tasks, reminders, and cron jobs.",
        parameters=[],
        handler=list_reminders_handler,
    )

    cancel_reminder = Tool(
        name="cancel_reminder",
        description="Cancel a scheduled task or reminder by its ID.",
        parameters=[
            ToolParameter(
                name="task_id",
                param_type="string",
                description="The ID of the task to cancel",
                required=True,
            ),
        ],
        handler=cancel_reminder_handler,
    )

    add_cron = Tool(
        name="add_cron_task",
        description="Add a recurring task using cron expression. For advanced scheduling.",
        parameters=[
            ToolParameter(
                name="name",
                param_type="string",
                description="Name for this scheduled task",
                required=True,
            ),
            ToolParameter(
                name="message",
                param_type="string",
                description="Message/prompt to execute when the task runs",
                required=True,
            ),
            ToolParameter(
                name="cron_expression",
                param_type="string",
                description="Cron expression (minute hour day month weekday)",
                required=True,
            ),
            ToolParameter(
                name="active_hours_start",
                param_type="integer",
                description="Only run after this hour (0-23, default: 0)",
                required=False,
            ),
            ToolParameter(
                name="active_hours_end",
                param_type="integer",
                description="Only run before this hour (0-23, default: 24)",
                required=False,
            ),
        ],
        handler=add_cron_task_handler,
    )

    daily_briefing = Tool(
        name="setup_daily_briefing",
        description="Set up a daily morning briefing with weather, calendar, and news.",
        parameters=[
            ToolParameter(
                name="hour",
                param_type="integer",
                description="Hour to send briefing (0-23, default: 8)",
                required=False,
            ),
            ToolParameter(
                name="minute",
                param_type="integer",
                description="Minute to send briefing (0-59, default: 0)",
                required=False,
            ),
            ToolParameter(
                name="custom_message",
                param_type="string",
                description="Custom briefing prompt (optional)",
                required=False,
            ),
        ],
        handler=setup_daily_briefing_handler,
    )

    return [set_reminder, list_reminders, cancel_reminder, add_cron, daily_briefing]