from pgmpy.models import BayesianModel
from pgmpy.estimators import MaximumLikelihoodEstimator
from pgmpy.inference import VariableElimination
import pandas as pd

# 构建贝叶斯网络结构（基于状态转移关系）
model = BayesianModel([
    ('AGV_idle', 'AGVMovingToRobotArm'),
    ('AGVMovingToRobotArm', 'AGVAtRobotArm'),
    ('AGVAtRobotArm', 'AGVMovingToOrigin'),
    ('AGVMovingToOrigin', 'AGV_idle'),
    ('RobotArm_idle', 'RobotArm_producing'),
    ('AGVAtRobotArm', 'RobotArm_producing')
])

# 生成模拟数据用于贝叶斯网络的训练
data = pd.DataFrame({
    'AGV_idle': [1, 0, 0, 0, 1, 1, 0, 1],
    'AGVMovingToRobotArm': [0, 1, 0, 0, 0, 0, 1, 0],
    'AGVAtRobotArm': [0, 0, 1, 0, 0, 0, 0, 0],
    'AGVMovingToOrigin': [0, 0, 0, 1, 0, 0, 0, 0],
    'RobotArm_idle': [1, 1, 0, 1, 0, 1, 1, 0],
    'RobotArm_producing': [0, 0, 1, 0, 1, 0, 0, 1]
})

# 使用最大似然估计来拟合参数
model.fit(data, estimator=MaximumLikelihoodEstimator)

# 进行推理
inference = VariableElimination(model)

# 查询某个状态的概率分布
query_result = inference.query(variables=['AGVAtRobotArm'], evidence={'AGV_idle': 1})
query_result
