"""
Adaptive weight management for CTG-LC
"""
from typing import Dict
import time

class AdaptiveWeightManager:
    """
    Manages dynamic trust weights for nodes based on behavior
    """
    
    def __init__(self,
                 initial_weight: float = 1.0,
                 min_weight: float = 0.1,
                 penalty: float = 0.1,
                 recovery: float = 0.01,
                 recovery_threshold: int = 5):
        """
        Args:
            initial_weight: Initial weight for all nodes
            min_weight: Minimum weight threshold
            penalty: Weight reduction per violation (Δw)
            recovery: Weight increase per honest round (γ)
            recovery_threshold: Consecutive honest rounds needed for recovery
        """
        self.initial_weight = initial_weight
        self.min_weight = min_weight
        self.penalty = penalty
        self.recovery = recovery
        self.recovery_threshold = recovery_threshold
        
        # Node weights: node_id -> weight
        self.weights: Dict[str, float] = {}
        
        # Honest round counters: node_id -> consecutive_honest_rounds
        self.honest_counters: Dict[str, int] = {}
        
        # Violation history: node_id -> [(timestamp, violation_type), ...]
        self.violation_history: Dict[str, list] = {}
        
        # Statistics
        self.total_penalties = 0
        self.total_recoveries = 0
    
    def initialize_node(self, node_id: str):
        """Initialize weight for a new node"""
        self.weights[node_id] = self.initial_weight
        self.honest_counters[node_id] = 0
        self.violation_history[node_id] = []
    
    def get_weight(self, node_id: str) -> float:
        """Get current weight for a node"""
        if node_id not in self.weights:
            self.initialize_node(node_id)
        return self.weights[node_id]
    
    def penalize(self, node_id: str, violation_type: str = 'unknown'):
        """
        Apply penalty to a node for suspicious behavior
        
        Args:
            node_id: Node to penalize
            violation_type: Type of violation (for logging)
        """
        if node_id not in self.weights:
            self.initialize_node(node_id)
        
        # Apply penalty
        old_weight = self.weights[node_id]
        self.weights[node_id] = max(self.min_weight, old_weight - self.penalty)
        
        # Reset honest counter
        self.honest_counters[node_id] = 0
        
        # Log violation
        self.violation_history[node_id].append((time.time(), violation_type))
        
        # Update statistics
        self.total_penalties += 1
    
    def reward(self, node_id: str):
        """
        Reward node for honest behavior
        
        Args:
            node_id: Node to reward
        """
        if node_id not in self.weights:
            self.initialize_node(node_id)
        
        # Increment honest counter
        self.honest_counters[node_id] += 1
        
        # Apply recovery if threshold reached
        if self.honest_counters[node_id] >= self.recovery_threshold:
            old_weight = self.weights[node_id]
            self.weights[node_id] = min(self.initial_weight, old_weight + self.recovery)
            
            # Reset counter
            self.honest_counters[node_id] = 0
            
            # Update statistics
            self.total_recoveries += 1
    
    def get_total_weight(self, node_ids: list) -> float:
        """
        Calculate total weight for a set of nodes
        
        Args:
            node_ids: List of node IDs
            
        Returns:
            Sum of weights
        """
        return sum(self.get_weight(node_id) for node_id in node_ids)
    
    def get_weighted_quorum_size(self, node_ids: list) -> float:
        """
        Calculate 2/3 weighted quorum threshold
        
        Args:
            node_ids: List of node IDs in domain
            
        Returns:
            2/3 of total weight
        """
        total_weight = self.get_total_weight(node_ids)
        return (2.0 / 3.0) * total_weight
    
    def is_isolated(self, node_id: str) -> bool:
        """Check if node is isolated (weight at minimum)"""
        return self.get_weight(node_id) <= self.min_weight
    
    def get_statistics(self) -> dict:
        """Get weight management statistics"""
        return {
            'total_penalties': self.total_penalties,
            'total_recoveries': self.total_recoveries,
            'isolated_nodes': [node_id for node_id, w in self.weights.items() 
                             if w <= self.min_weight],
            'average_weight': sum(self.weights.values()) / max(1, len(self.weights)),
            'weight_distribution': self.weights.copy()
        }
    
    def reset_statistics(self):
        """Reset statistics"""
        self.total_penalties = 0
        self.total_recoveries = 0