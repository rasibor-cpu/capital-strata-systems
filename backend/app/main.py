from fastapi import FastAPI

app = FastAPI(title="REA Capital Backend", version="0.1.0")

@app.get("/")
def health():
    return {"status": "ok"}
