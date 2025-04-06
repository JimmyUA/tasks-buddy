# app/services/ai_service.py
import vertexai
from vertexai.generative_models import GenerativeModel, Part, HarmCategory, HarmBlockThreshold
import json
from core.config import settings
from models.task_models import ProcessedTaskData

# Initialize Vertex AI
try:
    vertexai.init(project=settings.gcp_project_id, location=settings.vertex_ai_region)
    print(f"Vertex AI Initialized. Project: {settings.gcp_project_id}, Region: {settings.vertex_ai_region}")
except Exception as e:
    print(f"Error initializing Vertex AI: {e}")
    # Handle initialization error appropriately

# Configure the generation config (optional, tune as needed)
generation_config = {
    "temperature": 0.3,  # Lower temperature for more deterministic output
    "top_p": 0.8,
    "top_k": 40,
    "max_output_tokens": 512,
}

# Configure safety settings (adjust based on expected input/output)
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}

# Define the prompt template
PROMPT_TEMPLATE = """
Analyze the following raw task input. Your goal is to structure it for a task management system.

Raw Input: "{raw_input}"

Instructions:
1.  **Extract Core Action:** Identify the main task or action the user wants to perform. Rephrase it clearly and concisely for a task description.
2.  **Identify Due Dates/Times:** Look for any mention of specific dates (e.g., "Monday", "tomorrow", "June 5th"), times (e.g., "by 5 pm", "at noon"), or relative deadlines (e.g., "end of week", "next Tuesday"). If found, extract the textual hint. Do not try to parse into a specific date format.
3.  **Suggest Tags:** Based on the content, suggest 1-3 relevant tags from common categories like 'work', 'personal', 'meeting', 'call', 'email', 'errands', 'urgent', 'project_x', 'writing', 'research', 'planning', 'review'. If unsure, provide an empty list.
4.  **Estimate Priority:** Based *only* on keywords in the raw input (like 'urgent', 'asap', 'important', 'critical', 'must do', 'deadline', 'low priority', 'later'), suggest a priority level: 'High', 'Medium', or 'Low'. If no strong keywords are present, suggest 'Medium'.
5.  **Format Output:** Return the result ONLY as a JSON object with the following keys:
    - "processed_description": The extracted core action (string).
    - "due_date_hint": The textual hint for the deadline, or null if none found (string or null).
    - "tags": A list of suggested tags (list of strings).
    - "priority_suggestion": The estimated priority ('High', 'Medium', or 'Low') (string).

Example:
Raw Input: "Need to prepare the urgent presentation slides for the client meeting on Friday morning"
Output:
```json
{{
  "processed_description": "Prepare presentation slides for Friday client meeting",
  "due_date_hint": "Friday morning",
  "tags": ["work", "meeting", "urgent"],
  "priority_suggestion": "High"
}}
Now, process the provided Raw Input. Return ONLY the JSON object.
"""


async def process_raw_task_input(raw_input: str) -> ProcessedTaskData:
    """
    Process the raw task input using Vertex AI Gemini to extract structured task data.
    """
    # Call the Gemini model with the prompt
    try:
        model = GenerativeModel.from_pretrained(settings.gemini_model_name)
        response = await model.generate(
            prompt=Part(prompt=PROMPT_TEMPLATE.format(raw_input=raw_input)),
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
    except Exception as e:
        print(f"Error calling Vertex AI Gemini API: {e}")
        # Fallback: Use raw input as description if AI fails
        return ProcessedTaskData(processed_description=raw_input, priority_suggestion="Medium")  # Basic fallback

    # Attempt to parse the JSON response
    try:
        # Gemini might wrap the JSON in ```json ... ``` markdown, try to extract it
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()  # Clean leading/trailing whitespace

        # Handle potential empty responses or non-JSON text before parsing
        if not response_text or not response_text.startswith("{"):
            print(f"Warning: Gemini returned non-JSON or empty response: '{response.text}'")
            # Return default structure on failure to parse or empty response
            return ProcessedTaskData(processed_description=raw_input, priority_suggestion="Medium")

        data = json.loads(response_text)
        return ProcessedTaskData(**data)

    except json.JSONDecodeError as json_err:
        print(f"Error decoding JSON response from Gemini: {json_err}")
        print(f"Raw response text: {response.text}")
        # Fallback: Use raw input as description if AI fails
        return ProcessedTaskData(processed_description=raw_input, priority_suggestion="Medium")
    except Exception as parse_err:  # Catch other potential errors during parsing/validation
        print(f"Error processing Gemini response: {parse_err}")
        print(f"Raw response text: {response.text}")
        return ProcessedTaskData(processed_description=raw_input, priority_suggestion="Medium")


    except Exception as e:
        print(f"Error calling Vertex AI Gemini API: {e}")
    # Fallback: Use raw input as description if AI fails
    return ProcessedTaskData(processed_description=raw_input, priority_suggestion="Medium")  # Basic fallback
