import os
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
import state

logger = logging.getLogger(__name__)

def process_telegram_task(task: dict):
    """
    Process a single Telegram task.
    task format:
    {
        "event_id": int,
        "generation": int,
        "message": str
    }
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing. Telegram transport disabled.")
        return
        
    event_id = task.get("event_id")
    generation = task.get("generation")
    message = task.get("message")
    
    if not event_id or generation is None or not message:
        logger.error(f"Malformed Telegram task: {task}")
        return
        
    # Check generation against state
    if generation != state.get_generation():
        logger.info(f"Discarding Telegram alert for event {event_id} due to stale generation.")
        return
        
    # Dispatch HTTP request
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }).encode('utf-8')
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                logger.info(f"Successfully sent Telegram alert for event {event_id}.")
            else:
                logger.error(f"Telegram API returned unexpected status {response.status}: {response.read().decode('utf-8')}")
    except urllib.error.URLError as e:
        logger.error(f"Failed to send Telegram alert for event {event_id}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error sending Telegram alert for event {event_id}: {e}")

def create_worker_callback():
    """
    Returns a callback function for the background worker.
    """
    def callback(task):
        try:
            process_telegram_task(task)
        except Exception as e:
            logger.exception(f"Telegram worker callback failed: {e}")
            
    return callback
