from fastapi import APIRouter, HTTPException, Depends
from auth import get_current_user
from database import supabase
from pydantic import BaseModel

router = APIRouter(
    tags = ["projects"]
)

class ProjectCreate(BaseModel):
    name: str
    description: str = ""

router.get("/api/projects")
async def get_all_projects(clerkid: str = Depends(get_current_user)):
    try:
        projects=supabase.table("projects").select("*").eq("clerk_id", clerkid).execute()
        return{
            "status": "Projects retrieved successfully!",
            "data":projects.data
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to get projects data due to {str(e)}"))
    

router.post("/api/projects")
async def create_project(project: ProjectCreate, clerkid: str = Depends(get_current_user)):
    try:
        project_detail = supabase.table("projects").insert({
            "name": project.name,
            "description": project.description,
            "clerk_id": clerkid
        }).execute()

        if not created_project.data:
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
    

router.delete("/api/projects/{project_id}")
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