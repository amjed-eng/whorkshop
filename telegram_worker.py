import os
import urllib.request
import urllib.parse
import urllib.error
import logging
import threading
import state

logger = logging.getLogger(__name__)

_dedup_lock = threading.Lock()
_sent_alerts = set()

def reset_deduplication():
    with _dedup_lock:
        _sent_alerts.clear()

def send_telegram_message(message, token=None, chat_id=None, opener=None):
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        logger.warning("Telegram token or chat ID missing.")
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, method="POST")
    opener_to_use = opener or urllib.request.build_opener()
    
    try:
        with opener_to_use.open(req, timeout=5.0) as response:
            if response.status == 200:
                return True
            else:
                logger.error(f"Telegram API returned unexpected status: {response.status}")
                return False
    except urllib.error.HTTPError as e:
        logger.error(f"Telegram HTTP Error: {e.code}")
        return False
    except Exception as e:
        logger.error(f"Telegram Network/Timeout Error: {e}")
        return False

def create_telegram_worker_callback(opener=None):
    def process_telegram_task(task):
        try:
            if not isinstance(task, dict):
                logger.error("Malformed telegram task received")
                return
                
            generation = task.get("generation")
            event_id = task.get("event_id")
            message = task.get("message")
            
            if generation is None or event_id is None or message is None:
                logger.error("Malformed telegram task missing required fields")
                return
                
            if generation != state.get_generation():
                logger.info("Discarding stale telegram task due to generation mismatch")
                return
                
            dedup_key = (generation, event_id)
            with _dedup_lock:
                if dedup_key in _sent_alerts:
                    logger.info("Duplicate telegram task, ignoring")
                    return
                _sent_alerts.add(dedup_key)
                
            send_telegram_message(message, opener=opener)
            
        except Exception as e:
            logger.error(f"Unexpected error in Telegram worker: {e}")
            
    return process_telegram_task
