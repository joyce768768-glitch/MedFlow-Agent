"""OAG 底座验证脚本：测试 TBox 公理、ABox 构建、三类时态查询。

运行方式：cd backend && python -m app.tests.test_oag
或者：cd backend && python -c "from app.tests.test_oag import run_all; run_all()"
"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime, timedelta

# 确保种子数据在测试前加载
from app.storage import store
from app.mock_data import seed_all
seed_all(store)


def test_tbox_axioms():
    """测试 TBox 公理校验函数。"""
    from app.graph.ontology import (
        AxiomViolation,
        EntityType,
        RelType,
        TBoxEdge,
        TBoxNode,
        validate_belong_to_uniqueness,
        validate_entity_fields,
        validate_identity_mutex,
        validate_rel_type,
        validate_valid_time,
        validate_visit_cardinality,
    )

    results = []

    # 1. 实体属性完备性
    try:
        validate_entity_fields(EntityType.PATIENT, {"patient_id": "p1", "patient_name": "test"})
        results.append(("实体属性完备性-通过", True))
    except Exception as e:
        results.append(("实体属性完备性-通过", False, str(e)))

    try:
        validate_entity_fields(EntityType.PATIENT, {"patient_id": "p1"})
        results.append(("实体属性完备性-缺失必填应报错", False))
    except AxiomViolation:
        results.append(("实体属性完备性-缺失必填应报错", True))
    except Exception as e:
        results.append(("实体属性完备性-缺失必填应报错", False, str(e)))

    # 2. 关系合法性
    try:
        validate_rel_type(RelType.WORK_IN, EntityType.DOCTOR, EntityType.DEPARTMENT)
        results.append(("关系合法性-WORK_IN", True))
    except Exception as e:
        results.append(("关系合法性-WORK_IN", False, str(e)))

    try:
        validate_rel_type(RelType.WORK_IN, EntityType.PATIENT, EntityType.DEPARTMENT)
        results.append(("关系合法性-源类错误应报错", False))
    except AxiomViolation:
        results.append(("关系合法性-源类错误应报错", True))

    # 3. 时态公理
    try:
        validate_valid_time(RelType.WORK_IN, None)
        results.append(("时态公理-WORK_IN无时态应报错", False))
    except AxiomViolation:
        results.append(("时态公理-WORK_IN无时态应报错", True))

    try:
        validate_valid_time(RelType.LOCATE_IN, None)
        results.append(("时态公理-LOCATE_IN无时态应通过", True))
    except Exception as e:
        results.append(("时态公理-LOCATE_IN无时态应通过", False, str(e)))

    # 4. 唯一归属公理
    existing = [TBoxEdge("r1", "p1", RelType.BELONG_TO)]
    new_edge = TBoxEdge("r1", "p2", RelType.BELONG_TO)
    try:
        validate_belong_to_uniqueness(existing, new_edge)
        results.append(("唯一归属公理-重复归属应报错", False))
    except AxiomViolation:
        results.append(("唯一归属公理-重复归属应报错", True))

    # 5. 基数约束：Patient --has_visit--> VisitRecord，target 是 VisitRecord
    existing_visits = [TBoxEdge("p1", "v1", RelType.HAS_VISIT)]
    new_visit = TBoxEdge("p2", "v1", RelType.HAS_VISIT)
    try:
        validate_visit_cardinality(existing_visits, new_visit)
        results.append(("基数约束-同一VisitRecord多患者应报错", False))
    except AxiomViolation:
        results.append(("基数约束-同一VisitRecord多患者应报错", True))

    # 6. 身份互斥
    try:
        validate_identity_mutex("u1", "u1")
        results.append(("身份互斥-同一ID应报错", False))
    except AxiomViolation:
        results.append(("身份互斥-同一ID应报错", True))

    return results


def test_abox_build():
    """测试 ABox 从 Store 构建对象图。"""
    from app.storage import store
    from app.graph.abox import get_ograph, reset_ograph

    og = reset_ograph()
    og.build_from_store(store)
    stats = og.get_stats()

    results = []
    results.append(("节点数 > 0", stats["node_count"] > 0, f"node_count={stats['node_count']}"))
    results.append(("边数 > 0", stats["edge_count"] > 0, f"edge_count={stats['edge_count']}"))

    # 检查节点类型分布
    dist = stats.get("node_type_distribution", {})
    results.append(("Patient 节点存在", "Patient" in dist, f"Patient={dist.get('Patient', 0)}"))
    results.append(("Doctor 节点存在", "Doctor" in dist, f"Doctor={dist.get('Doctor', 0)}"))
    results.append(("Department 节点存在", "Department" in dist, f"Department={dist.get('Department', 0)}"))
    results.append(("Room 节点存在", "Room" in dist, f"Room={dist.get('Room', 0)}"))
    results.append(("VisitRecord 节点存在", "VisitRecord" in dist, f"VisitRecord={dist.get('VisitRecord', 0)}"))
    results.append(("ExamReport 节点存在", "ExamReport" in dist, f"ExamReport={dist.get('ExamReport', 0)}"))

    # 检查关系类型分布
    rel_dist = stats.get("rel_type_distribution", {})
    results.append(("has_visit 边存在", "has_visit" in rel_dist, f"has_visit={rel_dist.get('has_visit', 0)}"))
    results.append(("belong_to 边存在", "belong_to" in rel_dist, f"belong_to={rel_dist.get('belong_to', 0)}"))

    # 节点总数应 >= 20+
    total_entities = sum(dist.values())
    results.append(("实体总数 >= 20", total_entities >= 20, f"total={total_entities}"))

    return results


def test_temporal_queries():
    """测试三类时态图查询。"""
    from app.storage import store
    from app.graph.temporal_query import (
        patient_full_chain,
        visit_context_isolation,
        doctor_on_duty,
    )

    results = []

    # 1. 患者全链路查询
    try:
        chain = patient_full_chain("p003", store=store)
        results.append(("患者全链路-p003有数据", len(chain.get("visits", [])) > 0 or len(chain.get("reports", [])) > 0,
                       f"visits={len(chain.get('visits', []))}, reports={len(chain.get('reports', []))}"))
        results.append(("患者全链路-包含患者信息", chain.get("patient", {}).get("patient_id") == "p003",
                       f"patient_id={chain.get('patient', {}).get('patient_id')}"))
    except Exception as e:
        results.append(("患者全链路查询", False, str(e)))

    # 2. 就诊上下文隔离查询（从 p003 的 bookings 中取第一个 visit_id）
    p003 = store.get_patient("p003")
    if p003 and p003.get("bookings"):
        visit_id = p003["bookings"][0]["booking_id"]
        try:
            ctx = visit_context_isolation(visit_id, store=store)
            results.append(("就诊上下文隔离-有数据", len(ctx.get("visit", {})) > 0,
                           f"visit_id={ctx.get('visit', {}).get('visit_id', 'N/A')}"))
            results.append(("就诊上下文隔离-隔离提示存在", "isolation_note" in ctx,
                           ctx.get("isolation_note", "")))
        except Exception as e:
            results.append(("就诊上下文隔离查询", False, str(e)))
    else:
        results.append(("就诊上下文隔离查询-跳过（p003无bookings）", True))

    # 3. 医生当班查询（u_doc_02 陈伟 - 呼吸科）
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        duty = doctor_on_duty("u_doc_02", date=today, store=store)
        results.append(("医生当班-有数据", len(duty.get("visits", [])) > 0 or len(duty.get("patients_treated", [])) > 0,
                       f"visits={len(duty.get('visits', []))}, total_patients={duty.get('total_patients', 0)}"))
    except Exception as e:
        results.append(("医生当班查询", False, str(e)))

    # 4. 测试不同医生
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        duty = doctor_on_duty("u_doc_03", date=today, store=store)
        results.append(("医生当班-神经内科刘敏", duty.get("doctor", {}).get("doctor_name") == "刘敏",
                       f"doctor={duty.get('doctor', {}).get('doctor_name', 'N/A')}"))
    except Exception as e:
        results.append(("医生当班-神经内科", False, str(e)))

    return results


def run_all():
    """运行所有验证测试。"""
    print("=" * 60)
    print("OAG 底座验证脚本")
    print("=" * 60)

    all_results = []

    print("\n📋 测试 1: TBox 公理校验函数")
    r1 = test_tbox_axioms()
    for name, passed, *detail in r1:
        status = "✅" if passed else "❌"
        detail_str = f" ({detail[0]})" if detail and detail[0] else ""
        print(f"  {status} {name}{detail_str}")
    all_results.extend(r1)

    print("\n📋 测试 2: ABox 从 Store 构建对象图")
    r2 = test_abox_build()
    for name, passed, *detail in r2:
        status = "✅" if passed else "❌"
        detail_str = f" ({detail[0]})" if detail and detail[0] else ""
        print(f"  {status} {name}{detail_str}")
    all_results.extend(r2)

    print("\n📋 测试 3: 三类时态图查询")
    r3 = test_temporal_queries()
    for name, passed, *detail in r3:
        status = "✅" if passed else "❌"
        detail_str = f" ({detail[0]})" if detail and detail[0] else ""
        print(f"  {status} {name}{detail_str}")
    all_results.extend(r3)

    # 汇总
    passed = sum(1 for r in all_results if r[1])
    failed = sum(1 for r in all_results if not r[1])
    total = len(all_results)

    print("\n" + "=" * 60)
    print(f"📊 汇总: {passed}/{total} 通过, {failed}/{total} 失败")
    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
