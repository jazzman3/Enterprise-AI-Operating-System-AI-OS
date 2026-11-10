"""Reproducible localhost HTTP API benchmark. Requires running API + local demo mode.
No claim of real-world LLM inference performance.
"""
import argparse,concurrent.futures,datetime,json,statistics,time
from pathlib import Path
import httpx
p=argparse.ArgumentParser()
p.add_argument('--url',default='http://127.0.0.1:8000')
p.add_argument('--requests',type=int,default=300)
p.add_argument('--workers',type=int,default=8)
p.add_argument('--output',default='benchmarks/results.json')
a=p.parse_args()
headers={'Authorization':'Bearer local-analyst-key-change-me-now'}

def request_one(_):
    start=time.perf_counter()
    try:
       with httpx.Client(timeout=8) as client:
          r=client.get(a.url+'/api/v1/catalog',headers=headers)
       return {'seconds':time.perf_counter()-start,'ok':r.status_code==200,'status':r.status_code}
    except Exception as exc:return {'seconds':time.perf_counter()-start,'ok':False,'error':str(exc)}

def percentile(s,p):return s[round((len(s)-1)*p)]
with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
    t=time.perf_counter();records=list(pool.map(request_one,range(a.requests)));elapsed=time.perf_counter()-t
lat=sorted(x['seconds']*1000 for x in records)
report={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scenario':'GET /api/v1/catalog — synthetic deterministic local demo',
 'requests':a.requests,'concurrency':a.workers,'errors':sum(not x['ok'] for x in records),'duration_s':round(elapsed,3),
 'throughput_rps':round(a.requests/elapsed,2),'latency_ms':{'p50':round(percentile(lat,.5),3),'p95':round(percentile(lat,.95),3),'p99':round(percentile(lat,.99),3)},
 'notes':'Local HTTP API benchmark, includes creating per-request client. Not production-scale, agent inference, cloud, or true LLM benchmark.'}
Path(a.output).parent.mkdir(parents=True,exist_ok=True)
Path(a.output).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
if report['errors']:raise SystemExit(1)
