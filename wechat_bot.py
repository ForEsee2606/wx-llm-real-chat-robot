"""
微信聊天机器人 - wxauto(微信3.9)+ Claude Code(复用订阅)。

只监听并回复一个联系人(TARGET_CONTACT，通常是你自己的大号)。
工作方式：AddListenChat 注册该联系人 -> 循环 GetListenMessage 拉取新消息
         -> 只取好友发来的文本 -> 交给 Claude 生成回复 -> SendMsg 回复。

安全设计：
  - 只监听 TARGET_CONTACT 一个人，其他任何聊天都不触发，绝不会误回。
  - 只处理 FriendMessage 且内容是普通文本(跳过图片/表情/系统/自己发的)。
  - 用消息 id 去重，避免重复回复。
  - DRY_RUN=True 时只打印不发送，便于联调。

运行：
  .venv-bot/Scripts/python.exe wechat_bot.py
前提：微信3.9主窗口已打开并登录，运行期间别手动操作微信窗口。
"""
import time
import sys
import os

from config import (
    TARGET_CONTACT, POLL_INTERVAL, MODEL, SYSTEM_PROMPT,
    DRY_RUN, REPLY_MODE, PROACTIVE_ENABLED,
    ACTIVE_HOUR_START, ACTIVE_HOUR_END,
    IDLE_MIN_MINUTES, IDLE_MAX_MINUTES, MAX_PROACTIVE_PER_DAY,
)
from claude_backend import ClaudeBackend
from message_handler import handle_message, smart_flush_decision
from proactive import (
    create_proactive_state, proactive_tick, check_full_chat_timeout, _roll_idle_gap,
)
from reply_engine import set_wx_ref


def main():
    try:
        from wxauto import WeChat
    except Exception as e:
        print(f"导入 wxauto 失败：{e}")
        sys.exit(1)

    try:
        wx = WeChat()
    except Exception as e:
        print(f"连接微信失败：{e}")
        print("请确认微信3.9主窗口已打开（从托盘点出来），且小号已登录。")
        sys.exit(1)
    set_wx_ref(wx)

    backend = ClaudeBackend(system_prompt=SYSTEM_PROMPT, model=MODEL)

    try:
        wx.AddListenChat(who=TARGET_CONTACT)
    except Exception as e:
        print(f"添加监听对象「{TARGET_CONTACT}」失败：{e}")
        print("请确认 TARGET_CONTACT 名称和微信里显示的完全一致。")
        sys.exit(1)

    proactive_state = create_proactive_state()
    proactive_state["last_incoming"] = time.monotonic()
    proactive_state["next_idle_gap"] = _roll_idle_gap()

    if PROACTIVE_ENABLED:
        mode_display = "⚡快速模式" if REPLY_MODE == "fast" else "🎭真人模式(含完整聊天)"
        print(f"机器人已启动 | 监听对象={TARGET_CONTACT} | 回复模式={mode_display} | DRY_RUN={DRY_RUN} | "
              f"主动发消息=开(活跃{ACTIVE_HOUR_START}-{ACTIVE_HOUR_END}点, "
              f"冷场{IDLE_MIN_MINUTES}-{IDLE_MAX_MINUTES}分, 每日上限{MAX_PROACTIVE_PER_DAY})")
        if REPLY_MODE == "human":
            print(f"[完整聊天] 已启用：首次回复有延迟 → 连续聊天加速响应 → 1分钟无消息自动退出")
    else:
        mode_display = "⚡快速模式" if REPLY_MODE == "fast" else "🎭真人模式(含完整聊天)"
        print(f"机器人已启动 | 监听对象={TARGET_CONTACT} | 回复模式={mode_display} | DRY_RUN={DRY_RUN} | 主动发消息=关")
        if REPLY_MODE == "human":
            print(f"[完整聊天] 已启用：首次回复有延迟 → 连续聊天加速响应 → 1分钟无消息自动退出")
    print("按 Ctrl+C 停止\n")

    while True:
        try:
            msgs = wx.GetListenMessage(who=TARGET_CONTACT)
            for msg in (msgs or []):
                try:
                    handle_message(msg, backend, proactive_state)
                except Exception as e:
                    print(f"[处理单条消息出错，继续] {e}")
            try:
                smart_flush_decision(backend, wx, proactive_state)
            except Exception as e:
                print(f"[智能合并出错，继续] {e}")
            try:
                proactive_tick(backend, proactive_state)
            except Exception as e:
                print(f"[主动发消息出错，继续] {e}")
            try:
                check_full_chat_timeout(proactive_state)
            except Exception as e:
                print(f"[完整聊天超时检查出错，继续] {e}")
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\n已停止。")
            break
        except Exception as e:
            print(f"[轮询异常，继续] {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    from datetime import datetime
    log_file = f"logs/bot_{datetime.now():%Y-%m-%d_%H-%M-%S}.log"
    fh = open(log_file, "w", encoding="utf-8")
    _old_print = print
    def _tee(*a, **kw):
        kw2 = {k: v for k, v in kw.items() if k != "file"}
        _old_print(*a, file=fh, **kw2)
        fh.flush()
        _old_print(*a, **kw)
    import builtins; builtins.print = _tee
    print(f"[日志] 日志文件: {os.path.abspath(log_file)}")
    try:
        main()
    finally:
        fh.close()
