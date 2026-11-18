"""Re-sum the four seats' Claude Code session logs (usage per assistant message) and price them at public list prices.
Every model-spend figure in README, FACTORY and the deck comes from this output only.
De-duplication: the last usage record per message id. Printed twice: all records, and the room window 2026-11-17 04:57Z to 10:30Z.
Reads usage.jsonl next to this file (usage fields only; extract.py made it). Run: python3 aggregate.py"""
import json,glob,os,collections,sys
HERE=os.path.dirname(os.path.abspath(__file__))
# Public list prices, USD per million tokens: input, output, cache read, cache write 5 min (1.25x input), cache write 1 h (2x input)
P={'claude-opus-5-5':(4.0,20.0,0.20,5.0,8.0),'claude-sonnet-5-5':(2.0,10.0,0.20,2.5,4.0)}
seats=['builder','verifier','cost-auditor','planner']
def run(lo=None,hi=None):
    tot=collections.defaultdict(lambda:collections.Counter()); cost=collections.Counter(); unk=set()
    last={}  # last usage record per (seat, message id), in file order
    for line in open(os.path.join(HERE,'usage.jsonl'),encoding='utf-8'):
        r=json.loads(line)
        if lo and r['ts']<lo: continue
        if hi and r['ts']>hi: continue
        last[(r['seat'],r['id'])]=r
    for r in last.values():
        s=r['seat']; c=tot[s]
        c['in']+=r['in']; c['out']+=r['out']; c['cr']+=r['cache_read']; c['w5']+=r['w5']; c['w1']+=r['w1']; c['msgs']+=1
        if r['model'] not in P: unk.add(r['model']); continue
        pi,po,pr,p5,p1=P[r['model']]
        cost[s]+=(r['in']*pi+r['out']*po+r['cache_read']*pr+r['w5']*p5+r['w1']*p1)/1e6
    return tot,cost,unk
def show(title,lo=None,hi=None):
    tot,cost,unk=run(lo,hi); print('##',title,'unknown models:',unk or 'none')
    T=collections.Counter(); C=0
    for s in seats:
        c=tot[s]; T.update(c); C+=cost[s]
        print(f"{s:13} msgs={c['msgs']:5} in={c['in']:>10,} out={c['out']:>10,} cache_write={c['w5']+c['w1']:>12,}(1h={c['w1']:,}) cache_read={c['cr']:>13,} total={c['in']+c['out']+c['w5']+c['w1']+c['cr']:>13,} usd={cost[s]:.2f}")
    print(f"{'ALL':13} msgs={T['msgs']:5} in={T['in']:>10,} out={T['out']:>10,} cache_write={T['w5']+T['w1']:>12,} cache_read={T['cr']:>13,} total={T['in']+T['out']+T['w5']+T['w1']+T['cr']:>13,} usd={C:.2f}")
if __name__=='__main__':
    show('all records in seat session logs')
    show('room window 2026-11-17T04:57Z..10:30Z','2026-11-17T04:57:00','2026-11-17T10:30:59')
