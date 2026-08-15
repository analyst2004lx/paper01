"""
Simplified network simulator for CTG-LC experiments
"""
import random
import time
from typing import Dict, List, Callable
from queue import Queue
import threading
from .message import Message

class NetworkSimulator:
    """
    Simulates network with configurable delays and packet loss
    """
    
    def __init__(self, 
                 mean_delay: float = 0.03,  # 30ms
                 jitter: float = 0.01,       # ±10ms
                 packet_loss: float = 0.001, # 0.1%
                 bandwidth_limit: float = 100.0):  # 100 Mbps
        """
        Args:
            mean_delay: Average network delay (seconds)
            jitter: Delay variation (seconds)
            packet_loss: Packet loss probability
            bandwidth_limit: Bandwidth limit (Mbps)
        """
        self.mean_delay = mean_delay
        self.jitter = jitter
        self.packet_loss = packet_loss
        self.bandwidth_limit = bandwidth_limit
        
        # Node registry: node_id -> receive_callback
        self.nodes: Dict[str, Callable] = {}
        
        # Message queues for each node
        self.message_queues: Dict[str, Queue] = {}
        
        # Statistics
        self.total_messages = 0
        self.dropped_messages = 0
        self.total_bytes = 0
        
        # Bandwidth tracking (messages per second)
        self.bandwidth_history = []
        self.last_bandwidth_check = time.time()
        self.messages_since_last_check = 0
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        # Running flag
        self.running = False
        self.worker_threads = []
    
    def register_node(self, node_id: str, receive_callback: Callable):
        """
        Register a node with its message receive callback
        
        Args:
            node_id: Node identifier
            receive_callback: Function to call when message arrives
        """
        with self.lock:
            self.nodes[node_id] = receive_callback
            self.message_queues[node_id] = Queue()
    
    def unregister_node(self, node_id: str):
        """Unregister a node"""
        with self.lock:
            if node_id in self.nodes:
                del self.nodes[node_id]
                del self.message_queues[node_id]
    
    def send(self, message: Message, recipients: List[str]):
        """
        Send message to recipients with simulated delay
        
        Args:
            message: Message to send
            recipients: List of recipient node IDs
        """
        with self.lock:
            self.total_messages += len(recipients)
            self.messages_since_last_check += len(recipients)
            
            # Estimate message size (simplified)
            msg_size = len(str(message.to_dict()))
            self.total_bytes += msg_size * len(recipients)
        
        for recipient_id in recipients:
            # Simulate packet loss
            if random.random() < self.packet_loss:
                with self.lock:
                    self.dropped_messages += 1
                continue
            
            # Simulate network delay
            delay = max(0, random.gauss(self.mean_delay, self.jitter))
            
            # Schedule delivery
            threading.Timer(delay, self._deliver, args=(message, recipient_id)).start()
    
    def _deliver(self, message: Message, recipient_id: str):
        """Internal: Deliver message to recipient"""
        with self.lock:
            if recipient_id in self.nodes:
                # Add to message queue
                self.message_queues[recipient_id].put(message)
    
    def start(self):
        """Start network worker threads"""
        self.running = True
        
        # Start worker threads for each node
        for node_id in self.nodes.keys():
            worker = threading.Thread(target=self._worker, args=(node_id,), daemon=True)
            worker.start()
            self.worker_threads.append(worker)
        
        # Start bandwidth monitor
        monitor = threading.Thread(target=self._bandwidth_monitor, daemon=True)
        monitor.start()
        self.worker_threads.append(monitor)
    
    def stop(self):
        """Stop network"""
        self.running = False
        for thread in self.worker_threads:
            thread.join(timeout=1.0)
    
    def _worker(self, node_id: str):
        """Worker thread to process messages for a node"""
        while self.running:
            try:
                # Get message from queue (blocking with timeout)
                message = self.message_queues[node_id].get(timeout=0.1)
                
                # Call node's receive callback
                if node_id in self.nodes:
                    self.nodes[node_id](message)
                
            except:
                continue
    
    def _bandwidth_monitor(self):
        """Monitor bandwidth utilization"""
        while self.running:
            time.sleep(1.0)  # Check every second
            
            with self.lock:
                current_time = time.time()
                elapsed = current_time - self.last_bandwidth_check
                
                if elapsed > 0:
                    # Calculate messages per second
                    msgs_per_sec = self.messages_since_last_check / elapsed
                    
                    # Estimate bandwidth (assume 1KB per message)
                    bandwidth_mbps = (msgs_per_sec * 1024 * 8) / 1_000_000
                    
                    # Calculate utilization percentage
                    utilization = (bandwidth_mbps / self.bandwidth_limit) * 100
                    
                    self.bandwidth_history.append({
                        'time': current_time,
                        'msgs_per_sec': msgs_per_sec,
                        'bandwidth_mbps': bandwidth_mbps,
                        'utilization': utilization
                    })
                    
                    # Reset counters
                    self.messages_since_last_check = 0
                    self.last_bandwidth_check = current_time
    
    def get_statistics(self) -> dict:
        """Get network statistics"""
        with self.lock:
            return {
                'total_messages': self.total_messages,
                'dropped_messages': self.dropped_messages,
                'drop_rate': self.dropped_messages / max(1, self.total_messages),
                'total_bytes': self.total_bytes,
                'bandwidth_history': self.bandwidth_history.copy()
            }
    
    def reset_statistics(self):
        """Reset statistics counters"""
        with self.lock:
            self.total_messages = 0
            self.dropped_messages = 0
            self.total_bytes = 0
            self.bandwidth_history = []
            self.messages_since_last_check = 0
            self.last_bandwidth_check = time.time()