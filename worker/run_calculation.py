import sys,json,math
from pyscf import gto,scf,dft
data=json.load(sys.stdin)
atoms=[]
for line in data["xyz"].strip().splitlines()[2:]:
    parts=line.split()
    atoms.append((parts[0],tuple(float(x) for x in parts[1:])))
mol=gto.M(atom=atoms,unit="Angstrom",basis=data["basis"],charge=data["charge"],spin=data["spin"],verbose=0)
cls={"RHF":scf.RHF,"UHF":scf.UHF,"RKS":dft.RKS,"UKS":dft.UKS}[data["method"]]
mf=cls(mol)
if data["method"].endswith("KS"): mf.xc=data["functional"]
mf.max_cycle=60
energy=float(mf.kernel())
if not mf.converged or not math.isfinite(energy): raise RuntimeError("SCF did not converge")
result={"energy_hartree":energy,"converged":True,"method":data["method"],"basis":data["basis"],"atom_count":len(atoms)}
if data.get("analyze",True):
    energies=mf.mo_energy
    occupations=mf.mo_occ
    if isinstance(energies,(list,tuple)):
        result["orbital_energies_hartree"]=[[float(x) for x in e] for e in energies]
    else:
        es=[float(x) for x in energies]
        result["orbital_energies_hartree"]=es
        occupied=[e for e,o in zip(es,occupations) if o>0]
        virtual=[e for e,o in zip(es,occupations) if o==0]
        if occupied: result["homo_hartree"]=max(occupied)
        if virtual: result["lumo_hartree"]=min(virtual)
        if occupied and virtual: result["gap_ev"]=(min(virtual)-max(occupied))*27.211386245988
print(json.dumps(result))
