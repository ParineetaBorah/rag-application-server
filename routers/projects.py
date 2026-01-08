from fastapi import APIRouter, HTTPException, Depends
from auth import get_current_user
from database import supabase, s3_client, BUCKET_NAME
from pydantic import BaseModel
import uuid

router = APIRouter(
    tags = ["projects"]
)

class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectSettingsUpdate(BaseModel):
    embedding_model: str
    rag_strategy: str
    agent_type: str
    chunks_per_search: int
    final_context_size: int
    similarity_threshold: float
    number_of_queries: int
    reranking_enabled: bool
    reranking_model: str
    vector_weight: float
    keyword_weight: float

@router.get("/api/projects")
async def get_all_projects(clerkid: str = Depends(get_current_user)):
    print("hitting here")
    try:
        projects=supabase.table("projects").select("*").eq("clerk_id", clerkid).execute()
        return{
            "status": "Projects retrieved successfully!",
            "data":projects.data
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to get projects data due to {str(e)}"))
    

@router.post("/api/projects")
async def create_project(project: ProjectCreate, clerkid: str = Depends(get_current_user)):
    try:
        project_detail = supabase.table("projects").insert({
            "name": project.name,
            "description": project.description,
            "clerk_id": clerkid
        }).execute()

        if not project_detail.data:
            raise HTTPException(status_code=500, detail="Project creation failed")
        
        created_project = project_detail.data[0]
        project_id = created_project.get("id")
        
        project_settings = supabase.table("project_settings").insert({
            "project_id": project_id,
            "embedding_model": "text-embedding-large",
            "rag_strategy": "basic",
            "agent_type": "agentic",
            "chunks_per_search": 10,
            "final_context_size": 5,
            "similarity_threshold": 0.3,
            "number_of_queries": 5,
            "reranking_enabled": True,
            "reranking_model": "rerank-engine-v3.0",
            "vector_weight": 0.7,
            "keyword_weight": 0.3,

        }).execute()

        if not project_settings.data:
            supabase.table("projects").delete().eq("id", project_id).execute()
            raise HTTPException(status_code=500, detail="Project settings creation failed")
        
        return {
            "status": "Project created successfully!",
            "data": created_project
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to create project due to {str(e)}"))  
    

@router.delete("/api/projects/{project_id}")
async def delete_project(project_id: str, clerkid: str = Depends(get_current_user)):
    try:
        project = supabase.table("projects").select("*").eq("id", project_id).eq("clerk_id", clerkid).execute()

        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found or unauthorized")

        deleted_result = supabase.table("projects").delete().eq("id", project_id).eq("clerk_id", clerkid).execute()
        
        return {
            "status": "Project deleted successfully!",
            "data": deleted_result.data[0]
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to delete project due to {str(e)}"))  


@router.get("/api/projects/{project_id}")
async def get_project(
    project_id:str,
    clerkid: str = Depends(get_current_user)
):
    try:
        project_detail = supabase.table("projects").select("*").eq("id", project_id).eq("clerk_id", clerkid).execute()
        if not project_detail.data:
            raise HTTPException(status_code=404, detail="Project not found or unauthorized")

        return {
            "status":"Project retrieved successfully!",
            "data":project_detail.data[0]
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to get project due to {str(e)}"))


@router.get("/api/projects/{project_id}/chats")
async def get_project_chats(
    project_id:str,
    clerkid: str = Depends(get_current_user)
):
    try:
        chats = supabase.table("chats").select("*").eq("project_id",project_id).eq("clerk_id",clerkid).order("created_at",desc=True).execute()

        return {
            "status":"Chats retrieved successfully!",
            "data":chats.data or []
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to get chats due to {str(e)}"))
    

@router.get("/api/projects/{project_id}/settings")
async def get_project_settings(
    project_id:str,
    clerkid: str = Depends(get_current_user)
):
    try:
        settings = supabase.table("project_settings").select("*").eq("project_id",project_id).execute()
        if not settings.data:
            raise HTTPException(status_code=404, detail="No settings found for this project")

        return {
            "status":"Settings retrieved successfully!",
            "data":settings.data[0]
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to get settings due to {str(e)}"))


@router.put("/api/projects/{project_id}/settings")
async def update_project_settings(
    project_id: str,
    settings: ProjectSettingsUpdate,
    clerkid: str = Depends(get_current_user)
):
    try:
        table_res = supabase.table("projects").select("*").eq("id",project_id).eq("clerk_id",clerkid).execute()
        if not table_res.data:
            raise HTTPException(status_code=404, detail="Project not found or unauthorized")
        
        settings_res = supabase.table("project_settings").update(settings.model_dump()).eq("project_id",project_id).execute()
        if not settings_res.data:
            raise HTTPException(status_code=404, detail="Project Settings not found or unauthorized")
        
        return {
            "status":"Settings updated successfully!",
            "data":settings_res.data[0]
        }
       
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to update settings due to {str(e)}"))




