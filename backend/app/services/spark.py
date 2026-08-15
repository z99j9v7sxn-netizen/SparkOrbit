"""兼容薄壳：旧代码仍可从 spark 模块导入，实际已切换至 DeepSeek。"""
from app.services.llm import extract_json, llm_available, llm_chat, llm_chat_stream

spark_available = llm_available
spark_chat = llm_chat
spark_chat_stream = llm_chat_stream

__all__ = ["extract_json", "spark_available", "spark_chat", "spark_chat_stream"]
