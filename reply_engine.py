import time
import random
import re as _re

from config import TARGET_CONTACT, DRY_RUN, MAX_REPLY_PARTS
from delay import get_random_delay, get_reply_length_mode, get_typing_delay
from message_handler import filter_new_messages, get_pending

_wx_ref = {}
_last_successful_reply_text = None


def set_wx_ref(wx):
    _wx_ref["wx"] = wx


def _wx_send(text: str, is_first_reply: bool = False) -> None:
    wx = _wx_ref.get("wx")
    if wx is None:
        return

    if is_first_reply:
        wx.SendMsg(text, who=TARGET_CONTACT)
        return

    if random.random() < 0.7:
        typing_time = min(len(text) * 0.08 + random.uniform(0.2, 1.0), 3.0)
        time.sleep(typing_time)

    wx.SendMsg(text, who=TARGET_CONTACT)


def do_reply(backend, combined_text: str, wx, proactive_state: dict, force_send: bool = False) -> bool:
    from persona_updater import extract_dynamic_persona, update_persona_file

    pending = get_pending()
    delay = get_random_delay(proactive_state)

    if delay > 0.3:
        print(f"💭 ... ({delay:.1f}s)" if delay > 2 else "", end="")
        time.sleep(delay)
        if delay > 2:
            print()
    else:
        time.sleep(delay)

    raw_msgs = wx.GetListenMessage(who=TARGET_CONTACT)
    new_contents = filter_new_messages(raw_msgs)
    if new_contents:
        if force_send:
            print(f"[📩 强制模式] 发现{len(new_contents)}条新消息但继续发送")
            for nc in new_contents:
                pending.setdefault("force_send_remaining", []).append(nc)
                print(f"  + {nc} (稍后处理)")
        else:
            print(f"[📩 发现有{len(new_contents)}条新消息，取消本次回复")
            for nc in new_contents:
                pending["messages"].append(nc)
                print(f"  + {nc}")
            return True

    length_mode = get_reply_length_mode()

    length_instruction = ""
    if length_mode == "short":
        length_instruction = "【重要】这次只回1条超短消息（2-8个字），比如：'在呢'、'吃了'、'不知道'、'笑死'、'真的假的'。绝对不要写长句！"
    elif length_mode == "medium":
        length_instruction = "【重要】这次只回1条中等长度的消息（10-20个字），不要拆成多条！把意思浓缩成一句话。"
    else:
        length_instruction = "【重要】这次可以稍微多说一点，但每条要短（3-8个字），按标点拆成2-3条发送。"

    reply = backend.reply(TARGET_CONTACT, combined_text + "\n" + length_instruction)
    if not reply:
        print("[!] 未生成回复，跳过")
        return False

    raw_parts = [p.strip() for p in _re.split(r'[。！？!?]', reply) if p.strip()]

    if len(raw_parts) <= 1 or any(len(p) > 20 for p in raw_parts):
        comma_parts = [p.strip() for p in _re.split(r'[，,、；;]', reply) if p.strip()]
        if len(comma_parts) > len(raw_parts):
            raw_parts = comma_parts

    if len(raw_parts) <= 1 or any(len(p) > 25 for p in raw_parts):
        space_parts = [p.strip() for p in _re.split(r'\s+', reply) if p.strip()]
        if len(space_parts) > len(raw_parts):
            raw_parts = space_parts

    final_parts = []
    for part in raw_parts:
        if len(part) > 15:
            sub_parts = _re.split(r'[，,、；:：\s]', part)
            for sp in sub_parts:
                sp = sp.strip()
                if sp:
                    final_parts.append(sp)
        else:
            final_parts.append(part)

    if not final_parts:
        final_parts = [reply]

    parts = [_re.sub(r'^[，。！？!?、；:\s]+', '', p).strip()
             for p in final_parts
             if _re.sub(r'^[，。！？!?、；:\s]+', '', p).strip()]

    if length_mode == "short":
        if len(parts) > 1:
            print(f"[📏 短消息模式] 原始{len(parts)}条，只取第1条")
            parts = parts[:1]
    elif length_mode == "medium":
        if len(parts) > 2:
            print(f"[📏 中等模式] 原始{len(parts)}条，合并为2条")
            parts = parts[:2]
    else:
        if len(parts) > MAX_REPLY_PARTS:
            print(f"[⚠️ 回复过长] 原始{len(parts)}条，合并为{MAX_REPLY_PARTS}条")
            merged_parts = parts[:MAX_REPLY_PARTS - 1]
            last_part = ' '.join(parts[MAX_REPLY_PARTS - 1:])
            merged_parts.append(last_part)
            parts = merged_parts

    mode_display = {"short": "📏短消息", "medium": "📏中等", "multi": "📏多条"}
    print(f"[回] {mode_display.get(length_mode, '')} {' | '.join(parts)}")
    for i, part in enumerate(parts):
        if i > 0:
            typing_delay = get_typing_delay(part)
            print(f"  ⌨️ 打字中({typing_delay}s)...")
            time.sleep(typing_delay)

        raw_msgs = wx.GetListenMessage(who=TARGET_CONTACT)
        new_contents = filter_new_messages(raw_msgs)
        if new_contents:
            remaining = len(parts) - i
            if force_send:
                print(f"[📩 强制模式] 发送第{i+1}条前发现{len(new_contents)}条新消息")
                for nc in new_contents:
                    pending.setdefault("force_send_remaining", []).append(nc)
                    print(f"  + {nc} (稍后处理)")
            else:
                print(f"[📩 发送第{i+1}条前发现{len(new_contents)}条新消息，取消剩余{remaining}条")
                for nc in new_contents:
                    pending["messages"].append(nc)
                    print(f"  + {nc}")
                return True

        if not DRY_RUN:
            _wx_send(part, is_first_reply=(i == 0))

    global _last_successful_reply_text
    _last_successful_reply_text = reply

    return False


def do_actual_reply(backend, wx, proactive_state: dict) -> None:
    from persona_updater import extract_dynamic_persona, update_persona_file

    pending = get_pending()
    attempt = 0
    force_send = False
    last_combined_msg = None

    while True:
        msgs = pending["messages"]
        if not msgs:
            break

        combined = " | ".join(msgs)
        if attempt == 0:
            print(f"[合并] {combined}")
        else:
            print(f"[🔄 合并新消息({attempt})] {combined}")

        last_combined_msg = combined
        attempt += 1

        if attempt > 20 and not force_send:
            print(f"[⚠️ 已重试{attempt-1}次，下次将强制发送")
            force_send = True

        has_new_msg = do_reply(backend, combined, wx, proactive_state, force_send=force_send)

        if has_new_msg and not force_send:
            print(f"[🔁 准备第{attempt+1}次尝试...")
            continue
        else:
            pending["messages"] = []
            pending["flushing"] = False
            if force_send and pending.get("force_send_remaining"):
                remaining = pending.pop("force_send_remaining", [])
                if remaining:
                    print(f"[⚠️ 强制发送后有{len(remaining)}条未回复，将在下次处理]")
                    pending["messages"] = remaining

            if last_combined_msg and _last_successful_reply_text:
                print("\n[🧠 分析对话中...]")
                updates = extract_dynamic_persona(backend, last_combined_msg, _last_successful_reply_text)
                if updates:
                    update_persona_file(updates, backend)

            break
