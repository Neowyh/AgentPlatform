"""IM Channel integration for the Gateway.

Provides a pluggable channel system that connects external messaging platforms
(Feishu/Lark, Slack, Telegram) to the iDeer agent via the ChannelManager,
Provides a pluggable channel system that connects external messaging platforms
(Feishu/Lark, Slack, Telegram) to the agent via the ChannelManager,
which uses ``langgraph-sdk`` to communicate with Gateway's LangGraph-compatible API.
"""

from app.channels.base import Channel
from app.channels.message_bus import InboundMessage, MessageBus, OutboundMessage

__all__ = [
    "Channel",
    "InboundMessage",
    "MessageBus",
    "OutboundMessage",
]


def __getattr__(name: str):
    if name == "service":
        from importlib import import_module

        return import_module("app.channels.service")
    raise AttributeError(name)
