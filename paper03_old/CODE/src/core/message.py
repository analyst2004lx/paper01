"""
Message definitions for CTG-LC protocol
"""
from dataclasses import dataclass
from typing import Optional, Any
from enum import Enum
import time
import hashlib
import json

class MessageType(Enum):
    """Message types in CTG-LC protocol"""
    # Client requests
    TASK_REQUEST = "TASK_REQUEST"
    
    # Scheduler consensus (PBFT among schedulers)
    SCHED_PRE_PREPARE = "SCHED_PRE_PREPARE"
    SCHED_PREPARE = "SCHED_PREPARE"
    SCHED_COMMIT = "SCHED_COMMIT"
    
    # Domain broadcast
    DOMAIN_ASSIGNMENT = "DOMAIN_ASSIGNMENT"
    
    # Agent consensus (within domain)
    PRE_PREPARE = "PRE_PREPARE"
    PREPARE = "PREPARE"
    COMMIT = "COMMIT"
    
    # Responses
    REPLY = "REPLY"
    
    # Attacks
    MALICIOUS = "MALICIOUS"

@dataclass
class Position:
    """2D position in workspace"""
    x: float
    y: float
    
    def distance_to(self, other: 'Position') -> float:
        """Euclidean distance"""
        return ((self.x - other.x)**2 + (self.y - other.y)**2)**0.5
    
    def to_dict(self):
        return {'x': self.x, 'y': self.y}

@dataclass
class Task:
    """Task definition"""
    task_id: str
    task_type: str
    location: Position
    required_roles: list  # e.g., ['AGV', 'RobotArm']
    time_window: tuple  # (start_time, end_time)
    
    def to_dict(self):
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'location': self.location.to_dict(),
            'required_roles': self.required_roles,
            'time_window': self.time_window
        }

@dataclass
class Message:
    """Base message class with spatiotemporal fields"""
    msg_type: MessageType
    sender_id: str
    timestamp: float
    position: Optional[Position]  # Sender's position
    task_id: Optional[str]
    payload: Any
    signature: Optional[str] = None
    
    # Consensus fields
    view: int = 0
    sequence: int = 0
    
    def __post_init__(self):
        """Auto-generate timestamp if not provided"""
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def compute_digest(self) -> str:
        """Compute message digest for signing"""
        data = {
            'msg_type': self.msg_type.value,
            'sender_id': self.sender_id,
            'timestamp': self.timestamp,
            'position': self.position.to_dict() if self.position else None,
            'task_id': self.task_id,
            'payload': str(self.payload),
            'view': self.view,
            'sequence': self.sequence
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    def to_dict(self):
        """Serialize to dict"""
        return {
            'msg_type': self.msg_type.value,
            'sender_id': self.sender_id,
            'timestamp': self.timestamp,
            'position': self.position.to_dict() if self.position else None,
            'task_id': self.task_id,
            'payload': self.payload,
            'signature': self.signature,
            'view': self.view,
            'sequence': self.sequence
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Deserialize from dict"""
        position = Position(**data['position']) if data['position'] else None
        return cls(
            msg_type=MessageType(data['msg_type']),
            sender_id=data['sender_id'],
            timestamp=data['timestamp'],
            position=position,
            task_id=data['task_id'],
            payload=data['payload'],
            signature=data.get('signature'),
            view=data.get('view', 0),
            sequence=data.get('sequence', 0)
        )