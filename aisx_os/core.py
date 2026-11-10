"""Multi-tenant workflow engine with durable SQLite state and approval-gated progression.

Safe-by-default deterministic outputs; no external side effects or hidden network calls.
"""
from __future__ import annotations
import hashlib, hmac, json, os, re, secrets, sqlite3, time
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any

BASE=Path(__file__).resolve().parent.parent
CATALOG=json.loads((BASE/'config/catalog.json').read_text())
AGENTS={x['id']:x for x in CATALOG['agents']}
WORKFLOWS={x['id']:x for x in CATALOG['workflows']}
DEPARTMENTS={x['id']:x for x in CATALOG['departments']}
lock=RLock()

def db_path():
    return os.getenv('AISX_DB_PATH',str(BASE/'data'/'aisx.db'))

@contextmanager
def connect():
    path=db_path()
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(path,timeout=15)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=15000')
    try:
        yield c
        c.commit()
    except:
        c.rollback()
        raise
    finally:
        c.close()

def init_db():
    with connect() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, tenant TEXT NOT NULL, workflow TEXT NOT NULL,
           input TEXT NOT NULL, status TEXT NOT NULL, step INTEGER NOT NULL DEFAULT 0,
           created REAL NOT NULL, updated REAL NOT NULL, version INTEGER NOT NULL DEFAULT 1);
        CREATE INDEX IF NOT EXISTS idx_runs_tenant ON runs(tenant,created DESC);
        CREATE TABLE IF NOT EXISTS outputs(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL,
          step INTEGER NOT NULL, agent TEXT NOT NULL, output TEXT NOT NULL, created REAL NOT NULL,
          FOREIGN KEY(run_id) REFERENCES runs(id));
        CREATE UNIQUE INDEX IF NOT EXISTS idx_outputs_unique ON outputs(run_id,step);
        CREATE TABLE IF NOT EXISTS approvals(run_id TEXT PRIMARY KEY, approved INTEGER NOT NULL,
          reviewer TEXT NOT NULL, timestamp REAL NOT NULL, FOREIGN KEY(run_id) REFERENCES runs(id));
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant TEXT NOT NULL,
          run_id TEXT, actor TEXT NOT NULL,event TEXT NOT NULL,payload TEXT NOT NULL,
          timestamp REAL NOT NULL,prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
        ''')

def append_audit(c,tenant,run_id,actor,event,payload):
    prev=c.execute('SELECT hash FROM audit ORDER BY id DESC LIMIT 1').fetchone()
    prev_hash=prev['hash'] if prev else 'GENESIS'
    timestamp=time.time()
    body=json.dumps({'tenant':tenant,'run_id':run_id,'actor':actor,'event':event,
           'payload':payload,'timestamp':timestamp,'prev_hash':prev_hash},sort_keys=True,separators=(',',':'))
    digest=hashlib.sha256(body.encode()).hexdigest()
    c.execute('INSERT INTO audit(tenant,run_id,actor,event,payload,timestamp,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?)',
       (tenant,run_id,actor,event,json.dumps(payload,sort_keys=True),timestamp,prev_hash,digest))
    return digest

def verify_audit():
    prev='GENESIS'
    with connect() as c:
      for r in c.execute('SELECT * FROM audit ORDER BY id'):
        payload=json.loads(r['payload'])
        body=json.dumps({'tenant':r['tenant'],'run_id':r['run_id'],'actor':r['actor'],'event':r['event'],
         'payload':payload,'timestamp':r['timestamp'],'prev_hash':prev},sort_keys=True,separators=(',',':'))
        if r['prev_hash']!=prev or not hmac.compare_digest(hashlib.sha256(body.encode()).hexdigest(),r['hash']):return False
        prev=r['hash']
    return True

def validate_catalog():
    assert len(DEPARTMENTS)==9 and len(AGENTS)==40 and len(WORKFLOWS)==8
    for a in AGENTS.values():
      assert a['department'] in DEPARTMENTS and DEPARTMENTS[a['department']]['enabled']
    for w in WORKFLOWS.values():
      assert w['steps'] and w['steps'][-1]['requires_approval']
      for s in w['steps']:
        assert s['agent_id'] in AGENTS
    return True

def agent_response(agent_id,task):
    a=AGENTS[agent_id]
    safe=re.sub(r'[\x00-\x1f]',' ',task).strip()[:500]
    return {'agent_id':agent_id,'agent_name':a['name'],'department':a['department'],
      'draft_only':True,'provider':'deterministic_offline','task_summary':safe,
      'recommendations':[f'Validate facts and sources for {a["name"].lower()}.',
          'Document risks, assumptions and evidence.',
          'Obtain authorized human review before taking action.'],
      'disclaimer':'Generated demonstration draft; no external operation performed.'}

def run_view(c,r):
    output=[{'step':v['step'],'agent_id':v['agent'],'result':json.loads(v['output'])} for v in c.execute('SELECT * FROM outputs WHERE run_id=? ORDER BY step',(r['id'],))]
    app=c.execute('SELECT * FROM approvals WHERE run_id=?',(r['id'],)).fetchone()
    return {'id':r['id'],'tenant':r['tenant'],'workflow':r['workflow'],'status':r['status'],
      'step':r['step'],'created':r['created'],'updated':r['updated'],'outputs':output,
      'approval':({'approved':bool(app['approved']),'reviewer':app['reviewer']} if app else None)}

def process(c,run_id):
    r=c.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
    w=WORKFLOWS[r['workflow']]
    step=r['step']
    if r['status'] in ('completed','rejected'):return
    while step<len(w['steps']):
      s=w['steps'][step]
      if s['requires_approval']:
        app=c.execute('SELECT approved FROM approvals WHERE run_id=?',(run_id,)).fetchone()
        if app is None:
          c.execute('UPDATE runs SET status=?,step=?,updated=?,version=version+1 WHERE id=?',('awaiting_approval',step,time.time(),run_id))
          append_audit(c,r['tenant'],run_id,'system','approval_requested',{'step':step,'agent':s['agent_id']})
          return
        if not app['approved']:
          c.execute('UPDATE runs SET status=?,updated=?,version=version+1 WHERE id=?',('rejected',time.time(),run_id))
          return
      result=agent_response(s['agent_id'],r['input'])
      c.execute('INSERT OR IGNORE INTO outputs(run_id,step,agent,output,created) VALUES(?,?,?,?,?)',
          (run_id,step,s['agent_id'],json.dumps(result),time.time()))
      append_audit(c,r['tenant'],run_id,'system','step_completed',{'step':step,'agent':s['agent_id']})
      step+=1
    c.execute('UPDATE runs SET status=?,step=?,updated=?,version=version+1 WHERE id=?',('completed',step,time.time(),run_id))
    append_audit(c,r['tenant'],run_id,'system','run_completed',{})

def new_run(tenant,workflow,task,actor):
    if workflow not in WORKFLOWS:raise ValueError('Unknown workflow')
    task=task.strip()
    if not task or len(task)>2000:raise ValueError('Task must have 1-2000 characters')
    rid='run_'+secrets.token_hex(12)
    with lock,connect() as c:
      now=time.time()
      c.execute('INSERT INTO runs(id,tenant,workflow,input,status,step,created,updated) VALUES(?,?,?,?,?,?,?,?)',
        (rid,tenant,workflow,task,'running',0,now,now))
      append_audit(c,tenant,rid,actor,'run_created',{'workflow':workflow})
      process(c,rid)
      return run_view(c,c.execute('SELECT * FROM runs WHERE id=?',(rid,)).fetchone())

def get_run(tenant,rid):
    with connect() as c:
      r=c.execute('SELECT * FROM runs WHERE id=? AND tenant=?',(rid,tenant)).fetchone()
      return run_view(c,r) if r else None

def list_runs(tenant,limit=50):
    with connect() as c:
      return [run_view(c,r) for r in c.execute('SELECT * FROM runs WHERE tenant=? ORDER BY created DESC LIMIT ?',(tenant,min(limit,100)))]

def review_run(tenant,rid,approve,reviewer):
    with lock,connect() as c:
      r=c.execute('SELECT * FROM runs WHERE id=? AND tenant=?',(rid,tenant)).fetchone()
      if not r:return None
      if r['status']!='awaiting_approval':raise ValueError('Run is not awaiting approval')
      c.execute('INSERT INTO approvals(run_id,approved,reviewer,timestamp) VALUES(?,?,?,?)', (rid,int(approve),reviewer,time.time()))
      append_audit(c,tenant,rid,reviewer,'approved' if approve else 'rejected',{})
      if approve:process(c,rid)
      else:c.execute('UPDATE runs SET status=?,updated=? WHERE id=?',('rejected',time.time(),rid))
      return run_view(c,c.execute('SELECT * FROM runs WHERE id=?',(rid,)).fetchone())
