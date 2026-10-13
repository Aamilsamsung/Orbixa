"""Run on your own PC in WSL2 with PySCF installed.
Set ORBIXA_WORKER_KEY in your local environment, never in Git.
"""
import os,json,time,subprocess,sys,urllib.request,urllib.error
API=os.getenv("ORBIXA_API_URL","https://orbixa-api-preview.onrender.com").rstrip("/")
KEY=os.getenv("ORBIXA_WORKER_KEY","")
if len(KEY)<24: raise SystemExit("Set ORBIXA_WORKER_KEY (at least 24 characters) before starting")
def post(path,payload):
    data=json.dumps(payload).encode()
    req=urllib.request.Request(API+path,data=data,headers={"Content-Type":"application/json","X-Worker-Key":KEY},method="POST")
    with urllib.request.urlopen(req,timeout=40) as response: return json.load(response)
print("Orbixa worker started; polling",API,flush=True)
while True:
    try:
        claim=post("/api/worker/claim",{})
        job=claim.get("job")
        if job:
            print("Running",job["id"],flush=True)
            env=dict(os.environ,OPENBLAS_NUM_THREADS="2",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2")
            try:
                p=subprocess.run([sys.executable,os.path.join(os.path.dirname(__file__),"run_calculation.py")],input=json.dumps(job["request"]),text=True,capture_output=True,timeout=120,env=env)
                if p.returncode: outcome={"status":"failed","error":(p.stderr or p.stdout)[-1500:]}
                else: outcome={"status":"completed","result":json.loads(p.stdout)}
            except subprocess.TimeoutExpired: outcome={"status":"failed","error":"Calculation exceeded 120 seconds"}
            except Exception as exc: outcome={"status":"failed","error":str(exc)[:1000]}
            req=urllib.request.Request(API+"/api/worker/jobs/"+job["id"]+"/complete",data=json.dumps(outcome).encode(),headers={"Content-Type":"application/json","X-Worker-Key":KEY,"X-Lease-Token":job["lease_token"]},method="POST")
            with urllib.request.urlopen(req,timeout=30) as response: print("Submitted",json.load(response),flush=True)
        else: time.sleep(5)
    except (urllib.error.URLError,TimeoutError,ValueError) as exc:
        print("Connection issue:",str(exc)[:200],flush=True)
        time.sleep(10)
