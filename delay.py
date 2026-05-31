import time
import random
from datetime import datetime

from config import REPLY_MODE


def get_random_delay(proactive_state: dict) -> float:
    if REPLY_MODE == "fast":
        return random.uniform(0.05, 0.2)

    now = time.monotonic()

    if proactive_state["full_chat_active"]:
        time_since_full_chat = now - proactive_state["full_chat_start_time"]
        if time_since_full_chat >= proactive_state["FULL_CHAT_TIMEOUT"]:
            proactive_state["full_chat_active"] = False
            print("[完整聊天] 已退出（1分钟超时），下次回复将恢复正常延迟")

    if proactive_state["full_chat_active"]:
        if random.random() < 0.6:
            return random.uniform(0.08, 0.3)
        elif random.random() < 0.15:
            return random.uniform(1.5, 3.5)
        else:
            return random.uniform(0.25, 0.8)
    else:
        hour = datetime.now().hour

        if random.random() < 0.2:
            return random.uniform(0.2, 0.6)
        elif random.random() < 0.1:
            return random.uniform(4.0, 10.0)
        else:
            base = random.uniform(0.8, 2.5)

        if 2 <= hour <= 5:
            base *= 1.3
        elif 12 <= hour <= 13:
            base *= 0.9

        return min(base, 12.0)


def get_adaptive_window(msg_count: int, content_length: int) -> float:
    if msg_count == 1:
        base_wait = 1.0
    elif msg_count == 2:
        base_wait = 1.5
    else:
        base_wait = 2.0

    if content_length > 20:
        base_wait += 0.3

    if content_length > 50:
        base_wait += 0.2

    return min(base_wait, 2.5)


def get_reply_length_mode() -> str:
    r = random.random()
    if r < 0.50:
        return "short"
    elif r < 0.60:
        return "medium"
    else:
        return "multi"


def get_typing_delay(text: str) -> float:
    char_count = len(text)
    base_delay = char_count / random.uniform(3.5, 5.0)
    randomness = random.uniform(0.2, 0.8)
    total_delay = base_delay + randomness
    total_delay = max(0.4, min(total_delay, 3.5))
    return round(total_delay, 2)
