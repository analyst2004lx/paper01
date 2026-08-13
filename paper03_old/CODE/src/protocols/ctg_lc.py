"""
CTG-LC protocol implementation with three-layer architecture
"""
import time
from typing import Dict, List, Optional, Set
from collections import defaultdict

from ..core.node import BaseNode, NodeRole, NodeState
from ..core.message import Message, MessageType, Position, Task
from ..utils.spatiotemporal import SpatiotemporalValidator
from ..utils.adaptive_weights import AdaptiveWeightManager

class CTGLCNode(BaseNode):
    """
    CTG-LC node with spatiotemporal validation, task-coupled consensus,
    and adaptive weights
    """
    
    def __init__(self,
                 node_id: str,
                 role: NodeRole,
                 position: Position,
                 network_simulator,
                 scheduler_ids: List[str],
                 is_byzantine: bool = False):
        """
        Args:
            node_id: Node identifier
            role: Node role
            position: Position
            network_simulator: Network simulator
            scheduler_ids: List of scheduler node IDs (m replicas)
            is_byzantine: Whether Byzantine
        """
        super().__init__(node_id, role, position, network_simulator, is_byzantine)
        
        self.scheduler_ids = scheduler_ids
        self.m = len(scheduler_ids)
        self.is_scheduler = (role == NodeRole.SCHEDULER)
        
        # Layer 1: Spatiotemporal validation
        self.validator = SpatiotemporalValidator()
        
        # Layer 3: Adaptive weights
        self.weight_manager = AdaptiveWeightManager()
        
        # Task domains: task_id -> [node_ids]
        self.task_domains: Dict[str, List[str]] = {}
        
        # Domain assignments received from schedulers: task_id -> {scheduler_id -> domain}
        self.domain_assignments: Dict[str, Dict[str, List[str]]] = defaultdict(dict)
        
        # Consensus state per task
        self.prepare_votes: Dict[str, Dict[str, Message]] = defaultdict(dict)
        self.commit_votes: Dict[str, Dict[str, Message]] = defaultdict(dict)
        
        # Committed tasks
        self.committed_tasks: Dict[str, any] = {}
        
        # Statistics
        self.spatiotemporal_rejections = 0
        self.domain_expansions = 0
        # Attack detection statistics
        self.replay_attacks_detected = 0
        self.spatial_forgeries_detected = 0
        self.cross_domain_attacks_detected = 0
        self.conflicting_messages_detected = 0
    def handle_message(self, message: Message):
        """Handle CTG-LC messages with spatiotemporal validation"""
        # Layer 1: Spatiotemporal validation
        if message.msg_type != MessageType.DOMAIN_ASSIGNMENT:
            is_valid, violation_type = self.validator.validate_message(message)
            
            if not is_valid:
                self.spatiotemporal_rejections += 1
                
                # Classify attack type
                if violation_type == 'timestamp':
                    self.replay_attacks_detected += 1
                elif violation_type == 'spatial':
                    self.spatial_forgeries_detected += 1
                elif violation_type == 'kinematic':
                    self.spatial_forgeries_detected += 1
                
                self.weight_manager.penalize(message.sender_id, violation_type)
                return
        
        # Verify signature
        if not self.verify_signature(message):
            self.weight_manager.penalize(message.sender_id, 'invalid_signature')
            return
        # Check for cross-domain attacks
        if message.msg_type in [MessageType.PREPARE, MessageType.COMMIT]:
            task_id = message.task_id
            sender_id = message.sender_id
            
            if task_id in self.task_domains:
                if sender_id not in self.task_domains[task_id]:
                    # Cross-domain attack detected
                    self.cross_domain_attacks_detected += 1
                    self.weight_manager.penalize(sender_id, 'cross_domain')
                    return
        # Route to appropriate handler
        msg_type = message.msg_type
        
        if msg_type == MessageType.DOMAIN_ASSIGNMENT:
            self.handle_domain_assignment(message)
        elif msg_type == MessageType.PRE_PREPARE:
            self.handle_pre_prepare(message)
        elif msg_type == MessageType.PREPARE:
            self.handle_prepare(message)
        elif msg_type == MessageType.COMMIT:
            self.handle_commit(message)
    
    def handle_domain_assignment(self, message: Message):
        """
        Handle domain assignment from scheduler
        
        Args:
            message: DOMAIN_ASSIGNMENT message with payload = domain (list of node IDs)
        """
        task_id = message.task_id
        scheduler_id = message.sender_id
        domain = message.payload
        
        # Record assignment from this scheduler
        self.domain_assignments[task_id][scheduler_id] = domain
        
        # Check if we have 2m/3 + 1 matching assignments
        if len(self.domain_assignments[task_id]) >= (2 * self.m // 3 + 1):
            # Find most common domain (should be identical if schedulers are honest)
            domain_counts = defaultdict(int)
            for d in self.domain_assignments[task_id].values():
                domain_tuple = tuple(sorted(d))  # Convert to hashable
                domain_counts[domain_tuple] += 1
            
            # Get domain with most votes
            agreed_domain_tuple = max(domain_counts, key=domain_counts.get)
            agreed_domain = list(agreed_domain_tuple)
            
            # Accept domain if we're in it
            if self.node_id in agreed_domain:
                self.task_domains[task_id] = agreed_domain
                
                # Initialize weights for domain members
                for node_id in agreed_domain:
                    self.weight_manager.initialize_node(node_id)
    
    def initiate_consensus(self, task_id: str, task_data: any, domain: List[str]):
        """
        Initiate consensus within task-coupled domain
        
        Args:
            task_id: Task identifier
            task_data: Task data
            domain: List of node IDs in domain
        """
        if not self.is_scheduler:
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
        
        # Broadcast to domain only (not all nodes)
        self.broadcast(message, domain)
        
        # Scheduler also sends PREPARE
        self.send_prepare(task_id, task_data, domain)
    
    def handle_pre_prepare(self, message: Message):
        """Handle PRE-PREPARE message"""
        task_id = message.task_id
        
        # Check if we're in the domain
        if task_id not in self.task_domains:
            return
        
        domain = self.task_domains[task_id]
        
        # Send PREPARE
        self.send_prepare(task_id, message.payload, domain)
    
    def send_prepare(self, task_id: str, task_data: any, domain: List[str]):
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
        
        # Broadcast to domain
        self.broadcast(message, domain)
        
        # Record own vote
        self.prepare_votes[task_id][self.node_id] = message
        
        # Reward self for honest behavior
        self.weight_manager.reward(self.node_id)
        
        # Check if prepared
        self.check_prepared(task_id)
    
    def handle_prepare(self, message: Message):
        """Handle PREPARE message"""
        task_id = message.task_id
        sender_id = message.sender_id
        
        # Check if sender is in domain
        if task_id not in self.task_domains:
            return
        
        if sender_id not in self.task_domains[task_id]:
            # Task coupling violation
            self.weight_manager.penalize(sender_id, 'task_coupling_violation')
            return
        
        # Record vote
        self.prepare_votes[task_id][sender_id] = message
        
        # Reward sender for honest participation
        self.weight_manager.reward(sender_id)
        
        # Check if prepared
        self.check_prepared(task_id)
    
    def check_prepared(self, task_id: str):
        """Check if prepared state reached using weighted quorum"""
        if task_id in self.committed_tasks:
            return
        
        if task_id not in self.task_domains:
            return
        
        domain = self.task_domains[task_id]
        votes = self.prepare_votes[task_id]
        
        # Calculate weighted quorum
        vote_weight = self.weight_manager.get_total_weight(list(votes.keys()))
        quorum_threshold = self.weight_manager.get_weighted_quorum_size(domain)
        
        if vote_weight >= quorum_threshold:
            # Prepared!
            self.state = NodeState.PREPARED
            self.send_commit(task_id, list(votes.values())[0].payload, domain)
    
    def send_commit(self, task_id: str, task_data: any, domain: List[str]):
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
        
        # Broadcast to domain
        self.broadcast(message, domain)
        
        # Record own vote
        self.commit_votes[task_id][self.node_id] = message
        
        # Check if committed
        self.check_committed(task_id)
    
    def handle_commit(self, message: Message):
        """Handle COMMIT message"""
        task_id = message.task_id
        sender_id = message.sender_id
        
        # Check if sender is in domain
        if task_id not in self.task_domains:
            return
        
        if sender_id not in self.task_domains[task_id]:
            self.weight_manager.penalize(sender_id, 'task_coupling_violation')
            return
        
        # Record vote
        self.commit_votes[task_id][sender_id] = message
        
        # Check if committed
        self.check_committed(task_id)
    
    def check_committed(self, task_id: str):
        """Check if committed state reached using weighted quorum"""
        if task_id in self.committed_tasks:
            return
        
        if task_id not in self.task_domains:
            return
        
        domain = self.task_domains[task_id]
        votes = self.commit_votes[task_id]
        
        # Calculate weighted quorum
        vote_weight = self.weight_manager.get_total_weight(list(votes.keys()))
        quorum_threshold = self.weight_manager.get_weighted_quorum_size(domain)
        
        if vote_weight >= quorum_threshold:
            # Committed!
            self.state = NodeState.COMMITTED
            self.committed_tasks[task_id] = list(votes.values())[0].payload
            self.consensus_rounds += 1
    
    def get_consensus_result(self, task_id: str) -> Optional[any]:
        """Get consensus result for task"""
        return self.committed_tasks.get(task_id)
    
    def get_statistics(self) -> dict:
        """Get CTG-LC statistics"""
        stats = super().get_statistics()
        stats.update({
            'spatiotemporal_rejections': self.spatiotemporal_rejections,
            'domain_expansions': self.domain_expansions,
            'validator_stats': self.validator.get_statistics(),
            'weight_stats': self.weight_manager.get_statistics()
        })
        return stats