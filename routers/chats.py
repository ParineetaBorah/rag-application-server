from fastapi import APIRouter, HTTPException, Depends
from auth import get_current_user
from database import supabase
from pydantic import BaseModel

router = APIRouter(
    tags = ["chats"]
)
class CreateChat(BaseModel):
    title: str
    project_id: str


@router.post("/api/chats")
async def create_chat(
    chat:CreateChat,
    clerkid: str = Depends(get_current_user)
):
    try:
        chat_res = supabase.table("chats").insert({
            "title": chat.title,
            "project_id": chat.project_id,
            "clerk_id": clerkid
        }).execute()
        
        return {
            "status": "Chat created successfully!",
            "data": chat_res.data[0]
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to create chat due to {str(e)}"))

@router.delete(f"/api/chats/{chat_id}")
async def create_chat(
    chat_id: str,
    clerkid: str = Depends(get_current_user)
):
    try:
        chat_del = supabase.table("chats").delete().eq("id", chat_id).eq("clerk_id", clerkid).execute()

        if not chat_del.data:
                raise HTTPException(status_code=404, detail="Chat not found")
        
        return {
            "status": "Chat created successfully!",
            "data": chat_del.data[0]
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to delete chat due to {str(e)}"))