"""把仓库根下的 clbs/algorithm 挂成独立包 `_clbs_algorithm`,避免与 STRC/algorithm 撞名。

clbs 内部使用相对导入(from .network import ...),因此必须以 package 方式加载。
STRC 其余模块只应从本文件转导出符号,不要直接 `import algorithm.*` 指望落到 clbs。
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_STRC_ROOT = os.path.dirname(_HERE)
_REPO_ROOT = os.path.dirname(_STRC_ROOT)
_CLBS_ROOT = os.path.join(_REPO_ROOT, "clbs")
_CLBS_ALGO = os.path.join(_CLBS_ROOT, "algorithm")
_PKG = "_clbs_algorithm"

if not os.path.isdir(_CLBS_ALGO):
    raise ImportError(f"clbs algorithm package not found: {_CLBS_ALGO}")

CLBS_ROOT = _CLBS_ROOT
CLBS_INPUT = os.path.join(_CLBS_ROOT, "input")


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


# 按依赖序加载(与 clbs 相对导入一致)
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
clbs_ga = _ga

load_instance = _instance.load_instance
parse_instance = _instance.parse_instance
feature_params = _instance.feature_params
Instance = _instance.Instance
build_instance = _generator.build_instance
make_spec = _generator.make_spec

Network = _network.Network
ReservationTable = _network.ReservationTable
Router = _network.Router
RoutePlan = _network.RoutePlan
Segment = _network.Segment

DecodeResult = _decoder.DecodeResult
TransportRecord = _decoder.TransportRecord
OpRecord = _decoder.OpRecord
blocking_opponents = _decoder.blocking_opponents
decode = _decoder.decode
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
