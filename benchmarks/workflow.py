"""End-to-end workflow API benchmark with approval and audit verification."""
import os,json,tempfile,time,statistics,datetime
from pathlib import Path
from fastapi.testclient import TestClient
os.environ['AISX_ALLOW_LOCAL_DEMO']='true'
with tempfile.TemporaryDirectory() as td:
 os.environ['AISX_DB_PATH']=td+'/benchmark.db'
 from aisx_os.api import app
 a={'Authorization':'Bearer local-analyst-key-change-me-now'}
 b={'Authorization':'Bearer local-approver-key-change-me-now'}
 admin={'Authorization':'Bearer local-admin-key-change-me-now'}
 samples=[]
 with TestClient(app) as c:
  for i in range(100):
   t=time.perf_counter()
   run=c.post('/api/v1/runs',headers=a,json={'workflow':'security_incident','task':f'Synthetic event {i}'}).json()
   result=c.post(f"/api/v1/runs/{run['id']}/review",headers=b,json={'approve':True}).json()
   samples.append({'ms':(time.perf_counter()-t)*1000,'ok':result['status']=='completed' and len(result['outputs'])==4})
  audit=c.get('/api/v1/audit/verify',headers=admin).json()['valid']
 s=sorted(x['ms'] for x in samples)
 report={'scenario':'100 durable 4-step security workflows with human-role approval (automated test authorization)','runs':len(samples),'completed':sum(x['ok'] for x in samples),'audit_integrity':audit,
    'latency_ms':{'p50':round(s[49],3),'p95':round(s[94],3),'p99':round(s[98],3)},
    'notes':'In-process API execution. Uses synthetic scenarios and reviewer-key automation; not an LLM accuracy or cloud throughput benchmark.'}
 Path('benchmarks/workflow_results.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
 if not all(x['ok'] for x in samples) or not audit:raise SystemExit(1)
