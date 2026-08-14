"""
CTG-LC: Context-Aware Trust Graph for Localized Consensus
Main package initialization
"""

__version__ = "1.0.0"
__author__ = "CTG-LC Research Team"
__description__ = "Experimental framework for CTG-LC protocol evaluation"

# Package-level imports for convenience
from src.core.message import Message, MessageType, Position, Task
from src.core.node import BaseNode, NodeRole
from src.core.network import NetworkSimulator
from src.protocols.ctg_lc import CTGLCNode
from src.protocols.pbft import PBFTNode

__all__ = [
    'Message',
    'MessageType',
    'Position',
    'Task',
    'BaseNode',
    'NodeRole',
    'NetworkSimulator',
    'CTGLCNode',
    'PBFTNode',
]