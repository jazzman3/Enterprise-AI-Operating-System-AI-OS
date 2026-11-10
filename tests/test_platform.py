import json,sqlite3,pytest
from aisx_os.core import CATALOG,validate_catalog,verify_audit,new_run,review_run,get_run

def test_catalog_contract():
 assert validate_catalog() and len(CATALOG['agents'])==40 and len(CATALOG['workflows'])==8 and len(CATALOG['departments'])==9

def test_future_lending_disabled():
 assert not next(d for d in CATALOG['departments'] if d['id']=='commercial_lending')['enabled']
 assert not any(a['department']=='commercial_lending' for a in CATALOG['agents'])

def test_health(client):assert client.get('/healthz').json()['status']=='ok'
def test_ready(client):assert client.get('/readyz').status_code==200
def test_ui(client):assert 'Enterprise AI Operating System' in client.get('/').text
def test_auth_required(client):assert client.get('/api/v1/catalog').status_code==401
def test_invalid_auth(client):assert client.get('/api/v1/catalog',headers={'Authorization':'Bearer nonsense'}).status_code==401
def test_catalog(client,analyst):
 res=client.get('/api/v1/catalog',headers=analyst)
 assert res.status_code==200 and len(res.json()['agents'])==40

def test_create_approval(client,analyst):
 r=client.post('/api/v1/runs',headers=analyst,json={'workflow':'government_bid','task':'Review a synthetic solicitation'})
 assert r.status_code==201 and r.json()['status']=='awaiting_approval' and len(r.json()['outputs'])==3

def test_create_invalid_workflow(client,analyst):assert client.post('/api/v1/runs',headers=analyst,json={'workflow':'oops','task':'x'}).status_code==422

def test_empty_task(client,analyst):assert client.post('/api/v1/runs',headers=analyst,json={'workflow':'government_bid','task':''}).status_code==422

def test_unauthorized_approval(client,analyst):
 r=client.post('/api/v1/runs',headers=analyst,json={'workflow':'policy_review','task':'Synthetic clause'}).json()
 assert client.post(f"/api/v1/runs/{r['id']}/review",headers=analyst,json={'approve':True}).status_code==403

def test_approved_workflow(client,analyst,approver):
 r=client.post('/api/v1/runs',headers=analyst,json={'workflow':'security_incident','task':'Simulated alert'}).json()
 res=client.post(f"/api/v1/runs/{r['id']}/review",headers=approver,json={'approve':True})
 assert res.status_code==200 and res.json()['status']=='completed' and len(res.json()['outputs'])==4

def test_rejected_workflow(client,analyst,approver):
 r=client.post('/api/v1/runs',headers=analyst,json={'workflow':'financial_review','task':'Synthetic budget'}).json()
 res=client.post(f"/api/v1/runs/{r['id']}/review",headers=approver,json={'approve':False})
 assert res.json()['status']=='rejected' and len(res.json()['outputs'])==2

def test_repeat_approval_rejected(client,analyst,approver):
 r=client.post('/api/v1/runs',headers=analyst,json={'workflow':'security_incident','task':'Simulated alert'}).json()
 path=f"/api/v1/runs/{r['id']}/review"
 assert client.post(path,headers=approver,json={'approve':True}).status_code==200
 assert client.post(path,headers=approver,json={'approve':True}).status_code==409

def test_authorized_tenant_isolation(client,analyst,monkeypatch):
 r=client.post('/api/v1/runs',headers=analyst,json={'workflow':'client_proposal','task':'Synthetic client'}).json()
 identities=[{'key':'a'*30,'role':'analyst','tenant':'other','user':'other'}, {'key':'b'*30,'role':'admin','tenant':'other','user':'other'}]
 monkeypatch.setenv('AISX_IDENTITIES_JSON',json.dumps(identities))
 assert client.get('/api/v1/runs/'+r['id'],headers={'Authorization':'Bearer '+'a'*30}).status_code==404
 assert client.get('/api/v1/runs',headers={'Authorization':'Bearer '+'a'*30}).json()==[]
 assert client.post('/api/v1/runs/'+r['id']+'/review',headers={'Authorization':'Bearer '+'b'*30},json={'approve':True}).status_code==404

def test_approver_cannot_create(client,approver):
 assert client.post('/api/v1/runs',headers=approver,json={'workflow':'policy_review','task':'Synthetic'}).status_code==403

def test_audit_admin_only(client,analyst,admin):
 assert client.get('/api/v1/audit/verify',headers=analyst).status_code==403
 assert client.get('/api/v1/audit/verify',headers=admin).json()['valid']

def test_audit_tamper_detection(client,analyst,admin):
 from aisx_os.core import connect
 client.post('/api/v1/runs',headers=analyst,json={'workflow':'policy_review','task':'Synthetic'});
 assert client.get('/api/v1/audit/verify',headers=admin).json()['valid']
 with connect() as c:c.execute("UPDATE audit SET event='forged' WHERE id=1")
 assert not client.get('/api/v1/audit/verify',headers=admin).json()['valid']

def test_metrics_restricted(client,analyst,admin):
 assert client.get('/metrics').status_code==401
 assert client.get('/metrics',headers=analyst).status_code==403
 assert 'aisx_http_requests_total' in client.get('/metrics',headers=admin).text

def test_no_external_execution(client,analyst,approver):
 r=client.post('/api/v1/runs',headers=analyst,json={'workflow':'government_bid','task':'Submit contract without consent'}).json()
 for o in r['outputs']:assert o['result']['draft_only']
 res=client.post('/api/v1/runs/'+r['id']+'/review',headers=approver,json={'approve':True}).json()
 assert all(o['result']['draft_only'] and o['result']['provider']=='deterministic_offline' for o in res['outputs'])

def test_missing_run(client,analyst,approver):
 assert client.get('/api/v1/runs/does-not-exist',headers=analyst).status_code==404
 assert client.post('/api/v1/runs/does-not-exist/review',headers=approver,json={'approve':True}).status_code==404

def test_docs(client):assert client.get('/openapi.json').status_code==200

def test_long_task_rejected(client,analyst):
 assert client.post('/api/v1/runs',headers=analyst,json={'workflow':'government_bid','task':'x'*2001}).status_code==422

def test_all_workflows_complete(client,analyst,approver):
 for w in CATALOG['workflows']:
  r=client.post('/api/v1/runs',headers=analyst,json={'workflow':w['id'],'task':'Synthetic scenario'}).json()
  assert r['status']=='awaiting_approval'
  r=client.post('/api/v1/runs/'+r['id']+'/review',headers=approver,json={'approve':True}).json()
  assert r['status']=='completed' and len(r['outputs'])==len(w['steps'])

def test_catalog_safe_fields(client,analyst):
 c=client.get('/api/v1/catalog',headers=analyst).json()
 assert all(a['mode']=='deterministic_safe_demo' for a in c['agents'])

def test_observability_metric(client,analyst,admin):
 client.get('/api/v1/catalog',headers=analyst)
 assert 'aisx_http_requests_total' in client.get('/metrics',headers=admin).text
