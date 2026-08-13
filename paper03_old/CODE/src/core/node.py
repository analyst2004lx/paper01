"""
Base node class for CTG-LC experiments
"""
import time
import threading
from typing import Optional, List, Callable
from queue import Queue
from enum import Enum

from .message import Message, MessageType, Position, Task
from .crypto import SimpleCrypto
from ..utils.spatiotemporal import SpatiotemporalValidator
from ..utils.adaptive_weights import AdaptiveWeightManager

class NodeRole(Enum):
    """Node roles in the system"""
    SCHEDULER = "SCHEDULER"
    AGV = "AGV"
    ROBOT_ARM = "ROBOT_ARM"
    CLIENT = "CLIENT"

class NodeState(Enum):
    """Node states"""
    IDLE = "IDLE"
    WAITING = "WAITING"
    PREPARED = "PREPARED"
    COMMITTED = "COMMITTED"

class BaseNode:
    """
    Base node class with common functionality
    """
    
    def __init__(self,
                 node_id: str,
                 role: NodeRole,
                 position: Position,
                 network_simulator,
                 is_byzantine: bool = False):
        """
        Args:
            node_id: Unique node identifier
            role: Node role
            position: Initial position
            network_simulator: Network simulator instance
            is_byzantine: Whether this node is Byzantine
        """
        self.node_id = node_id
        self.role = role
        self.position = position
        self.network = network_simulator
        self.is_byzantine = is_byzantine
        
        # Cryptography
        self.crypto = SimpleCrypto(node_id)
        
        # State
        self.state = NodeState.IDLE
        self.current_view = 0
        self.current_sequence = 0
        
        # Message log
        self.message_log = []
        
        # Statistics
        self.messages_sent = 0
        self.messages_received = 0
        self.consensus_rounds = 0
        
        # Register with network
        self.network.register_node(node_id, self.receive_message)
    
    def receive_message(self, message: Message):
        """
        Callback for receiving messages from network
        
        Args:
            message: Received message
        """
        self.messages_received += 1
        self.message_log.append({
            'timestamp': time.time(),
            'message': message,
            'direction': 'received'
        })
        
        # Subclasses override this to handle messages
        self.handle_message(message)
    
    def handle_message(self, message: Message):
        """
        Handle received message (to be overridden by subclasses)
        
        Args:
            message: Message to handle
        """
        pass
    
    def send_message(self, message: Message, recipients: List[str]):
        """
        Send message to recipients
        
        Args:
            message: Message to send
            recipients: List of recipient node IDs
        """
        # Sign message
        digest = message.compute_digest()
        message.signature = self.crypto.sign(digest)
        
        # Log
        self.messages_sent += len(recipients)
        self.message_log.append({
            'timestamp': time.time(),
            'message': message,
            'direction': 'sent',
            'recipients': recipients
        })
        
        # Send via network
        self.network.send(message, recipients)
    
    def broadcast(self, message: Message, domain: List[str]):
        """
        Broadcast message to all nodes in domain
        
        Args:
            message: Message to broadcast
            domain: List of node IDs in domain
        """
        self.send_message(message, domain)
    
    def verify_signature(self, message: Message) -> bool:
        """
        Verify message signature
        
        Args:
            message: Message to verify
            
        Returns:
            True if signature is valid, False otherwise
        """
        digest = message.compute_digest()
        return self.crypto.verify(message.sender_id, digest, message.signature)
    
    def get_statistics(self) -> dict:
        """Get node statistics"""
        return {
            'node_id': self.node_id,
            'role': self.role.value,
            'is_byzantine': self.is_byzantine,
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received,
            'consensus_rounds': self.consensus_rounds,
            'state': self.state.value
        }
    
    def reset_statistics(self):
        """Reset statistics"""
        self.messages_sent = 0
        self.messages_received = 0
        self.consensus_rounds = 0
        self.message_log = []