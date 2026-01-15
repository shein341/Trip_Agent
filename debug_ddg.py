from langchain_community.tools import DuckDuckGoSearchRun
try:
    search = DuckDuckGoSearchRun()
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
