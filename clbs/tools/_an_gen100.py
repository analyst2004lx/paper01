# -*- coding: utf-8 -*-
"""临时分析:同代数(局部搜索免费)口径下各档的对比。"""
import json
import statistics as st
from collections import defaultdict

from scipy.stats import wilcoxon

recs = [json.loads(l) for l in
        open('output/matrix/gen100/records.jsonl', encoding='utf-8') if l.strip()]
res = [r for r in recs if r.get('kind') == 'result']
print('results:', len(res))

by = defaultdict(dict)
for r in res:
    by[(r['instance'], r['seed'])][r['arm']] = r

print()
print('=== 同代数 100gen x 60pop:局部搜索的解码不计入预算,等于免费 ===')
for base in ['twostage', 'nofeedback', 'opendispatch', 'nostagger']:
    pairs = [(v[base]['makespan'], v['closed']['makespan'])
             for v in by.values() if base in v and 'closed' in v]
    d = [a - b for a, b in pairs]
    nz = [x for x in d if x != 0]
    p = wilcoxon([a for a, b in pairs], [b for a, b in pairs]).pvalue if nz else 1.0
    print(f'closed vs {base:14s} n={len(pairs):3d} 非平局={len(nz):3d} '
          f'平均相对收益 {st.mean([(a - b) / a for a, b in pairs]):+.2%}  p={p:.4f}')

print()
print('=== 各档实际消耗的挂钟时间与均值 ===')
t = defaultdict(list)
m = defaultdict(list)
for r in res:
    t[r['arm']].append(r.get('runtime_sec') or 0.0)
    m[r['arm']].append(r['makespan'])
for k in sorted(t, key=lambda x: -st.mean(t[x])):
    print(f'  {k:14s} {st.mean(t[k]):7.1f}s   平均 C_max {st.mean(m[k]):6.2f}')

print()
print('=== 按格子(算例)分解 closed vs nofeedback ===')
cell = defaultdict(list)
for v in by.values():
    if 'nofeedback' in v and 'closed' in v:
        cell[v['closed']['instance']].append(
            (v['nofeedback']['makespan'], v['closed']['makespan']))
for name, pairs in sorted(cell.items()):
    g = st.mean([(a - b) / a for a, b in pairs])
    nz = [1 for a, b in pairs if a != b]
    p = wilcoxon([a for a, b in pairs], [b for a, b in pairs]).pvalue if nz else 1.0
    print(f'  {name:34s} {g:+7.2%}  n={len(pairs)} 非平局={len(nz)} p={p:.3f}')
