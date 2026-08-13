"""
Core components for CTG-LC simulation
"""

from src.core.message import Message, MessageType, Position, Task
# crypto.SimpleCrypto is the implementation; expose it as CryptoEngine for backward compatibility
from src.core.crypto import SimpleCrypto as CryptoEngine
from src.core.network import NetworkSimulator
from src.core.node import BaseNode, NodeRole

__all__ = [
    'Message',
    'MessageType',
    'Position',
    'Task',
    'CryptoEngine',
    'NetworkSimulator',
    'BaseNode',
    'NodeRole',
]