# Run Orbixa scientific calculations on your Windows PC

This is an **experimental personal worker**, not a hardened multi-user service. The hosted Orbixa website submits a job to the Render API, and the PC worker polls for it over outbound HTTPS. No port forwarding required.

## Install

Open Windows PowerShell as Administrator and run:

```powershell
wsl --install -d Ubuntu
```

Restart Windows if requested. In Ubuntu, install Python and clone the project:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
git clone https://github.com/Aamilsamsung/Orbixa.git
cd Orbixa
python3 -m venv .venv
source .venv/bin/activate
pip install pyscf
python -c "import pyscf; print(pyscf.__version__)"
```

## Configure private keys

Generate **two different** secrets, each at least 24 characters, using:

```bash
python -c "import secrets; print(secrets.token_urlsafe(36))"
```

On the Render API dashboard, open **Environment** and set `ORBIXA_OWNER_KEY` and `ORBIXA_WORKER_KEY` to those two secrets. Do not commit them or paste them into chat. The owner key lets you submit jobs; the worker key lets your PC claim jobs and return results.

In Ubuntu, set only the worker key in your current terminal:

```bash
read -rsp "Worker key: " ORBIXA_WORKER_KEY; echo
export ORBIXA_WORKER_KEY
python worker/worker.py
```

Keep the terminal open and the PC awake. Open https://orbixa-science-preview.onrender.com, enter your **owner key** in the calculation panel, select hydrogen H2, and submit an RHF/STO-3G job.

## Current limits

- 10 atoms, STO-3G, RHF/UHF/RKS/UKS.
- One outstanding job, 120-second worker timeout, two BLAS threads.
- No geometry optimization.
- The worker needs internet access; jobs cannot run while the PC is off.
- Render Free has ephemeral disk: **queued jobs/results can be lost on restart or redeploy**.
- The worker is not a full memory sandbox. On an 8 GB PC, keep molecules small and monitor memory.

**Do not use this prototype for untrusted public users or research-grade results until security hardening and numerical benchmarks are complete.**
