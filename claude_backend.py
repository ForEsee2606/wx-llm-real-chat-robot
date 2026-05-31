"""
Claude 后端 - 直接调中转站 HTTP API（Anthropic 格式），绕开 claude CLI。
每个微信联系人维护独立的对话历史列表，实现多轮上下文。

配置来自 ~/.claude/settings.json 的 env 字段：
  ANTHROPIC_AUTH_TOKEN  - 中转站 API key
  ANTHROPIC_BASE_URL    - 中转站地址（例如 https://api.penguinsaichat.dpdns.org）
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime

# 从 ~/.claude/settings.json 读取中转站配置
def _load_relay_config() -> tuple[str, str]:
    cfg_path = os.path.expanduser(r"~\.claude\settings.json")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            data = json.load(f)
        env = data.get("env", {})
        key = env.get("ANTHROPIC_AUTH_TOKEN", "")
        base = env.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
        return key, base
    except Exception as e:
        raise RuntimeError(f"读取 settings.json 失败: {e}")


_API_KEY, _BASE_URL = _load_relay_config()
_MESSAGES_URL = f"{_BASE_URL}/v1/messages"


class ClaudeBackend:
    def __init__(self, system_prompt: str, model: str = "claude-opus-4-7",
                 timeout: int = 60):
        self.system_prompt = system_prompt
        self.model = model
        self.timeout = timeout
        self._histories: dict[str, list] = {}

    def reset(self, contact: str) -> None:
        self._histories.pop(contact, None)

    def _parse_response(self, data: dict) -> str | None:
        """解析API响应的text块"""
        try:
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text = block.get("text", "").strip()
                    if text:
                        return text
        except (KeyError, IndexError, TypeError):
            pass
        return None

    def _post(self, system: str, messages: list, max_tokens: int = 500) -> str | None:
        """发送API请求的底层方法"""
        payload = json.dumps({
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            _MESSAGES_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": _API_KEY,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            print(f"[backend] HTTP {e.code}: {body}")
            return None
        except Exception as e:
            print(f"[backend] 请求失败: {e}")
            return None

        text = self._parse_response(data)
        if not text:
            print(f"[backend] 解析失败: {str(data)[:200]}")
            return None
        return text

    def extract_memory(self, message: str) -> str | None:
        """判断消息是否包含需要长期记住的重要信息；返回要记住的内容或None"""
        if len(message) < 8:
            return None
        if len(message) < 3:
            return None
        sys_prompt = "你是一个记忆提取器。判断消息中是否有需要长期记住的重要信息（生日、喜好、习惯、重要事件等）。有则用一句话概括（10字内），没有只回「无」。只输出结果，不要解释。"
        old_timeout = self.timeout
        self.timeout = 10  # 短超时，避免卡住主流程
        result = self._post(sys_prompt, [{"role": "user", "content": message}], max_tokens=30)
        self.timeout = old_timeout
        if result and "无" not in result:
            return result.strip()
        return None

    def reply(self, contact: str, message: str) -> str | None:
        """根据联系人上下文生成回复"""
        history = self._histories.setdefault(contact, [])
        history.append({"role": "user", "content": f"对方说：{message}"})

        if len(history) > 80:
            history[:] = history[-80:]

        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S (%A)")
        time_hint = {"role": "user",
                      "content": f"【当前真实时间: {now_str}】请根据这个准确时间来判断你现在的状态。"}
        messages = [time_hint] + history

        text = self._post(self.system_prompt, messages)
        if not text:
            history.pop()
            return None

        text = __import__("re").sub(r'[（(][^）)]*[）)]', '', text).strip()
        history.append({"role": "assistant", "content": text})
        return text
