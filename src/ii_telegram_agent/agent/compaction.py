"""
Conversation Compaction - Adaptive context summarization.

Inspired by OpenClaw's compaction safeguard system with adaptive chunking
and progressive fallback. When conversation context grows too large,
this module intelligently summarizes older messages while preserving
critical information.

Key features:
- Adaptive chunking based on message importance
- Preserves tool call results and their context
- Maintains user preferences and facts mentioned
- Progressive fallback if summarization fails
- Token-aware compaction (respects model context limits)
"""

import structlog
from dataclasses import dataclass
from typing import Any

from ..llm.base import BaseLLM, LLMMessage, LLMResponse

logger = structlog.get_logger()

# Approximate tokens per character (conservative estimate)
CHARS_PER_TOKEN = 4

# Default context budget: leave room for system prompt + response
DEFAULT_MAX_CONTEXT_TOKENS = 100_000
DEFAULT_COMPACTION_THRESHOLD = 0.7  # Compact when 70% of budget used
DEFAULT_KEEP_RECENT = 10  # Always keep last N message pairs


@dataclass
class CompactionConfig:
    """Configuration for conversation compaction."""

    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
    compaction_threshold: float = DEFAULT_COMPACTION_THRESHOLD
    keep_recent_messages: int = DEFAULT_KEEP_RECENT
    preserve_tool_results: bool = True
    preserve_memories: bool = True
    enabled: bool = True


@dataclass
class CompactionResult:
    """Result of a compaction operation."""

    original_message_count: int
    compacted_message_count: int
    summary: str
    tokens_saved_estimate: int
    success: bool
    error: str | None = None


def estimate_tokens(messages: list[LLMMessage]) -> int:
    """Estimate token count for a list of messages."""
    total_chars = sum(len(m.content) for m in messages)
    # Add overhead for role markers and formatting
    overhead = len(messages) * 20
    return (total_chars + overhead) // CHARS_PER_TOKEN


def _classify_message_importance(message: LLMMessage) -> int:
    """Rate a message's importance for context preservation.

    Returns a score 0-10 where higher = more important to keep verbatim.
    """
    score = 5  # baseline

    content_lower = message.content.lower()

    # Tool calls and results are high-value context
    if message.role == "tool":
        score += 2
    if message.tool_calls:
        score += 2

    # Messages with specific data/facts
    if any(marker in content_lower for marker in [
        "remember", "important", "my name", "my email", "password",
        "api key", "deadline", "meeting", "address", "phone",
    ]):
        score += 3

    # Error messages should be preserved
    if "error" in content_lower or "failed" in content_lower:
        score += 1

    # Very short messages are less important
    if len(message.content) < 20:
        score -= 2

    # Very long messages contain more context
    if len(message.content) > 1000:
        score += 1

    return max(0, min(10, score))


def _extract_key_facts(messages: list[LLMMessage]) -> list[str]:
    """Extract key facts and information from messages for the summary."""
    facts = []

    for msg in messages:
        content = msg.content

        # Look for structured information
        if msg.role == "tool" and msg.content.strip():
            # Tool results often contain important data
            preview = msg.content[:200]
            if preview.strip():
                facts.append(f"[Tool result]: {preview}")

        # Look for messages where user states facts
        if msg.role == "user":
            content_lower = content.lower()
            if any(phrase in content_lower for phrase in [
                "my name is", "i work", "i live", "i prefer",
                "remember that", "don't forget", "important:",
            ]):
                facts.append(f"[User stated]: {content[:200]}")

    return facts[:10]  # Cap at 10 key facts


async def compact_conversation(
    llm: BaseLLM,
    messages: list[LLMMessage],
    config: CompactionConfig | None = None,
) -> tuple[list[LLMMessage], CompactionResult]:
    """Compact a conversation by summarizing older messages.

    Strategy:
    1. Keep the most recent messages verbatim
    2. Summarize older messages into a context block
    3. Preserve high-importance messages and tool results

    Args:
        llm: LLM to use for summarization
        messages: Full message history
        config: Compaction configuration

    Returns:
        Tuple of (compacted messages, compaction result)
    """
    config = config or CompactionConfig()

    if not config.enabled:
        return messages, CompactionResult(
            original_message_count=len(messages),
            compacted_message_count=len(messages),
            summary="",
            tokens_saved_estimate=0,
            success=True,
        )

    current_tokens = estimate_tokens(messages)
    threshold_tokens = int(config.max_context_tokens * config.compaction_threshold)

    # No compaction needed
    if current_tokens < threshold_tokens:
        return messages, CompactionResult(
            original_message_count=len(messages),
            compacted_message_count=len(messages),
            summary="",
            tokens_saved_estimate=0,
            success=True,
        )

    logger.info(
        "Starting conversation compaction",
        message_count=len(messages),
        estimated_tokens=current_tokens,
        threshold=threshold_tokens,
    )

    # Split: older messages to summarize, recent to keep
    keep_count = min(config.keep_recent_messages * 2, len(messages))
    older_messages = messages[:-keep_count] if keep_count < len(messages) else []
    recent_messages = messages[-keep_count:]

    if not older_messages:
        return messages, CompactionResult(
            original_message_count=len(messages),
            compacted_message_count=len(messages),
            summary="",
            tokens_saved_estimate=0,
            success=True,
        )

    # Extract key facts before summarizing
    key_facts = _extract_key_facts(older_messages)

    # Identify high-importance messages to preserve
    preserved_messages: list[LLMMessage] = []
    to_summarize: list[LLMMessage] = []

    for msg in older_messages:
        importance = _classify_message_importance(msg)
        if importance >= 8:
            preserved_messages.append(msg)
        else:
            to_summarize.append(msg)

    # Build the summarization prompt
    try:
        summary = await _generate_summary(llm, to_summarize, key_facts)
    except Exception as e:
        logger.error("Compaction summarization failed, using fallback", error=str(e))
        summary = _fallback_summary(to_summarize, key_facts)

    # Build the compacted message list
    summary_message = LLMMessage(
        role="user",
        content=f"[Previous conversation summary]: {summary}",
    )
    summary_ack = LLMMessage(
        role="assistant",
        content="I've noted the conversation context. Let me continue helping you with that in mind.",
    )

    compacted = [summary_message, summary_ack] + preserved_messages + recent_messages

    tokens_saved = current_tokens - estimate_tokens(compacted)

    result = CompactionResult(
        original_message_count=len(messages),
        compacted_message_count=len(compacted),
        summary=summary[:500],
        tokens_saved_estimate=max(0, tokens_saved),
        success=True,
    )

    logger.info(
        "Compaction complete",
        original=result.original_message_count,
        compacted=result.compacted_message_count,
        tokens_saved=result.tokens_saved_estimate,
    )

    return compacted, result


async def _generate_summary(
    llm: BaseLLM,
    messages: list[LLMMessage],
    key_facts: list[str],
) -> str:
    """Use the LLM to generate a conversation summary."""
    # Build a condensed transcript
    transcript_parts = []
    for msg in messages:
        role = msg.role.upper()
        content = msg.content[:300]  # Truncate long messages
        transcript_parts.append(f"{role}: {content}")

    transcript = "\n".join(transcript_parts)

    facts_section = ""
    if key_facts:
        facts_section = "\n\nKey facts to preserve:\n" + "\n".join(f"- {f}" for f in key_facts)

    summary_prompt = f"""Summarize the following conversation into a concise context block.
Preserve:
- Any specific facts, names, dates, or numbers mentioned
- The user's requests and what was accomplished
- Any preferences or important information the user shared
- Tool results and their outcomes

Keep it under 500 words.{facts_section}

Conversation:
{transcript}

Summary:"""

    response = await llm.generate(
        messages=[LLMMessage(role="user", content=summary_prompt)],
        system_prompt="You are a conversation summarizer. Create concise, fact-preserving summaries.",
    )

    return response.content.strip()


def _fallback_summary(
    messages: list[LLMMessage],
    key_facts: list[str],
) -> str:
    """Create a basic summary without LLM (fallback for when summarization fails)."""
    parts = ["Earlier in this conversation:"]

    # Include key facts
    if key_facts:
        parts.append("\nKey information:")
        for fact in key_facts:
            parts.append(f"  - {fact}")

    # Include message count and roles
    user_count = sum(1 for m in messages if m.role == "user")
    assistant_count = sum(1 for m in messages if m.role == "assistant")
    tool_count = sum(1 for m in messages if m.role == "tool")

    parts.append(f"\n[{user_count} user messages, {assistant_count} assistant responses, {tool_count} tool calls summarized]")

    # Include first and last user messages for context
    user_messages = [m for m in messages if m.role == "user"]
    if user_messages:
        parts.append(f"\nFirst topic: {user_messages[0].content[:150]}")
        if len(user_messages) > 1:
            parts.append(f"Last topic before this: {user_messages[-1].content[:150]}")

    return "\n".join(parts)
