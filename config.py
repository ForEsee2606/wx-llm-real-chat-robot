import os

TARGET_CONTACT = "伊"
POLL_INTERVAL = 1
MERGE_WINDOW = 1.5
MODEL = "deepseek-ai/DeepSeek-V4-Flash"

REPLY_MODE = "human"

PROACTIVE_ENABLED = True
ACTIVE_HOUR_START = 8
ACTIVE_HOUR_END = 23
IDLE_MIN_MINUTES = 30
IDLE_MAX_MINUTES = 90
MAX_PROACTIVE_PER_DAY = 12

SCHEDULED_GREETINGS = [
    (7, 9, 0.6, "现在是早上，你刚起床迷迷糊糊的，给对方发条消息：可以撒娇说不想起床、问对方醒了没、或者分享做的梦"),
    (11, 13, 0.5, "现在是中午饭点，你有点饿或者刚吃完，跟对方聊聊：吐槽食堂/外卖、问对方吃啥了、或者分享你看到的有趣东西"),
    (15, 17, 0.4, "下午课间/休息时间，你可能有点无聊或困了，找对方聊聊天：分享刷到的视频、吐槽上课、或者随口问问对方在干嘛"),
    (18, 20, 0.5, "傍晚时分，你可能在回宿舍/准备晚饭，跟对方 says today thing、或者约着晚上一起打游戏/连麦"),
    (21, 23, 0.6, "晚上快睡觉了，有点舍不得结束对话，可以说晚安、分享今天的感受、或者撒个娇让对方哄你睡"),
]

NIGHT_OWL_CHANCE = 0.1
NIGHT_OWL_HOURS = (0, 3)

_base_dir = os.path.dirname(__file__) or "."
PERSONA_FILE = os.path.join(_base_dir, "persona.txt")
PROMPT_FILE = os.path.join(_base_dir, "prompt.txt")

with open(PERSONA_FILE, encoding="utf-8") as _f:
    _persona = _f.read().strip()
with open(PROMPT_FILE, encoding="utf-8") as _f:
    _prompt_rules = _f.read().strip()

SYSTEM_PROMPT = _persona + "\n\n" + _prompt_rules

DRY_RUN = False

MAX_REPLY_PARTS = 3

SKIP_CONTENTS = {"[图片]", "[视频]", "[动画表情]", "[文件]", "[语音]",
                 "[位置]", "[链接]", "[聊天记录]", "[名片]", "[转账]", "[红包]"}


def rebuild_system_prompt(backend) -> None:
    with open(PERSONA_FILE, encoding="utf-8") as f:
        p = f.read().strip()
    backend.system_prompt = p + "\n\n" + _prompt_rules
