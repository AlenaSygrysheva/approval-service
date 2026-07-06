from fastapi import FastAPI

from app.routers import approval_requests, health

app = FastAPI(title="Approval Service", version="1.0.0")
app.include_router(health.router)
app.include_router(approval_requests.router)
