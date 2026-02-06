"""
Execution Approval System - In-chat approval for sensitive operations.

Inspired by OpenClaw's exec-approval system where dangerous tool calls
(shell commands, file writes, email sends) require explicit user approval
before execution. Users can approve/deny inline via Telegram /approve command.

Security model:
- Tools are classified by risk level (safe, moderate, dangerous)
- Safe tools execute immediately
- Moderate tools log a warning but execute
- Dangerous tools require explicit /approve before execution
"""

import asyncio
import structlog
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Coroutine

logger = structlog.get_logger()


class RiskLevel(str, Enum):
    """Risk classification for tool operations."""
    SAFE = "safe"              # search, recall, browse - auto-execute
    MODERATE = "moderate"      # file read, code exec - execute with warning
    DANGEROUS = "dangerous"    # shell, file write/delete, email send - require approval


# Default risk classification for known tools
DEFAULT_RISK_MAP: dict[str, RiskLevel] = {
    # Safe
    "web_search": RiskLevel.SAFE,
    "browse_webpage": RiskLevel.SAFE,
    "recall": RiskLevel.SAFE,
    "remember": RiskLevel.SAFE,
    "list_files": RiskLevel.SAFE,
    "search_files": RiskLevel.SAFE,
    "list_reminders": RiskLevel.SAFE,
    "list_allowed_commands": RiskLevel.SAFE,
    "system_info": RiskLevel.SAFE,
    "get_calendar": RiskLevel.SAFE,
    "today_schedule": RiskLevel.SAFE,
    "check_email": RiskLevel.SAFE,
    "inbox_summary": RiskLevel.SAFE,

    # Moderate
    "execute_code": RiskLevel.MODERATE,
    "read_file": RiskLevel.MODERATE,
    "set_reminder": RiskLevel.MODERATE,
    "cancel_reminder": RiskLevel.MODERATE,
    "add_cron_task": RiskLevel.MODERATE,
    "setup_daily_briefing": RiskLevel.MODERATE,
    "create_event": RiskLevel.MODERATE,

    # Dangerous
    "run_command": RiskLevel.DANGEROUS,
    "write_file": RiskLevel.DANGEROUS,
    "send_email": RiskLevel.DANGEROUS,
    "write_skill": RiskLevel.DANGEROUS,
}


@dataclass
class PendingApproval:
    """A tool execution waiting for user approval."""
    id: str
    tool_name: str
    arguments: dict[str, Any]
    risk_level: RiskLevel
    description: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=5))
    approved: bool = False
    denied: bool = False

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_pending(self) -> bool:
        return not self.approved and not self.denied and not self.is_expired

    def format_for_display(self) -> str:
        """Format this approval request for display in chat."""
        args_display = "\n".join(
            f"  {k}: {str(v)[:100]}" for k, v in self.arguments.items()
        )
        risk_emoji = {
            RiskLevel.DANGEROUS: "🔴",
            RiskLevel.MODERATE: "🟡",
            RiskLevel.SAFE: "🟢",
        }[self.risk_level]

        return (
            f"{risk_emoji} **Approval Required**\n\n"
            f"**Tool:** `{self.tool_name}`\n"
            f"**Risk:** {self.risk_level.value}\n"
            f"**Arguments:**\n```\n{args_display}\n```\n\n"
            f"Reply `/approve {self.id}` to execute\n"
            f"Reply `/deny {self.id}` to cancel\n"
            f"_Expires in 5 minutes_"
        )


class ApprovalManager:
    """Manages pending execution approvals.

    Integrates with the tool execution pipeline to intercept
    dangerous operations and require user confirmation.
    """

    def __init__(
        self,
        risk_map: dict[str, RiskLevel] | None = None,
        approval_required: bool = True,
        auto_approve_for_admins: bool = True,
    ):
        self._risk_map = risk_map or dict(DEFAULT_RISK_MAP)
        self._pending: dict[str, PendingApproval] = {}
        self._approval_events: dict[str, asyncio.Event] = {}
        self.approval_required = approval_required
        self.auto_approve_for_admins = auto_approve_for_admins

    def get_risk_level(self, tool_name: str) -> RiskLevel:
        """Get the risk level for a tool."""
        return self._risk_map.get(tool_name, RiskLevel.MODERATE)

    def set_risk_level(self, tool_name: str, level: RiskLevel) -> None:
        """Override the risk level for a tool."""
        self._risk_map[tool_name] = level

    def needs_approval(self, tool_name: str) -> bool:
        """Check if a tool call requires approval."""
        if not self.approval_required:
            return False
        return self.get_risk_level(tool_name) == RiskLevel.DANGEROUS

    def create_approval_request(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        description: str = "",
    ) -> PendingApproval:
        """Create a pending approval request."""
        import uuid
        approval_id = str(uuid.uuid4())[:8]

        if not description:
            description = f"Execute `{tool_name}` with given arguments"

        approval = PendingApproval(
            id=approval_id,
            tool_name=tool_name,
            arguments=arguments,
            risk_level=self.get_risk_level(tool_name),
            description=description,
        )

        self._pending[approval_id] = approval
        self._approval_events[approval_id] = asyncio.Event()

        logger.info(
            "Approval request created",
            approval_id=approval_id,
            tool=tool_name,
            risk=approval.risk_level.value,
        )

        return approval

    def approve(self, approval_id: str) -> bool:
        """Approve a pending request."""
        approval = self._pending.get(approval_id)
        if approval is None or not approval.is_pending:
            return False

        approval.approved = True
        event = self._approval_events.get(approval_id)
        if event:
            event.set()

        logger.info("Approval granted", approval_id=approval_id, tool=approval.tool_name)
        return True

    def deny(self, approval_id: str) -> bool:
        """Deny a pending request."""
        approval = self._pending.get(approval_id)
        if approval is None or not approval.is_pending:
            return False

        approval.denied = True
        event = self._approval_events.get(approval_id)
        if event:
            event.set()

        logger.info("Approval denied", approval_id=approval_id, tool=approval.tool_name)
        return True

    async def wait_for_approval(
        self, approval_id: str, timeout: float = 300.0
    ) -> bool:
        """Wait for an approval decision. Returns True if approved."""
        event = self._approval_events.get(approval_id)
        if event is None:
            return False

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.info("Approval timed out", approval_id=approval_id)
            return False

        approval = self._pending.get(approval_id)
        return approval.approved if approval else False

    def get_pending(self, approval_id: str) -> PendingApproval | None:
        """Get a pending approval by ID."""
        return self._pending.get(approval_id)

    def list_pending(self) -> list[PendingApproval]:
        """List all pending approvals."""
        self._cleanup_expired()
        return [a for a in self._pending.values() if a.is_pending]

    def _cleanup_expired(self) -> None:
        """Remove expired approvals."""
        expired = [
            aid for aid, a in self._pending.items()
            if a.is_expired or a.approved or a.denied
        ]
        for aid in expired:
            self._pending.pop(aid, None)
            self._approval_events.pop(aid, None)


# Global singleton
_approval_manager: ApprovalManager | None = None


def get_approval_manager() -> ApprovalManager:
    """Get or create the global approval manager."""
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalManager()
    return _approval_manager
