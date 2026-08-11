"""Mock 种子数据：演示账号 + 患者初始 State。

演示账号（面试官可切换体验）：
- 主治医生：attending / 123456
- MDT 专家：mdtexpert / 123456
- 护士：     nurse / 123456
- 历史只读医生：readonly / 123456
"""
from __future__ import annotations

from app.storage import Store, now, store, uid


def _seed_users() -> None:
    """4 个演示角色（Demo 不做密码哈希，明文占位）。"""
    users = [
        {
            "user_id": "u_att_01",
            "username": "attending",
            "password": "123456",
            "name": "张明",
            "role": "attending",          # 主治医生
            "department": "消化内科",
            "title": "主治医师",
            "active": True,
        },
        {
            "user_id": "u_mdt_01",
            "username": "mdtexpert",
            "password": "123456",
            "name": "李华",
            "role": "mdt_expert",         # MDT 会诊专家
            "department": "心内科",
            "title": "主任医师",
            "active": True,
        },
        {
            "user_id": "u_nurse_01",
            "username": "nurse",
            "password": "123456",
            "name": "王芳",
            "role": "nurse",              # 护士
            "department": "消化内科",
            "title": "主管护师",
            "active": True,
        },
        {
            "user_id": "u_ro_01",
            "username": "readonly",
            "password": "123456",
            "name": "陈强",
            "role": "readonly",           # 历史只读医生（急诊旧接诊）
            "department": "急诊科",
            "title": "主治医师",
            "active": True,
        },
        {
            "user_id": "u_admin_01",
            "username": "admin",
            "password": "123456",
            "name": "系统管理员",
            "role": "admin",              # 后台管理员
            "department": "信息科",
            "title": "管理员",
            "active": True,
        },
    ]
    for u in users:
        store.add_user(u)


def _seed_departments() -> None:
    """初始科室。"""
    for name in ["消化内科", "心内科", "急诊科", "信息科", "检验科", "影像科"]:
        store.add_department(name)


def _seed_kb() -> None:
    """Mock 知识库：4 类初始条目，供后台管理与病历 SubAgent 引用。"""
    # 1. 临床指南/诊疗常规
    store.add_kb(
        category="guide",
        title="急性胃炎诊疗常规",
        content=(
            "急性胃炎多因饮食不当、应激、NSAIDs 等引起。\n"
            "诊断要点：上腹痛、恶心、上腹压痛；结合胃镜可确诊。\n"
            "治疗原则：抑酸（PPI）、保护胃黏膜、对症解痉；清淡饮食；"
            "若伴出血按上消化道出血处理。\n"
            "随访：3-7 日复诊评估疗效。"
        ),
        tags=["胃炎", "消化内科", "上腹痛"],
    )
    store.add_kb(
        category="guide",
        title="胆囊炎鉴别诊断要点",
        content=(
            "胆囊炎典型表现：右上腹痛、Murphy 征阳性、发热。\n"
            "需与急性胃炎、胰腺炎、消化性溃疡鉴别。\n"
            "辅助检查：腹部 B 超（首选）、肝胆酶谱、血常规。\n"
            "处理：抗感染、解痉；重症或化脓性需外科会诊。"
        ),
        tags=["胆囊炎", "鉴别诊断", "B超"],
    )
    # 2. SOAP 病历模板
    store.add_kb(
        category="soap_template",
        title="消化内科初诊 SOAP 模板",
        content=(
            "S（主观）：主诉 + 现病史 + 既往史。\n"
            "O（客观）：生命体征 + 阳性查体 + 辅助检查结果。\n"
            "A（评估）：初步诊断 + 鉴别诊断 + 风险评估。\n"
            "P（计划）：进一步检查 + 治疗方案 + 健康宣教 + 随访计划。"
        ),
        tags=["SOAP", "模板", "初诊"],
    )
    # 3. 药品/检查项字典
    store.add_kb(
        category="drug_dict",
        title="常用抑酸与解痉药品字典",
        content=(
            "奥美拉唑 40mg ivgtt qd（PPI，抑酸）。\n"
            "雷尼替丁 150mg bid（H2 受体阻滞剂）。\n"
            "山莨菪碱 10mg im prn（解痉止痛）。\n"
            "铝碳酸镁 1.0g tid po（胃黏膜保护）。\n"
            "注意：解痉药禁用于青光眼、前列腺增生。"
        ),
        tags=["药品", "PPI", "解痉"],
    )
    store.add_kb(
        category="drug_dict",
        title="常用检查项与参考值",
        content=(
            "血常规：WBC 4-10×10^9/L，中性粒细胞比例 50-70%。\n"
            "腹部 B 超：评估肝胆胰脾，胆囊壁毛糙提示胆囊炎。\n"
            "腹部 CT：用于急腹症鉴别，如胰腺炎、穿孔。\n"
            "肝胆酶谱：ALT/AST/BIL 升高提示肝胆疾病。"
        ),
        tags=["检查", "参考值", "血常规", "B超"],
    )
    # 4. MDT 会诊模板
    store.add_kb(
        category="mdt_template",
        title="MDT 会诊意见标准结构",
        content=(
            "会诊意见建议按以下结构提交：\n"
            "1. 影像/检验解读：结合本次结果给出判断；\n"
            "2. 鉴别诊断补充：列出需排除的诊断；\n"
            "3. 进一步检查建议：明确下一步检查项；\n"
            "4. 治疗调整建议：药物/介入/外科倾向。\n"
            "提交后冻结留痕，供主治采纳。"
        ),
        tags=["MDT", "会诊", "模板"],
    )


def _seed_patients() -> None:
    """2 名患者：p001 有完整历史版本/MDT/检查任务；p002 较简。"""

    # ---------- 患者 p001 ----------
    p001_state = {
        "patient_id": "p001",
        "patient_name": "张伟",
        "attending_doctor_ids": ["u_att_01"],
        "mdt_invitations": [
            {
                "invitation_id": uid("inv"),
                "expert_id": "u_mdt_01",
                "expert_name": "李华",
                "invited_at": now(),
                "expires_at": "2099-12-31T23:59:59+08:00",  # Demo 长效
                "active": True,
            }
        ],
        "emr_main": {
            "content": "患者张伟，男，45岁，因上腹痛就诊。初步诊断：急性胃炎。予抑酸对症治疗，建议随诊。",
            "locked": True,
            "locked_at": now(),
            "locked_by": "u_att_01",
            "locked_by_name": "张明",
        },
        "treatment_versions": [
            {
                "version_id": uid("ver"),
                "version_no": 2,
                "content": "【v2 诊疗方案】调整：加用解痉药；完善腹部 B 超；3 日后复诊评估。",
                "created_at": now(),
                "created_by": "u_att_01",
                "created_by_name": "张明",
            },
            {
                "version_id": uid("ver"),
                "version_no": 1,
                "content": "【v1 诊疗方案】急性胃炎：抑酸 + 对症，清淡饮食。",
                "created_at": now(),
                "created_by": "u_att_01",
                "created_by_name": "张明",
            },
        ],
        "mdt_comments": [
            {
                "comment_id": uid("cmt"),
                "author_id": "u_mdt_01",
                "author_name": "李华",
                "author_role": "mdt_expert",
                "content": "建议排除胆囊疾病，完善腹部 B 超及肝胆酶谱。",
                "created_at": now(),
                "is_adopted": True,
                "adopted_by": "u_att_01",
                "adopted_by_name": "张明",
                "adopted_at": now(),
            },
            {
                "comment_id": uid("cmt"),
                "author_id": "u_mdt_01",
                "author_name": "李华",
                "author_role": "mdt_expert",
                "content": "若 B 超阴性，可考虑胃镜进一步评估。",
                "created_at": now(),
                "is_adopted": False,
                "adopted_by": None,
                "adopted_by_name": None,
                "adopted_at": None,
            },
        ],
        "check_tasks": [
            {
                "task_id": uid("task"),
                "task_type": "blood",
                "task_label": "血常规",
                "status": "done",
                "created_at": now(),
                "created_by": "u_att_01",
                "created_by_name": "张明",
                "completed_at": now(),
                "result": {"summary": "WBC 8.2，中性粒细胞比例 72%，基本正常。"},
            },
            {
                "task_id": uid("task"),
                "task_type": "ultrasound",
                "task_label": "腹部B超",
                "status": "pending",
                "created_at": now(),
                "created_by": "u_att_01",
                "created_by_name": "张明",
                "completed_at": None,
                "result": None,
            },
        ],
        "enable_emr_subagent": bool(store.get_subagent_config()["enable_emr_subagent"]),
        "enable_lab_subagent": bool(store.get_subagent_config()["enable_lab_subagent"]),
        "audit_log": [],
        "notify_queue": [],
        "ai_draft": None,
        "status": "in_progress",
        "hitl_pending": False,
    }
    store.upsert_patient(p001_state)  # type: ignore[arg-type]
    store.append_audit("p001", "seed", {"user_id": "system", "name": "系统"}, "初始化患者 p001 演示数据")

    # ---------- 患者 p002 ----------
    p002_state = {
        "patient_id": "p002",
        "patient_name": "李娜",
        "attending_doctor_ids": ["u_att_01"],
        "mdt_invitations": [],
        "emr_main": {
            "content": "",
            "locked": False,
            "locked_at": None,
            "locked_by": None,
            "locked_by_name": None,
        },
        "treatment_versions": [
            {
                "version_id": uid("ver"),
                "version_no": 1,
                "content": "【v1 诊疗方案】待接诊评估。",
                "created_at": now(),
                "created_by": "u_att_01",
                "created_by_name": "张明",
            }
        ],
        "mdt_comments": [],
        "check_tasks": [],
        "enable_emr_subagent": bool(store.get_subagent_config()["enable_emr_subagent"]),
        "enable_lab_subagent": bool(store.get_subagent_config()["enable_lab_subagent"]),
        "audit_log": [],
        "notify_queue": [],
        "ai_draft": None,
        "status": "waiting",
        "hitl_pending": False,
    }
    store.upsert_patient(p002_state)  # type: ignore[arg-type]
    store.append_audit("p002", "seed", {"user_id": "system", "name": "系统"}, "初始化患者 p002 演示数据")


def _seed_buildings() -> None:
    """楼宇/楼层/房间种子数据。"""
    b1 = store.add_building("门诊楼")
    f1 = store.add_floor(b1["building_id"], "1层")
    store.bind_room(b1["building_id"], f1["floor_id"], "101诊室", "消化内科")
    store.bind_room(b1["building_id"], f1["floor_id"], "102诊室", "心内科")
    f2 = store.add_floor(b1["building_id"], "2层")
    store.bind_room(b1["building_id"], f2["floor_id"], "201诊室", "消化内科")
    store.bind_room(b1["building_id"], f2["floor_id"], "202内镜室", "消化内科")

    b2 = store.add_building("住院楼")
    f3 = store.add_floor(b2["building_id"], "3层")
    store.bind_room(b2["building_id"], f3["floor_id"], "301病房", "消化内科")
    store.bind_room(b2["building_id"], f3["floor_id"], "302病房", "心内科")

    b3 = store.add_building("医技楼")
    f4 = store.add_floor(b3["building_id"], "1层")
    store.bind_room(b3["building_id"], f4["floor_id"], "检验科", "检验科")
    store.bind_room(b3["building_id"], f4["floor_id"], "B超室", "影像科")
    f5 = store.add_floor(b3["building_id"], "2层")
    store.bind_room(b3["building_id"], f5["floor_id"], "CT室", "影像科")


def _seed_exam_items() -> None:
    """检验/检查项目字典种子数据。"""
    items = [
        ("CBC", "血常规", "blood", "EDTA抗凝血2ml", "WBC 4-10×10^9/L"),
        ("LFT", "肝功能", "blood", "空腹抽血3ml", "ALT 0-40 U/L"),
        ("ABD-US", "腹部B超", "ultrasound", "空腹，仰卧位", "无标准值，描述性报告"),
        ("CT-ABD", "腹部CT", "ct", "禁食4小时，增强需造影剂", "无标准值，描述性报告"),
        ("EGD", "胃镜", "other", "禁食8小时", "无标准值，描述性报告"),
        ("ECG", "心电图", "other", "静卧5分钟", "无标准值，描述性报告"),
    ]
    for code, name, cat, spec, ref in items:
        store.add_exam_item(code=code, name=name, category=cat, spec=spec, ref_range=ref)


def _seed_rag_docs() -> None:
    """RAG 文档库种子数据（含 Mock 分块）。"""
    docs = [
        ("急性胃炎诊疗规范v2", "clinical_guide",
         "急性胃炎多因饮食不当、应激、NSAIDs 等引起。\n"
         "诊断要点：上腹痛、恶心、上腹压痛；结合胃镜可确诊。\n"
         "治疗原则：抑酸（PPI）、保护胃黏膜、对症解痉；清淡饮食。\n"
         "若伴出血按上消化道出血处理。\n随访：3-7 日复诊评估疗效。"),
        ("消化内科初诊SOAP模板", "soap_template",
         "S（主观）：主诉 + 现病史 + 既往史。\n"
         "O（客观）：生命体征 + 阳性查体 + 辅助检查结果。\n"
         "A（评估）：初步诊断 + 鉴别诊断 + 风险评估。\n"
         "P（计划）：进一步检查 + 治疗方案 + 健康宣教 + 随访计划。"),
        ("MDT会诊意见标准结构", "mdt_template",
         "会诊意见建议按以下结构提交：\n"
         "1. 影像/检验解读：结合本次结果给出判断；\n"
         "2. 鉴别诊断补充：列出需排除的诊断；\n"
         "3. 进一步检查建议：明确下一步检查项；\n"
         "4. 治疗调整建议：药物/介入/外科倾向。\n"
         "提交后冻结留痕，供主治采纳。"),
    ]
    for title, cat, content in docs:
        doc = store.add_rag_doc(title=title, category=cat, content=content,
                                uploaded_by="u_admin_01", uploaded_by_name="系统管理员")
        # 种子文档直接设为 active，方便召回测试
        store.set_rag_doc_status(doc["doc_id"], "active")


def seed_all(store: Store) -> None:
    _seed_users()
    _seed_departments()
    _seed_kb()
    _seed_buildings()
    _seed_exam_items()
    _seed_rag_docs()
    _seed_patients()


# 导入即播种
seed_all(store)
