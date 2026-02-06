"""
Multi-channel abstraction layer (inspired by OpenClaw's channel plugin system).

This module provides a unified interface for messaging across platforms.
Telegram is the primary channel, but the architecture supports adding
WhatsApp, Discord, Slack, Signal, and more.
"""

from .base import BaseChannel, ChannelMessage, ChannelType

__all__ = ["BaseChannel", "ChannelMessage", "ChannelType"]
