import sys
sys.path.insert(0, r"C:\Users\26065\IdeaProjects\untitled7")

from wxauto import WeChat

wx = WeChat()
print("WeChat() 成功")

# 列所有会话，看看能否找到 "伊"
try:
    sessions = wx.GetSession()
    print(f"共 {len(sessions)} 个会话")
    names = [s[0] if isinstance(s, (list, tuple)) else str(s)[:30] for s in sessions[:20]]
    print("前20个会话:", names)
    if "伊" in names:
        print("'伊' 在会话列表中!")
    else:
        print("'伊' 不在前20个。搜索全列表:")
        all_names = [s[0] if isinstance(s, (list, tuple)) else str(s) for s in sessions]
        matches = [n for n in all_names if "伊" in n]
        print("含'伊'的会话:", matches)
except Exception as e:
    print(f"GetSession() 报错: {e}")
