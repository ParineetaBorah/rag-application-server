from fastapi import APIRouter, HTTPException, Depends
from auth import get_current_user
from database import supabase
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from typing import List, Dict, Tuple

llm = ChatOpenAI(model="gpt-4o", temperature=0)

embeddings_model = OpenAIEmbeddings(
    model="text-embedding-3-large",
    dimensions=1536
)

router = APIRouter(
    tags = ["chats"]
)
class CreateChat(BaseModel):
    title: str
    project_id: str


@router.post("/api/chats")
async def create_chat(
    chat: CreateChat,
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

@router.delete("/api/chats/{chat_id}")
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

@router.get("/api/chats/{chat_id}")
async def get_chats(
    chat_id: str,
    clerkid: str = Depends(get_current_user)
):
    try:
        chat_res = supabase.table("chats").select("*").eq("id", chat_id).eq("clerk_id", clerkid).execute()

        if not chat_res.data:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        chat = chat_res.data[0]

        message_res = supabase.table("messages").select("*").eq("chat_id", chat_id).order("created_at", desc=False).execute()

        chat["messages"] = message_res.data or []
        
        return {
            "status": "Chat retrieved successfully!",
            "data": chat
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to get chat due to {str(e)}"))


def load_project_settings(project_id: str):
    try:
        settings = supabase.table("project_settings").select("*").eq("project_id", project_id).execute()
        if not settings.data:
            raise HTTPException(status_code=404, detail="Project settings not found")
        return settings.data[0]
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to load project settings due to {str(e)}"))

def get_document_ids(project_id: str):
    try:
        document_ids = supabase.table("project_documents").select("id").eq("project_id", project_id).execute()
        document_id_list = [ data['id'] for data in document_ids.data]
        print(f"Found {len(document_id_list)} documents for project {project_id}")

        return document_id_list
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to get document ids due to {str(e)}"))

def vector_search(message: str, document_ids: list[str], settings: dict):
    try:
        query_embedding = embeddings_model.embed_query(message)
        vector_search_res = supabase.rpc("vector_search_document_chunks", {
            "query_embedding": query_embedding,
            "filter_document_ids": document_ids,
            "match_threshold": settings["similarity_threshold"],
            "chunks_per_search": settings["chunks_per_search"]
        }).execute()

        return vector_search_res.data if vector_search_res.data else []
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to perform vector search due to {str(e)}"))

def build_context(chunks: List[Dict]) -> Tuple[List[str], List[str], List[str], List[Dict]]:
    """
    Returns:
        Tuple of (texts, images, tables, citations)
    """
    if not chunks:
        return [], [], [], []
    
    texts = []
    images = []
    tables = []
    citations = [] 
    
    # Batch fetch all filenames in ONE query
    doc_ids = [chunk['document_id'] for chunk in chunks if chunk.get('document_id')]
    unique_doc_ids: List[str] = list(set(doc_ids))  # ✅ Fixed syntax
    
    filename_map = {}
    
    if unique_doc_ids:
        result = supabase.table('project_documents')\
            .select('id, filename')\
            .in_('id', unique_doc_ids)\
            .execute()
        filename_map = {doc['id']: doc['filename'] for doc in result.data}
    
    # Process each chunk
    for chunk in chunks:
        original_content = chunk.get('original_content', {})
        
        # Extract content from chunk
        chunk_text = original_content.get('text', '')
        chunk_images = original_content.get('images', [])
        chunk_tables = original_content.get('tables', [])

        # Collect content
        if chunk_text:  # ✅ Add this check back
            texts.append(chunk_text)
        images.extend(chunk_images)
        tables.extend(chunk_tables)
        
        # Add citation for every chunk
        doc_id = chunk.get('document_id')
        if doc_id:
            citations.append({
                "chunk_id": chunk.get('id'),
                "document_id": doc_id,
                "filename": filename_map.get(doc_id, 'Unknown Document'),
                "page": chunk.get('page_number', 'Unknown')
            })
    
    return texts, images, tables, citations

def prepare_prompt_and_invoke_llm(
    user_query: str,
    texts: List[str],
    images: List[str],
    tables: List[str]
) -> str:
    """
    Builds system prompt with context and invokes LLM with multi-modal support
    
    Args:
        user_query: The user's question
        texts: List of text chunks from documents
        images: List of base64-encoded images
        tables: List of HTML table strings
    
    Returns:
        AI response string
    """
    # Build system prompt parts
    prompt_parts = []
    
    # Main instruction
    prompt_parts.append(
        "You are a helpful AI assistant that answers questions based solely on the provided context. "
        "Your task is to provide accurate, detailed answers using ONLY the information available in the context below.\n\n"
        "IMPORTANT RULES:\n"
        "- Only answer based on the provided context (texts, tables, and images)\n"
        "- If the answer cannot be found in the context, respond with: 'I don't have enough information in the provided context to answer that question.'\n"
        "- Do not use external knowledge or make assumptions beyond what's explicitly stated\n"
        "- When referencing information, be specific and cite relevant parts of the context\n"
        "- Synthesize information from texts, tables, and images to provide comprehensive answers\n\n"
    )
    
    # Add text contexts
    if texts:
        prompt_parts.append("=" * 80)
        prompt_parts.append("CONTEXT DOCUMENTS")
        prompt_parts.append("=" * 80 + "\n")
        
        for i, text in enumerate(texts, 1):
            prompt_parts.append(f"--- Document Chunk {i} ---")
            prompt_parts.append(text.strip())
            prompt_parts.append("")
    
    # Add tables if present
    if tables:
        prompt_parts.append("\n" + "=" * 80)
        prompt_parts.append("RELATED TABLES")
        prompt_parts.append("=" * 80)
        prompt_parts.append(
            "The following tables contain structured data that may be relevant to your answer. "
            "Analyze the table contents carefully.\n"
        )
        
        for i, table_html in enumerate(tables, 1):
            prompt_parts.append(f"--- Table {i} ---")
            prompt_parts.append(table_html)
            prompt_parts.append("")
    
    # Reference images if present
    if images:
        prompt_parts.append("\n" + "=" * 80)
        prompt_parts.append("RELATED IMAGES")
        prompt_parts.append("=" * 80)
        prompt_parts.append(
            f"{len(images)} image(s) will be provided alongside the user's question. "
            "These images may contain diagrams, charts, figures, formulas, or other visual information. "
            "Carefully analyze the visual content when formulating your response. "
            "The images are part of the retrieved context and should be used to answer the question.\n"
        )
    
    # Final instruction
    prompt_parts.append("=" * 80)
    prompt_parts.append(
        "Based on all the context provided above (documents, tables, and images), "
        "please answer the user's question accurately and comprehensively."
    )
    prompt_parts.append("=" * 80)
    
    system_prompt = "\n".join(prompt_parts)
    
    # Build messages for LLM
    messages = [SystemMessage(content=system_prompt)]
    
    # Create human message with user query and images
    if images:
        # Multi-modal message: text + images
        content_parts = [{"type": "text", "text": user_query}]
        
        # Add each image to the content array
        for img_base64 in images:
            # Clean base64 string if it has data URI prefix
            if img_base64.startswith('data:image'):
                img_base64 = img_base64.split(',', 1)[1]
            
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}
            })
        
        messages.append(HumanMessage(content=content_parts))
    else:
        # Text-only message
        messages.append(HumanMessage(content=user_query))
    
    # Invoke LLM and return response
    print(f"🤖 Invoking LLM with {len(messages)} messages ({len(texts)} texts, {len(tables)} tables, {len(images)} images)...")
    response = llm.invoke(messages)
    
    return response.content


class SendMessageRequest(BaseModel):
    content: str

@router.post("/api/projects/{project_id}/chats/{chat_id}/messages")
async def send_message(
    project_id: str,
    chat_id: str,
    request: SendMessageRequest,
    clerkid: str = Depends(get_current_user)
):
    try:
        message = request.content
        message_res = supabase.table("messages").insert({
            "content": message,
            "chat_id": chat_id,
            "role": "user",
            "clerk_id": clerkid
        }).execute()
        
        user_message = message_res.data[0]
        print(f"User message saved successfully: {user_message['id']}")


        # 2. Load project settings
        # We need settings to know: chunk size, similarity threshold, etc.
        settings = load_project_settings(project_id)

        # 3. Get document IDs for this project
        # This narrows our search scope to only documents uploaded to this specific project
        document_ids = get_document_ids(project_id)

        # 4. Generate query embedding
        # Convert the user's text question into a vector so we can perform similarity search
        # 5. Perform vector search using the RPC function
        # Search through the chunks to find the most relevant chunks for answering the question
        chunks = vector_search(message, document_ids, settings)
        print(f"Found {len(chunks)} chunks for message: {message}")
        
        # 6. Build context from retrieved chunks
        # Format the retrieved chunks into a structured context with citations
        texts, images, tables, citations = build_context(chunks)
        
        # 7. Build system prompt with injected context 
        # 8. Call LLM & get response
        # Add the retrieved document context to the system prompt so the LLM can answer based on the documents
        print(f"🤖 Preparing context and calling LLM...")
        ai_response = prepare_prompt_and_invoke_llm(
            user_query=message,
            texts=texts,
            images=images,
            tables=tables
        )
        
        # 9. Save AI message with citations to database
        # Store the AI's response along with citations
        ai_content_res = supabase.table("messages").insert({
            "content": ai_response,
            "chat_id": chat_id,
            "role": "assistant",
            "clerk_id": clerkid,
            "citations": citations
        }).execute()

        ai_message = ai_content_res.data[0]
        print(f"AI message saved successfully: {ai_message['id']}")

        return {
            "status": "Message sent successfully!",
            "data": {
                "userMessage": user_message,
                "aiMessage": ai_message
            }
        }
    except Exception as e:
        return HTTPException(status_code=500, detail=str(f"Failed to send message due to {str(e)}"))


