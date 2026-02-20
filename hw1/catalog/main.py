from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Go to /health-check"}

@app.get("/health-check")
def health_check():
    return {"status": "ok"}