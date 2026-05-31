import time

from config import SKIP_CONTENTS, PERSONA_FILE
from delay import get_adaptive_window

_seen_msg_ids: set[str] = set()

_pending = {
    "messages": [],
    "last_time": 0.0,
    "flushing": False,
}


def filter_new_messages(raw_msgs) -> list:
    from wxauto.elements import FriendMessage

    new_contents = []
    for msg in (raw_msgs or []):
        if not isinstance(msg, FriendMessage):
            continue

        mid = str(getattr(msg, "id", "") or "")
        content = (getattr(msg, "content", "") or "").strip()

        if not content:
            continue

        if mid and mid in _seen_msg_ids:
            continue

        if mid:
            _seen_msg_ids.add(mid)

        new_contents.append(content)

    return new_contents


def handle_message(msg, backend, proactive_state: dict) -> None:
    from wxauto.elements import FriendMessage
    from config import rebuild_system_prompt

    if not isinstance(msg, FriendMessage):
        return

    mid = str(getattr(msg, "id", "") or "")
    content = (getattr(msg, "content", "") or "").strip()
    if not content:
        return
    if content in SKIP_CONTENTS:
        print(f"[跳过非文本] {content}")
        return
    if mid and mid in _seen_msg_ids:
        return
    if mid:
        _seen_msg_ids.add(mid)

    try:
        mem = backend.extract_memory(content)
        if mem:
            print(f"[记忆] {mem}")
            with open(PERSONA_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n- {mem}")
            rebuild_system_prompt(backend)
    except Exception as e:
        print(f"[记忆] 提取失败: {e}")

    from proactive import mark_incoming
    mark_incoming(proactive_state)

    _pending["messages"].append(content)
    _pending["last_time"] = time.monotonic()
    label = f"[收] {content}"
    if len(_pending["messages"]) > 1:
        label += " (继续等待)"
    print(label)


def get_pending():
    return _pending


def smart_flush_decision(backend, wx, proactive_state: dict) -> None:
    from reply_engine import do_actual_reply

    if not _pending["messages"]:
        return

    if _pending["flushing"]:
        return

    now = time.monotonic()
    elapsed = now - _pending["last_time"]
    msg_count = len(_pending["messages"])

    max_wait = get_adaptive_window(msg_count, 0)
    if elapsed >= max_wait:
        print(f"[⏰ 超时触发({elapsed:.1f}s>={max_wait:.1f}s，{msg_count}条)")
        _pending["flushing"] = True
        do_actual_reply(backend, wx, proactive_state)
        return

    if msg_count > 1:
        remaining = max_wait - elapsed
        print(f"[⏳ 等待中{remaining:.1f}s({msg_count}条积攒)")
