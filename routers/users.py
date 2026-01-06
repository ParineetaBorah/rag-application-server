from fastapi import APIRouter, HTTPException
from database import supabase
from pydantic import BaseModel

router = APIRouter(
    tags = ["users"]
)

@router.post("/create-user")
async def create_user(webhook_data: dict):
    try:
        event_type = webhook_data.get("type")
        clerk_id = None

        if event_type == "user.created":
            user_data = webhook_data.get("data", {})
            print(f"Received webhook data: {user_data}")
            clerk_id = user_data.get("id")
            print(f"Received user created event with clerk_id: {clerk_id}")

        if not clerk_id:
            raise HTTPException(status_code=400, detail="UserId not found in webhook data")

        # Insert user into Supabase
        result = supabase.table("users").insert({"clerk_id": clerk_id}).execute()
        return {"status":200, "data":result.data[0]}
    
    except Exception as e:
        return HTTPException(status_code=500, detail=str(e))