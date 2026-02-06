"""
Tests for multi-channel abstraction layer.
"""

import pytest
from datetime import datetime

from ii_telegram_agent.channels.base import (
    BaseChannel,
    ChannelMessage,
    ChannelRegistry,
    ChannelType,
    OutgoingMessage,
)


def test_channel_message_creation():
    """Test creating a channel message."""
    msg = ChannelMessage(
        text="Hello, world!",
        sender_id="123",
        channel_type=ChannelType.TELEGRAM,
        channel_id="chat_456",
        sender_name="Test User",
    )

    assert msg.text == "Hello, world!"
    assert msg.channel_type == ChannelType.TELEGRAM
    assert not msg.is_voice
    assert not msg.is_image
    assert not msg.has_attachments


def test_channel_message_voice():
    """Test voice message detection."""
    msg = ChannelMessage(
        text="",
        sender_id="123",
        channel_type=ChannelType.TELEGRAM,
        channel_id="chat_456",
        voice_data=b"audio_data",
    )

    assert msg.is_voice
    assert msg.has_attachments


def test_channel_message_image():
    """Test image message detection."""
    msg = ChannelMessage(
        text="Check this out",
        sender_id="123",
        channel_type=ChannelType.TELEGRAM,
        channel_id="chat_456",
        image_data=b"image_data",
    )

    assert msg.is_image
    assert msg.has_attachments


def test_channel_type_enum():
    """Test channel type values."""
    assert ChannelType.TELEGRAM.value == "telegram"
    assert ChannelType.WHATSAPP.value == "whatsapp"
    assert ChannelType.DISCORD.value == "discord"
    assert ChannelType.SLACK.value == "slack"


def test_outgoing_message():
    """Test outgoing message creation."""
    msg = OutgoingMessage(
        text="Response text",
        channel_id="chat_456",
        parse_mode="markdown",
    )

    assert msg.text == "Response text"
    assert msg.parse_mode == "markdown"


def test_channel_registry():
    """Test channel registry operations."""
    registry = ChannelRegistry()

    assert len(registry.all_channels) == 0
    assert len(registry.connected_channels) == 0


def test_channel_registry_get_nonexistent():
    """Test getting a non-registered channel."""
    registry = ChannelRegistry()
    assert registry.get(ChannelType.TELEGRAM) is None
