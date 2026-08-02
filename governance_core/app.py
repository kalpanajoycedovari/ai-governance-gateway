from fastapi import FastAPI
from router import router

app = FastAPI(title="Governance Gateway")
app.include_router(router)


@app.get("/")
def root():
    return {"status": "governance gateway up"}