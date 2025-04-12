# app/core/config.py
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import List

# Load .env file if it exists (especially for local development)
load_dotenv()


class Settings(BaseSettings):
    gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "default-project-id")
    vertex_ai_region: str = os.getenv("VERTEX_AI_REGION", "us-central1")
    google_application_credentials: str | None = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    tasks_collection: str = os.getenv("TASKS_COLLECTION", "tasks")
    users_collection: str = os.getenv("USERS_COLLECTION", "users")  # For future use

    # Basic keyword preferences for MVP
    high_priority_keywords: List[str] = os.getenv("HIGH_PRIORITY_KEYWORDS", "urgent,asap,important,deadline".split(","))

    # Gemini model name
    gemini_model_name: str = "gemini-2.0-flash-001"  # Or another appropriate Gemini model

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        extra = 'ignore'  # Ignore extra env vars


settings = Settings()

# Ensure credentials path is handled correctly
if settings.google_application_credentials and not os.path.exists(settings.google_application_credentials):
    print(f"Warning: Service account key file not found at {settings.google_application_credentials}")
    # In Cloud Run, GOOGLE_APPLICATION_CREDENTIALS might not be set if using default service account identity
    # The library handles finding default credentials in that case.
