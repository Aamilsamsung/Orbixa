"""Orbixa cloud job broker. Experimental: SQLite on ephemeral Render filesystem."""
import os, json, uuid, sqlite3, secrets, time, math, importlib.util
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal

app=FastAPI(title="Orbixa API",version="0.7.0")
app.add_middleware(CORSMiddleware,allow_origins=["https://orbixa-science-preview.onrender.com","http://localhost:8080"],allow_methods=["GET","POST"],allow_headers=["Content-Type","Authorization","X-Worker-Key"])
DB=os.getenv("ORBIXA_QUEUE_DB","/tmp/orbixa-queue.sqlite3")
MAX_ATOMS=10
ELEMENTS={"H":1,"He":2,"Li":3,"Be":4,"B":5,"C":6,"N":7,"O":8,"F":9,"Ne":10,"Na":11,"Mg":12,"Al":13,"Si":14,"P":15,"S":16,"Cl":17,"Ar":18,"K":19,"Ca":20}
class Calculation(BaseModel):
    xyz:str=Field(min_length=8,max_length=4000)
    method:Literal["RHF","UHF","RKS","UKS"]="RHF"
    basis:Literal["sto-3g"]="sto-3g"
    functional:Literal["pbe","b3lyp"]="pbe"
    charge:int=Field(default=0,ge=-3,le=3)
    spin:int=Field(default=0,ge=0,le=5)
    optimize:bool=False
    analyze:bool=True
class WorkerResult(BaseModel):
    status:Literal["completed","failed"]
    result:dict|None=None
    error:str|None=None
def owner_key():
    key=os.getenv("ORBIXA_OWNER_KEY","")
    return key if len(key)>=24 else None
def worker_key():
    key=os.getenv("ORBIXA_WORKER_KEY","")
    return key if len(key)>=24 else None
def owner_auth(authorization):
    key=owner_key()
    if not key or not authorization or not secrets.compare_digest(authorization,"Bearer "+key):
        raise HTTPException(401,"Owner authorization required")
def worker_auth(key):
    secret=worker_key()
    if not secret or not key or not secrets.compare_digest(key,secret):
        raise HTTPException(401,"Worker authorization required")
@contextmanager
def connection():
    con=sqlite3.connect(DB,timeout=10,isolation_level=None)
    con.row_factory=sqlite3.Row
    try: yield con
    finally: con.close()
def init_db():
    with connection() as c:
        c.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, request TEXT NOT NULL, result TEXT, error TEXT, created REAL NOT NULL, updated REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, lease_until REAL NOT NULL DEFAULT 0, lease_token TEXT)")
init_db()
def validate_xyz(req):
    lines=req.xyz.strip().splitlines()
    try: n=int(lines[0])
    except (IndexError,ValueError): raise ValueError("XYZ must start with atom count")
    if not 1<=n<=MAX_ATOMS or len(lines)!=n+2: raise ValueError("XYZ must contain 1–10 atoms and match its declared atom count")
    atoms=[]
    for line in lines[2:]:
        parts=line.split()
        if len(parts)!=4 or parts[0] not in ELEMENTS: raise ValueError("Malformed atom or unsupported element")
        try: coords=[float(v) for v in parts[1:]]
        except ValueError: raise ValueError("Invalid coordinates")
        if not all(math.isfinite(x) and abs(x)<1000 for x in coords): raise ValueError("Coordinates must be finite")
        for _,other in atoms:
            if sum((x-y)**2 for x,y in zip(coords,other))<0.04: raise ValueError("Atoms are too close")
        atoms.append((parts[0],coords))
    electrons=sum(ELEMENTS[a] for a,_ in atoms)-req.charge
    if electrons<1 or req.spin>electrons or (electrons-req.spin)%2: raise ValueError("Invalid charge/spin")
    if req.method in ("RHF","RKS") and (req.spin!=0 or electrons%2): raise ValueError("Restricted methods require closed-shell molecules")
    if req.optimize: raise ValueError("Geometry optimization is disabled in the initial worker tier")
    return atoms
def view(row):
    d=dict(row)
    d.pop("lease_token",None)
    d["request"]=json.loads(d["request"])
    d["result"]=json.loads(d["result"]) if d["result"] else None
    return d
@app.get("/health")
def health():
    return {"status":"ok","version":"0.7.0","mode":"pc-worker-queue","calculation_enabled":bool(owner_key() and worker_key()),"pyscf_on_api":False}
@app.get("/api/limits")
def limits():
    return {"max_atoms":MAX_ATOMS,"max_concurrent_per_owner":1,"methods":["RHF","UHF","RKS","UKS"],"basis":["sto-3g"],"optimization":False,"worker_timeout_seconds":120,"storage":"ephemeral SQLite; jobs can be lost on restart","configured":bool(owner_key() and worker_key())}
@app.post("/api/validate")
def validate(req:Calculation):
    try: atoms=validate_xyz(req)
    except ValueError as e: raise HTTPException(422,str(e))
    return {"valid":True,"atom_count":len(atoms)}
@app.post("/api/jobs",status_code=202)
def submit(req:Calculation,authorization:str|None=Header(default=None)):
    owner_auth(authorization)
    try: validate_xyz(req)
    except ValueError as e: raise HTTPException(422,str(e))
    now=time.time()
    with connection() as c:
        c.execute("BEGIN IMMEDIATE")
        c.execute("UPDATE jobs SET status='failed',error='Worker lease expired',updated=? WHERE status='running' AND lease_until<?",(now,now))
        count=c.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
        if count>=1: raise HTTPException(429,"One pending/running job at a time")
        key=str(uuid.uuid4())
        c.execute("INSERT INTO jobs (id,status,request,created,updated) VALUES (?,?,?,?,?)",(key,"queued",req.model_dump_json(),now,now))
    return {"id":key,"status":"queued"}
@app.get("/api/jobs")
def list_jobs(authorization:str|None=Header(default=None)):
    owner_auth(authorization)
    with connection() as c: return [view(r) for r in c.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT 30")]
@app.get("/api/jobs/{job_id}")
def get_job(job_id:str,authorization:str|None=Header(default=None)):
    owner_auth(authorization)
    with connection() as c: row=c.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
    if not row: raise HTTPException(404,"Job not found")
    return view(row)
@app.post("/api/worker/claim")
def claim(x_worker_key:str|None=Header(default=None)):
    worker_auth(x_worker_key)
    now=time.time()
    with connection() as c:
        c.execute("BEGIN IMMEDIATE")
        c.execute("UPDATE jobs SET status='failed',error='Worker timed out',updated=? WHERE status='running' AND lease_until<?",(now,now))
        row=c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if not row: return {"job":None}
        token=secrets.token_urlsafe(32)
        c.execute("UPDATE jobs SET status='running',attempts=attempts+1,updated=?,lease_until=?,lease_token=? WHERE id=?",(now,now+150,token,row["id"]))
        return {"job":{"id":row["id"],"request":json.loads(row["request"]),"lease_token":token}}
@app.post("/api/worker/jobs/{job_id}/complete")
def complete(job_id:str,payload:WorkerResult,x_worker_key:str|None=Header(default=None),x_lease_token:str|None=Header(default=None)):
    worker_auth(x_worker_key)
    if not x_lease_token: raise HTTPException(401,"Lease token required")
    with connection() as c:
        c.execute("BEGIN IMMEDIATE")
        row=c.execute("SELECT status,lease_token,lease_until FROM jobs WHERE id=?",(job_id,)).fetchone()
        if not row or row["status"]!="running" or row["lease_until"]<time.time() or not secrets.compare_digest(row["lease_token"] or "",x_lease_token):
            raise HTTPException(409,"Lease invalid or expired")
        if len(json.dumps(payload.model_dump()))>100000: raise HTTPException(413,"Result too large")
        c.execute("UPDATE jobs SET status=?,result=?,error=?,updated=?,lease_token=NULL WHERE id=?",(payload.status,json.dumps(payload.result) if payload.result else None,(payload.error or "")[:2000],time.time(),job_id))
    return {"saved":True}
