"""
Run script for the REA Capital Orchestration API (Phase 12.7)

Usage (from repo root):
  python backend/run_api.py

Assumes:
- FastAPI + uvicorn installed in backend environment
- API app lives in backend/app/api.py as `app`
"""

import uvicorn


def main() -> None:
    uvicorn.run(
        "app.api:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
