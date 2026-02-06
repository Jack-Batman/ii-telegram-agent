"""
Scheduler - Cron-like job scheduling for proactive agent behavior.

Supports:
- Cron expressions for recurring tasks
- One-time scheduled tasks
- Daily briefings
- Heartbeat checks during active hours
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional
import re

from croniter import croniter

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of scheduled tasks."""
    CRON = "cron"
    ONE_TIME = "one_time"
    HEARTBEAT = "heartbeat"
    REMINDER = "reminder"
    DAILY_BRIEFING = "daily_briefing"


@dataclass
class ScheduledTask:
    """A scheduled task."""
    id: str
    name: str
    task_type: TaskType
    message: str
    cron_expression: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    active_hours: Optional[tuple[int, int]] = None
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.cron_expression and not self.next_run:
            self.next_run = self._calculate_next_run()
        elif self.scheduled_time and not self.next_run:
            self.next_run = self.scheduled_time

    def _calculate_next_run(self) -> Optional[datetime]:
        """Calculate the next run time based on cron expression."""
        if not self.cron_expression:
            return None
        
        try:
            cron = croniter(self.cron_expression, datetime.now())
            next_time = cron.get_next(datetime)
            
            if self.active_hours:
                start_hour, end_hour = self.active_hours
                while not (start_hour <= next_time.hour < end_hour):
                    next_time = cron.get_next(datetime)
            
            return next_time
        except Exception as e:
            logger.error(f"Error calculating next run for {self.name}: {e}")
            return None

    def should_run(self) -> bool:
        """Check if the task should run now."""
        if not self.enabled:
            return False
        
        if not self.next_run:
            return False
        
        now = datetime.now()
        
        if self.active_hours:
            start_hour, end_hour = self.active_hours
            if not (start_hour <= now.hour < end_hour):
                return False
        
        return now >= self.next_run

    def mark_completed(self):
        """Mark the task as completed and calculate next run."""
        self.last_run = datetime.now()
        
        if self.task_type == TaskType.ONE_TIME or self.task_type == TaskType.REMINDER:
            self.enabled = False
            self.next_run = None
        elif self.cron_expression:
            self.next_run = self._calculate_next_run()

    def to_dict(self) -> dict:
        """Convert to dictionary for persistence."""
        return {
            "id": self.id,
            "name": self.name,
            "task_type": self.task_type.value,
            "message": self.message,
            "cron_expression": self.cron_expression,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "active_hours": list(self.active_hours) if self.active_hours else None,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduledTask":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            task_type=TaskType(data["task_type"]),
            message=data["message"],
            cron_expression=data.get("cron_expression"),
            scheduled_time=datetime.fromisoformat(data["scheduled_time"]) if data.get("scheduled_time") else None,
            active_hours=tuple(data["active_hours"]) if data.get("active_hours") else None,
            enabled=data.get("enabled", True),
            last_run=datetime.fromisoformat(data["last_run"]) if data.get("last_run") else None,
            next_run=datetime.fromisoformat(data["next_run"]) if data.get("next_run") else None,
            metadata=data.get("metadata", {}),
        )


class Scheduler:
    """
    Task scheduler with cron support.
    
    Features:
    - Add/remove/list scheduled tasks
    - Cron expressions for recurring tasks
    - One-time scheduled tasks
    - Active hours filtering
    - Persistence to disk
    """

    def __init__(
        self,
        workspace_dir: Optional[str] = None,
        callback: Optional[Callable[[ScheduledTask], Coroutine[Any, Any, None]]] = None,
    ):
        self.workspace_dir = Path(workspace_dir or "~/.ii-telegram-agent/workspace").expanduser()
        self.tasks_file = self.workspace_dir / "scheduled_tasks.json"
        self.callback = callback
        self.tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        self._load_tasks()

    def _load_tasks(self):
        """Load tasks from disk."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        if self.tasks_file.exists():
            try:
                data = json.loads(self.tasks_file.read_text())
                for task_data in data.get("tasks", []):
                    task = ScheduledTask.from_dict(task_data)
                    self.tasks[task.id] = task
                logger.info(f"Loaded {len(self.tasks)} scheduled tasks")
            except Exception as e:
                logger.error(f"Error loading tasks: {e}")

    def _save_tasks(self):
        """Save tasks to disk."""
        try:
            data = {
                "tasks": [task.to_dict() for task in self.tasks.values()],
                "updated_at": datetime.now().isoformat(),
            }
            self.tasks_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Error saving tasks: {e}")

    def add_cron_task(
        self,
        name: str,
        message: str,
        cron_expression: str,
        active_hours: Optional[tuple[int, int]] = None,
        metadata: Optional[dict] = None,
    ) -> ScheduledTask:
        """Add a recurring cron task."""
        task = ScheduledTask(
            id=str(uuid.uuid4())[:8],
            name=name,
            task_type=TaskType.CRON,
            message=message,
            cron_expression=cron_expression,
            active_hours=active_hours,
            metadata=metadata or {},
        )
        self.tasks[task.id] = task
        self._save_tasks()
        logger.info(f"Added cron task: {name} ({cron_expression})")
        return task

    def add_one_time_task(
        self,
        name: str,
        message: str,
        scheduled_time: datetime,
        metadata: Optional[dict] = None,
    ) -> ScheduledTask:
        """Add a one-time scheduled task."""
        task = ScheduledTask(
            id=str(uuid.uuid4())[:8],
            name=name,
            task_type=TaskType.ONE_TIME,
            message=message,
            scheduled_time=scheduled_time,
            metadata=metadata or {},
        )
        self.tasks[task.id] = task
        self._save_tasks()
        logger.info(f"Added one-time task: {name} at {scheduled_time}")
        return task

    def add_reminder(
        self,
        message: str,
        delay: timedelta,
        name: Optional[str] = None,
    ) -> ScheduledTask:
        """Add a reminder that fires after a delay."""
        scheduled_time = datetime.now() + delay
        task = ScheduledTask(
            id=str(uuid.uuid4())[:8],
            name=name or f"Reminder: {message[:30]}...",
            task_type=TaskType.REMINDER,
            message=message,
            scheduled_time=scheduled_time,
        )
        self.tasks[task.id] = task
        self._save_tasks()
        logger.info(f"Added reminder in {delay}: {message}")
        return task

    def add_daily_briefing(
        self,
        hour: int = 8,
        minute: int = 0,
        message: Optional[str] = None,
    ) -> ScheduledTask:
        """Add a daily briefing task."""
        cron_expr = f"{minute} {hour} * * *"
        default_message = """Generate my daily briefing including:
- Today's weather forecast
- My calendar events for today
- Any reminders or pending tasks
- Top 3 news headlines relevant to my interests
Keep it concise and actionable."""
        
        task = ScheduledTask(
            id="daily-briefing",
            name="Daily Briefing",
            task_type=TaskType.DAILY_BRIEFING,
            message=message or default_message,
            cron_expression=cron_expr,
            metadata={"hour": hour, "minute": minute},
        )
        self.tasks[task.id] = task
        self._save_tasks()
        logger.info(f"Added daily briefing at {hour:02d}:{minute:02d}")
        return task

    def remove_task(self, task_id: str) -> bool:
        """Remove a task by ID."""
        if task_id in self.tasks:
            del self.tasks[task_id]
            self._save_tasks()
            logger.info(f"Removed task: {task_id}")
            return True
        return False

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def list_tasks(self, enabled_only: bool = False) -> list[ScheduledTask]:
        """List all tasks."""
        tasks = list(self.tasks.values())
        if enabled_only:
            tasks = [t for t in tasks if t.enabled]
        return sorted(tasks, key=lambda t: t.next_run or datetime.max)

    def get_due_tasks(self) -> list[ScheduledTask]:
        """Get all tasks that are due to run."""
        return [task for task in self.tasks.values() if task.should_run()]

    async def _run_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                due_tasks = self.get_due_tasks()
                
                for task in due_tasks:
                    logger.info(f"Running scheduled task: {task.name}")
                    
                    if self.callback:
                        try:
                            await self.callback(task)
                        except Exception as e:
                            logger.error(f"Error in task callback for {task.name}: {e}")
                    
                    task.mark_completed()
                    self._save_tasks()
                
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(60)

    def start(self):
        """Start the scheduler."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Scheduler stopped")

    def parse_natural_time(self, text: str) -> Optional[datetime]:
        """Parse natural language time expressions."""
        text = text.lower().strip()
        now = datetime.now()
        
        patterns = [
            (r"in (\d+) minutes?", lambda m: now + timedelta(minutes=int(m.group(1)))),
            (r"in (\d+) hours?", lambda m: now + timedelta(hours=int(m.group(1)))),
            (r"in (\d+) days?", lambda m: now + timedelta(days=int(m.group(1)))),
            (r"tomorrow at (\d+):?(\d*)(?:\s*(am|pm))?", lambda m: self._parse_tomorrow_time(m)),
            (r"at (\d+):(\d+)(?:\s*(am|pm))?", lambda m: self._parse_time_today(m)),
            (r"at (\d+)(?:\s*(am|pm))", lambda m: self._parse_hour_today(m)),
        ]
        
        for pattern, handler in patterns:
            match = re.search(pattern, text)
            if match:
                return handler(match)
        
        return None

    def _parse_tomorrow_time(self, match) -> datetime:
        """Parse 'tomorrow at X' expressions."""
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        period = match.group(3)
        
        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        
        tomorrow = datetime.now() + timedelta(days=1)
        return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def _parse_time_today(self, match) -> datetime:
        """Parse 'at HH:MM' expressions."""
        hour = int(match.group(1))
        minute = int(match.group(2))
        period = match.group(3) if len(match.groups()) > 2 else None
        
        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        
        result = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if result < datetime.now():
            result += timedelta(days=1)
        
        return result

    def _parse_hour_today(self, match) -> datetime:
        """Parse 'at X am/pm' expressions."""
        hour = int(match.group(1))
        period = match.group(2)
        
        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        
        result = datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0)
        
        if result < datetime.now():
            result += timedelta(days=1)
        
        return result