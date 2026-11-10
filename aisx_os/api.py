"""AISX AI OS API: scoped keys, tenant-isolated workflow execution and governance."""
import hashlib,hmac,json,os,time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends,FastAPI,HTTPException,Header,Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel,Field
from prometheus_client import Counter,Histogram,generate_latest,CONTENT_TYPE_LATEST
from .core import (AGENTS,WORKFLOWS,DEPARTMENTS,agent_response,get_run,init_db,list_runs,new_run,review_run,validate_catalog,verify_audit)

REQUESTS=Counter('aisx_http_requests_total','API requests',['route','result'])
LATENCY=Histogram('aisx_operation_seconds','Workflow operation durations',['operation'])

def identities():
    # explicit tenant:role:key mapping; do not silently use default keys
    cfg=os.getenv('AISX_IDENTITIES_JSON','')
    if cfg:
        try:ident=json.loads(cfg)
        except ValueError:raise RuntimeError('AISX_IDENTITIES_JSON must be JSON')
        if not isinstance(ident,list) or not ident:raise RuntimeError('At least one identity required')
        for x in ident:
            if x.get('role') not in ('analyst','approver','admin') or not x.get('tenant') or len(x.get('key',''))<24:raise RuntimeError('Identity configuration invalid')
        return ident
    if os.getenv('AISX_ALLOW_LOCAL_DEMO','false').lower()=='true':
        return [{'key':'local-analyst-key-change-me-now','tenant':'demo','role':'analyst','user':'analyst'},
          {'key':'local-approver-key-change-me-now','tenant':'demo','role':'approver','user':'approver'},
          {'key':'local-admin-key-change-me-now','tenant':'demo','role':'admin','user':'admin'}]
    raise RuntimeError('Configure AISX_IDENTITIES_JSON or set AISX_ALLOW_LOCAL_DEMO=true for localhost only')

@asynccontextmanager
async def lifespan(app):
    validate_catalog();identities();init_db();yield

app=FastAPI(title='AISX Enterprise AI OS',version='3.0.0',lifespan=lifespan,docs_url='/docs' if os.getenv('AISX_ENABLE_DOCS','true').lower()=='true' else None)

def principal(authorization:str|None=Header(None)):
    if not authorization or not authorization.startswith('Bearer '):raise HTTPException(401,'Bearer token required')
    given=authorization[7:].encode()
    for x in identities():
        if hmac.compare_digest(given,x['key'].encode()):return x
    raise HTTPException(401,'Invalid token')

def role(p,roles):
    if p['role'] not in roles:raise HTTPException(403,'Insufficient role')

def fail(x):
    REQUESTS.labels(x,'error').inc()

def ok(x):REQUESTS.labels(x,'ok').inc()

class NewRun(BaseModel):
    workflow:str
    task:str=Field(min_length=1,max_length=2000)
class Review(BaseModel):
    approve:bool

@app.get('/healthz')
def health():return {'status':'ok','service':'aisx-ai-os'}
@app.get('/readyz')
def ready():
    try:validate_catalog();init_db();identities();return {'status':'ready'}
    except Exception:raise HTTPException(503,'Dependency unavailable')
@app.get('/api/v1/catalog')
def catalog(p=Depends(principal)):
    ok('catalog');return {'departments':list(DEPARTMENTS.values()),'agents':list(AGENTS.values()),'workflows':list(WORKFLOWS.values())}
@app.get('/api/v1/capabilities')
def capabilities(p=Depends(principal)):
    return {'service':'AISX Enterprise AI OS','version':'3.0.0','workflow_count':len(WORKFLOWS),'agent_count':len(AGENTS),'department_count':len(DEPARTMENTS),'mode':'safe_deterministic_demo','integrations':['rag','mlops','sentinelforge'],'integration_status':'contracts_only_not_connected'}
@app.post('/api/v1/runs',status_code=201)
def create_run(body:NewRun,p=Depends(principal)):
    role(p,('analyst','admin'))
    try:
      with LATENCY.labels('create_run').time():res=new_run(p['tenant'],body.workflow,body.task,p.get('user',p['role']))
    except ValueError as e:fail('create_run');raise HTTPException(422,str(e))
    ok('create_run');return res
@app.get('/api/v1/runs')
def runs(p=Depends(principal)):
    ok('runs');return list_runs(p['tenant'])
@app.get('/api/v1/runs/{run_id}')
def run_detail(run_id:str,p=Depends(principal)):
    res=get_run(p['tenant'],run_id)
    if res is None:fail('run_detail');raise HTTPException(404,'Run not found')
    ok('run_detail');return res
@app.post('/api/v1/runs/{run_id}/review')
def review(run_id:str,body:Review,p=Depends(principal)):
    role(p,('approver','admin'))
    try:
      with LATENCY.labels('review_run').time():res=review_run(p['tenant'],run_id,body.approve,p.get('user',p['role']))
    except ValueError as e:fail('review');raise HTTPException(409,str(e))
    if res is None:fail('review');raise HTTPException(404,'Run not found')
    ok('review');return res
@app.get('/api/v1/audit/verify')
def audit_check(p=Depends(principal)):
    role(p,('admin',))
    return {'valid':verify_audit(),'note':'Local hash-chain integrity; independent external anchoring not configured'}
@app.get('/metrics')
def metrics(p=Depends(principal)):
    role(p,('admin',))
    return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)
@app.get('/',response_class=HTMLResponse)
def home():
    path=Path(__file__).resolve().parent.parent/'static'/'index.html'
    return path.read_text(encoding='utf-8')
