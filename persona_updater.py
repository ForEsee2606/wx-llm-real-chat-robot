import json as _json
from datetime import datetime

from config import PERSONA_FILE, rebuild_system_prompt


def _validate_extracted(updates: dict, user_msg: str, ai_reply: str) -> dict:
    combined = user_msg + ai_reply
    validated = {}
    for category, items in updates.items():
        kept = []
        for item in items:
            chars = [c for c in item if c not in '，。！？、；：""''（）\\s,!?;:\'"()·-—… ' and '\u4e00' <= c <= '\u9fff']
            matched = sum(1 for c in chars if c in combined)
            if len(chars) == 0 or matched / len(chars) >= 0.4:
                kept.append(item)
            else:
                print(f"[人设·校验] 丢弃疑似幻觉: {item}")
        if kept:
            validated[category] = kept
    return validated


def extract_dynamic_persona(backend, user_msg: str, ai_reply: str) -> dict:
    try:
        analysis_prompt = f"""你是一个严格的信息提取器。你的唯一任务是从对话中提取**明确提到**的信息。

【用户说】：{user_msg}
【AI回复】：{ai_reply}

严格规则：
- 只提取对话中**明确、直接**提到的信息，绝不推测、联想或编造
- 如果对话只是日常闲聊（如"想你了""在干嘛""晚安"），没有任何具体事实，输出空JSON
- "互相想念""互相喜欢"不算关系进展，只有称呼变化、承诺、重大决定才算
- 情感状态只记录有具体原因的（如"因为考试没考好不开心"），"表达了思念"不算
- 宁可漏掉也不要编造，不确定的信息不要写

只有明确提到以下信息时才提取：
1. **新事实**：对方明确说出的新情况（如"我换工作了""我明天要考试"）
2. **情感状态**：有具体原因的情绪（如"面试挂了很难过"）
3. **共同经历**：明确的约定或计划（如"周末去吃火锅"）
4. **关系进展**：称呼变化、重要承诺（如"以后叫你宝宝"）

输出格式（JSON，没有的类型不要写）：
{{{{
  "facts": ["事实1"],
  "emotions": ["情感描述"],
  "experiences": ["经历描述"],
  "relationship": ["关系进展"]
}}}}

如果没有任何值得记录的信息，输出：{{{{}}}}
只输出JSON，不要其他内容。"""

        old_timeout = backend.timeout
        backend.timeout = 15
        result = backend._post(
            analysis_prompt,
            [{"role": "user", "content": "请分析以上对话并输出JSON"}],
            max_tokens=200
        )
        backend.timeout = old_timeout

        if not result or '{}' in result or '{\n}' in result:
            return {}

        updates = _json.loads(result.strip())

        updates = {k: v for k, v in updates.items() if v}
        if not updates:
            return {}

        return _validate_extracted(updates, user_msg, ai_reply)

    except Exception as e:
        print(f"[人设更新] 提取失败: {e}")
        return {}


def update_persona_file(updates: dict, backend=None) -> None:
    if not updates:
        return

    now = datetime.now().strftime("%m-%d %H:%M")

    try:
        with open(PERSONA_FILE, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')
        new_lines = []

        added_facts = False
        added_emotions = False
        added_experiences = False
        added_relationship = False

        for line in lines:
            new_lines.append(line)

            if 'facts' in updates and not added_facts and '# 关于对方' in line and '- ' not in line:
                for fact in updates['facts']:
                    new_lines.append(f'- {fact} (得知于{now})')
                added_facts = True
                print(f"[人设·事实] {'; '.join(updates['facts'])}")

            elif 'emotions' in updates and not added_emotions and '# 性格与习惯' in line and line.endswith('习惯）'):
                new_lines.append(f'- 近期情绪状态：{"；".join(updates["emotions"])} ({now})')
                added_emotions = True
                print(f"[人设·情绪] {'; '.join(updates['emotions'])}")

            elif 'experiences' in updates and not added_experiences and '# 与对方的关系设定' in line and '散步。' in line:
                for exp in updates['experiences']:
                    new_lines.append(f'- {exp} ({now})')
                added_experiences = True
                print(f"[人设·经历] {'; '.join(updates['experiences'])}")

            elif 'relationship' in updates and not added_relationship and '在一起6个月' in line:
                for rel in updates['relationship']:
                    new_lines.append(f'- {rel} ({now})')
                added_relationship = True
                print(f"[人设·关系] {'; '.join(updates['relationship'])}")

        if not added_facts and 'facts' in updates:
            new_lines.append('\n# 动态更新的事实信息')
            for fact in updates['facts']:
                new_lines.append(f'- {fact} (得知于{now})')
            print(f"[人设·事实] {'; '.join(updates['facts'])}")

        if not added_emotions and 'emotions' in updates:
            new_lines.append('\n# 近期情绪状态')
            new_lines.append(f'- {"；".join(updates["emotions"])} ({now})')
            print(f"[人设·情绪] {'; '.join(updates['emotions'])}")

        if not added_experiences and 'experiences' in updates:
            new_lines.append('\n# 共同经历')
            for exp in updates['experiences']:
                new_lines.append(f'- {exp} ({now})')
            print(f"[人设·经历] {'; '.join(updates['experiences'])}")

        if not added_relationship and 'relationship' in updates:
            new_lines.append('\n# 关系进展')
            for rel in updates['relationship']:
                new_lines.append(f'- {rel} ({now})')
            print(f"[人设·关系] {'; '.join(updates['relationship'])}")

        with open(PERSONA_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))

        if backend:
            rebuild_system_prompt(backend)
            print("[人设] 系统提示已更新")

    except Exception as e:
        print(f"[人设更新] 写入失败: {e}")
