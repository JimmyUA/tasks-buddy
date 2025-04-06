# app/services/auth_service.py
import firebase_admin
from firebase_admin import credentials, auth
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from core.config import settings
import os

# Initialize Firebase Admin SDK
# Use credentials from env var if provided, otherwise expect default credentials (e.g., in Cloud Run)
try:
    if settings.google_application_credentials and os.path.exists(settings.google_application_credentials):
        cred = credentials.Certificate(settings.google_application_credentials)
    else:
        # If no specific path, try to use default credentials (useful for Cloud Run/Functions default service accounts)
        cred = credentials.ApplicationDefault()

    firebase_admin.initialize_app(cred)
    print("Firebase Admin SDK Initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")
    # Depending on your setup, you might want to raise an error or handle this differently
    # If running locally without the file, this will likely fail unless ADC is set up.


security = HTTPBearer()

async def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Dependency to verify Firebase ID token and return user ID.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, # Changed from 403
            detail="Not authenticated: No token provided",
            headers={"WWW-Authenticate": "Bearer"}, # Add header indicating Bearer required
        )
    try:
        decoded_token = auth.verify_id_token(token.credentials)
        user_id = decoded_token.get("uid")
        if not user_id:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: UID not found",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
            )
        print(f"Authenticated user: {user_id}") # For debugging
        return user_id
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"Token has expired\""},
        )
    except Exception as e:
        print(f"Token verification error: {e}") # Log the actual error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e}",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )