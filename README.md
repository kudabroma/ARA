# NomadTax Backend API

FastAPI backend for US tax residency (Substantial Presence Test, IRS Publication 519), 1099/W-2 tax calculation, FICA refund detection, Schedule C transaction categorization, and Form 8843 PDF generation.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Run Tests

```bash
pytest
```

## Deploy to Vercel

Push this repository to GitHub and import into Vercel. `vercel.json` routes all requests to `api/index.py`.
