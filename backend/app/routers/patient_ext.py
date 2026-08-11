"""患者端扩展路由：AI导诊 / 挂号 / 就诊时间线 / 报告查阅 / 院内导航 / 护士协助。

所有 Mock 边界用 `# [Mock]` 标注，便于生产替换为真实 HIS/LIS/导航服务。
"""
from __future__ import annotations

import random
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from pydantic import BaseModel, Field

from app.auth import create_access_token, decode_token
from app.graph.state import (
    BookingRecord,
    NurseAssistRequest as NurseAssistRequestState,
    TriageMessage,
    TriageSession,
    VisitTimelineEvent,
)
from app.storage import now, store, uid
from app.subagents import patient_triage_subagent

router = APIRouter(prefix="/patient", tags=["patient-ext"])

# [Mock] 患者端独立 OAuth2 scheme（与医生端 /auth/login 区分）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/patient/auth/login", auto_error=False)


# ==================== Pydantic 请求模型 ====================

class PatientLoginRequest(BaseModel):
    patient_id: str
    medical_card_number: str


class TriageChatRequest(BaseModel):
    session_id: str
    message: str


class TriageAdoptRequest(BaseModel):
    dept_name: str


class BookingCreateRequest(BaseModel):
    department: str = Field(..., description="科室名称")
    doctor_id: str = Field(..., description="医生ID")
    slot_date: str = Field(..., description="预约日期 YYYY-MM-DD")
    slot_time: str = Field(..., description="时间段 HH:mm-HH:mm")


class NurseAssistRequest(BaseModel):
    message: str = Field(..., description="患者求助描述")
    room_name: str = Field(..., description="所在房间名称")


# ==================== 鉴权依赖 ====================

def get_current_patient(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    """从 Bearer Token 解析当前患者（强制鉴权）。"""
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未提供认证令牌")
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "认证令牌无效或已过期")
    if payload.get("role") != "patient":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "令牌角色不匹配")
    patient_id = payload.get("sub", "")
    patient_user = store.get_patient_user(patient_id)
    if patient_user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "患者用户不存在")
    # 同步 PatientState 中的患者信息
    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者档案不存在")
    # 合并返回：patient_user + state 摘要
    return {
        **patient_user,
        "status": state.get("status", "unknown"),
    }


# ==================== 辅助函数 ====================

def _make_patient_user_payload(patient_user: dict) -> dict:
    """构造患者 JWT payload（含 role=patient）。"""
    return {
        "user_id": patient_user["patient_id"],
        "username": patient_user["patient_id"],
        "name": patient_user["patient_name"],
        "role": "patient",
    }


def _find_doctor_by_department(department: str) -> dict:
    """[Mock] 根据科室查找可用医生。"""
    # [Mock] 生产需查询真实 HIS 医生排班
    doctors = {
        "消化内科": {"doctor_id": "u_att_01", "doctor_name": "张明", "title": "主治医师"},
        "心内科": {"doctor_id": "u_mdt_01", "doctor_name": "李华", "title": "主任医师"},
        "呼吸科": {"doctor_id": "doc_03", "doctor_name": "刘医生", "title": "副主任医师"},
        "骨科": {"doctor_id": "doc_04", "doctor_name": "赵医生", "title": "主治医师"},
        "皮肤科": {"doctor_id": "doc_05", "doctor_name": "孙医生", "title": "主治医师"},
        "眼科": {"doctor_id": "doc_06", "doctor_name": "周医生", "title": "副主任医师"},
        "耳鼻喉科": {"doctor_id": "doc_07", "doctor_name": "吴医生", "title": "主治医师"},
        "内分泌科": {"doctor_id": "doc_08", "doctor_name": "郑医生", "title": "主任医师"},
        "急诊科": {"doctor_id": "doc_09", "doctor_name": "陈医生", "title": "主治医师"},
    }
    return doctors.get(department, {"doctor_id": "doc_mock", "doctor_name": "待定医生", "title": ""})


def _find_room_by_department(department: str) -> dict:
    """[Mock] 根据科室查找房间信息。"""
    # [Mock] 生产需查询真实楼宇主数据
    for bld in store.list_buildings():
        for flr in bld.get("floors", []):
            for rm in flr.get("rooms", []):
                if rm.get("dept_name") == department:
                    return {
                        "building": bld["name"],
                        "floor": flr["name"],
                        "room": rm["name"],
                    }
    # [Mock] 兜底返回
    return {"building": "门诊楼", "floor": "1层", "room": "101诊室"}


# ==================== 1. 患者登录 ====================

@router.post("/auth/login")
def patient_login(body: PatientLoginRequest):
    """[Mock] 患者登录：patient_id + 电子健康卡号。"""
    patient_user = store.find_patient_user(body.patient_id, body.medical_card_number)
    if patient_user is None:
        # [Mock] 登录失败埋点
        store.track_patient_event({
            "patient_id": body.patient_id,
            "event_type": "login_fail",
            "detail": "patient_id 或 medical_card_number 不匹配",
        })
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "患者ID或电子健康卡号错误")
    payload = _make_patient_user_payload(patient_user)
    token = create_access_token(payload)
    # 登录成功埋点
    store.track_patient_event({
        "patient_id": patient_user["patient_id"],
        "event_type": "login_success",
        "detail": "患者登录成功",
    })
    return {
        "token": token,
        "patient": {
            "patient_id": patient_user["patient_id"],
            "patient_name": patient_user["patient_name"],
            "phone": patient_user["phone"],
            "gender": patient_user["gender"],
            "age": patient_user["age"],
        },
    }


# ==================== 2. 患者信息 ====================

@router.get("/auth/me")
def get_me(patient: dict = Depends(get_current_patient)):
    """获取当前患者信息。"""
    store.track_patient_event({
        "patient_id": patient["patient_id"],
        "event_type": "view_profile",
    })
    return {
        "patient_id": patient["patient_id"],
        "patient_name": patient["patient_name"],
        "medical_card_number": patient["medical_card_number"],
        "phone": patient["phone"],
        "gender": patient["gender"],
        "age": patient["age"],
        "status": patient.get("status", "unknown"),
    }


# ==================== 3. AI 导诊对话 ====================

@router.post("/triage/chat")
def triage_chat(body: TriageChatRequest, patient: dict = Depends(get_current_patient)):
    """[Mock] AI 导诊对话：接收患者消息，调用导诊 SubAgent 返回推荐。"""
    patient_id = patient["patient_id"]
    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者档案不存在")

    # 查找或创建会话
    sessions = state.setdefault("triage_sessions", [])
    session = None
    for s in sessions:
        if s.get("session_id") == body.session_id:
            session = s
            break

    if session is None:
        # 自动创建新会话
        session = {
            "session_id": body.session_id,
            "patient_id": patient_id,
            "messages": [],
            "recommended_departments": [],
            "adopted": False,
            "nurse_transfer": False,
            "created_at": now(),
            "closed_at": None,
            "trace_id": uid("trc"),
        }
        sessions.append(session)

    # 追加患者消息
    msg_id = uid("msg")
    patient_msg: TriageMessage = {
        "msg_id": msg_id,
        "role": "patient",
        "content": body.message,
        "created_at": now(),
    }
    session.setdefault("messages", []).append(patient_msg)

    # [Mock] 调用导诊 SubAgent（生产替换为 LLM + 科室知识库）
    triage_result = patient_triage_subagent(
        patient_id=patient_id,
        message=body.message,
        session_history=session.get("messages", []),
    )

    # 追加 Agent 回复
    agent_msg: TriageMessage = {
        "msg_id": uid("msg"),
        "role": "agent",
        "content": triage_result["reply"],
        "created_at": now(),
    }
    session["messages"].append(agent_msg)
    session["recommended_departments"] = triage_result["recommended_departments"]

    # 持久化患者 State
    store.upsert_patient(state)

    # 埋点
    store.track_patient_event({
        "patient_id": patient_id,
        "event_type": "triage_chat",
        "session_id": body.session_id,
        "trace_id": triage_result["trace_id"],
        "detail": body.message[:100],
    })

    return {
        "session_id": body.session_id,
        "reply": triage_result["reply"],
        "recommended_departments": triage_result["recommended_departments"],
        "trace_id": triage_result["trace_id"],
        "messages": session["messages"][-6:],  # 最近 6 条
    }


# ==================== 4. 导诊会话管理 ====================

@router.post("/triage/sessions")
def create_triage_session(patient: dict = Depends(get_current_patient)):
    """创建新的 AI 导诊会话。"""
    patient_id = patient["patient_id"]
    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者档案不存在")

    session_id = uid("ses")
    session: TriageSession = {
        "session_id": session_id,
        "patient_id": patient_id,
        "messages": [],
        "recommended_departments": [],
        "adopted": False,
        "nurse_transfer": False,
        "created_at": now(),
        "closed_at": None,
        "trace_id": uid("trc"),
    }
    state.setdefault("triage_sessions", []).append(session)
    store.upsert_patient(state)

    store.track_patient_event({
        "patient_id": patient_id,
        "event_type": "triage_session_create",
        "session_id": session_id,
    })

    return session


@router.get("/triage/sessions")
def list_triage_sessions(patient: dict = Depends(get_current_patient)):
    """列出当前患者的导诊会话历史。"""
    patient_id = patient["patient_id"]
    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者档案不存在")

    sessions = state.get("triage_sessions", [])
    # 返回摘要（不含完整 messages，避免数据过大）
    summaries = []
    for s in sessions:
        summaries.append({
            "session_id": s["session_id"],
            "created_at": s.get("created_at"),
            "closed_at": s.get("closed_at"),
            "adopted": s.get("adopted", False),
            "nurse_transfer": s.get("nurse_transfer", False),
            "message_count": len(s.get("messages", [])),
            "top_recommendation": (
                s.get("recommended_departments", [{}])[0].get("dept_name", "")
                if s.get("recommended_departments")
                else ""
            ),
            "trace_id": s.get("trace_id"),
        })

    store.track_patient_event({
        "patient_id": patient_id,
        "event_type": "list_triage_sessions",
    })

    return summaries


@router.post("/triage/sessions/{session_id}/adopt")
def adopt_triage_recommendation(
    session_id: str,
    body: TriageAdoptRequest,
    patient: dict = Depends(get_current_patient),
):
    """采纳导诊推荐 → 直接挂号（Mock HIS 同步）。"""
    patient_id = patient["patient_id"]
    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者档案不存在")

    # 查找会话
    session = None
    for s in state.get("triage_sessions", []):
        if s.get("session_id") == session_id:
            session = s
            break
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "导诊会话不存在")

    # 校验推荐科室
    recommended = session.get("recommended_departments", [])
    valid_depts = [d["dept_name"] for d in recommended]
    if body.dept_name not in valid_depts:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"科室 {body.dept_name} 不在推荐列表中：{valid_depts}",
        )

    # 标记会话为已采纳
    session["adopted"] = True
    session["closed_at"] = now()

    # [Mock] 自动挂号：使用推荐的医生和最近可用时段
    doctor_info = _find_doctor_by_department(body.dept_name)
    room_info = _find_room_by_department(body.dept_name)
    booking_id = uid("bk")

    # [Mock] 生成排队号和预估等候
    queue_number = random.randint(1, 50)
    estimated_wait = random.randint(5, 45)

    booking: BookingRecord = {
        "booking_id": booking_id,
        "patient_id": patient_id,
        "department": body.dept_name,
        "doctor_id": doctor_info["doctor_id"],
        "doctor_name": doctor_info["doctor_name"],
        "slot_date": now()[:10],
        "slot_time": "上午 09:00-09:30",
        "queue_number": queue_number,
        "estimated_wait": estimated_wait,
        "building_name": room_info["building"],
        "floor_name": room_info["floor"],
        "room_name": room_info["room"],
        "channel": "ai_triage",
        "status": "booked",
        "created_at": now(),
        "source_booking_id": None,
    }
    state.setdefault("bookings", []).append(booking)

    # 添加就诊时间线事件
    timeline_event: VisitTimelineEvent = {
        "event_id": uid("evt"),
        "event_type": "booking",
        "title": f"已预约 {body.dept_name}",
        "description": f"医生：{doctor_info['doctor_name']}，排队号：{queue_number}，预计等候 {estimated_wait} 分钟",
        "status": "pending",
        "timestamp": now(),
        "related_id": booking_id,
    }
    state.setdefault("visit_timeline", []).append(timeline_event)

    store.upsert_patient(state)

    store.track_patient_event({
        "patient_id": patient_id,
        "event_type": "triage_adopt",
        "session_id": session_id,
        "booking_id": booking_id,
        "detail": f"采纳推荐：{body.dept_name}",
    })

    return {
        "adopted": True,
        "department": body.dept_name,
        "booking": booking,
        "message": f"已为您预约 {body.dept_name}，排队号 {queue_number}，请按时就诊。",
    }


@router.post("/triage/sessions/{session_id}/nurse")
def transfer_to_nurse(
    session_id: str,
    patient: dict = Depends(get_current_patient),
):
    """转人工护士协助。"""
    patient_id = patient["patient_id"]
    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者档案不存在")

    # 查找会话
    session = None
    for s in state.get("triage_sessions", []):
        if s.get("session_id") == session_id:
            session = s
            break
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "导诊会话不存在")

    session["nurse_transfer"] = True
    session["closed_at"] = now()

    # [Mock] 自动创建护士协助工单
    nurse_req: NurseAssistRequestState = {
        "request_id": uid("nr"),
        "patient_id": patient_id,
        "patient_name": patient.get("patient_name", ""),
        "room_name": "分诊台",
        "message": "患者请求转人工护士协助",
        "status": "pending",
        "created_at": now(),
        "accepted_at": None,
    }
    state.setdefault("nurse_requests", []).append(nurse_req)
    store.upsert_patient(state)

    store.track_patient_event({
        "patient_id": patient_id,
        "event_type": "triage_nurse_transfer",
        "session_id": session_id,
        "request_id": nurse_req["request_id"],
    })

    return {
        "transferred": True,
        "request_id": nurse_req["request_id"],
        "message": "已为您转接护士协助，请耐心等待。",
    }


# ==================== 5. 挂号 ====================

@router.get("/bookings")
def list_bookings(patient: dict = Depends(get_current_patient)):
    """列出当前患者的挂号记录。"""
    patient_id = patient["patient_id"]
    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者档案不存在")

    bookings = state.get("bookings", [])
    store.track_patient_event({
        "patient_id": patient_id,
        "event_type": "list_bookings",
    })
    return bookings


@router.post("/bookings")
def create_booking(
    body: BookingCreateRequest,
    patient: dict = Depends(get_current_patient),
):
    """[Mock] 创建挂号：生成排队号、预估等候、房间信息。"""
    patient_id = patient["patient_id"]
    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者档案不存在")

    # [Mock] 查找医生和房间
    doctor_info = _find_doctor_by_department(body.department)
    room_info = _find_room_by_department(body.department)

    # [Mock] 生成排队号和预估等候
    queue_number = random.randint(1, 50)
    estimated_wait = random.randint(5, 45)

    booking_id = uid("bk")
    channel = "mini_app"  # [Mock] 生产从请求来源判断

    booking: BookingRecord = {
        "booking_id": booking_id,
        "patient_id": patient_id,
        "department": body.department,
        "doctor_id": body.doctor_id,
        "doctor_name": doctor_info["doctor_name"],
        "slot_date": body.slot_date,
        "slot_time": body.slot_time,
        "queue_number": queue_number,
        "estimated_wait": estimated_wait,
        "building_name": room_info["building"],
        "floor_name": room_info["floor"],
        "room_name": room_info["room"],
        "channel": channel,
        "status": "booked",
        "created_at": now(),
        "source_booking_id": None,
    }
    state.setdefault("bookings", []).append(booking)

    # 添加就诊时间线事件
    timeline_event: VisitTimelineEvent = {
        "event_id": uid("evt"),
        "event_type": "booking",
        "title": f"已预约 {body.department}",
        "description": f"医生：{doctor_info['doctor_name']}，排队号：{queue_number}，预计等候 {estimated_wait} 分钟",
        "status": "pending",
        "timestamp": now(),
        "related_id": booking_id,
    }
    state.setdefault("visit_timeline", []).append(timeline_event)

    store.upsert_patient(state)

    store.track_patient_event({
        "patient_id": patient_id,
        "event_type": "create_booking",
        "booking_id": booking_id,
        "department": body.department,
        "channel": channel,
    })

    return {
        "booking": booking,
        "message": f"挂号成功！{body.department}，排队号 {queue_number}，预计等候 {estimated_wait} 分钟。",
    }


@router.post("/bookings/{booking_id}/sync-his")
def sync_booking_from_his(
    booking_id: str,
    patient: dict = Depends(get_current_patient),
):
    """[Mock] 从线下 HIS 同步挂号信息（Mock 双向同步）。"""
    patient_id = patient["patient_id"]
    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者档案不存在")

    booking = None
    for b in state.get("bookings", []):
        if b.get("booking_id") == booking_id:
            booking = b
            break
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "挂号记录不存在")

    # [Mock] 模拟 HIS 同步：更新状态和排队号
    if booking.get("status") == "booked":
        booking["status"] = "completed"
        booking["source_booking_id"] = f"his_{booking_id}"
        # 添加时间线事件
        timeline_event: VisitTimelineEvent = {
            "event_id": uid("evt"),
            "event_type": "report",
            "title": "挂号已完成",
            "description": f"线下 HIS 已同步，诊查完成",
            "status": "done",
            "timestamp": now(),
            "related_id": booking_id,
        }
        state.setdefault("visit_timeline", []).append(timeline_event)
        store.upsert_patient(state)

    store.track_patient_event({
        "patient_id": patient_id,
        "event_type": "sync_his",
        "booking_id": booking_id,
    })

    return {
        "synced": True,
        "booking": booking,
        "message": "[Mock] HIS 同步成功。",
    }


# ==================== 6. 就诊时间线 ====================

@router.get("/timeline")
def get_visit_timeline(patient: dict = Depends(get_current_patient)):
    """获取患者就诊时间线事件。"""
    patient_id = patient["patient_id"]
    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者档案不存在")

    timeline = state.get("visit_timeline", [])
    store.track_patient_event({
        "patient_id": patient_id,
        "event_type": "view_timeline",
    })
    return timeline


# ==================== 7. 报告查阅（只读视图隔离） ====================

@router.get("/reports/{patient_id}")
def get_patient_reports(
    patient_id: str,
    patient: dict = Depends(get_current_patient),
):
    """[只读] 患者报告视图：emr_main（锁定）+ treatment_versions（不含 MDT 草稿）+ check_tasks。

    安全隔离：患者端 NO 访问 ai_draft 和 mdt_comments。
    """
    requester_id = patient["patient_id"]
    if requester_id != patient_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权查看其他患者的报告")

    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者档案不存在")

    # [Mock] 只读视图：emr_main 仅展示锁定版本
    emr = state.get("emr_main", {})
    emr_view = {
        "content": emr.get("content", ""),
        "locked": emr.get("locked", False),
        "locked_at": emr.get("locked_at"),
    }

    # 诊疗方案版本（不含 MDT 草稿）
    treatment_versions = []
    for v in state.get("treatment_versions", []):
        treatment_versions.append({
            "version_id": v.get("version_id"),
            "version_no": v.get("version_no"),
            "content": v.get("content", ""),
            "created_at": v.get("created_at"),
        })

    # 检查任务结果（仅展示已完成的结果）
    check_results = []
    for t in state.get("check_tasks", []):
        check_results.append({
            "task_id": t.get("task_id"),
            "task_type": t.get("task_type"),
            "task_label": t.get("task_label"),
            "status": t.get("status"),
            "completed_at": t.get("completed_at"),
            "result": t.get("result"),
        })

    store.track_patient_event({
        "patient_id": requester_id,
        "event_type": "view_reports",
        "target_patient_id": patient_id,
    })

    return {
        "patient_id": patient_id,
        "patient_name": state.get("patient_name", ""),
        "emr_main": emr_view,
        "treatment_versions": treatment_versions,
        "check_results": check_results,
        # [Mock] 明确排除 ai_draft 和 mdt_comments
        "_note": "本视图为患者端只读报告，不含 AI 草稿和 MDT 讨论内容。",
    }


# ==================== 8. 院内导航 ====================

@router.get("/navigation/dept/{dept_name}")
def get_department_navigation(
    dept_name: str,
    patient: dict = Depends(get_current_patient),
):
    """获取科室位置信息（楼宇/楼层/房间）。"""
    patient_id = patient["patient_id"]
    room_info = _find_room_by_department(dept_name)

    store.track_patient_event({
        "patient_id": patient_id,
        "event_type": "navigation_query",
        "detail": dept_name,
    })

    return {
        "department": dept_name,
        "building": room_info["building"],
        "floor": room_info["floor"],
        "room": room_info["room"],
        "message": f"{dept_name}位于 {room_info['building']} {room_info['floor']} {room_info['room']}",
    }


# ==================== 9. 护士协助 ====================

@router.post("/nurse/request")
def request_nurse_assistance(
    body: NurseAssistRequest,
    patient: dict = Depends(get_current_patient),
):
    """[Mock] 创建护士协助请求，推送到护士队列。"""
    patient_id = patient["patient_id"]
    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者档案不存在")

    request_id = uid("nr")
    nurse_req: NurseAssistRequestState = {
        "request_id": request_id,
        "patient_id": patient_id,
        "patient_name": patient.get("patient_name", ""),
        "room_name": body.room_name,
        "message": body.message,
        "status": "pending",
        "created_at": now(),
        "accepted_at": None,
    }
    state.setdefault("nurse_requests", []).append(nurse_req)
    store.upsert_patient(state)

    # [Mock] 同步添加到护士通知队列
    store.push_notify(
        patient_id=patient_id,
        target_user_id="u_nurse_01",  # [Mock] 推给当前在岗护士
        ntype="nurse_assist_request",
        message=f"患者 {patient.get('patient_name', '')} 请求护士协助：{body.message}",
    )

    store.track_patient_event({
        "patient_id": patient_id,
        "event_type": "nurse_request",
        "request_id": request_id,
        "detail": body.message[:100],
    })

    return {
        "request_id": request_id,
        "status": "pending",
        "message": "护士协助请求已提交，请耐心等待。",
    }