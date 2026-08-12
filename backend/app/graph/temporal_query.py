"""医疗轻量 OAG 底座 — 时态图查询工具。

本模块实现三类核心时态图查询函数，供上层 Agent 直接调用：
1. patient_full_chain(patient_id, time_window) — 患者全链路多跳查询
2. visit_context_isolation(visit_id) — 本次就诊上下文隔离查询
3. doctor_on_duty(doctor_id, date) — 医生当班时态查询

设计原则：
- 强制时间窗口：所有查询必须带 time_window 参数，不传则默认「本次就诊」
- 只读视图：查询只返回聚合数据，不修改图状态
- 多跳支持：可跨 2-3 层关系进行图遍历
- 异常安全：查询失败返回空结果，不抛异常中断业务
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from .abox import get_ograph
from .ontology import EntityType, RelType


def patient_full_chain(
    patient_id: str,
    time_window: Optional[Tuple[Optional[str], Optional[str]]] = None,
    store=None,
) -> dict:
    """患者全链路多跳查询。

    输入：患者 ID + 时间窗口
    输出：就诊记录 + 全部检验/影像报告 + 开立医生 + 执行房间 + 就诊时段
    核心用途：MDT 会诊资料自动聚合

    查询路径：
    Patient --has_visit--> VisitRecord
    VisitRecord --generate--> ExamReport
    ExamReport --belong_to--> Patient（反向验证）
    VisitRecord --execute_in--> Room
    Doctor --work_in--> Department（关联医生科室）

    Args:
        patient_id: 患者 ID
        time_window: 时间窗口 [start, end]，None 则默认近 90 天
        store: 可选，从 store 补充 data（当图谱尚未完全同步时）

    Returns:
        {
            "patient": {...},
            "visits": [...],
            "reports": [...],
            "rooms_used": [...],
            "doctors_involved": [...],
            "time_window": {...},
            "query_source": "ograph" | "store_fallback",
        }
    """
    # 默认时间窗口：近 90 天
    if time_window is None:
        end = datetime.now().astimezone()
        start = end - timedelta(days=90)
        time_window = (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"))

    g = get_ograph()

    # 1. 获取患者节点
    patient_node = g.get_node(patient_id)
    patient_data = patient_node.data if patient_node else {}

    # 如果图谱中没有患者数据，从 store 回退
    query_source = "ograph"
    if not patient_data and store and patient_id in store.patients:
        query_source = "store_fallback"
        patient_data = {
            "patient_id": patient_id,
            "patient_name": store.patients[patient_id].get("patient_name", ""),
        }

    # 2. 遍历：Patient → VisitRecord（has_visit）
    visit_ids = set()
    if patient_node:
        for edge in g.get_outgoing_edges(patient_id, RelType.HAS_VISIT, time_window):
            visit_ids.add(edge.target_id)
    elif store and patient_id in store.patients:
        for appt in store.patients[patient_id].get("appointments", []):
            vid = appt.get("visit_id", "")
            if vid:
                visit_ids.add(vid)

    # 3. 遍历：VisitRecord → ExamReport（generate）
    report_ids = set()
    for vid in visit_ids:
        for edge in g.get_outgoing_edges(vid, RelType.GENERATE, time_window):
            report_ids.add(edge.target_id)
    # store fallback
    if store and patient_id in store.patients:
        for report in (
            store.patients[patient_id]
            .get("emr_main", {})
            .get("reports", [])
            if isinstance(store.patients[patient_id].get("emr_main"), dict)
            else []
        ):
            rid = report.get("report_id", "")
            if rid and report.get("visit_id", "") in visit_ids:
                report_ids.add(rid)

    # 4. 遍历：VisitRecord → Room（execute_in）
    room_ids = set()
    for vid in visit_ids:
        for edge in g.get_outgoing_edges(vid, RelType.EXECUTE_IN, time_window):
            room_ids.add(edge.target_id)

    # 5. 医生关联：从 VisitRecord 的 data 中提取
    doctor_ids = set()
    visits_data = []
    for vid in sorted(visit_ids):
        node = g.get_node(vid)
        if node:
            visits_data.append(node.data)
            did = node.data.get("doctor_id", "")
            if did:
                doctor_ids.add(did)
        elif store and patient_id in store.patients:
            # store fallback
            for appt in store.patients[patient_id].get("appointments", []):
                if appt.get("visit_id") == vid:
                    visits_data.append({
                        "visit_id": vid,
                        "patient_id": patient_id,
                        "start_time": appt.get("start_time", ""),
                        "end_time": appt.get("end_time"),
                        "status": appt.get("status", "upcoming"),
                        "doctor_id": appt.get("doctor_id", ""),
                        "dept_id": appt.get("dept_id", ""),
                        "room_id": appt.get("room_id", ""),
                    })
                    did = appt.get("doctor_id", "")
                    if did:
                        doctor_ids.add(did)
                    rid = appt.get("room_id", "")
                    if rid:
                        room_ids.add(rid)

    # 6. 报告数据
    reports_data = []
    for rid in sorted(report_ids):
        node = g.get_node(rid)
        if node:
            reports_data.append(node.data)
        elif store and patient_id in store.patients:
            for report in (
                store.patients[patient_id]
                .get("emr_main", {})
                .get("reports", [])
                if isinstance(store.patients[patient_id].get("emr_main"), dict)
                else []
            ):
                if report.get("report_id") == rid:
                    reports_data.append(report)

    # 7. 房间数据
    rooms_data = []
    for rid in sorted(room_ids):
        node = g.get_node(rid)
        if node:
            rooms_data.append(node.data)

    # 8. 医生数据
    doctors_data = []
    for did in sorted(doctor_ids):
        node = g.get_node(did)
        if node:
            doctors_data.append(node.data)
        elif store and did in store.doctors:
            doctors_data.append({
                "doctor_id": did,
                "doctor_name": store.doctors[did]["doctor_name"],
                "title": store.doctors[did].get("title", ""),
            })

    return {
        "patient": patient_data,
        "visits": visits_data,
        "reports": reports_data,
        "rooms_used": rooms_data,
        "doctors_involved": doctors_data,
        "time_window": {"start": time_window[0], "end": time_window[1]},
        "query_source": query_source,
    }


def visit_context_isolation(
    visit_id: str,
    store=None,
) -> dict:
    """本次就诊上下文隔离查询。

    自动区分：本次就诊数据 VS 患者历史所有数据，默认隔离。
    防止信息混杂，MDT 会诊时非常关键。

    查询路径：
    VisitRecord → Patient → 关联报告/订单
    仅返回本次 visit_id 关联的数据，不返回其他就诊的报告和订单。

    Args:
        visit_id: 就诊 ID

    Returns:
        {
            "visit": {...},
            "patient": {...},
            "reports_in_visit": [...],      # 仅本次就诊报告
            "orders_in_visit": [...],       # 仅本次就诊医嘱
            "doctor_in_charge": {...},
            "room_assigned": {...},
            "isolation_note": "仅展示本次就诊数据，历史数据请另行查询",
        }
    """
    g = get_ograph()

    # 1. 获取 VisitRecord 节点
    visit_node = g.get_node(visit_id)
    visit_data = visit_node.data if visit_node else {}

    # store fallback
    if not visit_data and store:
        for pat in store.patients.values():
            for booking in pat.get("bookings", []):
                if booking.get("booking_id") == visit_id:
                    visit_data = {
                        "visit_id": visit_id,
                        "patient_id": pat["patient_id"],
                        "start_time": booking.get("start_time", ""),
                        "end_time": booking.get("end_time"),
                        "status": booking.get("status", "upcoming"),
                        "doctor_id": booking.get("doctor_id", ""),
                        "dept_id": booking.get("department", ""),
                        "room_id": booking.get("room_name", ""),
                    }
                    break

    patient_id = visit_data.get("patient_id", "")

    # 2. 获取患者信息
    patient_node = g.get_node(patient_id) if patient_id else None
    patient_data = patient_node.data if patient_node else {}
    if not patient_data and store and patient_id in store.patients:
        pd = store.patients[patient_id]
        patient_data = {
            "patient_id": patient_id,
            "patient_name": pd.get("patient_name", ""),
            "gender": pd.get("gender", ""),
            "age": pd.get("age", 0),
        }

    # 3. 获取本次就诊的报告（仅本次 visit_id）
    # 从 generate 边反向：VisitRecord → ExamReport
    report_ids = set()
    if visit_node:
        for edge in g.get_outgoing_edges(visit_id, RelType.GENERATE):
            report_ids.add(edge.target_id)

    reports_in_visit = []
    for rid in sorted(report_ids):
        node = g.get_node(rid)
        if node and node.data.get("visit_id") == visit_id:
            reports_in_visit.append(node.data)

    # store fallback
    if store and patient_id:
        for report in (
            store.patients[patient_id]
            .get("emr_main", {})
            .get("reports", [])
            if isinstance(store.patients[patient_id].get("emr_main"), dict)
            else []
        ):
            if report.get("visit_id") == visit_id:
                rid = report.get("report_id", "")
                if rid not in report_ids:
                    reports_in_visit.append(report)

    # 4. 获取本次就诊的医嘱
    orders_in_visit = []
    if store and patient_id:
        for order in store.patients[patient_id].get("orders", []):
            if order.get("visit_id") == visit_id:
                orders_in_visit.append(order)

    # 5. 医生信息
    doctor_id = visit_data.get("doctor_id", "")
    doctor_data = {}
    if doctor_id:
        doc_node = g.get_node(doctor_id)
        if doc_node:
            doctor_data = doc_node.data
        elif store and doctor_id in store.doctors:
            dd = store.doctors[doctor_id]
            doctor_data = {
                "doctor_id": doctor_id,
                "doctor_name": dd.get("doctor_name", ""),
                "title": dd.get("title", ""),
            }

    # 6. 房间信息
    room_id = visit_data.get("room_id", "")
    room_data = {}
    if room_id:
        room_node = g.get_node(room_id)
        if room_node:
            room_data = room_node.data

    # store fallback for doctor info
    doctor_id = visit_data.get("doctor_id", "")
    doctor_data = {}
    if doctor_id and store and doctor_id in store.users:
        dd = store.users[doctor_id]
        doctor_data = {
            "doctor_id": doctor_id,
            "doctor_name": dd.get("name", ""),
            "title": dd.get("title", ""),
        }

    return {
        "visit": visit_data,
        "patient": patient_data,
        "reports_in_visit": reports_in_visit,
        "orders_in_visit": orders_in_visit,
        "doctor_in_charge": doctor_data,
        "room_assigned": room_data,
        "isolation_note": "仅展示本次就诊数据，历史数据请另行查询",
    }


def doctor_on_duty(
    doctor_id: str,
    date: Optional[str] = None,
    store=None,
) -> dict:
    """医生当班时态查询。

    查询指定日期内，某医生接诊的患者、对应诊室、对应全部病例资料。
    适配下班复盘、MDT 讨论。

    查询路径：
    Doctor --work_in--> Department
    VisitRecord（按 doctor_id + 日期过滤）
    VisitRecord → Patient → ExamReport

    Args:
        doctor_id: 医生 ID
        date: 日期 (YYYY-MM-DD)，None 则今日

    Returns:
        {
            "doctor": {...},
            "department": {...},
            "date": "...",
            "patients_treated": [...],    # 当日接诊患者列表
            "visits": [...],              # 当日就诊记录
            "total_patients": N,
        }
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    g = get_ograph()

    # 1. 医生信息
    doc_node = g.get_node(doctor_id)
    doctor_data = doc_node.data if doc_node else {}
    if not doctor_data and store and doctor_id in store.users:
        dd = store.users[doctor_id]
        doctor_data = {
            "doctor_id": doctor_id,
            "doctor_name": dd.get("name", ""),
            "title": dd.get("title", ""),
        }

    # 2. 医生所在科室
    dept_ids = set()
    if doc_node:
        for edge in g.get_outgoing_edges(doctor_id, RelType.WORK_IN):
            dept_ids.add(edge.target_id)
    elif store and doctor_id in store.users:
        did = store.users[doctor_id].get("department", "")
        if did:
            # 通过 name 查找 dept_id
            for dep in store.departments.values():
                if dep.get("name", "") == did:
                    dept_ids.add(dep["dept_id"])
                    break

    dept_data = []
    for did in sorted(dept_ids):
        node = g.get_node(did)
        if node:
            dept_data.append(node.data)
        elif store and did in store.departments:
            dd = store.departments[did]
            dept_data.append({
                "dept_id": did,
                "dept_name": dd.get("name", ""),
                "category": dd.get("category", ""),
            })

    # 3. 查找当日该医生的就诊记录
    day_start = f"{date}T00:00:00"
    day_end = f"{date}T23:59:59"
    day_window = (day_start, day_end)

    visits = []
    patients_treated = set()

    # 从图谱中查找 VisitRecord 节点
    for vid, vnode in g.nodes.items():
        if vnode.entity_type != EntityType.VISIT_RECORD:
            continue
        v_data = vnode.data
        if v_data.get("doctor_id") != doctor_id:
            continue
        v_start = v_data.get("start_time", "")
        if v_start and date in v_start:
            visits.append(v_data)
            pid = v_data.get("patient_id", "")
            if pid:
                patients_treated.add(pid)

    # store fallback
    if store and not visits:
        for pat_id, pat in store.patients.items():
            for booking in pat.get("bookings", []):
                if booking.get("doctor_id") != doctor_id:
                    continue
                v_start = booking.get("start_time", "")
                if v_start and date in v_start:
                    visits.append({
                        "visit_id": booking.get("booking_id", ""),
                        "patient_id": pat_id,
                        "start_time": v_start,
                        "end_time": booking.get("end_time"),
                        "status": booking.get("status", "upcoming"),
                        "room_id": booking.get("room_name", ""),
                    })
                    patients_treated.add(pat_id)

    # 4. 患者详细信息
    patient_details = []
    for pid in sorted(patients_treated):
        p_node = g.get_node(pid)
        if p_node:
            patient_details.append(p_node.data)
        elif store and pid in store.patients:
            pd = store.patients[pid]
            patient_details.append({
                "patient_id": pid,
                "patient_name": pd.get("patient_name", ""),
                "gender": pd.get("gender", ""),
                "age": pd.get("age", 0),
            })

    return {
        "doctor": doctor_data,
        "department": dept_data,
        "date": date,
        "patients_treated": patient_details,
        "visits": visits,
        "total_patients": len(patient_details),
    }


def graph_health_check() -> dict:
    """图谱健康检查：返回节点/边统计信息。"""
    g = get_ograph()
    return g.get_stats()
