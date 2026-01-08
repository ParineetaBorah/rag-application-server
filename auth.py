import os 
from fastapi import Request, HTTPException
from clerk_backend_api import AuthenticateRequestOptions, Clerk

clerk = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))

async def get_current_user(request: Request) -> str:
    # print("Authorization:", request.headers.get("authorization"))

    try:
        request_state = clerk.authenticate_request(
            request,
            AuthenticateRequestOptions(
                authorized_parties=["http://localhost:3000"]
            )
        )
        print("Request state:", request_state.is_signed_in)

        if not request_state.is_signed_in:
            raise HTTPException(status_code=401, detail="Unauthorized")

        clerk_id = request_state.payload.get("sub")

        if not clerk_id:
            raise HTTPException(status_code=401, detail="Invalid Token")
        
        return clerk_id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")