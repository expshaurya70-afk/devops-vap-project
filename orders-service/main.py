from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os

app = FastAPI(title="Orders Service")

# --- In-memory "database" ---
orders_db = {}
next_id = 1

# URL of the users-service. We read this from an environment variable
# instead of hardcoding it, because "localhost:8001" only makes sense
# when running locally. Inside Kubernetes, this will be a service name
# like "http://users-service:8001" instead — env vars let us switch
# without touching code.
USERS_SERVICE_URL = os.getenv("USERS_SERVICE_URL", "http://localhost:8001")


class Order(BaseModel):
    user_id: int
    item: str
    quantity: int


class OrderOut(Order):
    id: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/orders", response_model=OrderOut, status_code=201)
async def create_order(order: Order):
    global next_id

    # Call users-service to check this user actually exists
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{USERS_SERVICE_URL}/users/{order.user_id}", timeout=5.0
            )
        except httpx.RequestError:
            # users-service is unreachable (down, wrong URL, etc.)
            raise HTTPException(
                status_code=503,
                detail="Could not reach users-service",
            )

    if response.status_code == 404:
        raise HTTPException(
            status_code=400,
            detail=f"User {order.user_id} does not exist",
        )
    response.raise_for_status()  # catch any other unexpected error

    order_id = next_id
    orders_db[order_id] = order
    next_id += 1
    return OrderOut(id=order_id, **order.dict())


@app.get("/orders", response_model=list[OrderOut])
def list_orders():
    return [OrderOut(id=oid, **o.dict()) for oid, o in orders_db.items()]


@app.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int):
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderOut(id=order_id, **order.dict())
