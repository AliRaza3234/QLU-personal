# QLU-2 AI Server

This is the monorepository for all backend AI services functioning in QLU-2. Documentation for these services can be found at the following URL:

    https://docs.google.com/spreadsheets/d/1g-eMoLn01v1-gnOTt1dgba_N5bsy7COUaqHVD8Vtaj8/

The backend API routes for all services are accessible through the following domains:

| Environment | Metadata and Docs URLs |
|-------------|------|
| Production  | https://qlu2-ai-backend-7wzmpo3asa-uc.a.run.app/docs |
| Staging     | https://qlu2-ai-backend-staging-7wzmpo3asa-uc.a.run.app/docs |
| Development | https://qlu2-ai-backend-development-7wzmpo3asa-uc.a.run.app/docs |

The backend server is built with FastAPI and currently deployed on Google Cloud Platform (GCP).

## Setup Instructions

Follow these steps to set up the project locally:

- Create and activate a Python virtual environment:
  ```bash
  python3 -m venv virtual
  source virtual/bin/activate
  ```

- Install `qutils` and `poetry` packages:
  ```bash
  pip install git+https://github.com/qlu-ai/qutils@development
  pip install poetry
  ```

- Install project dependencies via Poetry:
  ```bash
  poetry install
  ```

- Run the backend server:
  ```bash
  python3 main.py
  ```  
