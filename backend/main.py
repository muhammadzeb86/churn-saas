from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Churn SaaS API")

@app.get("/")
async def root():
    return JSONResponse(content={"message": "Churn SaaS backend is running"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
