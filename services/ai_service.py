# app/services/ai_service.py
import vertexai
from vertexai.generative_models import GenerativeModel, Part, HarmCategory, HarmBlockThreshold
import json
from datetime import datetime, timezone
from core.config import settings
from models.task_models import ProcessedTaskData

# Initialize Vertex AI
try:
    vertexai.init(project=settings.gcp_project_id, location=settings.vertex_ai_region)
    print(f"Vertex AI Initialized. Project: {settings.gcp_project_id}, Region: {settings.vertex_ai_region}")
except Exception as e:
    print(f"Error initializing Vertex AI: {e}")

# Configure generation config (tune as needed)
generation_config = {
    "temperature": 0.2, # Slightly lower for structured output
    "top_p": 0.8,
    "top_k": 40,
    "max_output_tokens": 512,
}

# Configure safety settings
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}

# Define the updated prompt template
PROMPT_TEMPLATE = """
Analyze the following raw task input. Your goal is to structure it for a task management system.

Raw Input: "{raw_input}"

**Current Time for Reference:** {current_time_utc}

Instructions:
1.  **Extract Core Action:** Identify the main task. Rephrase clearly.
2.  **Identify Deadline:** Look for specific dates (e.g., "Monday", "tomorrow", "June 5th", "2024-07-15"), times (e.g., "by 5 pm", "at noon"), or relative deadlines (e.g., "end of week", "next Tuesday"). If found, **parse it into a standard ISO 8601 datetime format (YYYY-MM-DDTHH:MM:SSZ)**, using the current time as reference for relative terms like "tomorrow". If no deadline is mentioned or it's too ambiguous, return null.
3.  **Suggest Tags:** Suggest 1-3 relevant tags (e.g., 'work', 'personal', 'meeting'). Return empty list if unsure.
4.  **Estimate Priority:** Based on keywords ('urgent', 'asap', 'important', 'critical', 'low priority'), suggest 'High', 'Medium', or 'Low'. Default to 'Medium'.
5.  **Format Output:** Return ONLY a JSON object with these exact keys:
    - "processed_description": The extracted core action (string).
    - "deadline": The parsed deadline in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ), or null if not found/parseable (string or null).
    - "tags": List of suggested tags (list of strings).
    - "priority_suggestion": Estimated priority ('High', 'Medium', or 'Low') (string).

Example 1:
Raw Input: "Need to prepare the urgent presentation slides for the client meeting on Friday morning"
Current Time for Reference: 2024-04-15T10:00:00Z
Output:
```json
{{
  "processed_description": "Prepare presentation slides for Friday client meeting",
  "deadline": "2024-04-19T09:00:00Z", // Assuming Friday morning is 9 AM
  "tags": ["work", "meeting", "urgent"],
  "priority_suggestion": "High"
}}

Example 2:
Raw Input: "Buy groceries"
Output:
```json
{{
  "processed_description": "Buy groceries",
  "deadline": null,
  "tags": ["personal", "errands"],
  "priority_suggestion": "Medium"
}}

Now, process the provided Raw Input. Return ONLY the JSON object.
"""

async def process_raw_task_input(raw_input: str) -> ProcessedTaskData:
    """
    Process the raw task input using Vertex AI Gemini to extract structured task data,
    including a parsed deadline.
    """
    current_time_iso = datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z'
    formatted_prompt = PROMPT_TEMPLATE.format(
        raw_input=raw_input,
        current_time_utc=current_time_iso
    )

    try:
        model = GenerativeModel.from_pretrained(settings.gemini_model_name)
        response = await model.generate(
            prompt=Part(prompt=formatted_prompt),
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
    except Exception as e:
        print(f"Error calling Vertex AI Gemini API: {e}")
        # Basic fallback without deadline
        return ProcessedTaskData(processed_description=raw_input, priority_suggestion="Medium", deadline=None)

    try:
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        if not response_text or not response_text.startswith("{"):
            print(f"Warning: Gemini returned non-JSON or empty response: '{response.text}'")
            return ProcessedTaskData(processed_description=raw_input, priority_suggestion="Medium", deadline=None)

        data = json.loads(response_text)

        # Manually parse the deadline string into a datetime object
        deadline_str = data.get("deadline")
        parsed_deadline = None
        if deadline_str:
            try:
                # Attempt to parse the ISO 8601 string
                # Ensure the 'Z' (Zulu/UTC) timezone indicator is handled correctly
                if deadline_str.endswith('Z'):
                    deadline_str = deadline_str[:-1] + '+00:00'
                parsed_deadline = datetime.fromisoformat(deadline_str)
                # Ensure it's timezone-aware (should be if parsing worked correctly)
                if parsed_deadline.tzinfo is None:
                    print(f"Warning: Parsed deadline {parsed_deadline} is timezone-naive. Assuming UTC.")
                    parsed_deadline = parsed_deadline.replace(tzinfo=timezone.utc)
            except ValueError as date_err:
                print(f"Error parsing deadline string '{deadline_str}' from AI: {date_err}")
                # Keep deadline as None if parsing fails
                parsed_deadline = None
            except Exception as general_date_err:
                 print(f"Unexpected error parsing deadline string '{deadline_str}': {general_date_err}")
                 parsed_deadline = None

        # Create ProcessedTaskData, replacing the string deadline with the parsed datetime object
        processed_data = ProcessedTaskData(
            processed_description=data.get("processed_description"),
            deadline=parsed_deadline, # Use the parsed datetime object or None
            tags=data.get("tags", []),
            priority_suggestion=data.get("priority_suggestion", "Medium")
        )
        return processed_data

    except json.JSONDecodeError as json_err:
        print(f"Error decoding JSON response from Gemini: {json_err}")
        print(f"Raw response text: {response.text}")
        return ProcessedTaskData(processed_description=raw_input, priority_suggestion="Medium", deadline=None)
    except Exception as parse_err:
        print(f"Error processing Gemini response: {parse_err}")
        print(f"Raw response text: {response.text}")
        return ProcessedTaskData(processed_description=raw_input, priority_suggestion="Medium", deadline=None)
