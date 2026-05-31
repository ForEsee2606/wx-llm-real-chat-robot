import time
import random
from datetime import datetime, timedelta

from config import (
    PROACTIVE_ENABLED, ACTIVE_HOUR_START, ACTIVE_HOUR_END,
    IDLE_MIN_MINUTES, IDLE_MAX_MINUTES, MAX_PROACTIVE_PER_DAY,
    SCHEDULED_GREETINGS, NIGHT_OWL_CHANCE, NIGHT_OWL_HOURS,
    TARGET_CONTACT, DRY_RUN,
)


def create_proactive_state() -> dict:
    return {
        "last_incoming": time.monotonic(),
        "last_proactive": 0.0,
        "next_idle_gap": 0.0,
        "day": None,
        "sent_today": 0,
        "plan": [],
        "fired": set(),
        "chat_active": False,
        "last_chat_time": 0.0,
        "chat_msg_count": 0,
        "last_checkin_time": 0.0,
        "topic_pending": False,
        "last_reply_time": 0.0,
        "topic_followup_sent": False,
        "full_chat_active": False,
        "full_chat_start_time": 0.0,
        "FULL_CHAT_TIMEOUT": 60.0,
    }


def _roll_idle_gap() -> float:
    return random.randint(IDLE_MIN_MINUTES, IDLE_MAX_MINUTES) * 60


def _build_day_plan(now_dt: datetime) -> list:
    plan = []
    today = now_dt.date()
    for h_start, h_end, chance, instruction in SCHEDULED_GREETINGS:
        if random.random() > chance:
            continue
        base = datetime.combine(today, datetime.min.time()).replace(hour=h_start)
        span_min = (h_end - h_start) * 60
        fire_at = base + timedelta(minutes=random.randint(0, max(span_min - 1, 0)))
        if fire_at <= now_dt:
            continue
        tag = f"{fire_at.hour:02d}:{fire_at.minute:02d}问候"
        plan.append((fire_at, instruction, tag))
    if random.random() < NIGHT_OWL_CHANCE:
        h0, h1 = NIGHT_OWL_HOURS
        base = datetime.combine(today, datetime.min.time()).replace(hour=h0)
        span_min = (h1 - h0) * 60
        fire_at = base + timedelta(minutes=random.randint(0, max(span_min - 1, 0)))
        if fire_at > now_dt:
            tag = f"{fire_at.hour:02d}:{fire_at.minute:02d}失眠"
            plan.append((fire_at, "你半夜失眠睡不着，主动给对方发条消息，"
                                  "可能在emo、刷手机睡不着、或者突然想他了", tag))
    plan.sort(key=lambda x: x[0])
    return plan


def _reset_day_if_needed(proactive_state: dict, now_dt: datetime) -> None:
    today = now_dt.date()
    if proactive_state["day"] != today:
        proactive_state["day"] = today
        proactive_state["sent_today"] = 0
        proactive_state["fired"] = set()
        proactive_state["plan"] = _build_day_plan(now_dt)
        when = "、".join(t for _, _, t in proactive_state["plan"]) or "今天不安排定时问候"
        print(f"[主动·排程] 今日计划: {when}")


def mark_incoming(proactive_state: dict) -> None:
    now = time.monotonic()
    proactive_state["last_incoming"] = now
    proactive_state["next_idle_gap"] = _roll_idle_gap()

    if not proactive_state["full_chat_active"]:
        proactive_state["full_chat_active"] = True
        proactive_state["full_chat_start_time"] = now
        print("[完整聊天] 已激活（专注聊天模式），后续回复将加速")
    else:
        proactive_state["full_chat_start_time"] = now

    time_since_last_chat = now - proactive_state["last_chat_time"]

    if time_since_last_chat <= 300:
        proactive_state["chat_active"] = True
        proactive_state["last_chat_time"] = now
        proactive_state["chat_msg_count"] += 1
    else:
        proactive_state["last_chat_time"] = now
        proactive_state["chat_msg_count"] = 1
        if proactive_state["chat_msg_count"] >= 2:
            proactive_state["chat_active"] = True
        else:
            proactive_state["chat_active"] = False


def check_full_chat_timeout(proactive_state: dict) -> None:
    if not proactive_state["full_chat_active"]:
        return

    now = time.monotonic()
    time_since_last_msg = now - proactive_state["full_chat_start_time"]

    if time_since_last_msg >= proactive_state["FULL_CHAT_TIMEOUT"]:
        proactive_state["full_chat_active"] = False
        print(f"[完整聊天] 已自动退出（{time_since_last_msg:.1f}秒无新消息），下次回复将恢复正常延迟")


def _emit_proactive(backend, instruction: str, tag: str, proactive_state: dict) -> None:
    from reply_engine import _wx_send

    prompt = (f"【系统提示：这是你主动发起的消息，不是在回复对方。{instruction}。"
              f"直接说你想说的话，不要解释，不要加引号。】")
    text = backend.reply(TARGET_CONTACT, prompt)
    if not text:
        print(f"[主动·{tag}] 未生成内容，跳过")
        return
    print(f"[主动·{tag}] {text}")
    now = time.monotonic()
    proactive_state["last_proactive"] = now
    proactive_state["last_incoming"] = now
    proactive_state["next_idle_gap"] = _roll_idle_gap()
    proactive_state["sent_today"] += 1
    if not DRY_RUN:
        _wx_send(text)


def proactive_tick(backend, proactive_state: dict) -> None:
    if not PROACTIVE_ENABLED:
        return
    now_dt = datetime.now()
    _reset_day_if_needed(proactive_state, now_dt)

    if proactive_state["sent_today"] >= MAX_PROACTIVE_PER_DAY:
        return

    for i, (fire_at, instruction, tag) in enumerate(proactive_state["plan"]):
        if i not in proactive_state["fired"] and now_dt >= fire_at:
            proactive_state["fired"].add(i)
            _emit_proactive(backend, instruction, tag, proactive_state)
            return

    if proactive_state["chat_active"]:
        now = time.monotonic()
        time_since_chat = now - proactive_state["last_chat_time"]
        time_since_checkin = now - proactive_state["last_checkin_time"]

        if 300 <= time_since_chat <= 900:
            if time_since_checkin >= 1800:
                _checkin_prompts = [
                    """你们正在聊天呢，他突然不回消息了。你有点担心也有点不耐烦，
                    发条消息问问他在干嘛或者是不是去忙了。要自然一点，不要太刻意。
                    比如：'人呢？'、'干嘛去了'、'还在吗'、'去忙了？'、'？？'""",

                    """聊得好好的突然不回了，你有点小失落但又不想表现得太明显。
                    随便找个借口再发一条，比如：'刚看到个好玩的东西'但其实没什么特别的，
                    或者直接问：'咋不回了'、'人没了？'、'去洗澡了？'""",

                    """他刚才还回得挺快的，现在突然消失了。你有点担心但更多是好奇，
                    发条消息试探一下：'在吗'、'忙啥呢'、'被外星人抓走了？(狗头)'、
                    '掉线了？'"""
                ]
                _emit_proactive(backend, random.choice(_checkin_prompts), "中断询问", proactive_state)
                proactive_state["last_checkin_time"] = now
                proactive_state["chat_msg_count"] = 0
                return
        elif time_since_chat > 900:
            proactive_state["chat_active"] = False
            proactive_state["chat_msg_count"] = 0

    if not (ACTIVE_HOUR_START <= now_dt.hour <= ACTIVE_HOUR_END):
        return
    if proactive_state["next_idle_gap"] <= 0:
        proactive_state["next_idle_gap"] = _roll_idle_gap()
    idle = time.monotonic() - proactive_state["last_incoming"]
    if idle >= proactive_state["next_idle_gap"]:
        _emit_proactive(backend,
                        random.choice([
                            "对方好长时间没理你了，你有点小失落但又不好意思直说，找个话题试探性地联系他",
                            "你刚刚刷到个好玩的东西想分享给他，但又要装作漫不经心的样子",
                            "假装有事找他其实就是想跟他说话，比如'在吗帮我看个东西'但其实没什么重要的事",
                            "突然想到他，忍不住发了条消息，说完又觉得会不会太明显了",
                            "有点无聊想找人聊天，但又不想表现得太主动，就随便找个借口联系他"
                        ]), "冷场", proactive_state)
