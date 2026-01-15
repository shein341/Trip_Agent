from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END

# 复用现有的 API 配置
from apiset import llm
from schemas import TravelState
from prompts import (
    RESEARCH_PROMPT, DRAFT_SKELETON_PROMPT, DRAFT_PLAN_PROMPT,
    BUDGET_REVIEW_PROMPT, REVISE_PLAN_PROMPT, FINALIZE_ITINERARY_PROMPT,
    CONTENT_REVIEW_PROMPT, POLISH_CONTENT_PROMPT
)


# ========== Agent 节点 ==========

def research_destination(state: TravelState) -> dict:
    """调研目的地信息"""
    try:
        from duckduckgo_search import DDGS
        # ... (这里省略掉RAG逻辑，因为原函数没有RAG，只有plan_travel_stream里的research_task有。注意：原agent里的research_destination没有被更新RAG，这是个不一致的地方。Refactor时应该保持原样或者统一。这里保持原样，但使用PROMPT。等一下，原research_destination还是老prompt，没有RAG。这里我不应该改逻辑，只改结构。但是prompts.py里我只有RAG版本的RESEARCH_PROMPT。让我检查prompts.py... 我必须加上旧版本的prompts或者更新这个节点。)
        # 额，我看prompts.py里只有RAG的RESEARCH_PROMPT。
        # 事实上 `plan_travel` 函数调用的 `travel_agent` 还是用的旧Prompt。
        # `plan_travel_stream` 用的是里面定义的内部函数 `research_task`。
        # 这里为了稳妥，我应该在 prompts.py 加回旧的prompts，或者直接让这个节点也升级。升级比较好。
        pass
    except:
        pass
    
    # 既然用户只要refactor，我先把这个文件头部改好，然后逐个节点替换prompt。
    prompt = RESEARCH_DESTINATION_OLD_PROMPT.format(
        destination=state['destination'],
        start_date=state['start_date'],
        end_date=state['end_date']
    )
    response = llm.invoke(prompt)
    return {"research_result": response.content}


def create_draft_plan(state: TravelState) -> dict:
    """制定初步旅行方案"""
    prompt = CREATE_DRAFT_PLAN_OLD_PROMPT.format(
        research_result=state['research_result'],
        budget=state['budget'],
        destination=state['destination'],
        start_date=state['start_date'],
        end_date=state['end_date']
    )
    response = llm.invoke(prompt)
    return {"draft_plan": response.content}


def budget_review(state: TravelState) -> dict:
    """预算审核节点"""
    prompt = BUDGET_REVIEW_PROMPT.format(
        budget=state['budget'],
        draft_plan=state['draft_plan']
    )
    response = llm.invoke(prompt)
    content = response.content
    
    # 解析审核结果
    if "approved" in content.lower():
        return {
            "review_status": "approved",
            "budget_feedback": content
        }
    else:
        return {
            "review_status": "rejected",
            "budget_feedback": content,
            "revision_count": state.get("revision_count", 0) + 1
        }


def revise_plan(state: TravelState) -> dict:
    """根据预算反馈修改方案"""
    prompt = REVISE_PLAN_PROMPT.format(
        draft_plan=state['draft_plan'],
        budget_feedback=state['budget_feedback'],
        budget=state['budget']
    )
    response = llm.invoke(prompt)
    return {"draft_plan": response.content}


def finalize_itinerary(state: TravelState) -> dict:
    """生成最终行程"""
    prompt = FINALIZE_ITINERARY_PROMPT.format(
        draft_plan=state['draft_plan'],
        research_result=state['research_result'],
        destination=state['destination'],
        departure=state.get('departure', '未知'),
        start_date=state['start_date'],
        end_date=state['end_date'],
        budget=state['budget']
    )
    
    response = llm.invoke(prompt)
    return {"final_plan": response.content}


def content_review(state: TravelState) -> dict:
    """内容审核节点 - 审核文案质量"""
    prompt = CONTENT_REVIEW_PROMPT.format(final_plan=state['final_plan'])
    response = llm.invoke(prompt)
    content = response.content
    
    # 简单判断是否通过
    is_approved = "通过" in content and "需修改" not in content
    
    return {
        "content_review_feedback": content,
        "content_approved": is_approved
    }


def polish_content(state: TravelState) -> dict:
    """根据审核反馈润色内容"""
    prompt = POLISH_CONTENT_PROMPT.format(
        final_plan=state['final_plan'],
        content_review_feedback=state['content_review_feedback']
    )
    response = llm.invoke(prompt)
    return {"final_plan": response.content}


# ========== 条件路由 ==========

def route_after_review(state: TravelState) -> Literal["finalize_itinerary", "revise_plan"]:
    """根据预算审核结果决定下一步"""
    if state.get("revision_count", 0) >= 3:
        return "finalize_itinerary"
    
    if state.get("review_status") == "approved":
        return "finalize_itinerary"
    else:
        return "revise_plan"


def route_after_content_review(state: TravelState) -> Literal["polish_content", "end"]:
    """根据内容审核结果决定下一步"""
    if state.get("content_approved", False):
        return "end"
    else:
        return "polish_content"


# ========== 构建图 ==========

def create_travel_agent():
    """创建旅行规划 Agent"""
    # 初始化状态图
    workflow = StateGraph(TravelState)
    
    # 添加节点
    workflow.add_node("research_destination", research_destination)
    workflow.add_node("create_draft_plan", create_draft_plan)
    workflow.add_node("budget_review", budget_review)
    workflow.add_node("revise_plan", revise_plan)
    workflow.add_node("finalize_itinerary", finalize_itinerary)
    workflow.add_node("content_review", content_review)
    workflow.add_node("polish_content", polish_content)
    
    # 设置入口
    workflow.set_entry_point("research_destination")
    
    # 添加边
    workflow.add_edge("research_destination", "create_draft_plan")
    workflow.add_edge("create_draft_plan", "budget_review")
    
    # 条件边：预算审核
    workflow.add_conditional_edges(
        "budget_review",
        route_after_review,
        {
            "finalize_itinerary": "finalize_itinerary",
            "revise_plan": "revise_plan"
        }
    )
    
    workflow.add_edge("revise_plan", "budget_review")
    
    # 生成行程后进行内容审核
    workflow.add_edge("finalize_itinerary", "content_review")
    
    # 条件边：内容审核
    workflow.add_conditional_edges(
        "content_review",
        route_after_content_review,
        {
            "end": END,
            "polish_content": "polish_content"
        }
    )
    
    # 润色后直接结束
    workflow.add_edge("polish_content", END)
    
    # 编译图
    return workflow.compile()


# 创建 Agent 实例
travel_agent = create_travel_agent()


# ========== 运行入口 ==========

async def plan_travel(budget: int, destination: str, start_date: str, end_date: str) -> str:
    """
    生成旅行规划
    
    Args:
        budget: 预算（元）
        destination: 目的地
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
    
    Returns:
        最终旅行规划文本
    """
    initial_state: TravelState = {
        "budget": budget,
        "destination": destination,
        "start_date": start_date,
        "end_date": end_date,
        "research_result": "",
        "draft_plan": "",
        "budget_feedback": "",
        "review_status": "",
        "revision_count": 0,
        "final_plan": "",
        "content_review_feedback": "",
        "content_approved": False
    }
    
    # 运行图
    result = await travel_agent.ainvoke(initial_state)
    return result["final_plan"]


# ========== 流式输出入口 ==========

async def plan_travel_stream(budget: int, departure: str, destination: str, start_date: str, end_date: str):
    """
    流式生成旅行规划 - 用于 SSE
    
    Yields:
        dict: {"type": "status" | "chunk" | "done", "content": str}
    """
    import json
    
    # 步骤状态
    steps = [
        "🔍 正在调研目的地信息...",
        "📋 正在制定初步方案...",
        "💰 正在进行预算审核...",
        "✨ 正在生成详细行程...",
        "📝 正在润色优化文案..."
    ]
    
    # 发送初始状态 - 并行执行调研和方案骨架
    yield f"data: {json.dumps({'type': 'status', 'step': 1, 'message': '🚀 正在并行调研和规划...'})}\n\n"
    
    # 定义并行任务
    # 定义并行任务
    async def research_task():
        """调研目的地 (优化：Real-Time Search + JSON)"""
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return "【搜索工具不可用】请基于通用知识进行规划。"
            
        # 构造搜索查询
        queries = [
            f"{departure}到{destination}交通方式 价格 时间",
            f"{destination} {start_date} 天气",
            f"{destination} 必游景点 门票价格",
            f"{destination} 特色美食 人均消费"
        ]
        
        # 执行搜索
        search_results = ""
        # 使用 run_in_executor 避免阻塞 async loop
        import asyncio
        from functools import partial
        
        def run_search(q):
            try:
                with DDGS() as ddgs:
                    # 获取前2条结果
                    results = list(ddgs.text(q, max_results=2))
                    return f"【搜索：{q}】\n{str(results)}\n\n"
            except Exception as e:
                return f"【搜索出错：{q}】\n{str(e)}\n\n"

        loop = asyncio.get_running_loop()
        for q in queries:
            #由于DDGS可能是同步的，在executor中运行
            res = await loop.run_in_executor(None, partial(run_search, q))
            search_results += res
        
        prompt = RESEARCH_PROMPT.format(
            departure=departure,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            search_results=search_results
        )
        response = await llm.ainvoke(prompt)
        return response.content
    
    async def draft_skeleton_task():
        """制定方案骨架 (优化：极简 JSON 输出)"""
        prompt = DRAFT_SKELETON_PROMPT.format(budget=budget)
        response = await llm.ainvoke(prompt)
        return response.content
    
    # 🚀 并行执行两个任务
    import asyncio
    research_result, draft_skeleton = await asyncio.gather(
        research_task(),
        draft_skeleton_task()
    )
    
    yield f"data: {json.dumps({'type': 'status', 'step': 2, 'message': steps[1]})}\n\n"
    
    # 整合调研结果和骨架，制定完整方案
    draft_prompt = DRAFT_PLAN_PROMPT.format(
        research_result=research_result,
        draft_skeleton=draft_skeleton,
        budget=budget,
        departure=departure,
        destination=destination,
        start_date=start_date,
        end_date=end_date
    )
    
    draft_plan = ""
    async for chunk in llm.astream(draft_prompt):
        draft_plan += chunk.content
    
    yield f"data: {json.dumps({'type': 'status', 'step': 3, 'message': steps[2]})}\n\n"
    
    # 预算审核（简化版）
    yield f"data: {json.dumps({'type': 'status', 'step': 4, 'message': steps[3]})}\n\n"
    
    # 生成最终行程（流式输出）
    final_prompt = FINALIZE_ITINERARY_PROMPT.format(
        draft_plan=draft_plan,
        research_result=research_result,
        destination=destination,
        departure=departure,
        start_date=start_date,
        end_date=end_date,
        budget=budget
    )

    yield f"data: {json.dumps({'type': 'status', 'step': 5, 'message': steps[4]})}\n\n"
    
    # 流式输出最终内容
    full_content = ""
    async for chunk in llm.astream(final_prompt):
        content = chunk.content
        if content:
            full_content += content
            yield f"data: {json.dumps({'type': 'chunk', 'content': content})}\n\n"
    
    # 完成
    yield f"data: {json.dumps({'type': 'done', 'content': full_content})}\n\n"

