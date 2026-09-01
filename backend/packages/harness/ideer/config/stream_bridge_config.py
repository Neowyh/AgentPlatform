"""Configuration for stream bridge."""

from typing import Literal

from pydantic import BaseModel, Field

StreamBridgeType = Literal["memory", "redis"]


class StreamBridgeConfig(BaseModel):
    """Configuration for the stream bridge that connects agent workers to SSE endpoints."""

    type: StreamBridgeType = Field(
        default="memory",
        description="Stream bridge backend type. 'memory' uses in-process asyncio.Queue (single-process only). 'redis' uses Redis Streams (planned for Phase 2, not yet implemented).",
    )
    redis_url: str | None = Field(
        default=None,
        description="Redis URL for the redis stream bridge type. Example: 'redis://localhost:6379/0'.",
    )
    queue_maxsize: int = Field(
        default=256,
        description="Maximum number of events buffered per run in the memory bridge.",
    )
    heartbeat_interval: float = Field(
        default=15.0,
        ge=1.0,
        le=60.0,
        description="Heartbeat interval in seconds for SSE keep-alive when no events arrive.",
    )
    cleanup_delay: float = Field(
        default=60.0,
        ge=0.0,
        le=600.0,
        description="Delay in seconds before cleaning up stream resources after a run ends, giving late subscribers a chance to drain remaining events.",
    )


# Global configuration instance — None means no stream bridge is configured
# (falls back to memory with defaults).
_stream_bridge_config: StreamBridgeConfig | None = None


def get_stream_bridge_config() -> StreamBridgeConfig | None:
    """Get the current stream bridge configuration, or None if not configured."""
    return _stream_bridge_config


def set_stream_bridge_config(config: StreamBridgeConfig | None) -> None:
    """Set the stream bridge configuration."""
    global _stream_bridge_config
    _stream_bridge_config = config


def load_stream_bridge_config_from_dict(config_dict: dict | None) -> None:
    """Load stream bridge configuration from a dictionary."""
    global _stream_bridge_config
    if config_dict is None:
        _stream_bridge_config = None
        return
    _stream_bridge_config = StreamBridgeConfig(**config_dict)
