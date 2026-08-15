"""
Clustered Byzantine node distribution
"""
import numpy as np
from typing import List, Tuple
from ..core.message import Position

class ClusteredByzantineDistribution:
    """
    Generate clustered Byzantine node positions
    """
    
    def __init__(self, workspace_width: float = 10.0, 
                 workspace_height: float = 10.0):
        self.width = workspace_width
        self.height = workspace_height
    
    def generate_clustered_positions(self, 
                                     num_byzantine: int,
                                     cluster_center: Tuple[float, float] = (2.5, 2.5),
                                     cluster_radius: float = 2.0) -> List[Position]:
        """
        Generate Byzantine nodes clustered around a center
        
        Args:
            num_byzantine: Number of Byzantine nodes
            cluster_center: Center of cluster (x, y)
            cluster_radius: Radius of cluster
            
        Returns:
            List of Byzantine node positions
        """
        positions = []
        
        for _ in range(num_byzantine):
            # Generate position within cluster using normal distribution
            angle = np.random.uniform(0, 2 * np.pi)
            distance = np.abs(np.random.normal(0, cluster_radius / 2))
            distance = min(distance, cluster_radius)
            
            x = cluster_center[0] + distance * np.cos(angle)
            y = cluster_center[1] + distance * np.sin(angle)
            
            # Clamp to workspace
            x = np.clip(x, 0.5, self.width - 0.5)
            y = np.clip(y, 0.5, self.height - 0.5)
            
            positions.append(Position(x, y))
        
        return positions
    
    def generate_uniform_positions(self, num_nodes: int) -> List[Position]:
        """Generate uniformly distributed positions"""
        positions = []
        
        for _ in range(num_nodes):
            x = np.random.uniform(0.5, self.width - 0.5)
            y = np.random.uniform(0.5, self.height - 0.5)
            positions.append(Position(x, y))
        
        return positions
    
    def calculate_violation_probability(self,
                                        byzantine_positions: List[Position],
                                        honest_positions: List[Position],
                                        k: int,
                                        num_simulations: int = 1000) -> float:
        """
        Calculate P(f_local >= k/3) through Monte Carlo simulation
        
        Args:
            byzantine_positions: Byzantine node positions
            honest_positions: Honest node positions
            k: Domain size
            num_simulations: Number of random task placements
            
        Returns:
            Violation probability
        """
        all_positions = byzantine_positions + honest_positions
        is_byzantine = [True] * len(byzantine_positions) + [False] * len(honest_positions)
        
        violations = 0
        
        for _ in range(num_simulations):
            # Random task position
            task_x = np.random.uniform(0, self.width)
            task_y = np.random.uniform(0, self.height)
            task_pos = Position(task_x, task_y)
            
            # Find k nearest nodes
            distances = [task_pos.distance_to(pos) for pos in all_positions]
            nearest_indices = np.argsort(distances)[:k]
            
            # Count Byzantine nodes in domain
            byzantine_count = sum(1 for idx in nearest_indices if is_byzantine[idx])
            
            # Check if violates k/3 bound
            if byzantine_count >= k / 3:
                violations += 1
        
        return violations / num_simulations