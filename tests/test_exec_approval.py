"""
Tests for exec-approval system.
"""

import asyncio
import pytest

from ii_telegram_agent.tools.exec_approval import (
    ApprovalManager,
    PendingApproval,
    RiskLevel,
    DEFAULT_RISK_MAP,
)


def test_risk_level_classification():
    """Test default risk level classifications."""
    manager = ApprovalManager()

    assert manager.get_risk_level("web_search") == RiskLevel.SAFE
    assert manager.get_risk_level("execute_code") == RiskLevel.MODERATE
    assert manager.get_risk_level("run_command") == RiskLevel.DANGEROUS
    assert manager.get_risk_level("send_email") == RiskLevel.DANGEROUS

    # Unknown tools should be moderate
    assert manager.get_risk_level("unknown_tool") == RiskLevel.MODERATE


def test_needs_approval():
    """Test approval requirement checking."""
    manager = ApprovalManager(approval_required=True)

    assert not manager.needs_approval("web_search")
    assert not manager.needs_approval("execute_code")
    assert manager.needs_approval("run_command")
    assert manager.needs_approval("send_email")


def test_needs_approval_disabled():
    """Test that approval can be disabled globally."""
    manager = ApprovalManager(approval_required=False)

    assert not manager.needs_approval("run_command")
    assert not manager.needs_approval("send_email")


def test_create_approval_request():
    """Test creating an approval request."""
    manager = ApprovalManager()

    approval = manager.create_approval_request(
        "run_command",
        {"command": "ls -la"},
        "List directory contents",
    )

    assert approval.id
    assert approval.tool_name == "run_command"
    assert approval.arguments == {"command": "ls -la"}
    assert approval.risk_level == RiskLevel.DANGEROUS
    assert approval.is_pending


def test_approve_request():
    """Test approving a request."""
    manager = ApprovalManager()

    approval = manager.create_approval_request(
        "run_command", {"command": "ls"}
    )

    assert approval.is_pending
    assert manager.approve(approval.id)
    assert approval.approved
    assert not approval.is_pending


def test_deny_request():
    """Test denying a request."""
    manager = ApprovalManager()

    approval = manager.create_approval_request(
        "run_command", {"command": "rm -rf test"}
    )

    assert manager.deny(approval.id)
    assert approval.denied
    assert not approval.is_pending


def test_approve_nonexistent():
    """Test approving a nonexistent request."""
    manager = ApprovalManager()
    assert not manager.approve("nonexistent_id")


def test_list_pending():
    """Test listing pending approvals."""
    manager = ApprovalManager()

    a1 = manager.create_approval_request("run_command", {"command": "ls"})
    a2 = manager.create_approval_request("send_email", {"to": "test@test.com"})

    pending = manager.list_pending()
    assert len(pending) == 2

    # Approve one
    manager.approve(a1.id)
    pending = manager.list_pending()
    assert len(pending) == 1
    assert pending[0].id == a2.id


def test_pending_approval_format():
    """Test approval display formatting."""
    manager = ApprovalManager()

    approval = manager.create_approval_request(
        "run_command",
        {"command": "ls -la /home"},
    )

    display = approval.format_for_display()
    assert "Approval Required" in display
    assert "run_command" in display
    assert approval.id in display
    assert "/approve" in display


def test_set_risk_level():
    """Test overriding risk levels."""
    manager = ApprovalManager()

    assert manager.get_risk_level("execute_code") == RiskLevel.MODERATE
    manager.set_risk_level("execute_code", RiskLevel.DANGEROUS)
    assert manager.get_risk_level("execute_code") == RiskLevel.DANGEROUS


@pytest.mark.asyncio
async def test_wait_for_approval_approved():
    """Test waiting for approval that gets approved."""
    manager = ApprovalManager()
    approval = manager.create_approval_request("run_command", {"command": "ls"})

    # Approve in background
    async def approve_later():
        await asyncio.sleep(0.1)
        manager.approve(approval.id)

    task = asyncio.create_task(approve_later())
    result = await manager.wait_for_approval(approval.id, timeout=5.0)
    await task

    assert result is True


@pytest.mark.asyncio
async def test_wait_for_approval_timeout():
    """Test approval timeout."""
    manager = ApprovalManager()
    approval = manager.create_approval_request("run_command", {"command": "ls"})

    result = await manager.wait_for_approval(approval.id, timeout=0.1)
    assert result is False
