import uvicorn
from fastapi import FastAPI
from clawsocialgraph.api.routes_registry import router as registry_router
from clawsocialgraph.api.routes_reputation import router as reputation_router
from clawsocialgraph.api.routes_economy import router as economy_router

app = FastAPI(title="Mock Society Server")

app.include_router(registry_router)
app.include_router(reputation_router)
app.include_router(economy_router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8005)
