import argparse,json
from .core import validate_catalog,CATALOG,init_db,AGENTS,WORKFLOWS
p=argparse.ArgumentParser()
p.add_argument('command',choices=['validate','catalog','init-db'])
a=p.parse_args()
if a.command=='validate':
 validate_catalog();print(f"VALID: departments={len(CATALOG['departments'])} agents={len(AGENTS)} workflows={len(WORKFLOWS)}")
elif a.command=='catalog':print(json.dumps(CATALOG,indent=2))
else:init_db();print('Database initialized')
