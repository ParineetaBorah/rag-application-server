from fastapi import APIRouter, HTTPException, Depends
from auth import get_current_user
from database import supabase, s3_client, BUCKET_NAME
from pydantic import BaseModel
import uuid

router = APIRouter(
    tags = ["files"]
)

class FileUploadrequest(BaseModel):
    filename:str
    file_type:str
    file_size:int 

class URLRequest(BaseModel):
    url:str


@router.get("/api/projects/{project_id}/files")
async def get_project_files(
    project_id:str,
    clerkid: str = Depends(get_current_user)
):
    try:
        files = supabase.table("project_documents").select("*").eq("project_id",project_id).eq("clerk_id",clerkid).order("created_at",desc=True).execute() 

        return {
            "status":"Files retrieved successfully!",
            "data":files.data or []
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to get files due to {str(e)}"))

@router.post('/api/projects/{project_id}/files/upload-url')
async def get_upload_url(
    project_id: str,
    file_request: FileUploadrequest,
    clerkid: str = Depends(get_current_user)
):
    try:
        project_res = supabase.table("projects").select("*").eq("id",project_id).eq("clerk_id",clerkid).execute()

        if not project_res.data:
            raise HTTPException(status_code=404, detail="Project not found or unauthorized")

        #generate s3 unique key
        file_extension = file_request.filename.split(".")[-1] if "." in file_request.filename else ""
        unique_id = uuid.uuid4()
        s3_key = f"projects/{project_id}/documents/{unique_id}.{file_extension}"

        #generate pre-signed url
        pre_signed_url = s3_client.generate_presigned_url(
            "put_object",
            Params = {
                "Bucket":BUCKET_NAME,
                "Key":s3_key,
                "ContentType":file_request.file_type
            },
            ExpiresIn=3600,
        )

        #update database with uploading status
        document_res =supabase.table("project_documents").insert({
            "processing_status":"uploading",
            "s3_key":s3_key,
            "file_size":file_request.file_size,
            "file_type":file_request.file_type,
            "filename":file_request.filename,
            "project_id":project_id,
            "clerk_id":clerkid
        }).execute()

        if not document_res.data:
            raise HTTPException(status_code=500, detail="Failed to update database with uploading status")

        return {
            "status":"Upload URL generated successfully!",
            f"data":{
                "upload_url":pre_signed_url,
                "s3_key":s3_key,
                "document":document_res.data[0]
            }
        }


    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to generate upload URL due to {str(e)}"))

@router.delete("/api/projects/{project_id}/files/{file_id}")
async def delete_document(
    project_id: str,
    file_id:str,
    clerkid: str = Depends(get_current_user)
):
    try:
        document_res = supabase.table("project_documents").select("*").eq("id", file_id).eq("project_id",project_id).eq("clerk_id",clerkid).execute()
        s3_key = document_res.data[0].get("s3_key")

        if s3_key:
            try:
                s3_client.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
            except Exception as e:
                print(f"Failed to delete file from S3: {str(e)}")

        delete_res = supabase.table("project_documents").delete().eq("id",file_id).execute()

        if not delete_res.data:
            raise HTTPException(status_code=500, detail="Failed to delete document")

        return {
            "status":"Document deleted successfully!",
            "data":delete_res.data[0]
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to delete document due to {str(e)}"))


@router.post("/api/projects/{project_id}/files/confirm")
async def get_upload_confirmation(
    project_id: str,
    confirm_request: dict,
    clerkid: str = Depends(get_current_user)
):
    try:
        s3_key = confirm_request.get("s3_key")

        if not s3_key:
            raise HTTPException(status_code=400, detail="S3 key is required")

        document_res = supabase.table("project_documents").update(
            {"processing_status":"queued"}
        ).eq("s3_key",s3_key).eq("project_id",project_id).eq("clerk_id",clerkid).execute()

        document = document_res.data[0]
        
        if not document_res.data:
            raise HTTPException(status_code=404, detail="Document not found or unauthorized")


        #start processing document

        return {
            "status": "Document uploaded successfully!",
            "data": document
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to get upload confirmation due to {str(e)}"))

@router.post("/api/projects/{project_id}/files/url")
async def get_file_url(
    project_id: str,
    url_request: URLRequest,
    clerkid: str = Depends(get_current_user)
):
    try:
        url = url_request.url.strip()

        if not url.startswith(("http","https")):
            url = "https://" + url

        document_res =supabase.table("project_documents").insert({
            "processing_status":"queued",
            "s3_key":"",
            "file_size":0,
            "file_type":'text/html',
            "filename":url,
            "project_id":project_id,
            "clerk_id":clerkid, 
            "source_type":"url",
            "source_url":url
        }).execute()

        if not document_res.data:
            raise HTTPException(status_code=500, detail="Failed to create url record")

        #start processsing here

        

        return {
            "status":"Document created successfully!",
            "data":document_res.data[0]
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to get file URL due to {str(e)}"))