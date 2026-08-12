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


def _seed_patient_users() -> None:
    """患者端登录用户（Mock 电子健康卡）。"""
    users = [
        {
            "patient_id": "p001",
            "patient_name": "张伟",
            "medical_card_number": "622202000001",
            "phone": "138****0001",
            "gender": "男",
            "age": 45,
        },
        {
            "patient_id": "p002",
            "patient_name": "李娜",
            "medical_card_number": "622202000002",
            "phone": "138****0002",
            "gender": "女",
            "age": 32,
        },
        # 扩展的 18 名患者用户（p003-p020）
        {"patient_id": "p003", "patient_name": "王建国", "medical_card_number": "622202000003", "phone": "138****0003", "gender": "男", "age": 68},
        {"patient_id": "p004", "patient_name": "刘芳", "medical_card_number": "622202000004", "phone": "138****0004", "gender": "女", "age": 35},
        {"patient_id": "p005", "patient_name": "陈明", "medical_card_number": "622202000005", "phone": "138****0005", "gender": "男", "age": 42},
        {"patient_id": "p006", "patient_name": "杨丽", "medical_card_number": "622202000006", "phone": "138****0006", "gender": "女", "age": 5},
        {"patient_id": "p007", "patient_name": "徐浩", "medical_card_number": "622202000007", "phone": "138****0007", "gender": "男", "age": 28},
        {"patient_id": "p008", "patient_name": "吴霞", "medical_card_number": "622202000008", "phone": "138****0008", "gender": "女", "age": 55},
        {"patient_id": "p009", "patient_name": "孙磊", "medical_card_number": "622202000009", "phone": "138****0009", "gender": "男", "age": 32},
        {"patient_id": "p010", "patient_name": "周梅", "medical_card_number": "622202000010", "phone": "138****0010", "gender": "女", "age": 72},
        {"patient_id": "p011", "patient_name": "黄强", "medical_card_number": "622202000011", "phone": "138****0011", "gender": "男", "age": 48},
        {"patient_id": "p012", "patient_name": "林静", "medical_card_number": "622202000012", "phone": "138****0012", "gender": "女", "age": 29},
        {"patient_id": "p013", "patient_name": "郑伟", "medical_card_number": "622202000013", "phone": "138****0013", "gender": "男", "age": 61},
        {"patient_id": "p014", "patient_name": "何娜", "medical_card_number": "622202000014", "phone": "138****0014", "gender": "女", "age": 38},
        {"patient_id": "p015", "patient_name": "马超", "medical_card_number": "622202000015", "phone": "138****0015", "gender": "男", "age": 52},
        {"patient_id": "p016", "patient_name": "朱琳", "medical_card_number": "622202000016", "phone": "138****0016", "gender": "女", "age": 24},
        {"patient_id": "p017", "patient_name": "胡斌", "medical_card_number": "622202000017", "phone": "138****0017", "gender": "男", "age": 66},
        {"patient_id": "p018", "patient_name": "高云", "medical_card_number": "622202000018", "phone": "138****0018", "gender": "女", "age": 41},
        {"patient_id": "p019", "patient_name": "林涛", "medical_card_number": "622202000019", "phone": "138****0019", "gender": "男", "age": 37},
        {"patient_id": "p020", "patient_name": "冯雪", "medical_card_number": "622202000020", "phone": "138****0020", "gender": "女", "age": 58},
        # —— 测试专用患者：白纸身份，无任何历史就诊 ——
        {"patient_id": "p021", "patient_name": "测试用户", "medical_card_number": "622202000021", "phone": "138****0021", "gender": "男", "age": 30},
    ]
    for u in users:
        store.add_patient_user(u)


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

    # ---------- 测试患者 p021：白纸身份，无历史就诊 ----------
    p021_state = {
        "patient_id": "p021",
        "patient_name": "测试用户",
        "gender": "男",
        "age": 30,
        "attending_doctor_ids": [],
        "mdt_invitations": [],
        "emr_main": {
            "content": "",
            "locked": False,
            "locked_at": None,
            "locked_by": None,
            "locked_by_name": None,
            "reports": [],
        },
        "treatment_versions": [],
        "mdt_comments": [],
        "check_tasks": [],
        "bookings": [],
        "orders": [],
        "visit_timeline": [],
        "triage_sessions": [],
        "nurse_requests": [],
        "enable_emr_subagent": False,
        "enable_lab_subagent": False,
        "audit_log": [],
        "notify_queue": [],
        "ai_draft": None,
        "status": "waiting",
        "hitl_pending": False,
    }
    store.upsert_patient(p021_state)  # type: ignore[arg-type]
    store.append_audit("p021", "seed", {"user_id": "system", "name": "系统"}, "初始化测试患者 p021（白纸身份）")


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
        # —— 血液检验 (blood) ——
        ("CBC", "血常规", "blood", "EDTA抗凝血2ml", "WBC 4-10×10^9/L，HGB 男120-160 g/L 女110-150 g/L"),
        ("LFT", "肝功能", "blood", "空腹抽血3ml", "ALT 0-40 U/L，AST 0-40 U/L，TBIL 5-21 μmol/L"),
        ("UA", "尿常规", "blood", "晨尿10ml", "蛋白(-)，潜血(-)，糖(-)，酮体(-)"),
        ("BUN-Cr", "肾功能", "blood", "空腹抽血3ml", "BUN 3.9-7.1 mmol/L，Cr 男57-111 女41-81 μmol/L"),
        ("ELECT", "电解质", "blood", "血清2ml", "K+ 3.5-5.3 mmol/L，Na+ 137-147 mmol/L，Ca2+ 2.11-2.52 mmol/L"),
        ("COAG", "凝血功能", "blood", "枸橼酸钠抗凝血2ml", "PT 11-14s，APTT 30-45s，FIB 2-4 g/L"),
        ("GLU", "空腹血糖", "blood", "空腹抽血2ml", "3.9-6.1 mmol/L"),
        ("LIPID", "血脂四项", "blood", "空腹抽血3ml", "TC <5.2 mmol/L，TG <1.7 mmol/L，LDL-C <3.4 mmol/L"),
        ("CARDIAC", "心肌酶谱", "blood", "血清3ml", "CK-MB 0-25 U/L，cTnI 0-0.04 ng/ml"),
        # —— CT影像 (ct) ——
        ("CT-ABD", "腹部CT", "ct", "禁食4小时，增强需造影剂", "无标准值，描述性报告"),
        ("CT-CHEST", "胸部CT", "ct", "去除金属物品，仰卧位", "无标准值，描述性报告"),
        ("CT-HEAD", "头颅CT", "ct", "去除金属物品，仰卧位", "无标准值，描述性报告"),
        # —— 超声 (ultrasound) ——
        ("ABD-US", "腹部B超", "ultrasound", "空腹8小时，仰卧位", "无标准值，描述性报告"),
        ("ECHO", "心脏B超", "ultrasound", "静卧5分钟，左侧卧位", "EF 55-70%，FS 25-35%"),
        ("THYROID-US", "甲状腺B超", "ultrasound", "去除颈部饰物，仰卧位", "无标准值，描述性报告"),
        ("RENAL-US", "泌尿系B超", "ultrasound", "憋尿充盈膀胱", "无标准值，描述性报告"),
        # —— 病理 (pathology) ——
        ("BIOPSY", "活检病理", "pathology", "病变部位取材，福尔马林固定", "病理诊断：良性/恶性/交界性"),
        ("FROZEN", "术中冰冻", "pathology", "新鲜组织，OCT包埋", "术中快速病理诊断，术后石蜡病理确诊"),
        ("CYTOLOGY", "细胞学检查", "pathology", "脱落细胞/穿刺液制片", "未见癌细胞/查见异型细胞/恶性肿瘤细胞"),
        # —— 其他 (other) ——
        ("EGD", "胃镜", "other", "禁食8小时，禁水2小时", "无标准值，描述性报告"),
        ("COLONOSCOPY", "肠镜", "other", "肠道准备（清肠），禁食8小时", "无标准值，描述性报告"),
        ("ECG", "心电图", "other", "静卧5分钟", "窦性心律，心率 60-100 bpm"),
        ("HOLTER", "动态心电图", "other", "佩戴24小时，记录日常活动", "24小时总心率 8-12万次，无明显异常节律"),
        ("CXR", "胸部X线", "other", "去除金属物品，站立位拍片", "双肺纹理清晰，心影不大"),
        ("MRI-HEAD", "头颅MRI", "other", "去除金属物品，仰卧位", "无标准值，描述性报告"),
        ("PFT", "肺功能", "other", "坐位，夹鼻嘴用力呼气", "FEV1 占预计值 ≥80%，FVC 正常"),
        ("BMD", "骨密度", "other", "去除金属物品，仰卧位", "T值 ≥-1.0 SD 正常"),
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
    _seed_patient_users()
    _seed_patients()
    _seed_oag_extended()
    # 构建 OAG 内存对象图
    try:
        from app.graph.abox import get_ograph
        og = get_ograph()
        og.build_from_store(store)
    except Exception as _e:
        # OAG 构建失败不影响主流程
        import sys
        print(f"[OAG] 图谱构建警告: {_e}", file=sys.stderr)


def _seed_oag_extended() -> None:
    """扩展 Mock 数据：20+ 患者就诊链路（多科室/多报告/不同时段/不同当班医生）。

    本函数在 _seed_patients() 之后调用，补充以下数据：
    1. 扩展多科室（呼吸科、神经内科、骨科、儿科、眼科等）
    2. 扩展医生（不同科室的当班医生）
    3. 18 名新患者 + 20+ 就诊记录 + 对应报告/医嘱
    4. 不同就诊时段（今日/昨日/上周/近3个月）
    5. 跨渠道挂号（mini_app / kiosk / window）
    """
    from datetime import datetime, timedelta

    # 1. 扩展科室
    extra_depts = ["呼吸科", "神经内科", "骨科", "儿科", "眼科", "耳鼻喉科", "皮肤科", "精神心理科"]
    for name in extra_depts:
        store.add_department(name)

    # 2. 扩展医生（与已有科室关联）
    extra_doctors = [
        {"user_id": "u_doc_02", "username": "chenwei", "password": "123456", "name": "陈伟", "role": "attending", "department": "呼吸科", "title": "副主任医师"},
        {"user_id": "u_doc_03", "username": "liuming", "password": "123456", "name": "刘敏", "role": "attending", "department": "神经内科", "title": "主治医师"},
        {"user_id": "u_doc_04", "username": "wangqiang", "password": "123456", "name": "王强", "role": "attending", "department": "骨科", "title": "副主任医师"},
        {"user_id": "u_doc_05", "username": "zhaorui", "password": "123456", "name": "赵蕊", "role": "attending", "department": "儿科", "title": "主治医师"},
        {"user_id": "u_doc_06", "username": "sunyang", "password": "123456", "name": "孙洋", "role": "attending", "department": "眼科", "title": "主治医师"},
        {"user_id": "u_doc_07", "username": "zhouming", "password": "123456", "name": "周明", "role": "attending", "department": "皮肤科", "title": "主治医师"},
        {"user_id": "u_doc_08", "username": "wugang", "password": "123456", "name": "吴刚", "role": "attending", "department": "心内科", "title": "副主任医师"},
    ]
    for doc in extra_doctors:
        store.add_user({**doc, "active": True, "avatar": ""})

    # 3. 扩展楼宇/房间
    b4 = store.add_building("门诊楼B座")
    f_b1 = store.add_floor(b4["building_id"], "1层")
    store.bind_room(b4["building_id"], f_b1["floor_id"], "101诊室", "呼吸科")
    store.bind_room(b4["building_id"], f_b1["floor_id"], "102诊室", "神经内科")
    store.bind_room(b4["building_id"], f_b1["floor_id"], "103诊室", "骨科")
    store.bind_room(b4["building_id"], f_b1["floor_id"], "104诊室", "儿科")
    f_b2 = store.add_floor(b4["building_id"], "2层")
    store.bind_room(b4["building_id"], f_b2["floor_id"], "201诊室", "眼科")
    store.bind_room(b4["building_id"], f_b2["floor_id"], "202诊室", "耳鼻喉科")
    store.bind_room(b4["building_id"], f_b2["floor_id"], "203诊室", "皮肤科")
    store.bind_room(b4["building_id"], f_b2["floor_id"], "204诊室", "精神心理科")

    b5 = store.add_building("医技楼B座")
    f_c1 = store.add_floor(b5["building_id"], "1层")
    store.bind_room(b5["building_id"], f_c1["floor_id"], "DR室", "影像科")
    store.bind_room(b5["building_id"], f_c1["floor_id"], "核磁室", "影像科")
    store.bind_room(b5["building_id"], f_c1["floor_id"], "脑电图室", "神经内科")

    # 4. 生成 18 名患者的就诊链路
    _generate_extended_patients()


def _generate_extended_patients() -> None:
    """生成 18 名患者 + 20+ 就诊链路。"""
    from datetime import datetime, timedelta

    today = datetime.now()
    patients_data = [
        # (patient_id, name, gender, age, dept, doctor_id, status, channel, days_ago)
        ("p003", "王建国", "男", 68, "呼吸科", "u_doc_02", "in_progress", "mini_app", 0),    # 今日正在就诊
        ("p003", "王建国", "男", 68, "呼吸科", "u_doc_02", "completed", "mini_app", -30),     # 30天前历史
        ("p004", "刘芳", "女", 35, "神经内科", "u_doc_03", "waiting", "kiosk", 0),             # 今日候诊中
        ("p005", "陈明", "男", 42, "骨科", "u_doc_04", "upcoming", "window", 1),               # 明日待就诊
        ("p005", "陈明", "男", 42, "骨科", "u_doc_04", "completed", "mini_app", -60),          # 60天前历史
        ("p006", "杨丽", "女", 5, "儿科", "u_doc_05", "in_progress", "kiosk", 0),             # 今日正在就诊
        ("p007", "徐浩", "男", 28, "眼科", "u_doc_06", "completed", "mini_app", -7),           # 7天前完成
        ("p007", "徐浩", "男", 28, "眼科", "u_doc_06", "upcoming", "mini_app", 2),             # 后天复诊
        ("p008", "吴霞", "女", 55, "皮肤科", "u_doc_07", "waiting", "window", 0),              # 今日候诊
        ("p009", "孙磊", "男", 32, "心内科", "u_doc_08", "in_progress", "mini_app", 0),        # 今日正在就诊
        ("p009", "孙磊", "男", 32, "心内科", "u_doc_08", "completed", "kiosk", -90),          # 90天前历史
        ("p010", "周梅", "女", 72, "消化内科", "u_att_01", "completed", "mini_app", -14),      # 14天前
        ("p011", "黄强", "男", 48, "呼吸科", "u_doc_02", "completed", "window", -21),          # 21天前
        ("p012", "林静", "女", 29, "神经内科", "u_doc_03", "upcoming", "mini_app", 3),         # 3天后
        ("p013", "郑伟", "男", 61, "骨科", "u_doc_04", "completed", "kiosk", -45),            # 45天前
        ("p014", "何娜", "女", 38, "儿科", "u_doc_05", "completed", "mini_app", -10),         # 10天前
        ("p015", "马超", "男", 52, "眼科", "u_doc_06", "upcoming", "window", 1),              # 明日
        ("p016", "朱琳", "女", 24, "皮肤科", "u_doc_07", "in_progress", "mini_app", 0),       # 今日
        ("p017", "胡斌", "男", 66, "心内科", "u_doc_08", "waiting", "kiosk", 0),              # 今日
        ("p018", "高云", "女", 41, "消化内科", "u_att_01", "upcoming", "mini_app", 2),        # 后天
        ("p019", "林涛", "男", 37, "神经内科", "u_doc_03", "completed", "window", -15),       # 15天前
        ("p020", "冯雪", "女", 58, "呼吸科", "u_doc_02", "upcoming", "kiosk", 1),             # 明日
    ]

    # 房间映射（从 store 动态查找）
    room_map = {}
    for bld in store.buildings.values():
        for floor in bld.get("floors", []):
            for room in floor.get("rooms", []):
                r_dept = room.get("dept_name", "")
                r_name = room.get("name", "")
                b_name = bld.get("name", "")
                f_name = floor.get("name", "")
                if r_dept not in room_map:
                    room_map[r_dept] = []
                room_map[r_dept].append({
                    "building_name": b_name,
                    "floor_name": f_name,
                    "room_name": r_name,
                })

    seen_patients = {}
    for pid, pname, gender, age, dept, doctor_id, status, channel, days_offset in patients_data:
        slot_date = (today + timedelta(days=days_offset)).strftime("%Y-%m-%d")
        start_time = f"{slot_date}T09:00:00+08:00" if days_offset <= 0 else f"{slot_date}T14:00:00+08:00"
        end_time = f"{slot_date}T10:00:00+08:00" if days_offset <= 0 else f"{slot_date}T15:00:00+08:00"

        # 查找房间
        rooms = room_map.get(dept, [])
        room = rooms[0] if rooms else {"building_name": "门诊楼", "floor_name": "1层", "room_name": "101诊室"}

        # 挂号记录
        booking_id = uid("bk")
        booking = {
            "booking_id": booking_id,
            "patient_id": pid,
            "patient_name": pname,
            "department": dept,
            "doctor_id": doctor_id,
            "doctor_name": "",
            "slot_date": slot_date,
            "slot_time": "09:00-10:00",
            "start_time": start_time,
            "end_time": end_time if status == "completed" else None,
            "queue_number": 1 + abs(days_offset),
            "estimated_wait": 15 * (1 + abs(days_offset)),
            "building_name": room["building_name"],
            "floor_name": room["floor_name"],
            "room_name": room["room_name"],
            "channel": channel,
            "status": status,
            "created_at": start_time,
        }

        # 获取医生名
        doc = store.get_user(doctor_id)
        if doc:
            booking["doctor_name"] = doc.get("name", "")

        # 构造患者状态
        if pid not in seen_patients:
            seen_patients[pid] = {
                "patient_id": pid,
                "patient_name": pname,
                "gender": gender,
                "age": age,
                "attending_doctor_ids": [doctor_id],
                "mdt_invitations": [],
                "emr_main": {
                    "content": f"患者{pname}，{gender}，{age}岁，因{dept}相关症状就诊。",
                    "locked": False,
                    "locked_at": None,
                    "locked_by": None,
                    "locked_by_name": None,
                    "reports": [],
                },
                "treatment_versions": [],
                "mdt_comments": [],
                "check_tasks": [],
                "bookings": [],
                "orders": [],
                "visit_timeline": [],
                "triage_sessions": [],
                "nurse_requests": [],
                "enable_emr_subagent": False,
                "enable_lab_subagent": False,
                "audit_log": [],
                "notify_queue": [],
                "ai_draft": None,
                "status": status,
                "hitl_pending": False,
            }

        state = seen_patients[pid]
        state["bookings"].append(booking)

        # 生成报告（对已完成的就诊）
        if status == "completed":
            report_id = uid("rpt")
            report = {
                "report_id": report_id,
                "patient_id": pid,
                "visit_id": booking_id,
                "report_type": "综合报告",
                "content": f"【{dept}】{pname}的诊疗报告：病情稳定，建议定期复查。",
                "report_time": end_time,
                "status": "finalized",
            }
            if isinstance(state["emr_main"], dict):
                state["emr_main"]["reports"].append(report)

            # 添加检查任务
            state["check_tasks"].append({
                "task_id": uid("tsk"),
                "task_type": "blood",
                "task_label": "血常规",
                "status": "done",
                "created_at": start_time,
                "created_by": doctor_id,
                "created_by_name": doc.get("name", "") if doc else "",
                "completed_at": end_time,
                "result": {"summary": "各项指标基本正常"},
                "visit_id": booking_id,
            })

    # 批量写入
    for pid, state in seen_patients.items():
        store.upsert_patient(state)
        store.append_audit(pid, "seed", {"user_id": "system", "name": "系统"}, f"扩展患者 {pid} 就诊链路")


# 导入即播种
seed_all(store)
