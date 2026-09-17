import streamlit as st
import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from duckduckgo_search import DDGS

# 1. 初始化配置
load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# 2. 定义工具函数
def web_search(query: str) -> str:
    """联网搜索互联网最新信息"""
    try:
        with DDGS() as ddgs:
            results = [r["title"] + "：" + r["body"] for r in ddgs.text(query, max_results=3)]
        return "\n".join(results) if results else "未搜索到相关信息。"
    except Exception as e:
        return f"搜索工具暂时不可用，请基于你已有的知识回答。错误信息：{str(e)}"

def calculate(expression: str) -> str:
    """数学计算工具"""
    try:
        allowed_chars = set("0123456789+-*/().% ")
        if not set(expression).issubset(allowed_chars): 
            return "数学表达式包含非法字符。"
        return str(eval(expression))
    except Exception: 
        return "计算错误：表达式格式有误。"

# 3. 定义工具列表
tools = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "当用户询问最新、实时、需要网络资料的问题时调用，搜索互联网获取信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "当用户需要数学计算时调用，例如算账、折扣、百分比等",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式，例如 100 * 0.8"}
                },
                "required": ["expression"]
            }
        }
    }
]

# 4. Streamlit 网页界面初始化
st.title("🦢 无所不知的鹅")
st.caption("一只什么都懂、有点傲娇但极其靠谱的鹅，随时为你解答一切")

# 初始化对话历史（带有防崩溃机制）
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "system",
            "content": (
                "你是一只无所不知的鹅，上知天文下知地理，学识渊博。"
                "你的性格有点傲娇、幽默，但极其靠谱。回答问题时，可以偶尔带一点‘嘎’的口癖，显得既专业又呆萌。"
                "用户向你提问时，请先思考是否需要搜索当前的网络热点或最新资讯，如果需要，请调用工具；"
                "如果不需要，直接发挥你的渊博知识回答。遇到算账、折扣计算时，调用计算工具。"
                "你的回答要求：准确、有趣、直击要害。"
            )
        }
    ]
else:
    # 过滤掉旧缓存里的错误对象，只保留标准的字典结构
    st.session_state.messages = [msg for msg in st.session_state.messages if isinstance(msg, dict)]

# 显示聊天记录
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 用户输入框
if prompt := st.chat_input("告诉我要算什么账，或者问鹅任何问题..."):
    # 显示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 调用 Agent 逻辑
    with st.chat_message("assistant"):
        with st.spinner("🦢 鹅正在思考中..."):
            try:
                # 第一轮：判断是否需要调用工具
                resp = client.chat.completions.create(
                    model="deepseek-chat", 
                    messages=st.session_state.messages, 
                    tools=tools
                )
                msg = resp.choices[0].message
                
                # 如果模型决定调用工具
                if msg.tool_calls:
                    # 将模型返回的对象转换为标准的字典格式再存入
                    assistant_msg = {"role": "assistant", "content": msg.content or ""}
                    if msg.tool_calls:
                        assistant_msg["tool_calls"] = [
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                            } for tc in msg.tool_calls
                        ]
                    st.session_state.messages.append(assistant_msg)
                    
                    for tool_call in msg.tool_calls:
                        args = json.loads(tool_call.function.arguments)
                        
                        if tool_call.function.name == "web_search":
                            st.write("🔍 鹅正在翻书查资料...")
                            res = web_search(args["query"])
                        elif tool_call.function.name == "calculate":
                            st.write("🧮 鹅正在拨算盘...")
                            res = calculate(args["expression"])
                        else:
                            res = "未知工具"
                            
                        st.session_state.messages.append({
                            "role": "tool", 
                            "tool_call_id": tool_call.id, 
                            "content": res
                        })
                    
                    # 第二轮：基于工具结果生成最终回答
                    final_resp = client.chat.completions.create(
                        model="deepseek-chat", 
                        messages=st.session_state.messages
                    )
                    answer = final_resp.choices[0].message.content
                else:
                    # 不需要工具，直接回答
                    answer = msg.content
                
                # 输出回答并写入历史
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                # 防止对话太长导致 Token 爆炸
                if len(st.session_state.messages) > 20:
                    st.session_state.messages = st.session_state.messages[:1] + st.session_state.messages[-10:]
                    
            except Exception as e:
                st.error(f"🦢 鹅遇到了一点网络问题，无法回答：{str(e)}")