"""
Experiment 1: Baseline Decomposition
Generates data for baseline_decomposition.pdf

Compares:
- PBFT (n=30)
- PBFT-Local (k=3)
- CTG-LC (k=3, m=3)
- CTG-LC-Global (k=30)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import time
import yaml
from typing import List, Dict

from src.core.network import NetworkSimulator
from src.core.message import Position, Task, Message, MessageType
from src.core.node import NodeRole
from src.protocols.pbft import PBFTNode
from src.protocols.ctg_lc import CTGLCNode

class BaselineDecompositionExperiment:
    """
    Experiment to decompose CTG-LC performance gains
    """
    
    def __init__(self, config_path: str = "experiments/config.yaml"):
        """Load configuration"""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.results = {
            'pbft': [],
            'pbft_local': [],
            'ctg_lc': [],
            'ctg_lc_global': []
        }
    
    def create_network(self) -> NetworkSimulator:
        """Create network simulator"""
        net_config = self.config['network']
        return NetworkSimulator(
            mean_delay=net_config['mean_delay'],
            jitter=net_config['jitter'],
            packet_loss=net_config['packet_loss'],
            bandwidth_limit=net_config['bandwidth_limit']
        )
    
    def generate_node_positions(self, n: int) -> List[Position]:
        """Generate random node positions in workspace"""
        workspace = self.config['workspace']
        positions = []
        for _ in range(n):
            x = np.random.uniform(0.5, workspace['width'] - 0.5)
            y = np.random.uniform(0.5, workspace['height'] - 0.5)
            positions.append(Position(x, y))
        return positions
    
    def select_task_domain(self, task_pos: Position, positions: List[Position], 
                          node_ids: List[str], k: int) -> List[str]:
        """
        Select k nearest nodes to task position
        
        Args:
            task_pos: Task position
            positions: List of all node positions
            node_ids: List of all node IDs
            k: Domain size
            
        Returns:
            List of k node IDs closest to task
        """
        distances = [(node_id, task_pos.distance_to(pos)) 
                    for node_id, pos in zip(node_ids, positions)]
        distances.sort(key=lambda x: x[1])
        return [node_id for node_id, _ in distances[:k]]
    
    def run_pbft_experiment(self, n: int, num_runs: int) -> Dict:
        """
        Run PBFT experiment (global consensus with all n nodes)
        
        Args:
            n: Number of nodes
            num_runs: Number of experiment runs
            
        Returns:
            Statistics dict
        """
        print(f"\n{'='*60}")
        print(f"Running PBFT Experiment (n={n})")
        print(f"{'='*60}")
        
        messages_list = []
        latencies_list = []
        
        for run in range(num_runs):
            # Create network
            network = self.create_network()
            
            # Create nodes
            positions = self.generate_node_positions(n)
            node_ids = [f"node_{i}" for i in range(n)]
            
            nodes = []
            for i, (node_id, pos) in enumerate(zip(node_ids, positions)):
                role = NodeRole.AGV if i < 10 else NodeRole.ROBOT_ARM
                is_primary = (i == 0)
                
                node = PBFTNode(
                    node_id=node_id,
                    role=role,
                    position=pos,
                    network_simulator=network,
                    all_nodes=node_ids,
                    is_primary=is_primary
                )
                nodes.append(node)
            
            # Start network
            network.start()
            
            # Initiate consensus
            task_id = f"task_{run}"
            task_data = {"action": "transport", "location": [5.0, 5.0]}
            
            start_time = time.time()
            nodes[0].initiate_consensus(task_id, task_data)
            
            # Wait for consensus (timeout 5 seconds)
            timeout = 5.0
            committed = False
            while time.time() - start_time < timeout:
                # Check if majority committed
                committed_count = sum(1 for node in nodes 
                                    if node.get_consensus_result(task_id) is not None)
                if committed_count >= (2 * nodes[0].f + 1):
                    committed = True
                    break
                time.sleep(0.01)
            
            end_time = time.time()
            
            # Collect statistics
            if committed:
                latency = (end_time - start_time) * 1000  # Convert to ms
                latencies_list.append(latency)
                
                # Count total messages
                net_stats = network.get_statistics()
                messages_list.append(net_stats['total_messages'])
            
            # Stop network
            network.stop()
            
            if (run + 1) % 10 == 0:
                print(f"  Completed {run + 1}/{num_runs} runs")
        
        return {
            'messages_mean': np.mean(messages_list),
            'messages_std': np.std(messages_list),
            'latency_mean': np.mean(latencies_list),
            'latency_std': np.std(latencies_list),
            'success_rate': len(latencies_list) / num_runs
        }
    
    def run_pbft_local_experiment(self, k: int, num_runs: int) -> Dict:
        """
        Run PBFT-Local experiment (PBFT restricted to k nodes)
        
        Args:
            k: Domain size
            num_runs: Number of runs
            
        Returns:
            Statistics dict
        """
        print(f"\n{'='*60}")
        print(f"Running PBFT-Local Experiment (k={k})")
        print(f"{'='*60}")
        
        messages_list = []
        latencies_list = []
        
        for run in range(num_runs):
            # Create network
            network = self.create_network()
            
            # Create k nodes only
            positions = self.generate_node_positions(k)
            node_ids = [f"node_{i}" for i in range(k)]
            
            nodes = []
            for i, (node_id, pos) in enumerate(zip(node_ids, positions)):
                role = NodeRole.AGV if i == 0 else NodeRole.ROBOT_ARM
                is_primary = (i == 0)
                
                node = PBFTNode(
                    node_id=node_id,
                    role=role,
                    position=pos,
                    network_simulator=network,
                    all_nodes=node_ids,
                    is_primary=is_primary
                )
                nodes.append(node)
            
            # Start network
            network.start()
            
            # Initiate consensus
            task_id = f"task_{run}"
            task_data = {"action": "transport", "location": [5.0, 5.0]}
            
            start_time = time.time()
            nodes[0].initiate_consensus(task_id, task_data)
            
            # Wait for consensus
            timeout = 5.0
            committed = False
            while time.time() - start_time < timeout:
                committed_count = sum(1 for node in nodes 
                                    if node.get_consensus_result(task_id) is not None)
                if committed_count >= (2 * nodes[0].f + 1):
                    committed = True
                    break
                time.sleep(0.01)
            
            end_time = time.time()
            
            # Collect statistics
            if committed:
                latency = (end_time - start_time) * 1000
                latencies_list.append(latency)
                
                net_stats = network.get_statistics()
                messages_list.append(net_stats['total_messages'])
            
            network.stop()
            
            if (run + 1) % 10 == 0:
                print(f"  Completed {run + 1}/{num_runs} runs")
        
        return {
            'messages_mean': np.mean(messages_list),
            'messages_std': np.std(messages_list),
            'latency_mean': np.mean(latencies_list),
            'latency_std': np.std(latencies_list),
            'success_rate': len(latencies_list) / num_runs
        }
    
    def run_ctg_lc_experiment(self, k: int, m: int, num_runs: int) -> Dict:
        """
        Run CTG-LC experiment (with scheduler replication)
        
        Args:
            k: Domain size (agent nodes)
            m: Scheduler replicas
            num_runs: Number of runs
            
        Returns:
            Statistics dict
        """
        print(f"\n{'='*60}")
        print(f"Running CTG-LC Experiment (k={k}, m={m})")
        print(f"{'='*60}")
        
        messages_list = []
        latencies_list = []
        spatiotemporal_rejections_list = []
        
        for run in range(num_runs):
            # Create network
            network = self.create_network()
            
            # Create scheduler nodes
            scheduler_ids = [f"scheduler_{i}" for i in range(m)]
            scheduler_positions = self.generate_node_positions(m)
            
            schedulers = []
            for i, (sched_id, pos) in enumerate(zip(scheduler_ids, scheduler_positions)):
                scheduler = CTGLCNode(
                    node_id=sched_id,
                    role=NodeRole.SCHEDULER,
                    position=pos,
                    network_simulator=network,
                    scheduler_ids=scheduler_ids
                )
                schedulers.append(scheduler)
            
            # Create agent nodes
            agent_positions = self.generate_node_positions(k)
            agent_ids = [f"agent_{i}" for i in range(k)]
            
            agents = []
            for i, (agent_id, pos) in enumerate(zip(agent_ids, agent_positions)):
                role = NodeRole.AGV if i == 0 else NodeRole.ROBOT_ARM
                
                agent = CTGLCNode(
                    node_id=agent_id,
                    role=role,
                    position=pos,
                    network_simulator=network,
                    scheduler_ids=scheduler_ids
                )
                agents.append(agent)
            
            all_nodes = schedulers + agents
            
            # Start network
            network.start()
            
            # Simulate domain assignment (schedulers agree on domain)
            task_id = f"task_{run}"
            task_data = {"action": "transport", "location": [5.0, 5.0]}
            domain = agent_ids  # All k agents in domain
            
            # Schedulers broadcast domain assignment
            for scheduler in schedulers:
                domain_msg = Message(
                    msg_type=MessageType.DOMAIN_ASSIGNMENT,
                    sender_id=scheduler.node_id,
                    timestamp=time.time(),
                    position=scheduler.position,
                    task_id=task_id,
                    payload=domain
                )
                scheduler.send_message(domain_msg, agent_ids)
            
            # Wait for domain acceptance
            time.sleep(0.1)
            
            # Initiate consensus
            start_time = time.time()
            schedulers[0].initiate_consensus(task_id, task_data, domain)
            
            # Wait for consensus
            timeout = 5.0
            committed = False
            while time.time() - start_time < timeout:
                committed_count = sum(1 for agent in agents 
                                    if agent.get_consensus_result(task_id) is not None)
                if committed_count >= len(agents) * 2 // 3:
                    committed = True
                    break
                time.sleep(0.01)
            
            end_time = time.time()
            
            # Collect statistics
            if committed:
                latency = (end_time - start_time) * 1000
                latencies_list.append(latency)
                
                net_stats = network.get_statistics()
                messages_list.append(net_stats['total_messages'])
                
                # Collect spatiotemporal rejections
                total_rejections = sum(node.spatiotemporal_rejections for node in all_nodes)
                spatiotemporal_rejections_list.append(total_rejections)
            
            network.stop()
            
            if (run + 1) % 10 == 0:
                print(f"  Completed {run + 1}/{num_runs} runs")
        
        return {
            'messages_mean': np.mean(messages_list),
            'messages_std': np.std(messages_list),
            'latency_mean': np.mean(latencies_list),
            'latency_std': np.std(latencies_list),
            'spatiotemporal_rejections_mean': np.mean(spatiotemporal_rejections_list),
            'success_rate': len(latencies_list) / num_runs
        }
    
    def run_all_experiments(self):
        """Run all baseline decomposition experiments"""
        exp_config = self.config['experiments']['baseline_decomposition']
        num_runs = exp_config['num_runs']
        
        n = self.config['system']['n']
        k = self.config['system']['k']
        m = self.config['system']['m']
        
        # 1. PBFT (n=30)
        print("\n" + "="*70)
        print("EXPERIMENT 1: PBFT (Global, n=30)")
        print("="*70)
        self.results['pbft'] = self.run_pbft_experiment(n, num_runs)
        
        # 2. PBFT-Local (k=3)
        print("\n" + "="*70)
        print("EXPERIMENT 2: PBFT-Local (k=3)")
        print("="*70)
        self.results['pbft_local'] = self.run_pbft_local_experiment(k, num_runs)
        
        # 3. CTG-LC (k=3, m=3)
        print("\n" + "="*70)
        print("EXPERIMENT 3: CTG-LC (k=3, m=3)")
        print("="*70)
        self.results['ctg_lc'] = self.run_ctg_lc_experiment(k, m, num_runs)
        
        # 4. CTG-LC-Global (k=30, m=3) - for validation
        print("\n" + "="*70)
        print("EXPERIMENT 4: CTG-LC-Global (k=30, m=3)")
        print("="*70)
        self.results['ctg_lc_global'] = self.run_ctg_lc_experiment(n, m, num_runs)
    
    def save_results(self, output_path: str = "data/baseline_decomposition.csv"):
        """Save results to CSV"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create DataFrame
        data = []
        for protocol, stats in self.results.items():
            data.append({
                'protocol': protocol,
                'messages_mean': stats['messages_mean'],
                'messages_std': stats['messages_std'],
                'latency_mean': stats['latency_mean'],
                'latency_std': stats['latency_std'],
                'success_rate': stats['success_rate']
            })
        
        df = pd.DataFrame(data)
        df.to_csv(output_path, index=False)
        
        print(f"\n✅ Results saved to {output_path}")
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(df.to_string(index=False))
        
        # Calculate reductions
        pbft_msgs = self.results['pbft']['messages_mean']
        ctg_msgs = self.results['ctg_lc']['messages_mean']
        msg_reduction = (1 - ctg_msgs / pbft_msgs) * 100
        
        pbft_lat = self.results['pbft']['latency_mean']
        ctg_lat = self.results['ctg_lc']['latency_mean']
        lat_reduction = (1 - ctg_lat / pbft_lat) * 100
        
        print(f"\n📊 Key Metrics:")
        print(f"  Communication Reduction: {msg_reduction:.1f}%")
        print(f"  Latency Reduction: {lat_reduction:.1f}%")

if __name__ == "__main__":
    print("="*70)
    print("CTG-LC Baseline Decomposition Experiment")
    print("="*70)
    
    experiment = BaselineDecompositionExperiment()
    experiment.run_all_experiments()
    experiment.save_results()
    
    print("\n✅ Experiment completed!")