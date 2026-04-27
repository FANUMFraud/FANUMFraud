from fastapi import FastAPI

app = FastAPI(title="FANUMFraud")

@app.get("/")
def root():
    return {"status": "ok", "message": "FANUMFraud działa"}