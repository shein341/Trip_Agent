from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
from contextlib import asynccontextmanager
from travel_agent import plan_travel, plan_travel_stream
from database import init_db, save_plan, get_history, get_plan_by_id, delete_plan
from apiset import llm
from schemas import (
    TravelRequest, TravelResponse, ChatRequest, ChatResponse, 
    HistoryResponse, BudgetItem, TravelRecord
)
from prompts import BUDGET_PARSING_PROMPT, CHAT_MODIFY_PROMPT

# 应用启动时初始化数据库
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="旅行规划 Agent", lifespan=lifespan)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


def extract_budget_breakdown(plan: str, total_budget: int) -> List[BudgetItem]:
    """从方案中提取预算分配（固定比例备用）"""
    categories = [
        {"category": "🚗 交通", "ratio": 0.30, "color": "#6366f1"},
        {"category": "🏨 住宿", "ratio": 0.35, "color": "#8b5cf6"},
        {"category": "🍜 餐饮", "ratio": 0.15, "color": "#f472b6"},
        {"category": "🎫 门票", "ratio": 0.12, "color": "#22d3ee"},
        {"category": "🛍️ 其他", "ratio": 0.08, "color": "#fbbf24"},
    ]
    
    return [
        BudgetItem(
            category=c["category"],
            amount=int(total_budget * c["ratio"]),
            color=c["color"]
        )
        for c in categories
    ]


async def extract_budget_with_llm(plan: str, total_budget: int) -> List[BudgetItem]:
    """使用 LLM 从生成的方案中解析真实预算数字"""
    import json as json_module
    import re
    
    prompt = BUDGET_PARSING_PROMPT.format(plan=plan[:2000], total_budget=total_budget)
    
    try:
        response = await llm.ainvoke(prompt)
        content = response.content
        
        # 提取 JSON
        json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
        if json_match:
            budget_data = json_module.loads(json_match.group())
            
            colors = {
                "交通": "#6366f1",
                "住宿": "#8b5cf6",
                "餐饮": "#f472b6",
                "门票": "#22d3ee",
                "其他": "#fbbf24"
            }
            
            emojis = {
                "交通": "🚗",
                "住宿": "🏨",
                "餐饮": "🍜",
                "门票": "🎫",
                "其他": "🛍️"
            }
            
            result = []
            for key, amount in budget_data.items():
                if key in colors:
                    result.append(BudgetItem(
                        category=f"{emojis.get(key, '')} {key}",
                        amount=int(amount) if isinstance(amount, (int, float)) else 0,
                        color=colors[key]
                    ))
            
            if result and sum(item.amount for item in result) > 0:
                return result
    except Exception as e:
        print(f"LLM 预算解析失败: {e}")
    
    # 失败时回退到固定比例
    return extract_budget_breakdown(plan, total_budget)


@app.get("/")
async def root():
    """返回前端页面"""
    return FileResponse("static/index.html")


@app.post("/travel-plan", response_model=TravelResponse)
async def create_travel_plan(request: TravelRequest):
    """生成旅行规划（非流式）"""
    try:
        plan = await plan_travel(
            budget=request.budget,
            destination=request.destination,
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        # 保存到数据库
        plan_id = await save_plan(
            destination=request.destination,
            budget=request.budget,
            start_date=request.start_date,
            end_date=request.end_date,
            plan_content=plan
        )
        
        budget_breakdown = extract_budget_breakdown(plan, request.budget)
        return TravelResponse(
            success=True, 
            plan=plan, 
            plan_id=plan_id,
            budget_breakdown=budget_breakdown
        )
    except Exception as e:
        return TravelResponse(success=False, plan="", message=str(e))


@app.get("/travel-plan-stream")
async def stream_travel_plan(
    budget: int,
    departure: str,
    destination: str,
    start_date: str,
    end_date: str
):
    """
    流式生成旅行规划 (SSE)
    
    使用 EventSource 接收实时生成的内容
    """
    async def event_generator():
        full_content = ""
        async for chunk in plan_travel_stream(budget, departure, destination, start_date, end_date):
            yield chunk
            # 收集完整内容用于保存
            if '"type": "chunk"' in chunk:
                import json
                try:
                    data = json.loads(chunk.replace("data: ", "").strip())
                    if data.get("type") == "chunk":
                        full_content += data.get("content", "")
                except:
                    pass
        
        # 保存到数据库
        if full_content:
            plan_id = await save_plan(
                departure=departure,
                destination=destination,
                budget=budget,
                start_date=start_date,
                end_date=end_date,
                plan_content=full_content
            )
            
            # 使用 LLM 解析预算
            budget_items = await extract_budget_with_llm(full_content, budget)
            budget_data = [{"category": item.category, "amount": item.amount, "color": item.color} for item in budget_items]
            
            import json
            yield f"data: {json.dumps({'type': 'budget', 'breakdown': budget_data})}\n\n"
            yield f"data: {json.dumps({'type': 'saved', 'plan_id': plan_id})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/history", response_model=HistoryResponse)
async def get_travel_history(limit: int = 20):
    """获取历史记录列表"""
    try:
        history = await get_history(limit)
        return HistoryResponse(success=True, history=history)
    except Exception as e:
        return HistoryResponse(success=False, message=str(e))


@app.get("/history/{plan_id}")
async def get_single_plan(plan_id: int):
    """获取单个规划详情"""
    try:
        record = await get_plan_by_id(plan_id)
        if record:
            return {"success": True, "record": record}
        return {"success": False, "message": "记录不存在"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.delete("/history/{plan_id}")
async def delete_travel_plan(plan_id: int):
    """删除旅行规划记录"""
    try:
        deleted = await delete_plan(plan_id)
        if deleted:
            return {"success": True, "message": "删除成功"}
        return {"success": False, "message": "记录不存在"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/chat-modify", response_model=ChatResponse)
async def chat_modify_plan(request: ChatRequest):
    """通过对话修改旅行方案"""
    try:
        prompt = CHAT_MODIFY_PROMPT.format(
            current_plan=request.current_plan,
            budget=request.budget,
            destination=request.destination,
            user_message=request.user_message
        )

        response = llm.invoke(prompt)
        modified_plan = response.content
        budget_breakdown = extract_budget_breakdown(modified_plan, request.budget)
        
        return ChatResponse(
            success=True,
            modified_plan=modified_plan,
            budget_breakdown=budget_breakdown
        )
    except Exception as e:
        return ChatResponse(success=False, modified_plan="", message=str(e))


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}
