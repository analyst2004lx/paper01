"""把仓库根下的 clbs/algorithm 挂成独立包 `_clbs_algorithm`,避免与 STRC/algorithm 撞名。

clbs 内部使用相对导入(from .network import ...),因此必须以 package 方式加载。
STRC 其余模块只应从本文件转导出符号,不要直接 `import algorithm.*` 指望落到 clbs。

Mount clbs/algorithm, under the repository root, as a separate package `_clbs_algorithm`, so the name does not collide with STRC/algorithm.

clbs uses relative imports internally (from .network import ...), so it must be loaded as a package.
Other STRC modules should re-export symbols only from this file; do not `import algorithm.*` and expect to land in clbs.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_STRC_ROOT = os.path.dirname(_HERE)
_REPO_ROOT = os.path.dirname(_STRC_ROOT)
_CLBS_ROOT = os.path.join(_REPO_ROOT, "clbs_new")
_CLBS_ALGO = os.path.join(_CLBS_ROOT, "algorithm")
_PKG = "_clbs_algorithm"

if not os.path.isdir(_CLBS_ALGO):
    raise ImportError(f"clbs algorithm package not found: {_CLBS_ALGO}")

CLBS_ROOT = _CLBS_ROOT
# 算例按 clbs_new 的布局(毛坯库、成品库分设,机器挂支线)与节点模型重新生成,
# 文件名与子目录(ext/、pub/)沿用旧版,见 tools/gen_instances.py。
# Instances are regenerated for the clbs_new layout (separate raw and finished stores, machines
# on spurs) and node model; names and subfolders (ext/, pub/) follow the old ones.
CLBS_INPUT = os.path.join(_STRC_ROOT, "input", "instances")


def _ensure_pkg() -> types.ModuleType:
    if _PKG in sys.modules:
        return sys.modules[_PKG]
    pkg = types.ModuleType(_PKG)
    pkg.__path__ = [_CLBS_ALGO]  # type: ignore[attr-defined]
    pkg.__package__ = _PKG
    sys.modules[_PKG] = pkg
    return pkg


def _load_sub(name: str):
    full = f"{_PKG}.{name}"
    if full in sys.modules:
        return sys.modules[full]
    _ensure_pkg()
    path = os.path.join(_CLBS_ALGO, f"{name}.py")
    spec = importlib.util.spec_from_file_location(full, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    setattr(sys.modules[_PKG], name, mod)
    return mod


# 按依赖序加载(与 clbs 相对导入一致) / Load in dependency order (same as clbs relative imports)
_instance = _load_sub("instance")
_network = _load_sub("network")
_stats = _load_sub("stats")
_pricing = _load_sub("pricing")
_decoder = _load_sub("decoder")
_ga = _load_sub("ga")
_baseline = _load_sub("baseline")
_validator = _load_sub("validator")
_report = _load_sub("report")
_generator = _load_sub("generator")

# 供 schedule_io 等复用 clbs 染色体构造(不要在 STRC 里再实现一遍)
# Reuse clbs chromosome construction here; do not implement it again inside STRC.
clbs_ga = _ga

# 机器节点容量 c:算例文件按 c=2 生成(paper01 的对照点),本文默认取 c=3;
# 设环境变量 STRC_MACHINE_CAP=2 即复现 experiments_c2/ 的结果,取 inf 为不限。
# Machine-node capacity c: instance files carry c=2 (paper01's reference point); this paper
# defaults to c=3. Set STRC_MACHINE_CAP=2 to reproduce experiments_c2/, or inf for unlimited.
_cap_env = os.environ.get("STRC_MACHINE_CAP", "3").strip().lower()
MACHINE_CAPACITY = None if _cap_env in ("inf", "none") else int(_cap_env)


def _with_capacity(inst):
    import dataclasses
    if not inst.node_model:
        return inst
    return dataclasses.replace(inst, machine_capacity=MACHINE_CAPACITY)


def load_instance(path: str):
    return _with_capacity(_instance.load_instance(path))


def parse_instance(data: dict):
    return _with_capacity(_instance.parse_instance(data))



feature_params = _instance.feature_params
Instance = _instance.Instance
build_instance = _generator.build_instance
make_spec = _generator.make_spec
make_pub_spec = _generator.make_pub_spec

Network = _network.Network
ReservationTable = _network.ReservationTable
Router = _network.Router
RoutePlan = _network.RoutePlan
Segment = _network.Segment
NodeModel = _network.NodeModel
NodeTable = _network.NodeTable
TaskPlan = _network.TaskPlan
NODE_INF = _network.INF
NODE_EPS = _network.NODE_EPS

DecodeResult = _decoder.DecodeResult
TransportRecord = _decoder.TransportRecord
OpRecord = _decoder.OpRecord
blocking_opponents = _decoder.blocking_opponents
decode = _decoder.decode
dispatch_exact_nodes = _decoder.dispatch_exact_nodes
critical_chain = _decoder.critical_chain

validate = _validator.validate

GAConfig = _ga.GAConfig
run_ga = _ga.run_ga

ARMS = _baseline.ARMS
solve_arm = _baseline.solve_arm

gantt_text = _report.gantt_text
wilcoxon_signed_rank = getattr(_stats, "wilcoxon_signed_rank", None)

__all__ = [
    "CLBS_ROOT",
    "CLBS_INPUT",
    "load_instance",
    "feature_params",
    "Instance",
    "Network",
    "ReservationTable",
    "DecodeResult",
    "blocking_opponents",
    "decode",
    "critical_chain",
    "validate",
    "GAConfig",
    "run_ga",
    "ARMS",
    "solve_arm",
    "gantt_text",
    "wilcoxon_signed_rank",
]
