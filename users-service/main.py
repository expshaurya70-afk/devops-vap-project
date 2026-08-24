from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Users Service")

# --- In-memory "database" ---
# Just a Python dict for now. We'll swap this for a real DB later if needed.
# Key = user_id, Value = user data
users_db = {}
next_id = 1


class User(BaseModel):
    name: str
    email: str


class UserOut(User):
    id: int


# --- Health check ---
# Kubernetes will poll this endpoint to decide if the pod is alive/ready.
@app.get("/health")
def health():
    return {"status": "ok"}


# --- Create a user ---
@app.post("/users", response_model=UserOut, status_code=201)
def create_user(user: User):
    global next_id
    user_id = next_id
    users_db[user_id] = user
    next_id += 1
    return UserOut(id=user_id, **user.dict())


# --- List all users ---
@app.get("/users", response_model=list[UserOut])
def list_users():
    return [UserOut(id=uid, **u.dict()) for uid, u in users_db.items()]


# --- Get a single user ---
@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(id=user_id, **user.dict())


# --- Delete a user ---
@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    del users_db[user_id]
