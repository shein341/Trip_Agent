from pydantic import BaseModel
from typing import List, Optional, TypedDict

# ====================
# API Request/Response Models
# ====================

class TravelRequest(BaseModel):
    """旅行规划请求"""
    budget: int
    departure: str
    destination: str
    start_date: str
    end_date: str


class BudgetItem(BaseModel):
    """预算项目"""
    category: str
    amount: int
    color: str


class TravelResponse(BaseModel):
    """旅行规划响应"""
    success: bool
    plan: str
    plan_id: Optional[int] = None
    budget_breakdown: List[BudgetItem] = []
    message: str = ""


class ChatRequest(BaseModel):
    """对话修改请求"""
    current_plan: str
    user_message: str
    budget: int
    destination: str


class ChatResponse(BaseModel):
    """对话修改响应"""
    success: bool
    modified_plan: str
    budget_breakdown: List[BudgetItem] = []
    message: str = ""


class TravelRecord(BaseModel):
    """数据库记录模型"""
    id: int
    departure: str
    destination: str
    budget: int
    start_date: str
    end_date: str
    plan_content: str
    created_at: str


class HistoryResponse(BaseModel):
    """历史记录响应"""
    success: bool
    history: List[TravelRecord] = []
    message: str = ""

# ====================
# LangGraph State
# ====================

class TravelState(TypedDict):
    """旅行规划状态"""
    # 用户输入
    budget: int  # 预算（元）
    destination: str  # 目的地
    start_date: str  # 开始日期
    end_date: str  # 结束日期
    
    # 中间状态
    research_result: str  # 目的地调研结果
    draft_plan: str  # 初步方案
    budget_feedback: str  # 预算审核反馈
    review_status: str  # approved / rejected
    revision_count: int  # 修改次数（防止无限循环）
    
    # 最终输出
    final_plan: str  # 最终旅行规划
    content_review_feedback: str  # 内容审核反馈
    content_approved: bool  # 内容是否通过审核
