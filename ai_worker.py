import os
import json
import logging
from groq import Groq
import db
import state
from prompt import build_prompt

logger = logging.getLogger(__name__)

def validate_ai_result(result: dict) -> bool:
    """Locally validate the AI structured output."""
    if not isinstance(result, dict):
        return False
        
    required_strings = [
        "event_type", "source", "target_service", "timestamp",
        "severity", "stage", "executive_title", "executive_summary",
        "business_impact", "recommended_action", "telegram_alert"
    ]
    
    for key in required_strings:
        if key not in result or not isinstance(result[key], str):
            return False
            
    if "attempt_count" not in result or not isinstance(result["attempt_count"], int):
        return False
        
    if "previous_related_events" not in result or not isinstance(result["previous_related_events"], list):
        return False
        
    if "current_risk_context" not in result or not isinstance(result["current_risk_context"], dict):
        return False
        
    if "risk_score" not in result or not isinstance(result["risk_score"], int):
        return False
        
    if not (0 <= result["risk_score"] <= 100):
        return False
        
    expected_keys = set(required_strings + ["attempt_count", "previous_related_events", "current_risk_context", "risk_score"])
    if set(result.keys()) != expected_keys:
        return False
        
    return True

def process_ai_task(task: dict, groq_client, telegram_queue, broadcast_callback):
    """
    Process a single AI task.
    """
    event_id = task.get("event_id")
    generation = task.get("generation")
    normalized_event = task.get("normalized_event")
    
    # 1. Check generation before AI call
    if generation != state.get_generation():
        logger.info(f"Discarding task {event_id} due to stale generation before Groq.")
        return
        
    prompt = build_prompt(normalized_event)
    
    schema = {
        "type": "object",
        "properties": {
            "event_type": {"type": "string"},
            "source": {"type": "string"},
            "target_service": {"type": "string"},
            "timestamp": {"type": "string"},
            "attempt_count": {"type": "integer"},
            "previous_related_events": {"type": "array"},
            "current_risk_context": {"type": "object"},
            "severity": {"type": "string"},
            "risk_score": {"type": "integer"},
            "stage": {"type": "string"},
            "executive_title": {"type": "string"},
            "executive_summary": {"type": "string"},
            "business_impact": {"type": "string"},
            "recommended_action": {"type": "string"},
            "telegram_alert": {"type": "string"}
        },
        "required": [
            "event_type", "source", "target_service", "timestamp", "attempt_count",
            "previous_related_events", "current_risk_context", "severity", "risk_score",
            "stage", "executive_title", "executive_summary", "business_impact", 
            "recommended_action", "telegram_alert"
        ],
        "additionalProperties": False
    }
    
    # 2. Call Groq
    try:
        response = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="openai/gpt-oss-20b",
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ai_result",
                    "schema": schema,
                    "strict": True
                }
            }
        )
        result_text = response.choices[0].message.content
        result = json.loads(result_text)
    except Exception as e:
        logger.exception(f"Groq API call failed: {e}")
        return
        
    # 3. Validate locally
    if not validate_ai_result(result):
        logger.error(f"Invalid AI output schema: {result}")
        return
        
    # 4. Check generation again
    if generation != state.get_generation():
        logger.info(f"Discarding task {event_id} due to stale generation after Groq.")
        return
        
    # 5. Update SQLite
    try:
        db.update_ai_classification(event_id, result, result["risk_score"])
    except Exception as e:
        logger.exception(f"Failed to update AI classification in DB: {e}")
        return
        
    # 6. Apply to presentation state
    accepted = state.apply_ai_result(result, generation)
    if not accepted:
        return
        
    # 7. Broadcast AI_RESULT
    if broadcast_callback:
        broadcast_callback("AI_RESULT", result)
        
    # 8. Check Telegram condition
    if result.get("severity") == "CRITICAL":
        alert_msg = result.get("telegram_alert", "")
        if alert_msg.strip():
            telegram_queue.put({
                "event_id": event_id,
                "generation": generation,
                "message": alert_msg
            })

def create_worker_callback(telegram_queue, broadcast_callback, groq_client=None):
    """
    Creates the callback for the generic worker thread.
    Allows injecting a fake groq_client for testing.
    """
    if groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if api_key:
            groq_client = Groq(api_key=api_key)
        else:
            logger.error("GROQ_API_KEY not found. AI worker will gracefully fail tasks.")
            groq_client = None

    def callback(task):
        if not groq_client:
            logger.error("No Groq client available to process task.")
            return
        process_ai_task(task, groq_client, telegram_queue, broadcast_callback)
        
    return callback
