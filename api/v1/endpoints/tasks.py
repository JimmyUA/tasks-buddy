# app/api/v1/endpoints/tasks.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict
from models.task_models import TaskCreate, TaskRead, ProcessedTaskData # Import ProcessedTaskData
from services import ai_service, auth_service
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from crud import task_crud
from core.config import settings
from datetime import datetime # Import datetime

router = APIRouter()

@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_new_task(
    task_in: TaskCreate,
    current_user_id: str = Depends(auth_service.get_current_user)
):
    """
    Receives raw task input (and optional deadline), processes with AI,
    ensures a deadline exists, applies overrides, and saves to Firestore.
    Requires a deadline to be either provided or extracted by AI.
    """
    print(f"Received raw input from user {current_user_id}: {task_in.rawInput}, Optional deadline: {task_in.deadline}")
    try:
        # 1. Process with AI
        processed_data: ProcessedTaskData = await ai_service.process_raw_task_input(task_in.rawInput)
        print(f"AI Processed Data: {processed_data}")

        # 2. Determine Deadline (Mandatory check)
        if not task_in.deadline and not processed_data.deadline:
            print("Task creation failed: Deadline not provided by user or detected by AI.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task deadline is required. Please provide a deadline or ensure it can be extracted from the task description."
            )
        elif task_in.deadline:
             print(f"Using user-provided deadline: {task_in.deadline}")
             # If user provides deadline, we might not need AI's version, or prefer user's.
             # For now, crud.create_task handles precedence.
        elif processed_data.deadline:
             print(f"Using AI-detected deadline: {processed_data.deadline}")

        # 3. Apply simple keyword-based priority boost
        final_priority = processed_data.priority_suggestion or 'Medium'
        raw_input_lower = task_in.rawInput.lower()
        if any(keyword in raw_input_lower for keyword in settings.high_priority_keywords):
            print(f"Keyword match found. Overriding priority to High.")
            final_priority = 'High'
        processed_data.priority_suggestion = final_priority

        # 4. Save to Database (Pass both task_in and processed_data)
        created_task = await task_crud.create_task(
            user_id=current_user_id,
            task_in=task_in, # Pass the full input model
            processed_data=processed_data
        )
        print(f"Task created successfully (ID: {created_task.id})")
        return created_task

    except ConnectionError as e:
        print(f"Database connection error: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database service is unavailable.")
    except ValueError as e:
        # Catch potential ValueError from crud if deadline check fails there
        print(f"Validation error creating task: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"Error creating task: {e}")
        # Consider more specific error logging/handling
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create task.")

# --- Other endpoints remain largely the same, but ensure they handle TaskRead correctly ---

@router.get("/", response_model=List[TaskRead])
async def read_user_tasks(
    current_user_id: str = Depends(auth_service.get_current_user)
):
    """
    Retrieves all tasks for the currently authenticated user, sorted.
    """
    print(f"Fetching tasks for user {current_user_id}")
    try:
        tasks = await task_crud.get_tasks_for_user(user_id=current_user_id)
        print(f"Retrieved {len(tasks)} tasks for user {current_user_id}")
        return tasks
    except ConnectionError as e:
         print(f"Database connection error: {e}")
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database service is unavailable.")
    except Exception as e:
        print(f"Error reading tasks: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve tasks.")


@router.put("/{task_id}/complete", response_model=TaskRead)
async def update_task_completion(
    task_id: str,
    completed_data: Dict[str, bool], # Renamed for clarity
    current_user_id: str = Depends(auth_service.get_current_user)
):
    """
    Updates the completion status of a specific task.
    """
    completed_status = completed_data.get("completed")
    if completed_status is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'completed' field missing in request body.")

    print(f"Updating completion status for task {task_id} to {completed_status} by user {current_user_id}")
    try:
        # Fetch the task to ensure it exists and belongs to the user
        task_doc: DocumentSnapshot = await task_crud.get_task(task_id)
        if not task_doc.exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

        task_data = task_doc.to_dict()
        if task_data.get("userId") != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to modify this task.")

        # Check if task already has the desired status (optional optimization)
        # if task_data.get("completed") == completed_status:
        #    print(f"Task {task_id} already has completion status {completed_status}.")
        #    # Re-fetch and return to ensure latest data, or just return based on task_data
        #    task_data['id'] = task_id # Add id back for TaskRead
        #    return TaskRead(**task_data)

        updated_task = await task_crud.update_task_completion(task_id=task_id, completed=completed_status)
        print(f"Task {task_id} completion status updated to {completed_status}")
        return updated_task

    except ConnectionError as e:
        print(f"Database connection error: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database service is unavailable.")
    except ValueError as e: # Catch specific errors like task not found after update
        print(f"Value error during task update: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        print(f"Error updating task completion: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update task completion status.")
