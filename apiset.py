import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 1. 加载环境变量
load_dotenv()

# 2. 配置你的 LLM（从 .env 读取敏感信息）
llm = ChatOpenAI(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    openai_api_base=os.getenv("OPENAI_API_BASE"),
    model=os.getenv("OPENAI_MODEL", "gemini-3-flash-preview"),
    temperature=0.7
)

# 3. 测试一下 (冒烟测试)
try:
    print("正在连接 API...")
    response = llm.invoke("你好，请回复'连接成功'四个字。")
    print(f"{response.content}")
except Exception as e:
    print(f"配置出错啦: {e}")
