"""
Simplified PBFT protocol for baseline comparison
"""
import time
from typing import Dict, List, Optional
from collections import defaultdict

from ..core.node import BaseNode, NodeRole, NodeState
from ..core.message import Message, MessageType, Position

class PBFTNode(BaseNode):
    """
    Simplified PBFT node (global consensus)
    """
    
    def __init__(self,
                 node_id: str,
                 role: NodeRole,
                 position: Position,
                 network_simulator,
                 all_nodes: List[str],
                 is_byzantine: bool = False,
                 is_primary: bool = False):
        """
        Args:
            node_id: Node identifier
            role: Node role
            position: Position
            network_simulator: Network simulator
            all_nodes: List of all node IDs in system
            is_byzantine: Whether Byzantine
            is_primary: Whether this node is primary
        """
        super().__init__(node_id, role, position, network_simulator, is_byzantine)
        
        self.all_nodes = all_nodes
        self.is_primary = is_primary
        
        # PBFT state
        self.prepare_votes: Dict[str, Dict[str, Message]] = defaultdict(dict)  # task_id -> {node_id -> message}
        self.commit_votes: Dict[str, Dict[str, Message]] = defaultdict(dict)
        
        # Quorum size (2f + 1 for n = 3f + 1)
        self.n = len(all_nodes)
        self.f = (self.n - 1) // 3
        self.quorum_size = 2 * self.f + 1
        
        # Task results
        self.committed_tasks: Dict[str, any] = {}
    
    def handle_message(self, message: Message):
        """Handle PBFT messages"""
        # Verify signature
        if not self.verify_signature(message):
            return
        
        msg_type = message.msg_type
        
        if msg_type == MessageType.PRE_PREPARE:
            self.handle_pre_prepare(message)
        elif msg_type == MessageType.PREPARE:
            self.handle_prepare(message)
        elif msg_type == MessageType.COMMIT:
            self.handle_commit(message)
    
    def initiate_consensus(self, task_id: str, task_data: any):
        """
        Primary initiates consensus
        
        Args:
            task_id: Task identifier
            task_data: Task data to agree on
        """
        if not self.is_primary:
            return
        
        self.current_sequence += 1
        
        # Create PRE-PREPARE message
        message = Message(
            msg_type=MessageType.PRE_PREPARE,
            sender_id=self.node_id,
            timestamp=time.time(),
            position=self.position,
            task_id=task_id,
            payload=task_data,
            view=self.current_view,
            sequence=self.current_sequence
        )
        
        # Broadcast to all nodes
        self.broadcast(message, self.all_nodes)
        
        # Primary also sends PREPARE
        self.send_prepare(task_id, task_data)
    
    def handle_pre_prepare(self, message: Message):
        """Handle PRE-PREPARE message"""
        if self.is_primary:
            return  # Primary doesn't process its own PRE-PREPARE
        
        task_id = message.task_id
        
        # Send PREPARE
        self.send_prepare(task_id, message.payload)
    
    def send_prepare(self, task_id: str, task_data: any):
        """Send PREPARE message"""
        message = Message(
            msg_type=MessageType.PREPARE,
            sender_id=self.node_id,
            timestamp=time.time(),
            position=self.position,
            task_id=task_id,
            payload=task_data,
            view=self.current_view,
            sequence=self.current_sequence
        )
        
        # Broadcast PREPARE
        self.broadcast(message, self.all_nodes)
        
        # Record own vote
        self.prepare_votes[task_id][self.node_id] = message
        
        # Check if prepared
        self.check_prepared(task_id)
    
    def handle_prepare(self, message: Message):
        """Handle PREPARE message"""
        task_id = message.task_id
        sender_id = message.sender_id
        
        # Record vote
        self.prepare_votes[task_id][sender_id] = message
        
        # Check if prepared
        self.check_prepared(task_id)
    
    def check_prepared(self, task_id: str):
        """Check if prepared state reached"""
        if task_id in self.committed_tasks:
            return  # Already committed
        
        # Count matching PREPARE votes
        votes = self.prepare_votes[task_id]
        
        if len(votes) >= self.quorum_size:
            # Prepared! Send COMMIT
            self.state = NodeState.PREPARED
            self.send_commit(task_id, list(votes.values())[0].payload)
    
    def send_commit(self, task_id: str, task_data: any):
        """Send COMMIT message"""
        message = Message(
            msg_type=MessageType.COMMIT,
            sender_id=self.node_id,
            timestamp=time.time(),
            position=self.position,
            task_id=task_id,
            payload=task_data,
            view=self.current_view,
            sequence=self.current_sequence
        )
        
        # Broadcast COMMIT
        self.broadcast(message, self.all_nodes)
        
        # Record own vote
        self.commit_votes[task_id][self.node_id] = message
        
        # Check if committed
        self.check_committed(task_id)
    
    def handle_commit(self, message: Message):
        """Handle COMMIT message"""
        task_id = message.task_id
        sender_id = message.sender_id
        
        # Record vote
        self.commit_votes[task_id][sender_id] = message
        
        # Check if committed
        self.check_committed(task_id)
    
    def check_committed(self, task_id: str):
        """Check if committed state reached"""
        if task_id in self.committed_tasks:
            return  # Already committed
        
        # Count matching COMMIT votes
        votes = self.commit_votes[task_id]
        
        if len(votes) >= self.quorum_size:
            # Committed!
            self.state = NodeState.COMMITTED
            self.committed_tasks[task_id] = list(votes.values())[0].payload
            self.consensus_rounds += 1
    
    def get_consensus_result(self, task_id: str) -> Optional[any]:
        """Get consensus result for task"""
        return self.committed_tasks.get(task_id)