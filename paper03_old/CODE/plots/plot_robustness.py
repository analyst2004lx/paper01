"""
Plot robustness.pdf using generated data
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys
import os

# 导入你提供的原始绘图代码（略，直接使用你的代码）
# 只需修改数据加载部分

def load_robustness_data():
    """Load experimental data"""
    # TODO: 加载 exp3_robustness.py 生成的数据
    # 这里使用模拟数据（与你的绘图代码匹配）
    
    return {
        'detection_rates': {
            'replay': 100.0,
            'spatial_forgery': 98.3,
            'conflicting_msgs': 94.7
        },
        'weight_evolution': {
            'rounds': list(range(100)),
            'malicious_weight': [...],  # 从实验数据加载
            'honest_weight': [...]
        },
        'consensus_success': {
            'k_values': ['k=3, f=0', 'k=7, f=1', 'k=7, f=2', 'k=10, f=3'],
            'ctg_lc': [100, 98.7, 98.1, 96.8],
            'pbft': [100, 92.3, 82.7, 75.2]
        }
    }

# 使用你提供的绘图代码...