"""
Base channel abstraction for multi-platform messaging.

Inspired by OpenClaw's channel plugin architecture, this provides
a unified interface that any messaging platform can implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator


class ChannelType(str, Enum):
    """Supported messaging channel types."""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    DISCORD = "discord"
    SLACK = "slack"
    SIGNAL = "signal"
    WEBCHAT = "webchat"
    IMESSAGE = "imessage"
    MATRIX = "matrix"


@dataclass
class ChannelMessage:
    """Platform-agnostic message representation.

    This is the canonical message format that flows through the system.
    Channel plugins convert their native format to/from this.
    """

    # Core fields
    text: str
    sender_id: str
    channel_type: ChannelType
    channel_id: str  # unique per channel instance (e.g., chat_id)

    # Sender info
    sender_name: str = ""
    sender_username: str = ""

    # Message metadata
    message_id: str = ""
    reply_to_message_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Rich content
    attachments: list[dict[str, Any]] = field(default_factory=list)
    voice_data: bytes | None = None
    image_data: bytes | None = None

    # Platform-specific raw data
    raw_data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_voice(self) -> bool:
        """Check if this is a voice message."""
        return self.voice_data is not None

    @property
    def is_image(self) -> bool:
        """Check if this has an image attachment."""
        return self.image_data is not None

    @property
    def has_attachments(self) -> bool:
        """Check if message has any attachments."""
        return bool(self.attachments) or self.is_voice or self.is_image


@dataclass
class OutgoingMessage:
    """Message being sent back to a channel."""

    text: str
    channel_id: str
    reply_to_message_id: str = ""
    parse_mode: str = "markdown"

    # Rich content
    voice_data: bytes | None = None
    image_data: bytes | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseChannel(ABC):
    """Abstract base class for messaging channel plugins.

    To add a new messaging platform:
    1. Create a subclass of BaseChannel
    2. Implement all abstract methods
    3. Register it in the channel registry

    Channels are responsible for:
    - Converting platform-native messages to ChannelMessage
    - Converting OutgoingMessage to platform-native format
    - Managing platform connections (webhooks, polling, websockets)
    - Handling platform-specific features (reactions, threads, etc.)
    """

    @property
    @abstractmethod
    def channel_type(self) -> ChannelType:
        """The type of this channel."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable channel name."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the channel is currently connected."""
        ...

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the messaging platform."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the messaging platform."""
        ...

    @abstractmethod
    async def send_message(self, message: OutgoingMessage) -> str:
        """Send a message. Returns the platform message ID."""
        ...

    @abstractmethod
    async def send_typing_indicator(self, channel_id: str) -> None:
        """Show a typing/processing indicator in the chat."""
        ...

    async def send_voice(self, channel_id: str, audio_data: bytes) -> str:
        """Send a voice message. Override if platform supports it."""
        raise NotImplementedError(f"{self.name} does not support voice messages")

    async def send_image(
        self, channel_id: str, image_data: bytes, caption: str = ""
    ) -> str:
        """Send an image. Override if platform supports it."""
        raise NotImplementedError(f"{self.name} does not support image messages")

    async def edit_message(
        self, channel_id: str, message_id: str, new_text: str
    ) -> None:
        """Edit a previously sent message. Override if platform supports it."""
        raise NotImplementedError(f"{self.name} does not support message editing")

    async def delete_message(self, channel_id: str, message_id: str) -> None:
        """Delete a message. Override if platform supports it."""
        raise NotImplementedError(f"{self.name} does not support message deletion")

    async def react(
        self, channel_id: str, message_id: str, emoji: str
    ) -> None:
        """Add a reaction to a message. Override if platform supports it."""
        raise NotImplementedError(f"{self.name} does not support reactions")


class ChannelRegistry:
    """Registry of active channel plugins.

    Manages the lifecycle of all connected channels and provides
    a unified interface for sending messages across platforms.
    """

    def __init__(self):
        self._channels: dict[ChannelType, BaseChannel] = {}

    def register(self, channel: BaseChannel) -> None:
        """Register a channel plugin."""
        self._channels[channel.channel_type] = channel

    def unregister(self, channel_type: ChannelType) -> None:
        """Unregister a channel plugin."""
        self._channels.pop(channel_type, None)

    def get(self, channel_type: ChannelType) -> BaseChannel | None:
        """Get a channel by type."""
        return self._channels.get(channel_type)

    @property
    def connected_channels(self) -> list[BaseChannel]:
        """Get all connected channels."""
        return [ch for ch in self._channels.values() if ch.is_connected]

    @property
    def all_channels(self) -> list[BaseChannel]:
        """Get all registered channels."""
        return list(self._channels.values())

    async def connect_all(self) -> None:
        """Connect all registered channels."""
        for channel in self._channels.values():
            if not channel.is_connected:
                await channel.connect()

    async def disconnect_all(self) -> None:
        """Disconnect all channels."""
        for channel in self._channels.values():
            if channel.is_connected:
                await channel.disconnect()

    async def broadcast(self, text: str, exclude: ChannelType | None = None) -> None:
        """Send a message to all connected channels (e.g., for alerts)."""
        for channel in self.connected_channels:
            if exclude and channel.channel_type == exclude:
                continue
            # Broadcast requires knowing target channel_ids; this is a placeholder
            pass


# Global registry singleton
_registry: ChannelRegistry | None = None


def get_channel_registry() -> ChannelRegistry:
    """Get or create the global channel registry."""
    global _registry
    if _registry is None:
        _registry = ChannelRegistry()
    return _registry
