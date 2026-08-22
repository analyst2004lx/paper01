import csv, glob, statistics as st
rows=[]
for f in glob.glob('experiments/e5_floor_*.csv'):
    rows += list(csv.DictReader(open(f,encoding='utf-8')))
def g(inst,mode,b):
    return [r for r in rows if r['instance']==inst and r['baseline_mode']==mode and float(r['budget_sec'])==b]
for inst in ('example_3x3x2','congested_8x4x4'):
    for mode in ('heuristic','ga'):
        print('='*70); print(inst, mode)
        ref=st.mean(float(r['ref_makespan']) for r in g(inst,mode,2.0))
        r2=st.mean(float(r['R2_makespan']) for r in g(inst,mode,2.0))
        print('  ref Cmax %.1f   R2 Cmax %.1f'%(ref,r2))
        # floor = 最小的未兑现预算格(gens=1)
        fl=[r for r in rows if r['instance']==inst and r['baseline_mode']==mode and float(r['budget_sec'])==0.005]
        f0=st.mean(float(r['R0_makespan']) for r in fl)
        fw=st.mean(float(r['R0_wall_ms']) for r in fl)
        r2w=st.mean(float(r['R2_wall_ms']) for r in fl)
        rat=[float(r['R2_makespan'])/float(r['R0_makespan']) for r in fl]
        print('  R0+ floor: Cmax %.1f  wall %.1fms   R2 wall %.2fms  speedup %.0fx'%(f0,fw,r2w,fw/r2w))
        print('  R2/R0+ at floor: %s  avg %.3f'%([round(x,3) for x in rat], st.mean(rat)))
        for b in (0.2,2.0):
            gg=g(inst,mode,b); rr=[float(r['R2_makespan'])/float(r['R0_makespan']) for r in gg]
            print('  R2/R0+ at %.1fs: %s avg %.3f'%(b,[round(x,3) for x in rr],st.mean(rr)))
        hon=[r for r in rows if r['instance']==inst and r['baseline_mode']==mode and r['budget_honored']=='True']
        print('  honored budgets:', sorted({float(r['budget_sec']) for r in hon}))
        ties=[r for r in rows if r['instance']==inst and r['baseline_mode']==mode and r['makespan_winner']=='tie']
        print('  tie cells:', len(ties))
