import os, math, uuid, importlib.util, concurrent.futures
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal

app=FastAPI(title="Orbixa API",version="0.5.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:8080","https://orbixa-science-preview.onrender.com"],allow_methods=["GET","POST"],allow_headers=["Content-Type"])
pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
jobs={}
ELEMENTS={"H":1,"He":2,"Li":3,"Be":4,"B":5,"C":6,"N":7,"O":8,"F":9,"Ne":10,"Na":11,"Mg":12,"Al":13,"Si":14,"P":15,"S":16,"Cl":17,"Ar":18,"K":19,"Ca":20}
class Calculation(BaseModel):
    xyz:str=Field(min_length=8,max_length=12000)
    method:Literal["RHF","UHF","RKS","UKS"]="RHF"
    basis:Literal["sto-3g","3-21g","6-31g","cc-pvdz"]="sto-3g"
    functional:Literal["pbe","b3lyp"]="pbe"
    charge:int=Field(default=0,ge=-5,le=5)
    spin:int=Field(default=0,ge=0,le=10)
    optimize:bool=False
    analyze:bool=True
def validate_xyz(req):
    lines=req.xyz.strip().splitlines()
    try: count=int(lines[0])
    except (IndexError,ValueError): raise ValueError("XYZ must start with an integer atom count")
    if count<1 or count>100 or len(lines)!=count+2: raise ValueError("XYZ atom count does not match atom lines")
    atoms=[]
    for line in lines[2:]:
        fields=line.split()
        if len(fields)!=4 or fields[0] not in ELEMENTS: raise ValueError("Unsupported element or malformed atom row")
        try: coords=[float(v) for v in fields[1:]]
        except ValueError: raise ValueError("Coordinates must be numeric")
        if not all(math.isfinite(v) and abs(v)<10000 for v in coords): raise ValueError("Coordinates must be finite")
        atoms.append((fields[0],coords))
    for i,(_,a) in enumerate(atoms):
        for _,b in atoms[:i]:
            if sum((x-y)**2 for x,y in zip(a,b)) < 0.04:
                raise ValueError("Atoms are unrealistically close together")
    electrons=sum(ELEMENTS[s] for s,_ in atoms)-req.charge
    if electrons<=0 or req.spin>electrons or (electrons-req.spin)%2: raise ValueError("Invalid charge and spin combination")
    if req.method in ("RHF","RKS") and req.spin!=0: raise ValueError("Restricted methods require spin zero")
    if req.method in ("RHF","RKS") and electrons%2: raise ValueError("Restricted methods require an even electron count")
    return atoms
def compute(key,req):
    jobs[key]["status"]="running"
    try:
        from pyscf import gto,scf,dft
        mol=gto.M(atom=validate_xyz(req),unit="Angstrom",basis=req.basis,charge=req.charge,spin=req.spin,verbose=0)
        cls={"RHF":scf.RHF,"UHF":scf.UHF,"RKS":dft.RKS,"UKS":dft.UKS}[req.method]
        mf=cls(mol)
        if req.method.endswith("KS"): mf.xc=req.functional
        mf.max_cycle=100
        if req.optimize:
            from pyscf.geomopt.geometric_solver import optimize
            mol=optimize(mf,maxsteps=50)
            mf=cls(mol)
            if req.method.endswith("KS"): mf.xc=req.functional
        energy=float(mf.kernel())
        if not mf.converged or not math.isfinite(energy): raise RuntimeError("SCF did not converge")
        result={"energy_hartree":energy,"converged":True,"method":req.method,"basis":req.basis}
        if req.analyze:
            orbital=mf.mo_energy
            occupation=mf.mo_occ
            if isinstance(orbital,(tuple,list)):
                result["orbital_energies_hartree"]=[[float(e) for e in spin] for spin in orbital]
            else:
                values=[float(e) for e in orbital]
                result["orbital_energies_hartree"]=values
                occ=[e for e,o in zip(values,occupation) if o>0]
                vac=[e for e,o in zip(values,occupation) if o==0]
                if occ: result["homo_hartree"]=max(occ)
                if vac: result["lumo_hartree"]=min(vac)
                if occ and vac: result["homo_lumo_gap_ev"]=(min(vac)-max(occ))*27.211386245988
        jobs[key].update(status="completed",**result)
    except Exception as e: jobs[key].update(status="failed",error=str(e))
@app.get("/health")
def health():
    return {"status":"ok","version":"0.5.0","pyscf_available":importlib.util.find_spec("pyscf") is not None,"public_calculations_enabled":os.getenv("ORBIXA_ENABLE_JOBS")=="true"}
@app.post("/api/validate")
def validate(req:Calculation):
    try: atoms=validate_xyz(req)
    except ValueError as e: raise HTTPException(422,str(e))
    return {"valid":True,"atom_count":len(atoms)}
@app.post("/api/jobs",status_code=202)
def submit(req:Calculation):
    if os.getenv("ORBIXA_ENABLE_JOBS")!="true": raise HTTPException(503,"Scientific calculation jobs are disabled in public preview")
    try: validate_xyz(req)
    except ValueError as e: raise HTTPException(422,str(e))
    if len(jobs)>=100: raise HTTPException(429,"Job capacity reached")
    key=str(uuid.uuid4())
    jobs[key]={"id":key,"status":"queued"}
    pool.submit(compute,key,req)
    return jobs[key]
@app.get("/api/jobs")
def list_jobs(limit:int=20):
    if not 1<=limit<=100: raise HTTPException(422,"Invalid limit")
    return list(jobs.values())[-limit:][::-1]
@app.get("/api/jobs/{job_id}")
def get_job(job_id:str):
    if job_id not in jobs: raise HTTPException(404,"Job not found")
    return jobs[job_id]
