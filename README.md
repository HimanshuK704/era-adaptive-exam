# Responsible AI-Powered Adaptive Examination System

Research prototype for a local computerized adaptive testing (CAT) demonstration.

## V1 scope
- Scalar ability estimate (`theta`)
- Rasch/1PL item response model
- Bayesian expected-a-p-posteriori (EAP) ability estimation
- Bounded calibration (4–6 items)
- Maximum Fisher Information item selection
- No repeated items within a session
- Local synthetic question bank
- Structured decision events
- No student result shown at exam completion (the UI is not implemented yet)

## Important limitations
This is a research prototype, not validated for high-stakes assessment. The included question bank and item difficulties are synthetic. Numerical choices are initial engineering defaults and must be validated through simulation before making research claims.

## Setup (Windows PowerShell)
From the project root:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m era.demo
python -m pytest
```

If PowerShell blocks activation, use:
```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m era.demo
.\.venv\Scripts\python.exe -m pytest
```

## Project layout
- `src/era/psychometrics/rasch.py`: Rasch likelihood and EAP posterior
- `src/era/adaptive/`: calibration and item selection
- `src/era/trace/`: structured decision events
- `src/era/data/`: clearly synthetic sample items
- `tests/`: unit tests

## Research integrity
Do not report accuracy, fairness, efficiency, or psychometric validity without running and documenting appropriate experiments. The sample difficulty parameters are synthetic placeholders, not calibrated item parameters.

## Web app (local)
Install the app and launch FastAPI:
```powershell
python -m pip install -e ".[test]"
uvicorn era.webapp:app --reload
```
Open `http://127.0.0.1:8000`. Health check: `/health`.

The web app loads `data/jeebench_mcq.json` if present, otherwise it falls back to the clearly synthetic sample bank. Only single-answer MCQ items are supported by this first web UI. Imported difficulty values are neutral placeholders, not calibrated parameters.

## JEEBench import (single-answer MCQ subset)
1. Download the official repository and extract `data.zip` from https://github.com/dair-iitd/jeebench.
2. Locate its `dataset.json` file.
3. Run:
```powershell
python scripts/import_jeebench.py path\to\dataset.json --output data\jeebench_mcq.json
```
The importer intentionally skips multi-correct and numerical questions. Inspect the import summary and review parsed question text/options before presenting the bank as verified. Cite Arora et al. (EMNLP 2023): https://aclanthology.org/2023.emnlp-main.468/.

## Render deployment
A starter `render.yaml` is included. Push the repository to GitHub, create a Render Blueprint from the repository, and verify `/health` and the complete exam flow after deployment. The included free-service configuration uses local SQLite on an ephemeral filesystem: records may be lost on restart/redeploy, and active in-memory sessions do not survive process restarts. This is acceptable only for a demo. Use managed persistent storage and durable session state before relying on it for real exams. The developer trace endpoints are unauthenticated and are for a controlled demonstration only; do not use this configuration for real student data.
