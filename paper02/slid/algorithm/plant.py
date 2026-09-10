"""自建离散事件产线:场景 A/B/C,只作迁移与机理扫描,不作主验证。

三个配置共享操作词表与可行性掩码 F,只改规模、行程均值与时长变异:
  A  2 AGV + 1 臂, sigma=0.12, 短行程
  B  4 AGV + 2 臂, sigma=0.12, 长行程(均值迁移)
  C  与 A 同布局, sigma=0.35(变异迁移)

行驶时间显式取对数正态,sigma 可调。每条活动带接收侧时刻与命令账本。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from .ingest import Activity
from .procmodel import ProcessModel

GOTO_ARM = "/agv/goto_arm"
GOTO_WH = "/agv/goto_wh"
PROCESS = "/arm/process"

T0 = datetime(2024, 1, 1, 8, 0, 0)


@dataclass(frozen=True)
class PlantConfig:
    name: str
    n_agv: int
    n_arm: int
    n_jobs: int
    sigma: float
    dist_arm: float
    dist_wh: float
    t_process: float = 10.0
    seed: int = 0


CONFIGS = {
    "A": PlantConfig("A", n_agv=2, n_arm=1, n_jobs=90, sigma=0.12,
                     dist_arm=8.0, dist_wh=8.0, seed=1),
    "B": PlantConfig("B", n_agv=4, n_arm=2, n_jobs=120, sigma=0.12,
                     dist_arm=16.0, dist_wh=12.0, seed=2),
    "C": PlantConfig("C", n_agv=2, n_arm=1, n_jobs=90, sigma=0.35,
                     dist_arm=8.0, dist_wh=8.0, seed=3),
}


def reference_model(n_agv: int = 4, n_arm: int = 2) -> ProcessModel:
    """A/B/C 共用的 F:AGV 在两站间往返,臂只加工。"""
    m = ProcessModel()
    m.capable["agv"] = {GOTO_ARM, GOTO_WH}
    m.capable["arm"] = {PROCESS}
    m.operations = {GOTO_ARM, GOTO_WH, PROCESS}
    for i in range(1, n_agv + 1):
        d = f"agv_{i}"
        m.resources.add(d)
        m.feasible[d] = {(GOTO_ARM, GOTO_WH), (GOTO_WH, GOTO_ARM)}
    for i in range(1, n_arm + 1):
        d = f"arm_{i}"
        m.resources.add(d)
        m.feasible[d] = {(PROCESS, PROCESS)}
    m.n_models = 1
    return m


def _lognorm(mean_s: float, sigma: float, rng: np.random.Generator) -> float:
    z = rng.normal()
    return float(max(0.25, np.exp(np.log(mean_s) + sigma * z)))


def generate(cfg: PlantConfig | str) -> list[Activity]:
    """生成一条良性作业流。作业串行,设备按轮转指派,命令先于开始。"""
    if isinstance(cfg, str):
        cfg = CONFIGS[cfg]
    rng = np.random.default_rng(cfg.seed)
    acts: list[Activity] = []
    eid = 0
    t = T0
    for j in range(cfg.n_jobs):
        case = f"{cfg.name}_J{j:04d}"
        agv = f"agv_{(j % cfg.n_agv) + 1}"
        arm = f"arm_{(j % cfg.n_arm) + 1}"
        t, eid = _emit(acts, case, agv, GOTO_ARM, "wh", "arm",
                       cfg.dist_arm, cfg.sigma, rng, t, eid)
        t, eid = _emit(acts, case, arm, PROCESS, None, None,
                       cfg.t_process, cfg.sigma, rng, t, eid)
        t, eid = _emit(acts, case, agv, GOTO_WH, "arm", "wh",
                       cfg.dist_wh, cfg.sigma, rng, t, eid)
        t = t + timedelta(seconds=1.5)
    return acts


def _emit(acts, case, device, op, start, end, mean_s, sigma, rng, t, eid):
    dur = _lognorm(mean_s, sigma, rng)
    t_cmd = t
    t_start = t + timedelta(milliseconds=150)
    t_end = t_start + timedelta(seconds=dur)
    eid += 1
    acts.append(Activity(
        case=case, event_id=str(eid), device=device, op=op,
        workflow=f"WF_{device.split('_')[0]}",
        t_cmd=t_cmd, t_start=t_start, t_end=t_end, t_done=t_end,
        start_pos=start, end_pos=end, planned_s=mean_s, outcome="success",
    ))
    return t_end + timedelta(milliseconds=200), eid
