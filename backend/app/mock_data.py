"""Mock 种子数据：演示账号 + 患者初始 State。

演示账号（面试官可切换体验）：
- 主治医生：attending / 123456
- MDT 专家：mdtexpert / 123456
- 护士：     nurse / 123456
- 历史只读医生：readonly / 123456
- 管理员：   admin / 123456
- 平台管理员：platform / 123456
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
            "dept_lead": True,            # 消化内科科室负责人（可管理本科室 prompt/schema）
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
        {
            "user_id": "u_padmin_01",
            "username": "platform",
            "password": "123456",
            "name": "平台管理员",
            "role": "platform_admin",     # 平台超级管理员（可管理医院管理员与全局配置）
            "department": "平台部",
            "title": "平台管理员",
            "active": True,
        },
        {
            "user_id": "u_lab_01",
            "username": "labtech",
            "password": "123456",
            "name": "林检验",
            "role": "lab_tech",           # 检验科技师
            "department": "检验科",
            "title": "主管检验技师",
            "active": True,
        },
        {
            "user_id": "u_img_01",
            "username": "imagingtech",
            "password": "123456",
            "name": "赵影像",
            "role": "imaging_tech",       # 影像科技师
            "department": "影像科",
            "title": "主管技师",
            "active": True,
        },
    ]
    for u in users:
        store.add_user(u)


def _seed_departments() -> None:
    """初始科室。"""
    for name in ["消化内科", "心内科", "急诊科", "信息科", "检验科", "影像科"]:
        store.add_department(name)


def _seed_kg_dept_aliases() -> None:
    """KG 54 科室 → 自建 14 业务科室 映射种子数据。

    设计原则：
    - KG 科室来源：disease-kb 数据源（语义层，用于疾病 BELONGS_TO）
    - 业务科室来源：mock_data._seed_departments + _seed_oag_extended（运营层，用于楼宇房间/医生/挂号）
    - 映射方向：KG 名 → 业务名（多对一）
    - 未配置映射的 KG 科室：get_business_dept_by_kg_name 兜底返回原 KG 名，不阻断业务
    """
    # 业务科室全集（mock_data 自建 + OAG 扩展 + 临床补建）
    BIZ = {
        "消化内科", "心内科", "急诊科", "信息科", "检验科", "影像科",
        "呼吸科", "神经内科", "骨科", "儿科", "眼科", "耳鼻喉科", "皮肤科", "精神心理科",
        "妇产科", "泌尿外科", "内分泌科", "肾内科", "肿瘤科", "中医科", "血液科",
    }
    # KG 54 科室 → 业务科室映射（基于实际疾病归属 + 同义对齐 + 临床正确归并）
    mapping = {
        # 完全同名 → 直接对齐
        "消化内科": "消化内科", "心内科": "心内科", "急诊科": "急诊科",
        "神经内科": "神经内科", "儿科": "儿科", "眼科": "眼科",
        "耳鼻喉科": "耳鼻喉科", "皮肤科": "皮肤科",
        # 同义不同名 → 对齐
        "呼吸内科": "呼吸科", "精神科": "精神心理科", "骨外科": "骨科",
        # 大科室归并（内科/外科等无对应自建，回退到最相近业务科室）
        "内科": "消化内科",            # 内科大类 → 默认消化内科（最常见）
        "外科": "骨科",                # 外科大类 → 默认骨科（外伤首诊）
        "普外科": "消化内科",          # 普外科（阑尾/疝/胃肠）→ 消化内科
        "心胸外科": "心内科",           # 心胸外科 → 心内科（术后随访归心内科）
        "神经外科": "神经内科",
        "泌尿外科": "泌尿外科",         # 临床正确：泌尿自有业务科室
        "泌尿内科": "肾内科",           # 泌尿内科（肾病）→ 肾内科
        "肝胆外科": "消化内科",         # 肝胆 → 消化（消化系统）
        "肿瘤外科": "肿瘤科",
        "肿瘤内科": "肿瘤科",
        "肿瘤科": "肿瘤科",
        "血液科": "血液科",             # 血液自有业务科室
        "内分泌科": "内分泌科",         # 内分泌自有业务科室（糖尿病首诊）
        "肾内科": "肾内科",             # 肾内自有业务科室
        "风湿免疫科": "骨科",           # 风湿 → 骨科（关节症状首诊）
        # 妇产/儿科细分
        "妇产科": "妇产科",             # 妇产自有业务科室
        "妇科": "妇产科",
        "产科": "妇产科",
        "儿科综合": "儿科",
        "小儿内科": "儿科",
        "小儿外科": "儿科",
        # 五官/口腔
        "五官科": "耳鼻喉科",           # 五官科 → 耳鼻喉（最常见主诉）
        "口腔科": "耳鼻喉科",           # 口腔 → 耳鼻喉（业务兜底）
        "皮肤性病科": "皮肤科",
        "性病科": "皮肤科",
        "整形美容科": "皮肤科",
        # 精神/心理细分
        "心理科": "精神心理科",
        # 其他运营/兜底
        "中医科": "中医科",             # 中医自有业务科室
        "中医综合": "中医科",
        "传染科": "急诊科",             # 传染首诊 → 急诊分诊
        "感染科": "急诊科",
        "烧伤科": "急诊科",
        "康复科": "骨科",               # 康复 → 骨科（术后康复最常见）
        "营养科": "消化内科",
        "遗传病科": "儿科",
        "肝病": "消化内科",             # 肝病 → 消化内科
        "肛肠科": "消化内科",
        "男科": "泌尿外科",             # 男科 → 泌尿外科
        "不孕不育": "妇产科",           # 不孕不育 → 妇产科
        "生殖健康": "妇产科",
        "减肥": "内分泌科",             # 减肥 → 内分泌（代谢）
        "其他科室": "急诊科",           # 其他 → 急诊分诊
        "其他综合": "急诊科",
    }
    for kg_name, biz_name in mapping.items():
        if biz_name in BIZ:
            store.add_kg_dept_alias(kg_name, biz_name, note="seed")
        else:
            # 配置错误兜底：业务名不在 BIZ 集合，回退到急诊科
            store.add_kg_dept_alias(kg_name, "急诊科", note="fallback_invalid_biz")


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
        "gender": "男",
        "age": 45,
        "phone": "138****0001",
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
                "result": {
                    "items": [
                        {"name": "白细胞计数", "value": "8.2", "unit": "10^9/L", "reference_range": "4-10", "abnormal": "normal"},
                        {"name": "红细胞计数", "value": "4.8", "unit": "10^12/L", "reference_range": "3.5-5.5", "abnormal": "normal"},
                        {"name": "血红蛋白", "value": "142", "unit": "g/L", "reference_range": "110-160", "abnormal": "normal"},
                        {"name": "血小板计数", "value": "220", "unit": "10^9/L", "reference_range": "100-300", "abnormal": "normal"},
                        {"name": "中性粒细胞百分比", "value": "72", "unit": "%", "reference_range": "40-75", "abnormal": "normal"},
                        {"name": "淋巴细胞百分比", "value": "28", "unit": "%", "reference_range": "20-50", "abnormal": "normal"},
                    ],
                    "summary": "各项指标基本正常",
                    "abnormal_count": 0,
                    "total_count": 6,
                    "entered_by": "u_lab_01",
                    "entered_by_name": "林检验",
                    "entered_at": now(),
                },
                "report": {
                    "report_no": f"LAB-{uid('blrpt')}",
                    "report_id": uid("blrpt"),
                    "patient_id": "p001",
                    "patient_name": "张伟",
                    "gender": "男",
                    "age": 45,
                    "department": "消化内科",
                    "attending_doctor_id": "u_att_01",
                    "attending_doctor_name": "张明",
                    "task_label": "血常规",
                    "task_id": "",
                    "created_by_name": "张明",
                    "specimen": "静脉血",
                    "draw_time": now(),
                    "completed_at": now(),
                    "issued_at": now(),
                    "entered_by": "u_lab_01",
                    "entered_by_name": "林检验",
                    "entered_at": now(),
                    "items": [
                        {"name": "白细胞计数", "value": "8.2", "unit": "10^9/L", "reference_range": "4-10", "abnormal": "normal"},
                        {"name": "红细胞计数", "value": "4.8", "unit": "10^12/L", "reference_range": "3.5-5.5", "abnormal": "normal"},
                        {"name": "血红蛋白", "value": "142", "unit": "g/L", "reference_range": "110-160", "abnormal": "normal"},
                        {"name": "血小板计数", "value": "220", "unit": "10^9/L", "reference_range": "100-300", "abnormal": "normal"},
                        {"name": "中性粒细胞百分比", "value": "72", "unit": "%", "reference_range": "40-75", "abnormal": "normal"},
                        {"name": "淋巴细胞百分比", "value": "28", "unit": "%", "reference_range": "20-50", "abnormal": "normal"},
                    ],
                    "summary": "各项指标基本正常",
                    "abnormal_count": 0,
                    "total_count": 6,
                    "status": "finalized",
                },
            },
            # —— 肝功能：已完成，ALT/AST 轻中度升高（匹配 KG 肝炎 SUGGESTED_TEST: 肝功能）——
            {
                "task_id": uid("task"),
                "task_type": "blood",
                "task_label": "肝功能",
                "status": "done",
                "created_at": now(),
                "created_by": "u_att_01",
                "created_by_name": "张明",
                "completed_at": now(),
                "result": {
                    "items": [
                        {"name": "谷丙转氨酶(ALT)", "value": "78", "unit": "U/L", "reference_range": "0-40", "abnormal": "high"},
                        {"name": "谷草转氨酶(AST)", "value": "65", "unit": "U/L", "reference_range": "0-40", "abnormal": "high"},
                        {"name": "总胆红素(TBIL)", "value": "18", "unit": "μmol/L", "reference_range": "5-21", "abnormal": "normal"},
                        {"name": "直接胆红素(DBIL)", "value": "6.2", "unit": "μmol/L", "reference_range": "0-7", "abnormal": "normal"},
                        {"name": "白蛋白(ALB)", "value": "45", "unit": "g/L", "reference_range": "35-55", "abnormal": "normal"},
                        {"name": "碱性磷酸酶(ALP)", "value": "128", "unit": "U/L", "reference_range": "40-150", "abnormal": "normal"},
                        {"name": "谷氨酰转肽酶(GGT)", "value": "92", "unit": "U/L", "reference_range": "0-60", "abnormal": "high"},
                    ],
                    "summary": "ALT、AST、GGT 升高，提示肝实质损伤",
                    "abnormal_count": 3,
                    "total_count": 7,
                    "entered_by": "u_lab_01",
                    "entered_by_name": "林检验",
                    "entered_at": now(),
                },
                "report": {
                    "report_no": f"LAB-{uid('blrpt')}",
                    "report_id": uid("blrpt"),
                    "patient_id": "p001",
                    "patient_name": "张伟",
                    "gender": "男",
                    "age": 45,
                    "department": "消化内科",
                    "attending_doctor_id": "u_att_01",
                    "attending_doctor_name": "张明",
                    "task_label": "肝功能",
                    "task_id": "",
                    "created_by_name": "张明",
                    "specimen": "空腹静脉血",
                    "draw_time": now(),
                    "completed_at": now(),
                    "issued_at": now(),
                    "entered_by": "u_lab_01",
                    "entered_by_name": "林检验",
                    "entered_at": now(),
                    "items": [
                        {"name": "谷丙转氨酶(ALT)", "value": "78", "unit": "U/L", "reference_range": "0-40", "abnormal": "high"},
                        {"name": "谷草转氨酶(AST)", "value": "65", "unit": "U/L", "reference_range": "0-40", "abnormal": "high"},
                        {"name": "总胆红素(TBIL)", "value": "18", "unit": "μmol/L", "reference_range": "5-21", "abnormal": "normal"},
                        {"name": "直接胆红素(DBIL)", "value": "6.2", "unit": "μmol/L", "reference_range": "0-7", "abnormal": "normal"},
                        {"name": "白蛋白(ALB)", "value": "45", "unit": "g/L", "reference_range": "35-55", "abnormal": "normal"},
                        {"name": "碱性磷酸酶(ALP)", "value": "128", "unit": "U/L", "reference_range": "40-150", "abnormal": "normal"},
                        {"name": "谷氨酰转肽酶(GGT)", "value": "92", "unit": "U/L", "reference_range": "0-60", "abnormal": "high"},
                    ],
                    "summary": "ALT、AST、GGT 升高，提示肝实质损伤",
                    "abnormal_count": 3,
                    "total_count": 7,
                    "status": "finalized",
                },
            },
            # —— 血脂四项：已完成，LDL-C 偏高 ——
            {
                "task_id": uid("task"),
                "task_type": "blood",
                "task_label": "血脂四项",
                "status": "done",
                "created_at": now(),
                "created_by": "u_att_01",
                "created_by_name": "张明",
                "completed_at": now(),
                "result": {
                    "items": [
                        {"name": "总胆固醇(TC)", "value": "5.8", "unit": "mmol/L", "reference_range": "<5.2", "abnormal": "high"},
                        {"name": "甘油三酯(TG)", "value": "1.9", "unit": "mmol/L", "reference_range": "<1.7", "abnormal": "high"},
                        {"name": "低密度脂蛋白(LDL-C)", "value": "3.8", "unit": "mmol/L", "reference_range": "<3.4", "abnormal": "high"},
                        {"name": "高密度脂蛋白(HDL-C)", "value": "1.1", "unit": "mmol/L", "reference_range": ">1.0", "abnormal": "normal"},
                    ],
                    "summary": "TC、TG、LDL-C 升高，混合型高脂血症",
                    "abnormal_count": 3,
                    "total_count": 4,
                    "entered_by": "u_lab_01",
                    "entered_by_name": "林检验",
                    "entered_at": now(),
                },
                "report": {
                    "report_no": f"LAB-{uid('blrpt')}",
                    "report_id": uid("blrpt"),
                    "patient_id": "p001",
                    "patient_name": "张伟",
                    "gender": "男",
                    "age": 45,
                    "department": "消化内科",
                    "attending_doctor_id": "u_att_01",
                    "attending_doctor_name": "张明",
                    "task_label": "血脂四项",
                    "task_id": "",
                    "created_by_name": "张明",
                    "specimen": "空腹静脉血",
                    "draw_time": now(),
                    "completed_at": now(),
                    "issued_at": now(),
                    "entered_by": "u_lab_01",
                    "entered_by_name": "林检验",
                    "entered_at": now(),
                    "items": [
                        {"name": "总胆固醇(TC)", "value": "5.8", "unit": "mmol/L", "reference_range": "<5.2", "abnormal": "high"},
                        {"name": "甘油三酯(TG)", "value": "1.9", "unit": "mmol/L", "reference_range": "<1.7", "abnormal": "high"},
                        {"name": "低密度脂蛋白(LDL-C)", "value": "3.8", "unit": "mmol/L", "reference_range": "<3.4", "abnormal": "high"},
                        {"name": "高密度脂蛋白(HDL-C)", "value": "1.1", "unit": "mmol/L", "reference_range": ">1.0", "abnormal": "normal"},
                    ],
                    "summary": "TC、TG、LDL-C 升高，混合型高脂血症",
                    "abnormal_count": 3,
                    "total_count": 4,
                    "status": "finalized",
                },
            },
            # —— 血淀粉酶：已完成，正常（排除胰腺炎）——
            {
                "task_id": uid("task"),
                "task_type": "blood",
                "task_label": "血淀粉酶",
                "status": "done",
                "created_at": now(),
                "created_by": "u_att_01",
                "created_by_name": "张明",
                "completed_at": now(),
                "result": {
                    "items": [
                        {"name": "淀粉酶(AMY)", "value": "85", "unit": "U/L", "reference_range": "30-110", "abnormal": "normal"},
                        {"name": "脂肪酶(LPS)", "value": "42", "unit": "U/L", "reference_range": "0-60", "abnormal": "normal"},
                    ],
                    "summary": "淀粉酶、脂肪酶正常，排除急性胰腺炎",
                    "abnormal_count": 0,
                    "total_count": 2,
                    "entered_by": "u_lab_01",
                    "entered_by_name": "林检验",
                    "entered_at": now(),
                },
                "report": {
                    "report_no": f"LAB-{uid('blrpt')}",
                    "report_id": uid("blrpt"),
                    "patient_id": "p001",
                    "patient_name": "张伟",
                    "gender": "男",
                    "age": 45,
                    "department": "消化内科",
                    "attending_doctor_id": "u_att_01",
                    "attending_doctor_name": "张明",
                    "task_label": "血淀粉酶",
                    "task_id": "",
                    "created_by_name": "张明",
                    "specimen": "空腹静脉血",
                    "draw_time": now(),
                    "completed_at": now(),
                    "issued_at": now(),
                    "entered_by": "u_lab_01",
                    "entered_by_name": "林检验",
                    "entered_at": now(),
                    "items": [
                        {"name": "淀粉酶(AMY)", "value": "85", "unit": "U/L", "reference_range": "30-110", "abnormal": "normal"},
                        {"name": "脂肪酶(LPS)", "value": "42", "unit": "U/L", "reference_range": "0-60", "abnormal": "normal"},
                    ],
                    "summary": "淀粉酶、脂肪酶正常，排除急性胰腺炎",
                    "abnormal_count": 0,
                    "total_count": 2,
                    "status": "finalized",
                },
            },
            # —— 腹部B超：待检 ——
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
        "gender": "女",
        "age": 32,
        "phone": "138****0002",
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
        "check_tasks": [
            # —— 血常规：已完成，WBC 轻度升高（匹配 KG 上呼吸道感染/感染 SUGGESTED_TEST: 血常规）——
            {
                "task_id": uid("task"),
                "task_type": "blood",
                "task_label": "血常规",
                "status": "done",
                "created_at": now(),
                "created_by": "u_att_01",
                "created_by_name": "张明",
                "completed_at": now(),
                "result": {
                    "items": [
                        {"name": "白细胞计数", "value": "11.5", "unit": "10^9/L", "reference_range": "4-10", "abnormal": "high"},
                        {"name": "红细胞计数", "value": "4.2", "unit": "10^12/L", "reference_range": "3.5-5.5", "abnormal": "normal"},
                        {"name": "血红蛋白", "value": "125", "unit": "g/L", "reference_range": "110-150", "abnormal": "normal"},
                        {"name": "血小板计数", "value": "180", "unit": "10^9/L", "reference_range": "100-300", "abnormal": "normal"},
                        {"name": "中性粒细胞百分比", "value": "78", "unit": "%", "reference_range": "40-75", "abnormal": "high"},
                        {"name": "淋巴细胞百分比", "value": "18", "unit": "%", "reference_range": "20-50", "abnormal": "low"},
                    ],
                    "summary": "WBC 及中性粒细胞升高，提示炎症/感染",
                    "abnormal_count": 3,
                    "total_count": 6,
                    "entered_by": "u_lab_01",
                    "entered_by_name": "林检验",
                    "entered_at": now(),
                },
                "report": {
                    "report_no": f"LAB-{uid('blrpt')}",
                    "report_id": uid("blrpt"),
                    "patient_id": "p002",
                    "patient_name": "李娜",
                    "gender": "女",
                    "age": 32,
                    "department": "消化内科",
                    "attending_doctor_id": "u_att_01",
                    "attending_doctor_name": "张明",
                    "task_label": "血常规",
                    "task_id": "",
                    "created_by_name": "张明",
                    "specimen": "EDTA抗凝血",
                    "draw_time": now(),
                    "completed_at": now(),
                    "issued_at": now(),
                    "entered_by": "u_lab_01",
                    "entered_by_name": "林检验",
                    "entered_at": now(),
                    "items": [
                        {"name": "白细胞计数", "value": "11.5", "unit": "10^9/L", "reference_range": "4-10", "abnormal": "high"},
                        {"name": "红细胞计数", "value": "4.2", "unit": "10^12/L", "reference_range": "3.5-5.5", "abnormal": "normal"},
                        {"name": "血红蛋白", "value": "125", "unit": "g/L", "reference_range": "110-150", "abnormal": "normal"},
                        {"name": "血小板计数", "value": "180", "unit": "10^9/L", "reference_range": "100-300", "abnormal": "normal"},
                        {"name": "中性粒细胞百分比", "value": "78", "unit": "%", "reference_range": "40-75", "abnormal": "high"},
                        {"name": "淋巴细胞百分比", "value": "18", "unit": "%", "reference_range": "20-50", "abnormal": "low"},
                    ],
                    "summary": "WBC 及中性粒细胞升高，提示炎症/感染",
                    "abnormal_count": 3,
                    "total_count": 6,
                    "status": "finalized",
                },
            },
            # —— 尿常规：已完成，蛋白+1（匹配 KG 糖尿病/感染 SUGGESTED_TEST: 尿常规）——
            {
                "task_id": uid("task"),
                "task_type": "blood",
                "task_label": "尿常规",
                "status": "done",
                "created_at": now(),
                "created_by": "u_att_01",
                "created_by_name": "张明",
                "completed_at": now(),
                "result": {
                    "items": [
                        {"name": "尿蛋白", "value": "+1", "unit": "", "reference_range": "(-)", "abnormal": "high"},
                        {"name": "尿潜血", "value": "(-)", "unit": "", "reference_range": "(-)", "abnormal": "normal"},
                        {"name": "尿糖", "value": "(-)", "unit": "", "reference_range": "(-)", "abnormal": "normal"},
                        {"name": "尿酮体", "value": "(-)", "unit": "", "reference_range": "(-)", "abnormal": "normal"},
                        {"name": "尿白细胞", "value": "+2", "unit": "/HP", "reference_range": "0-5", "abnormal": "high"},
                        {"name": "尿pH", "value": "5.5", "unit": "", "reference_range": "5.0-8.0", "abnormal": "normal"},
                    ],
                    "summary": "尿蛋白+1，白细胞+2，提示泌尿系感染",
                    "abnormal_count": 2,
                    "total_count": 6,
                    "entered_by": "u_lab_01",
                    "entered_by_name": "林检验",
                    "entered_at": now(),
                },
                "report": {
                    "report_no": f"LAB-{uid('blrpt')}",
                    "report_id": uid("blrpt"),
                    "patient_id": "p002",
                    "patient_name": "李娜",
                    "gender": "女",
                    "age": 32,
                    "department": "消化内科",
                    "attending_doctor_id": "u_att_01",
                    "attending_doctor_name": "张明",
                    "task_label": "尿常规",
                    "task_id": "",
                    "created_by_name": "张明",
                    "specimen": "晨尿",
                    "draw_time": now(),
                    "completed_at": now(),
                    "issued_at": now(),
                    "entered_by": "u_lab_01",
                    "entered_by_name": "林检验",
                    "entered_at": now(),
                    "items": [
                        {"name": "尿蛋白", "value": "+1", "unit": "", "reference_range": "(-)", "abnormal": "high"},
                        {"name": "尿潜血", "value": "(-)", "unit": "", "reference_range": "(-)", "abnormal": "normal"},
                        {"name": "尿糖", "value": "(-)", "unit": "", "reference_range": "(-)", "abnormal": "normal"},
                        {"name": "尿酮体", "value": "(-)", "unit": "", "reference_range": "(-)", "abnormal": "normal"},
                        {"name": "尿白细胞", "value": "+2", "unit": "/HP", "reference_range": "0-5", "abnormal": "high"},
                        {"name": "尿pH", "value": "5.5", "unit": "", "reference_range": "5.0-8.0", "abnormal": "normal"},
                    ],
                    "summary": "尿蛋白+1，白细胞+2，提示泌尿系感染",
                    "abnormal_count": 2,
                    "total_count": 6,
                    "status": "finalized",
                },
            },
            # —— C反应蛋白：待检 ——
            {
                "task_id": uid("task"),
                "task_type": "blood",
                "task_label": "C反应蛋白",
                "status": "ordered",
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
        ("CBC", "血常规", "blood", "EDTA抗凝血2ml", "WBC 4-10×10^9/L，HGB 男120-160 g/L 女110-150 g/L，PLT 100-300×10^9/L"),
        ("LFT", "肝功能", "blood", "空腹抽血3ml", "ALT 0-40 U/L，AST 0-40 U/L，TBIL 5-21 μmol/L，ALB 35-55 g/L"),
        ("RENAL", "肾功能", "blood", "空腹抽血3ml", "BUN 3.9-7.1 mmol/L，Cr 男57-111 女41-81 μmol/L，UA 男208-428 女155-357 μmol/L"),
        ("UA", "尿常规", "blood", "晨尿10ml", "蛋白(-)，潜血(-)，糖(-)，酮体(-)，pH 5.0-8.0"),
        ("ELECT", "电解质四项", "blood", "血清2ml", "K+ 3.5-5.3 mmol/L，Na+ 137-147 mmol/L，Cl- 99-110 mmol/L，Ca2+ 2.11-2.52 mmol/L"),
        ("COAG", "凝血功能", "blood", "枸橼酸钠抗凝血2ml", "PT 11-14s，APTT 30-45s，FIB 2-4 g/L，INR 0.8-1.2"),
        ("GLU", "空腹血糖", "blood", "空腹抽血2ml", "3.9-6.1 mmol/L"),
        ("HbA1c", "糖化血红蛋白", "blood", "EDTA抗凝血2ml", "4.0-6.0%"),
        ("LIPID", "血脂四项", "blood", "空腹抽血3ml", "TC <5.2 mmol/L，TG <1.7 mmol/L，LDL-C <3.4 mmol/L，HDL-C >1.0 mmol/L"),
        ("THYROID", "甲状腺功能五项", "blood", "血清3ml", "TSH 0.27-4.2 mIU/L，FT3 3.1-6.8 pmol/L，FT4 12-22 pmol/L"),
        ("CARDIAC", "心肌酶谱", "blood", "血清3ml", "CK-MB 0-25 U/L，cTnI 0-0.04 ng/ml，MYO <70 ng/ml，BNP <100 pg/ml"),
        ("TUMOR", "肿瘤标志物五项", "blood", "空腹抽血3ml", "AFP <20 ng/ml，CEA <5 ng/ml，CA19-9 <37 U/ml，CA125 <35 U/ml，CA15-3 <25 U/ml"),
        ("FECAL", "便常规+潜血", "blood", "新鲜粪便约5g", "外观成形软便，RBC 0，WBC 0-2/HP，潜血(-)"),
        ("CRP", "C反应蛋白", "blood", "血清2ml", "<10 mg/L"),
        ("PCT", "降钙素原", "blood", "血清2ml", "<0.05 ng/ml"),
        ("ESR", "血沉", "blood", "枸橼酸钠抗凝血2ml", "男0-15 mm/h，女0-20 mm/h"),
        ("VITD", "25羟维生素D", "blood", "血清2ml", "充足 ≥75 nmol/L，不足 50-74.9 nmol/L"),
        ("FER", "血清铁蛋白", "blood", "血清2ml", "男30-400 ng/ml，女13-150 ng/ml"),
        # —— CT影像 (ct) ——
        ("CT-ABD", "腹部CT平扫", "ct", "禁食4小时，增强需造影剂", "无标准值，描述性报告"),
        ("CT-ABD-E", "腹部CT增强", "ct", "禁食4小时，含碘造影剂", "无标准值，描述性报告"),
        ("CT-CHEST", "胸部CT平扫", "ct", "去除金属物品，仰卧位", "无标准值，描述性报告"),
        ("CT-ANGIO", "冠脉CTA", "ct", "心率控制<70次/分，造影剂", "冠脉狭窄程度评估，斑块性质描述"),
        ("CT-HEAD", "头颅CT平扫", "ct", "去除金属物品，仰卧位", "无标准值，描述性报告"),
        ("CT-PELVIS", "盆腔CT", "ct", "憋尿充盈膀胱，增强需造影剂", "无标准值，描述性报告"),
        # —— 磁共振 (mri) ——
        ("MRI-HEAD", "头颅MRI平扫", "mri", "去除金属物品，仰卧位，检查约15-30分钟", "无标准值，描述性报告"),
        ("MRI-SPINE", "脊柱MRI", "mri", "去除金属物品，俯卧/仰卧位", "椎间盘、椎体、脊髓、椎管描述"),
        ("MRI-KNEE", "膝关节MRI", "mri", "去除金属物品，仰卧位", "半月板、韧带、关节软骨描述"),
        ("MRI-ABDOMEN", "腹部MRI平扫", "mri", "禁食4-6小时，去除金属物品", "无标准值，描述性报告"),
        ("MRCP", "磁共振胰胆管成像", "mri", "禁食6-8小时", "胆道、胰管扩张/结石/占位描述"),
        # —— 超声 (ultrasound) ——
        ("ABD-US", "腹部B超", "ultrasound", "空腹8小时，仰卧位", "肝/胆/胰/脾/双肾描述性报告"),
        ("ECHO", "心脏彩超", "ultrasound", "静卧5分钟，左侧卧位", "EF 55-70%，FS 25-35%，各房室大小正常"),
        ("THYROID-US", "甲状腺B超", "ultrasound", "去除颈部饰物，仰卧位", "TI-RADS分级，无标准值"),
        ("RENAL-US", "泌尿系B超", "ultrasound", "憋尿充盈膀胱", "双肾/输尿管/膀胱描述性报告"),
        ("CAROTID-US", "颈动脉彩超", "ultrasound", "仰卧位，暴露颈部", "内膜厚度、斑块、狭窄程度描述"),
        ("BREAST-US", "乳腺B超", "ultrasound", "仰卧位，暴露胸部", "BI-RADS分级，无标准值"),
        ("PELVIC-US", "妇科B超", "ultrasound", "经腹需憋尿，经阴需排空膀胱", "子宫/卵巢描述性报告"),
        ("SCROTAL-US", "阴囊B超", "ultrasound", "仰卧位", "睾丸/附睾/精索描述性报告"),
        # —— X线 (xray) ——
        ("CXR", "胸部正位片", "xray", "去除金属物品，站立位拍片", "双肺纹理清晰，心影不大"),
        ("CXR-LAT", "胸部正侧位片", "xray", "去除金属物品，站立位拍片", "双肺/胸膜/心脏/纵隔描述"),
        ("XR-BONE", "骨关节X线", "xray", "去除金属物品，正侧位摄片", "骨质、关节间隙、骨折线描述"),
        ("XR-SPINE", "脊柱X线", "xray", "去除金属物品，正侧位+动力位", "椎体序列、椎间隙、骨赘描述"),
        ("MAMMO", "乳腺钼靶", "xray", "去除金属物品，加压摄片", "BI-RADS分级，钙化/肿块描述"),
        # —— 病理 (pathology) ——
        ("BIOPSY", "活检病理", "pathology", "病变部位取材，10%福尔马林固定", "病理诊断：良性/恶性/交界性"),
        ("FROZEN", "术中冰冻", "pathology", "新鲜组织，OCT包埋，30分钟出结果", "术中快速病理诊断，术后石蜡病理确诊"),
        ("CYTOLOGY", "细胞学检查", "pathology", "脱落细胞/穿刺液制片", "未见癌细胞/查见异型细胞/恶性肿瘤细胞"),
        ("IHC", "免疫组化", "pathology", "石蜡切片，按申请标记染色", "CK/CD/Ki-67/ER/PR/HER2等指标判读"),
        # —— 内镜 (endoscopy) ——
        ("EGD", "胃镜", "endoscopy", "禁食8小时，禁水2小时，口服局部麻醉剂", "食管/胃/十二指肠描述性报告"),
        ("COLONOSCOPY", "肠镜", "endoscopy", "肠道准备（清肠），禁食8小时", "全结肠/直肠黏膜描述性报告"),
        ("SIGMOID", "乙状结肠镜", "endoscopy", "肠道准备，术前排空", "直肠/乙状结肠描述性报告"),
        ("BRONCH", "支气管镜", "endoscopy", "术前禁食，局部/静脉麻醉", "气管/支气管描述，必要时活检"),
        # —— 心电/肺功能/其他功能 (physiology) ——
        ("ECG", "常规心电图", "physiology", "静卧5分钟，四肢+胸导联12导联", "窦性心律，心率 60-100 bpm"),
        ("HOLTER", "24小时动态心电图", "physiology", "佩戴24小时，记录日常活动", "24h总心率 8-12万次，室早/房早负荷评估"),
        ("ABPM", "24小时动态血压", "physiology", "佩戴上臂袖带24小时，昼夜记录", "24h平均 <130/80 mmHg，白天 <135/85 mmHg"),
        ("PFT", "肺功能检查", "physiology", "坐位，夹鼻嘴配合指令呼气吸气", "FEV1 占预计值 ≥80%，FVC 正常，DLCO 正常"),
        ("BMD", "双能X线骨密度", "physiology", "去除金属物品，仰卧位", "T值 ≥-1.0 正常，-2.5~-1.0 低骨量，≤-2.5 骨质疏松"),
        ("AUDIOMETRY", "纯音测听", "physiology", "隔声室，佩戴耳机，测气导骨导", "气导听阈 ≤25 dB HL"),
        ("EEG", "脑电图", "physiology", "头皮电极，清醒/睡眠状态，约30分钟", "背景α节律，无痫样放电"),
        ("TCD", "经颅多普勒", "physiology", "仰卧位，颞窗/枕窗探查", "颅内动脉血流速度、频谱形态评估"),
        # —— 其他特殊检查 (other) ——
        ("PET-CT", "PET-CT全身显像", "other", "禁食6小时，静注FDG，检查前控制血糖", "全身代谢显像，SUV值评估，肿瘤分期/疗效评估"),
        ("DEXA", "体成分分析", "other", "去除金属物品，仰卧位", "脂肪/肌肉/骨量分布，基础代谢率"),
        ("GASTRO-SCOPY", "24小时食管pH监测", "other", "鼻饲pH电极，佩戴24小时", "酸反流次数、DeMeester评分"),
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


def _seed_agent_resources() -> None:
    """Prompt/OutputSchema 版本化资源种子数据（v2 适配）。"""
    # —— 病历辅助 Agent 默认 Prompt ——
    emr_prompt = store.add_prompt_resource(
        name="病历辅助助手默认模板",
        content="""你是一家三级甲等医院的【AI 病历辅助助手】，协助主治医生起草和优化病历，绝不替代医生做最终决策。

【必须严格遵守的规则】
1. 你的输出仅是病历草稿建议，不会自动写入正式病历，必须由主治医生 HITL 审阅确认后才可采纳。
2. 病历结构遵循 SOAP 模板。
3. 不得编造患者未提供的检查数据或体征；如信息不足，明确告知医生需要补充哪些信息。
4. 不得给出剂量明确的处方；用药建议只能给出类别方向。
5. 输出末尾必须附带声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
        created_by="u_admin_01",
        agent_keys=["emr_agent"],
        remark="系统默认模板，适用于消化内科通用病历场景",
    )
    # 设为 online 状态
    store.update_prompt_resource(emr_prompt["prompt_id"], {"status": "online"})

    # —— 病历辅助 Agent 默认 OutputSchema ——
    emr_schema = store.add_schema_resource(
        name="SOAP 病历输出模板",
        json_schema={
            "chief_complaint": "主诉",
            "present_illness": "现病史",
            "past_history": "既往史",
            "examination": "查体",
            "assessment": "评估",
            "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
            "risk_flags": ["风险提示"],
            "plan": "诊疗计划",
        },
        created_by="u_admin_01",
        agent_keys=["emr_agent"],
        remark="SOAP 结构字段模板，前端用于渲染结构化病历卡片",
    )
    store.update_schema_resource(emr_schema["schema_id"], {"status": "online"})

    # —— 导诊 Agent 默认 Prompt ——
    triage_prompt = store.add_prompt_resource(
        name="AI 智能导诊助手默认模板",
        content="""你是一家三级甲等医院的【AI智能导诊助手】，只负责分诊科室推荐，绝对不能做诊断、开处方、推荐药物或给出治疗方案。

【必须严格遵守的规则】
1. 只根据用户描述的症状、病史、过敏史信息，推荐 2-3 个就诊科室。
2. 每个推荐必须给出简短理由。
3. 输出结尾必须附带强制免责声明。
4. 急重症建议立即前往急诊。
""",
        created_by="u_admin_01",
        agent_keys=["patient_triage_agent"],
        remark="系统默认导诊模板",
    )
    store.update_prompt_resource(triage_prompt["prompt_id"], {"status": "online"})

    # ============================================================
    # 病历 Agent 按科室配对（Prompt + Schema 成对，department 维度）
    # 通用模板（department=None）回退兜底；以下为专科配对，resolve 时按就诊科室优先匹配
    # ============================================================

    # —— 普外科配对：强调专科情况/手术史/影像 ——
    surg_prompt = store.add_prompt_resource(
        name="病历辅助·普外科专科模板",
        content="""你是一家三级甲等医院普外科的【AI 病历辅助助手】，协助主治医生起草 SOAP 病历，绝不替代医生做最终决策。

【普外科专科要点】
1. 现病史须描述疼痛/包块的性质、部位、持续时间与诱因。
2. 专科情况须记录包块大小/位置/活动度/压痛/边界。
3. 既往史重点追问手术史、外伤史、过敏史。
4. 优先关联影像所见（B超/CT/MRI）辅助判断。
5. 诊疗计划须含手术指征评估（是否需急诊/择期手术）。
6. 不得编造患者未提供的体征；用药只给类别方向，不给剂量。
7. 输出末尾附带声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
        created_by="u_admin_01",
        agent_keys=["emr_agent"],
        remark="普外科专科配对：专科情况/手术史/影像/手术指征",
        department="普外科",
    )
    store.update_prompt_resource(surg_prompt["prompt_id"], {"status": "online"})

    surg_schema = store.add_schema_resource(
        name="SOAP 病历·普外科输出模板",
        json_schema={
            "chief_complaint": "主诉",
            "present_illness": "现病史（疼痛/包块性质与演变）",
            "past_history": "既往史（含手术史/外伤史）",
            "specialty_examination": "专科情况（包块位置/大小/活动度/压痛/边界）",
            "examination": "全身查体",
            "imaging_findings": "影像所见",
            "assessment": "评估",
            "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
            "plan": "诊疗计划（含手术指征评估）",
            "risk_flags": ["风险提示"],
        },
        created_by="u_admin_01",
        agent_keys=["emr_agent"],
        remark="普外科专科配对：含 specialty_examination/imaging_findings 字段",
        department="普外科",
    )
    store.update_schema_resource(surg_schema["schema_id"], {"status": "online"})

    # —— 儿科配对：强调喂养史/发育史/家长代述 ——
    peds_prompt = store.add_prompt_resource(
        name="病历辅助·儿科专科模板",
        content="""你是一家三级甲等医院儿科的【AI 病历辅助助手】，协助主治医生起草 SOAP 病历，绝不替代医生做最终决策。

【儿科专科要点】
1. 主诉与现病史多由家长代述，须标注"（家长代述）"并评估可靠性。
2. 必采集喂养史（母乳/人工/辅食）、出生史（足月/早产/Apgar）、生长发育史（抬头/翻身/走路/说话）。
3. 体重/体温/呼吸/心率按年龄标准判读，成人标准不适用。
4. 用药须按体重折算剂量，慎用氨基糖苷类等儿童禁忌药。
5. 须关注家长焦虑情绪，沟通需安抚。
6. 不得编造未提供的体征；输出末尾声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
        created_by="u_admin_01",
        agent_keys=["emr_agent"],
        remark="儿科专科配对：喂养史/发育史/家长代述/按体重用药",
        department="儿科",
    )
    store.update_prompt_resource(peds_prompt["prompt_id"], {"status": "online"})

    peds_schema = store.add_schema_resource(
        name="SOAP 病历·儿科输出模板",
        json_schema={
            "chief_complaint": "主诉（标注家长代述及可靠性）",
            "present_illness": "现病史",
            "birth_history": "出生史（足月/早产/Apgar）",
            "feeding_history": "喂养史（母乳/人工/辅食）",
            "development_history": "发育史（运动/语言里程碑）",
            "past_history": "既往史（含疫苗史）",
            "examination": "查体（按年龄标准判读生命体征）",
            "assessment": "评估",
            "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
            "plan": "诊疗计划（按体重折算剂量）",
            "risk_flags": ["风险提示"],
        },
        created_by="u_admin_01",
        agent_keys=["emr_agent"],
        remark="儿科专科配对：含 feeding_history/development_history/birth_history 字段",
        department="儿科",
    )
    store.update_schema_resource(peds_schema["schema_id"], {"status": "online"})

    # —— 妇产科配对：强调月经史/婚育史/产科检查 ——
    obgyn_prompt = store.add_prompt_resource(
        name="病历辅助·妇产科专科模板",
        content="""你是一家三级甲等医院妇产科的【AI 病历辅助助手】，协助主治医生起草 SOAP 病历，绝不替代医生做最终决策。

【妇产科专科要点】
1. 必采集月经史（初潮/周期/经期/末次月经 LMP）、婚育史（孕产史 GxPx）。
2. 主诉涉及阴道出血/腹痛/停经须优先排除妊娠及相关急症（异位妊娠/流产）。
3. 产科须记录孕周（按 LMP 或 B 超推算）、胎动、产检情况。
4. 妇科双合诊/三合诊体征须规范描述。
5. 涉及隐私信息注意保护，不得在非必要场景外泄。
6. 不得编造未提供的体征；用药须标注妊娠期分级（A/B/C/D/X）。
7. 输出末尾声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
        created_by="u_admin_01",
        agent_keys=["emr_agent"],
        remark="妇产科专科配对：月经史/婚育史/孕周/妊娠期用药分级",
        department="妇产科",
    )
    store.update_prompt_resource(obgyn_prompt["prompt_id"], {"status": "online"})

    obgyn_schema = store.add_schema_resource(
        name="SOAP 病历·妇产科输出模板",
        json_schema={
            "chief_complaint": "主诉",
            "present_illness": "现病史",
            "menstrual_history": "月经史（初潮/周期/经期/LMP）",
            "obstetric_history": "婚育史（GxPx）",
            "past_history": "既往史",
            "specialty_examination": "专科检查（妇科双合诊/产科宫高腹围）",
            "examination": "全身查体",
            "assessment": "评估（含孕周）",
            "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
            "plan": "诊疗计划（妊娠期用药标注分级）",
            "risk_flags": ["风险提示"],
        },
        created_by="u_admin_01",
        agent_keys=["emr_agent"],
        remark="妇产科专科配对：含 menstrual_history/obstetric_history 字段",
        department="妇产科",
    )
    store.update_schema_resource(obgyn_schema["schema_id"], {"status": "online"})

    # ============================================================
    # 14 个业务科室配对（BIZ 全覆盖）——儿科已种子，其余 13 个批量生成
    # ============================================================
    _EMR_DEPT_PAIRS = [
        {
            "dept": "消化内科",
            "remark": "消化内科专科配对：腹痛特征/排便习惯/黄疸",
            "prompt": """你是一家三甲医院消化内科的【AI 病历辅助助手】，协助主治医生起草 SOAP 病历，绝不替代医生做最终决策。

【消化内科专科要点】
1. 腹痛须描述部位、性质、持续时间、放射、加重/缓解因素。
2. 必采集排便习惯（频率/性状/血便/黑便）、食欲、体重变化。
3. 黄疸须区分肝前/肝细胞性/梗阻性，记录皮肤瘙痒、尿色、粪色。
4. 既往史重点：肝炎/饮酒史/药物史/手术史。
5. 查体须含腹部压痛、肝脾触诊、移动性浊音、Murphy 征。
6. 不得编造未提供的体征；用药只给类别方向。
7. 输出末尾声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
            "schema": {
                "chief_complaint": "主诉",
                "present_illness": "现病史（腹痛特征与演变）",
                "bowel_habits": "排便习惯（频率/性状/血便）",
                "jaundice": "黄疸（皮肤/尿色/粪色）",
                "past_history": "既往史（肝炎/饮酒/药物）",
                "examination": "查体（腹部压痛/肝脾/移动性浊音）",
                "assessment": "评估",
                "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
                "plan": "诊疗计划",
                "risk_flags": ["风险提示"],
            },
        },
        {
            "dept": "心内科",
            "remark": "心内科专科配对：胸痛特征/心悸/水肿",
            "prompt": """你是一家三甲医院心内科的【AI 病历辅助助手】，协助主治医生起草 SOAP 病历，绝不替代医生做最终决策。

【心内科专科要点】
1. 胸痛须按 OCER 描述（部位/性质/放射/持续时间/诱因/缓解），警惕 ACS/主动脉夹层。
2. 必采集心悸、呼吸困难、水肿、晕厥、活动耐量。
3. 既往史重点：高血压/糖尿病/高血脂/吸烟/家族猝死史。
4. 查体须含血压（双上肢）、心率、心律、心音、杂音、肺啰音、下肢水肿。
5. 用药须标注抗血小板/抗凝/β阻滞剂的禁忌与相互作用。
6. 不得编造未提供的体征；输出末尾声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
            "schema": {
                "chief_complaint": "主诉",
                "present_illness": "现病史（胸痛 OCER 特征）",
                "cardiac_symptoms": "心血管症状（心悸/呼吸困难/水肿/晕厥）",
                "past_history": "既往史（高血压/糖尿病/吸烟/家族猝死）",
                "examination": "查体（血压双上肢/心率/心律/心音/杂音/下肢水肿）",
                "ecg_findings": "心电图所见",
                "assessment": "评估",
                "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
                "plan": "诊疗计划",
                "risk_flags": ["风险提示"],
            },
        },
        {
            "dept": "急诊科",
            "remark": "急诊科专科配对：ABCDE/时间轴/分诊",
            "prompt": """你是一家三甲医院急诊科的【AI 病历辅助助手】，协助主治医生起草 SOAP 病历，绝不替代医生做最终决策。

【急诊科专科要点】
1. 采用 ABCDE 初评，优先识别危及生命的急症。
2. 病史须按时间轴记录起病/到达/处置时间，简明优先。
3. 必记录生命体征（意识/呼吸/脉搏/血压/SpO2/体温）。
4. 创伤须描述机制（高能/低能）、受伤部位、FAST 体征。
5. 分诊须标注级别（Ⅰ-Ⅳ级），危重优先处置。
6. 不得编造未提供的体征；用药只给类别方向。
7. 输出末尾声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
            "schema": {
                "chief_complaint": "主诉",
                "present_illness": "现病史（按时间轴）",
                "trauma_mechanism": "创伤机制（高能/低能）",
                "vital_signs_timeline": "生命体征时间轴（意识/呼吸/脉搏/血压/SpO2）",
                "abcde_assessment": "ABCDE 初评",
                "triage_level": "分诊级别（Ⅰ-Ⅳ级）",
                "examination": "查体",
                "assessment": "评估",
                "plan": "处置计划",
                "risk_flags": ["风险提示"],
            },
        },
        {
            "dept": "呼吸科",
            "remark": "呼吸科专科配对：咳嗽/痰/呼吸困难",
            "prompt": """你是一家三甲医院呼吸内科的【AI 病历辅助助手】，协助主治医生起草 SOAP 病历，绝不替代医生做最终决策。

【呼吸科专科要点】
1. 咳嗽须描述性质（干/湿）、病程、诱因、昼夜规律。
2. 痰须描述量、色、气味、是否带血。
3. 呼吸困难须分级（mMRC/NYHA）、夜间阵发性、端坐呼吸。
4. 既往史重点：吸烟史（包年）、职业暴露、结核接触、哮喘/慢阻肺史。
5. 查体须含呼吸频率、节律、辅助呼吸肌、叩诊、听诊（啰音/哮鸣音）。
6. 不得编造未提供的体征；用药只给类别方向。
7. 输出末尾声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
            "schema": {
                "chief_complaint": "主诉",
                "present_illness": "现病史（咳嗽/呼吸困难演变）",
                "sputum": "痰特征（量/色/气味/血丝）",
                "dyspnea_grade": "呼吸困难分级（mMRC/NYHA）",
                "past_history": "既往史（吸烟包年/职业暴露/结核接触）",
                "examination": "查体（呼吸频率/节律/叩诊/听诊啰音哮鸣音）",
                "imaging_findings": "胸片/CT 所见",
                "assessment": "评估",
                "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
                "plan": "诊疗计划",
                "risk_flags": ["风险提示"],
            },
        },
        {
            "dept": "神经内科",
            "remark": "神经内科专科配对：意识/肌力/反射",
            "prompt": """你是一家三甲医院神经内科的【AI 病历辅助助手】，协助主治医生起草 SOAP 病历，绝不替代医生做最终决策。

【神经内科专科要点】
1. 意识须按 GCS 评分，瞳孔大小/对光反射必记录。
2. 肢体无力须描述部位、肌力分级（0-5级）、是否对称。
3. 卒中须记录起病时间（最后正常时间）、FAST 识别。
4. 既往史重点：高血压/糖尿病/房颤/吸烟/TIA 史。
5. 查体须含脑神经、肌力、肌张力、腱反射、病理征、感觉系统、共济。
6. 不得编造未提供的体征；用药须标注时间窗（溶栓）。
7. 输出末尾声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
            "schema": {
                "chief_complaint": "主诉",
                "present_illness": "现病史（起病时间/症状演变）",
                "consciousness": "意识状态（GCS 评分）",
                "motor_examination": "运动检查（肌力0-5级/肌张力/对称性）",
                "past_history": "既往史（高血压/糖尿病/房颤/TIA）",
                "neurological_exam": "神经系统查体（脑神经/反射/病理征/感觉/共济）",
                "imaging_findings": "CT/MRI 所见",
                "assessment": "评估（含时间窗）",
                "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
                "plan": "诊疗计划（含溶栓评估）",
                "risk_flags": ["风险提示"],
            },
        },
        {
            "dept": "骨科",
            "remark": "骨科专科配对：外伤机制/关节活动度/神经血管",
            "prompt": """你是一家三甲医院骨科的【AI 病历辅助助手】，协助主治医生起草 SOAP 病历，绝不替代医生做最终决策。

【骨科专科要点】
1. 外伤须描述机制（摔倒/高处坠落/车祸）、暴力方向、受伤时体位。
2. 疼痛须定位（关节/骨干/软组织）、VAS 评分、活动加重情况。
3. 专科检查须含畸形、肿胀、压痛、关节活动度（ROM）、纵向叩击痛。
4. 必评估远端神经血管（感觉/运动/末梢循环/毛细血管充盈）。
5. 既往史重点：骨质疏松/手术史/抗凝药使用。
6. 不得编造未提供的体征；用药只给类别方向。
7. 输出末尾声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
            "schema": {
                "chief_complaint": "主诉",
                "present_illness": "现病史（外伤机制与疼痛）",
                "trauma_mechanism": "外伤机制（暴力方向/体位）",
                "specialty_examination": "专科检查（畸形/肿胀/压痛/ROM/纵向叩击痛）",
                "neurovascular_status": "远端神经血管（感觉/运动/循环）",
                "past_history": "既往史（骨质疏松/手术/抗凝）",
                "imaging_findings": "X 线/CT/MRI 所见",
                "assessment": "评估",
                "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
                "plan": "诊疗计划（含手术指征）",
                "risk_flags": ["风险提示"],
            },
        },
        {
            "dept": "眼科",
            "remark": "眼科专科配对：视力/眼压/眼底",
            "prompt": """你是一家三甲医院眼科的【AI 病历辅助助手】，协助主治医生起草 SOAP 病历，绝不替代医生做最终决策。

【眼科专科要点】
1. 视力下降须区分急性/慢性、单/双眼、程度（手动/数指/光感）。
2. 必记录视力（远/近/矫正）、眼压、视野、色觉。
3. 红眼须区分结膜充血/睫状充血/混合充血，伴随分泌物/疼痛/畏光。
4. 眼底须描述视盘、黄斑、血管、出血/渗出。
5. 既往史重点：糖尿病/高血压/青光眼/外伤/近视史。
6. 不得编造未提供的体征；用药须标注眼局部/全身给药途径。
7. 输出末尾声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
            "schema": {
                "chief_complaint": "主诉",
                "present_illness": "现病史（视力下降/红眼特征）",
                "visual_acuity": "视力（远/近/矫正/单双眼）",
                "intraocular_pressure": "眼压",
                "eye_exam": "专科检查（充血类型/分泌物/畏光/瞳孔）",
                "fundus_findings": "眼底（视盘/黄斑/血管/出血渗出）",
                "past_history": "既往史（糖尿病/高血压/青光眼/近视）",
                "assessment": "评估",
                "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
                "plan": "诊疗计划",
                "risk_flags": ["风险提示"],
            },
        },
        {
            "dept": "耳鼻喉科",
            "remark": "耳鼻喉科专科配对：听力/鼻塞/咽痛",
            "prompt": """你是一家三甲医院耳鼻喉科的【AI 病历辅助助手】，协助主治医生起草 SOAP 病历，绝不替代医生做最终决策。

【耳鼻喉科专科要点】
1. 耳部症状须描述听力下降（传导/感音）、耳鸣、耳漏、耳痛、眩晕。
2. 鼻部须描述鼻塞（单/双侧）、分泌物、嗅觉、鼻出血、头痛。
3. 咽部须描述咽痛、吞咽困难、声嘶、异物感。
4. 必行耳镜/鼻镜/间接喉镜检查，记录所见。
5. 既往史重点：过敏史/手术史/放疗史。
6. 不得编造未提供的体征；用药只给类别方向。
7. 输出末尾声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
            "schema": {
                "chief_complaint": "主诉",
                "present_illness": "现病史（耳/鼻/咽症状）",
                "ent_symptoms": "耳鼻喉症状（听力/耳鸣/鼻塞/声嘶/眩晕）",
                "ent_exam": "专科检查（耳镜/鼻镜/间接喉镜）",
                "past_history": "既往史（过敏/手术/放疗）",
                "examination": "全身查体",
                "assessment": "评估",
                "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
                "plan": "诊疗计划",
                "risk_flags": ["风险提示"],
            },
        },
        {
            "dept": "皮肤科",
            "remark": "皮肤科专科配对：皮损形态/分布/瘙痒",
            "prompt": """你是一家三甲医院皮肤科的【AI 病历辅助助手】，协助主治医生起草 SOAP 病历，绝不替代医生做最终决策。

【皮肤科专科要点】
1. 皮损须按原发/继发损害分类，描述形态（斑疹/丘疹/水疱/结节/糜烂/鳞屑）。
2. 须记录分布（全身/局限/对称/沿神经）、排列（散在/群集/线状）、演变。
3. 瘙痒/疼痛/灼热须评估程度（VAS）。
4. 必采集过敏史、用药史（含外用药）、职业接触、家族史。
5. 查体须含皮肤划痕征、Koebner 现象、黏膜/甲/毛发受累。
6. 不得编造未提供的体征；用药须标注外用/系统给药。
7. 输出末尾声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
            "schema": {
                "chief_complaint": "主诉",
                "present_illness": "现病史（皮损出现/演变）",
                "skin_lesion": "皮损描述（原发/继发损害形态）",
                "distribution": "分布与排列（全身/对称/沿神经）",
                "symptoms": "自觉症状（瘙痒/疼痛/灼热 VAS）",
                "past_history": "既往史（过敏/外用药/职业接触）",
                "examination": "专科查体（划痕征/Koebner/黏膜甲毛发）",
                "assessment": "评估",
                "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
                "plan": "诊疗计划（外用/系统）",
                "risk_flags": ["风险提示"],
            },
        },
        {
            "dept": "精神心理科",
            "remark": "精神心理科专科配对：精神检查/自杀风险评估",
            "prompt": """你是一家三甲医院精神心理科的【AI 病历辅助助手】，协助主治医生起草 SOAP 病历，绝不替代医生做最终决策。

【精神心理科专科要点】
1. 须完成精神检查：外观/意识/接触/认知/思维/情感/意志/自知力。
2. 幻觉/妄想须描述内容、性质、对患者行为的影响。
3. 必评估自杀/自伤风险（意念/计划/既往史/保护因素）。
4. 抑郁须评 PHQ-9，焦虑须评 GAD-7，记录睡眠/食欲/性功能。
5. 既往史重点：精神病史/物质滥用/外伤/家族史。
6. 涉及隐私须保护；用药须标注依赖性与相互作用。
7. 输出末尾声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
""",
            "schema": {
                "chief_complaint": "主诉",
                "present_illness": "现病史（症状起病/演变）",
                "mental_status_exam": "精神检查（意识/思维/情感/意志/自知力）",
                "psychotic_symptoms": "精神病性症状（幻觉/妄想内容）",
                "suicide_risk": "自杀风险评估（意念/计划/既往史）",
                "screening_scales": "量表评分（PHQ-9/GAD-7）",
                "past_history": "既往史（精神病史/物质滥用/家族）",
                "assessment": "评估",
                "plan": "诊疗计划（含危机干预）",
                "risk_flags": ["风险提示"],
            },
        },
        {
            "dept": "信息科",
            "remark": "信息科（辅助科室）：不直接诊疗，简化病历模板",
            "prompt": """你是医院信息科的【AI 病历辅助助手】，协助录入/整理辅助检查相关记录。

【信息科说明】
1. 信息科为非临床辅助科室，不直接产生诊疗病历。
2. 主要用于检查申请单/报告单/会诊单的结构化录入辅助。
3. 如涉及患者主诉请转交相应临床科室处理。
4. 输出末尾声明："【声明】以上为 AI 草稿建议，仅供录入参考。"
""",
            "schema": {
                "record_type": "记录类型（检查申请/报告整理/会诊单）",
                "related_department": "关联临床科室",
                "content_summary": "内容摘要",
                "operator": "操作人",
                "remark": "备注",
            },
        },
        {
            "dept": "检验科",
            "remark": "检验科（辅助科室）：结果解读/危急值",
            "prompt": """你是医院检验科的【AI 辅助助手】，协助解读检验结果、标注危急值。

【检验科说明】
1. 检验科为非临床辅助科室，不直接产生诊疗病历，主要辅助结果解读。
2. 须标注危急值（钾/钠/血糖/血红蛋白/血小板/凝血等）。
3. 结果须按参考范围标注↑↓，结合临床背景提示意义。
4. 不得替代临床医生下达诊断；建议复检/结合临床。
5. 输出末尾声明："【声明】以上为 AI 草稿建议，仅供医生参考，不构成诊断。"
""",
            "schema": {
                "specimen_type": "标本类型",
                "abnormal_items": "异常项目（含↑↓与参考范围）",
                "critical_values": "危急值标注",
                "clinical_significance": "临床意义提示",
                "recommendation": "建议（复检/结合临床）",
                "remark": "备注",
            },
        },
        {
            "dept": "影像科",
            "remark": "影像科（辅助科室）：影像所见/征象描述",
            "prompt": """你是医院影像科的【AI 辅助助手】，协助起草影像检查报告结构化记录。

【影像科说明】
1. 影像科为辅助科室，主要辅助影像所见结构化描述，不直接下临床诊断。
2. 须按检查部位/序列描述：形态/密度/信号/强化/毗邻关系。
3. 阴性/阳性所见均须记录，测量值须标单位。
4. 须给出影像印象（impression），但提示"请结合临床"。
5. 输出末尾声明："【声明】以上为 AI 草稿建议，仅供医生参考。"
""",
            "schema": {
                "modality": "检查方式（X 线/CT/MRI/超声）",
                "body_part": "检查部位",
                "findings": "影像所见（形态/密度/信号/强化）",
                "measurements": "测量值（含单位）",
                "impression": "影像印象",
                "recommendation": "建议（随访/对比/结合临床）",
                "remark": "备注",
            },
        },
    ]

    for pair in _EMR_DEPT_PAIRS:
        # 儿科已在上方单独种子，跳过避免重复
        if pair["dept"] == "儿科":
            continue
        p = store.add_prompt_resource(
            name=f"病历辅助·{pair['dept']}专科模板",
            content=pair["prompt"],
            created_by="u_admin_01",
            agent_keys=["emr_agent"],
            remark=pair["remark"],
            department=pair["dept"],
        )
        store.update_prompt_resource(p["prompt_id"], {"status": "online"})
        s = store.add_schema_resource(
            name=f"SOAP 病历·{pair['dept']}输出模板",
            json_schema=pair["schema"],
            created_by="u_admin_01",
            agent_keys=["emr_agent"],
            remark=pair["remark"],
            department=pair["dept"],
        )
        store.update_schema_resource(s["schema_id"], {"status": "online"})


def seed_all(store: Store) -> None:
    _seed_users()
    _seed_departments()
    _seed_kg_dept_aliases()
    _seed_kb()
    _seed_buildings()
    _seed_exam_items()
    _seed_rag_docs()
    _seed_patient_users()
    _seed_patients()
    _seed_oag_extended()
    _seed_agent_resources()  # 14 科室 Prompt + Schema 配对（病历 Agent 按科室路由）
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
    extra_depts = ["呼吸科", "神经内科", "骨科", "儿科", "眼科", "耳鼻喉科", "皮肤科", "精神心理科",
                   "妇产科", "泌尿外科", "内分泌科", "肾内科", "肿瘤科", "中医科", "血液科"]
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
        {"user_id": "u_doc_09", "username": "hongyan", "password": "123456", "name": "洪燕", "role": "attending", "department": "妇产科", "title": "主任医师"},
        {"user_id": "u_doc_10", "username": "songjie", "password": "123456", "name": "宋杰", "role": "attending", "department": "泌尿外科", "title": "副主任医师"},
        {"user_id": "u_doc_11", "username": "tangli", "password": "123456", "name": "唐丽", "role": "attending", "department": "内分泌科", "title": "主任医师"},
        {"user_id": "u_doc_12", "username": "luofei", "password": "123456", "name": "罗飞", "role": "attending", "department": "肾内科", "title": "副主任医师"},
        {"user_id": "u_doc_13", "username": "denghua", "password": "123456", "name": "邓华", "role": "attending", "department": "肿瘤科", "title": "主任医师"},
        {"user_id": "u_doc_14", "username": "baiyun", "password": "123456", "name": "白云", "role": "attending", "department": "中医科", "title": "主任中医师"},
        {"user_id": "u_doc_15", "username": "qiushan", "password": "123456", "name": "邱山", "role": "attending", "department": "血液科", "title": "副主任医师"},
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
    f_b3 = store.add_floor(b4["building_id"], "3层")
    store.bind_room(b4["building_id"], f_b3["floor_id"], "301诊室", "妇产科")
    store.bind_room(b4["building_id"], f_b3["floor_id"], "302诊室", "泌尿外科")
    store.bind_room(b4["building_id"], f_b3["floor_id"], "303诊室", "内分泌科")
    store.bind_room(b4["building_id"], f_b3["floor_id"], "304诊室", "肾内科")
    store.bind_room(b4["building_id"], f_b3["floor_id"], "305诊室", "肿瘤科")
    f_b4 = store.add_floor(b4["building_id"], "4层")
    store.bind_room(b4["building_id"], f_b4["floor_id"], "401诊室", "中医科")
    store.bind_room(b4["building_id"], f_b4["floor_id"], "402诊室", "血液科")

    b5 = store.add_building("医技楼B座")
    f_c1 = store.add_floor(b5["building_id"], "1层")
    store.bind_room(b5["building_id"], f_c1["floor_id"], "DR室", "影像科")
    store.bind_room(b5["building_id"], f_c1["floor_id"], "核磁室", "影像科")
    store.bind_room(b5["building_id"], f_c1["floor_id"], "脑电图室", "神经内科")

    # 4. 生成 18 名患者的就诊链路
    _generate_extended_patients()


def _mock_blood_items(dept: str, days_offset: int) -> dict:
    """生成模拟血常规结果，按科室和病程生成不同异常模式。"""
    # 基础指标
    base_items = [
        {"name": "白细胞计数", "value": "6.8", "unit": "10^9/L", "reference_range": "4-10", "ref_low": 4, "ref_high": 10},
        {"name": "红细胞计数", "value": "4.6", "unit": "10^12/L", "reference_range": "3.5-5.5", "ref_low": 3.5, "ref_high": 5.5},
        {"name": "血红蛋白", "value": "138", "unit": "g/L", "reference_range": "110-160", "ref_low": 110, "ref_high": 160},
        {"name": "血小板计数", "value": "215", "unit": "10^9/L", "reference_range": "100-300", "ref_low": 100, "ref_high": 300},
        {"name": "中性粒细胞百分比", "value": "58", "unit": "%", "reference_range": "40-75", "ref_low": 40, "ref_high": 75},
        {"name": "淋巴细胞百分比", "value": "32", "unit": "%", "reference_range": "20-50", "ref_low": 20, "ref_high": 50},
        {"name": "单核细胞百分比", "value": "7", "unit": "%", "reference_range": "3-10", "ref_low": 3, "ref_high": 10},
        {"name": "嗜酸性粒细胞百分比", "value": "3", "unit": "%", "reference_range": "0.5-5", "ref_low": 0.5, "ref_high": 5},
        {"name": "红细胞压积", "value": "42", "unit": "%", "reference_range": "37-50", "ref_low": 37, "ref_high": 50},
        {"name": "平均红细胞体积", "value": "92", "unit": "fL", "reference_range": "80-100", "ref_low": 80, "ref_high": 100},
        {"name": "平均血红蛋白含量", "value": "30", "unit": "pg", "reference_range": "27-34", "ref_low": 27, "ref_high": 34},
        {"name": "平均血红蛋白浓度", "value": "325", "unit": "g/L", "reference_range": "320-360", "ref_low": 320, "ref_high": 360},
    ]

    # 按科室/病程生成不同异常模式
    abnormal_map = {
        "呼吸科": {  # 感染：白细胞高、中性高
            "白细胞计数": ("12.5", "high"),
            "中性粒细胞百分比": ("82", "high"),
            "淋巴细胞百分比": ("12", "low"),
        },
        "神经内科": {  # 脑血管：红细胞/血红蛋白偏低
            "红细胞计数": ("3.2", "low"),
            "血红蛋白": ("98", "low"),
            "白细胞计数": ("11.2", "high"),
        },
        "骨科": {  # 创伤：白细胞高、血小板高
            "白细胞计数": ("15.8", "high"),
            "血小板计数": ("345", "high"),
            "中性粒细胞百分比": ("88", "high"),
        },
        "儿科": {  # 儿童感染：白细胞高
            "白细胞计数": ("18.2", "high"),
            "中性粒细胞百分比": ("78", "high"),
            "淋巴细胞百分比": ("14", "low"),
        },
        "眼科": {  # 基本正常
        },
        "耳鼻喉科": {
            "白细胞计数": ("11.5", "high"),
        },
        "皮肤科": {
            "嗜酸性粒细胞百分比": ("8", "high"),
            "白细胞计数": ("10.8", "high"),
        },
        "精神心理科": {
            "红细胞计数": ("3.4", "low"),
            "血红蛋白": ("102", "low"),
        },
        "心内科": {  # 心血管：红细胞/血红蛋白偏低
            "红细胞计数": ("3.1", "low"),
            "血红蛋白": ("95", "low"),
            "白细胞计数": ("12.8", "high"),
        },
        "消化内科": {  # 消化道：贫血
            "红细胞计数": ("3.0", "low"),
            "血红蛋白": ("88", "low"),
            "平均红细胞体积": ("72", "low"),
        },
    }

    # 神经内科/消化内科 fallback
    if dept not in abnormal_map:
        abnormal_map[dept] = {}

    dept_abnormal = abnormal_map.get(dept, {})

    # 病程影响：越久远，异常越轻微（模拟恢复）
    recovery_factor = min(1.0, abs(days_offset) / 30)

    items = []
    abnormal_count = 0
    for it in base_items:
        item = dict(it)
        if item["name"] in dept_abnormal:
            val, abn = dept_abnormal[item["name"]]
            # 恢复期：异常值往正常方向拉
            try:
                fval = float(val)
                if recovery_factor > 0 and abn == "high":
                    fval = float(item["ref_high"]) + (fval - float(item["ref_high"])) * (1 - recovery_factor * 0.8)
                    val = f"{fval:.1f}"
                elif recovery_factor > 0 and abn == "low":
                    fval = float(item["ref_low"]) + (fval - float(item["ref_low"])) * (1 - recovery_factor * 0.8)
                    val = f"{fval:.1f}"
                item["value"] = val
                item["abnormal"] = abn
                abnormal_count += 1
            except ValueError:
                item["value"] = val
                item["abnormal"] = abn
                abnormal_count += 1
        else:
            item["abnormal"] = "normal"
        # 去掉辅助字段
        item.pop("ref_low", None)
        item.pop("ref_high", None)
        items.append(item)

    # 生成 summary
    if abnormal_count == 0:
        summary = "各项指标基本正常"
    elif abnormal_count <= 2:
        summary = f"检出 {abnormal_count} 项异常，建议结合临床综合判断"
    else:
        summary = f"检出 {abnormal_count} 项异常，提示可能存在{dept}相关问题，建议进一步检查"

    return {
        "items": items,
        "summary": summary,
        "abnormal_count": abnormal_count,
        "total_count": len(items),
        "entered_by": "u_lab_01",
        "entered_by_name": "林检验",
        "entered_at": now(),
    }


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
                r_name = room.get("room_name", "") or room.get("name", "")
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

            # 添加检查任务（血检数据存入报告）
            blood_items = _mock_blood_items(dept, days_offset)
            blood_report_id = uid("blrpt")
            # 构造报告单实体
            blood_report = {
                "report_no": f"LAB-{blood_report_id}",
                "report_id": blood_report_id,
                "patient_id": pid,
                "patient_name": pname,
                "gender": gender,
                "age": age,
                "department": dept,
                "attending_doctor_id": doctor_id,
                "attending_doctor_name": doc.get("name", "") if doc else "",
                "task_label": "血常规",
                "task_id": uid("tsk"),
                "created_by_name": doc.get("name", "") if doc else "",
                "specimen": "静脉血",
                "draw_time": start_time,
                "completed_at": end_time,
                "issued_at": end_time,
                "entered_by": "u_lab_01",
                "entered_by_name": "林检验",
                "entered_at": end_time,
                "items": blood_items["items"],
                "summary": blood_items["summary"],
                "abnormal_count": blood_items["abnormal_count"],
                "total_count": blood_items["total_count"],
                "status": "finalized",
            }
            # 血检结果也存一份在 task.result 用于列表展示
            state["check_tasks"].append({
                "task_id": blood_report["task_id"],
                "task_type": "blood",
                "task_label": "血常规",
                "status": "done",
                "created_at": start_time,
                "created_by": doctor_id,
                "created_by_name": doc.get("name", "") if doc else "",
                "completed_at": end_time,
                "result": blood_items,
                "report": blood_report,
                "visit_id": booking_id,
            })

        # —— in_progress / waiting 的当前就诊追加待检 blood 任务 ——
        if status in ("in_progress", "waiting") and days_offset == 0:
            doc_name = doc.get("name", "") if doc else ""
            # 每位当日患者按科室追加 2-3 个 blood 类待检任务，混合 ordered / pending
            pending_specs_by_dept = {
                "呼吸科": [("ordered", "血常规"), ("pending", "C反应蛋白"), ("ordered", "降钙素原")],
                "神经内科": [("ordered", "血常规"), ("pending", "凝血功能"), ("ordered", "电解质四项")],
                "骨科": [("ordered", "血常规"), ("ordered", "血沉"), ("pending", "C反应蛋白")],
                "儿科": [("ordered", "血常规"), ("pending", "C反应蛋白"), ("ordered", "尿常规")],
                "皮肤科": [("ordered", "血常规"), ("pending", "C反应蛋白")],
                "心内科": [("ordered", "血常规"), ("pending", "心肌酶谱"), ("ordered", "血脂四项")],
                "消化内科": [("ordered", "肝功能"), ("pending", "血常规"), ("ordered", "肾功能")],
            }
            specs = pending_specs_by_dept.get(dept, [("ordered", "血常规"), ("pending", "C反应蛋白")])
            for s_status, s_label in specs:
                state["check_tasks"].append({
                    "task_id": uid("tsk"),
                    "task_type": "blood",
                    "task_label": s_label,
                    "status": s_status,
                    "created_at": start_time,
                    "created_by": doctor_id,
                    "created_by_name": doc_name,
                    "completed_at": None,
                    "result": None,
                    "report": None,
                    "visit_id": booking_id,
                })

    # 批量写入
    for pid, state in seen_patients.items():
        store.upsert_patient(state)
        store.append_audit(pid, "seed", {"user_id": "system", "name": "系统"}, f"扩展患者 {pid} 就诊链路")

    # 补充检验报告数据
    _fill_lab_results()
    # 补充问诊数据（主诉/既往史/过敏史/现病史）
    _fill_clinical_data()
    # 补充影像检查报告（CT/B超/X光）
    _fill_imaging_results()


def _mock_lab_result(task_label: str, dept: str, gender: str, age: int,
                     pid: str, pname: str, doctor_id: str, doctor_name: str) -> dict:
    """按检验类型+科室生成模拟检验结果（含异常值），返回 result + report 两个 dict。"""

    # 各检验类型的指标定义 (name, value, unit, ref_range, abnormal)
    _LAB_DATA = {
        "C反应蛋白": {
            "items": [
                {"name": "C反应蛋白(CRP)", "value": "8.5", "unit": "mg/L", "reference_range": "0-10", "abnormal": "normal"},
            ],
            "abnormal_by_dept": {
                "呼吸科": [("C反应蛋白(CRP)", "45.2", "high")],
                "心内科": [("C反应蛋白(CRP)", "12.8", "high")],
                "消化内科": [("C反应蛋白(CRP)", "15.3", "high")],
                "儿科": [("C反应蛋白(CRP)", "32.0", "high")],
                "骨科": [("C反应蛋白(CRP)", "22.5", "high")],
                "皮肤科": [("C反应蛋白(CRP)", "11.2", "high")],
            },
            "summary_normal": "CRP 正常，无明显急性炎症",
            "summary_abnormal": "CRP 升高，提示炎症/感染",
        },
        "降钙素原": {
            "items": [
                {"name": "降钙素原(PCT)", "value": "0.05", "unit": "ng/mL", "reference_range": "<0.1", "abnormal": "normal"},
            ],
            "abnormal_by_dept": {
                "呼吸科": [("降钙素原(PCT)", "0.8", "high")],
                "儿科": [("降钙素原(PCT)", "0.35", "high")],
                "心内科": [("降钙素原(PCT)", "0.15", "high")],
            },
            "summary_normal": "PCT 正常，无细菌感染证据",
            "summary_abnormal": "PCT 升高，提示细菌感染可能",
        },
        "凝血功能": {
            "items": [
                {"name": "凝血酶原时间(PT)", "value": "12.5", "unit": "秒", "reference_range": "11-14", "abnormal": "normal"},
                {"name": "国际标准化比值(INR)", "value": "1.0", "unit": "", "reference_range": "0.8-1.2", "abnormal": "normal"},
                {"name": "活化部分凝血活酶时间(APTT)", "value": "35", "unit": "秒", "reference_range": "25-40", "abnormal": "normal"},
                {"name": "纤维蛋白原(FIB)", "value": "2.8", "unit": "g/L", "reference_range": "2-5", "abnormal": "normal"},
                {"name": "D-二聚体", "value": "0.3", "unit": "mg/L", "reference_range": "<0.5", "abnormal": "normal"},
            ],
            "abnormal_by_dept": {
                "神经内科": [("D-二聚体", "1.8", "high"), ("纤维蛋白原(FIB)", "5.2", "high")],
                "心内科": [("D-二聚体", "0.9", "high")],
                "骨科": [("D-二聚体", "1.2", "high")],
            },
            "summary_normal": "凝血功能各项指标正常",
            "summary_abnormal": "D-二聚体升高，需排查血栓/高凝状态",
        },
        "电解质四项": {
            "items": [
                {"name": "钾(K+)", "value": "4.2", "unit": "mmol/L", "reference_range": "3.5-5.5", "abnormal": "normal"},
                {"name": "钠(Na+)", "value": "140", "unit": "mmol/L", "reference_range": "135-145", "abnormal": "normal"},
                {"name": "氯(Cl-)", "value": "102", "unit": "mmol/L", "reference_range": "96-108", "abnormal": "normal"},
                {"name": "钙(Ca2+)", "value": "2.35", "unit": "mmol/L", "reference_range": "2.1-2.6", "abnormal": "normal"},
            ],
            "abnormal_by_dept": {
                "神经内科": [("钠(Na+)", "128", "low"), ("钾(K+)", "3.2", "low")],
                "消化内科": [("钾(K+)", "3.1", "low"), ("钠(Na+)", "132", "low")],
            },
            "summary_normal": "电解质各项正常",
            "summary_abnormal": "低钾低钠，需纠正电解质紊乱",
        },
        "心肌酶谱": {
            "items": [
                {"name": "肌酸激酶(CK)", "value": "120", "unit": "U/L", "reference_range": "0-200", "abnormal": "normal"},
                {"name": "肌酸激酶同工酶(CK-MB)", "value": "15", "unit": "U/L", "reference_range": "0-25", "abnormal": "normal"},
                {"name": "乳酸脱氢酶(LDH)", "value": "180", "unit": "U/L", "reference_range": "120-250", "abnormal": "normal"},
                {"name": "α-羟丁酸脱氢酶(HBDH)", "value": "120", "unit": "U/L", "reference_range": "72-182", "abnormal": "normal"},
                {"name": "肌钙蛋白I(cTnI)", "value": "0.02", "unit": "ng/mL", "reference_range": "<0.1", "abnormal": "normal"},
            ],
            "abnormal_by_dept": {
                "心内科": [("肌酸激酶(CK)", "385", "high"), ("肌酸激酶同工酶(CK-MB)", "38", "high"), ("肌钙蛋白I(cTnI)", "0.15", "high")],
            },
            "summary_normal": "心肌酶谱正常，排除急性心肌损伤",
            "summary_abnormal": "CK、CK-MB、cTnI 升高，提示心肌损伤",
        },
        "血脂四项": {
            "items": [
                {"name": "总胆固醇(TC)", "value": "4.8", "unit": "mmol/L", "reference_range": "<5.2", "abnormal": "normal"},
                {"name": "甘油三酯(TG)", "value": "1.4", "unit": "mmol/L", "reference_range": "<1.7", "abnormal": "normal"},
                {"name": "低密度脂蛋白(LDL-C)", "value": "3.0", "unit": "mmol/L", "reference_range": "<3.4", "abnormal": "normal"},
                {"name": "高密度脂蛋白(HDL-C)", "value": "1.2", "unit": "mmol/L", "reference_range": ">1.0", "abnormal": "normal"},
            ],
            "abnormal_by_dept": {
                "心内科": [("总胆固醇(TC)", "6.2", "high"), ("甘油三酯(TG)", "2.3", "high"), ("低密度脂蛋白(LDL-C)", "4.1", "high")],
                "消化内科": [("甘油三酯(TG)", "2.1", "high"), ("总胆固醇(TC)", "5.6", "high")],
            },
            "summary_normal": "血脂各项正常",
            "summary_abnormal": "TC、TG、LDL-C 升高，高脂血症",
        },
        "血沉": {
            "items": [
                {"name": "红细胞沉降率(ESR)", "value": "12", "unit": "mm/h", "reference_range": "0-20", "abnormal": "normal"},
            ],
            "abnormal_by_dept": {
                "骨科": [("红细胞沉降率(ESR)", "45", "high")],
                "呼吸科": [("红细胞沉降率(ESR)", "38", "high")],
            },
            "summary_normal": "血沉正常",
            "summary_abnormal": "血沉增快，提示炎症或自身免疫",
        },
        "尿常规": {
            "items": [
                {"name": "尿蛋白", "value": "(-)", "unit": "", "reference_range": "(-)", "abnormal": "normal"},
                {"name": "尿潜血", "value": "(-)", "unit": "", "reference_range": "(-)", "abnormal": "normal"},
                {"name": "尿糖", "value": "(-)", "unit": "", "reference_range": "(-)", "abnormal": "normal"},
                {"name": "尿酮体", "value": "(-)", "unit": "", "reference_range": "(-)", "abnormal": "normal"},
                {"name": "尿白细胞", "value": "0-3", "unit": "/HP", "reference_range": "0-5", "abnormal": "normal"},
                {"name": "尿pH", "value": "6.0", "unit": "", "reference_range": "5.0-8.0", "abnormal": "normal"},
            ],
            "abnormal_by_dept": {
                "儿科": [("尿白细胞", "+2", "high"), ("尿蛋白", "+1", "high")],
                "消化内科": [("尿蛋白", "+1", "high")],
                "皮肤科": [("尿白细胞", "+1", "high")],
            },
            "summary_normal": "尿常规正常",
            "summary_abnormal": "尿蛋白/白细胞异常，提示泌尿系问题",
        },
        "肝功能": {
            "items": [
                {"name": "谷丙转氨酶(ALT)", "value": "25", "unit": "U/L", "reference_range": "0-40", "abnormal": "normal"},
                {"name": "谷草转氨酶(AST)", "value": "22", "unit": "U/L", "reference_range": "0-40", "abnormal": "normal"},
                {"name": "总胆红素(TBIL)", "value": "15", "unit": "μmol/L", "reference_range": "5-21", "abnormal": "normal"},
                {"name": "白蛋白(ALB)", "value": "42", "unit": "g/L", "reference_range": "35-55", "abnormal": "normal"},
                {"name": "谷氨酰转肽酶(GGT)", "value": "35", "unit": "U/L", "reference_range": "0-60", "abnormal": "normal"},
            ],
            "abnormal_by_dept": {
                "消化内科": [("谷丙转氨酶(ALT)", "85", "high"), ("谷草转氨酶(AST)", "72", "high"), ("谷氨酰转肽酶(GGT)", "98", "high")],
            },
            "summary_normal": "肝功能正常",
            "summary_abnormal": "ALT、AST、GGT 升高，提示肝实质损伤",
        },
        "肾功能": {
            "items": [
                {"name": "尿素(UREA)", "value": "5.2", "unit": "mmol/L", "reference_range": "2.5-7.1", "abnormal": "normal"},
                {"name": "肌酐(CREA)", "value": "78", "unit": "μmol/L", "reference_range": "44-133", "abnormal": "normal"},
                {"name": "尿酸(UA)", "value": "320", "unit": "μmol/L", "reference_range": "150-420", "abnormal": "normal"},
            ],
            "abnormal_by_dept": {
                "消化内科": [("尿酸(UA)", "480", "high")],
                "心内科": [("尿素(UREA)", "8.5", "high"), ("肌酐(CREA)", "145", "high")],
            },
            "summary_normal": "肾功能正常",
            "summary_abnormal": "尿素/肌酐/尿酸升高，提示肾功能异常",
        },
    }

    # 通用血常规（复用 _mock_blood_items 的异常模式，但简化为 6 项）
    _BLOOD_BASE = [
        {"name": "白细胞计数", "value": "6.8", "unit": "10^9/L", "reference_range": "4-10", "abnormal": "normal"},
        {"name": "红细胞计数", "value": "4.5", "unit": "10^12/L", "reference_range": "3.5-5.5", "abnormal": "normal"},
        {"name": "血红蛋白", "value": "135", "unit": "g/L", "reference_range": "110-160", "abnormal": "normal"},
        {"name": "血小板计数", "value": "210", "unit": "10^9/L", "reference_range": "100-300", "abnormal": "normal"},
        {"name": "中性粒细胞百分比", "value": "58", "unit": "%", "reference_range": "40-75", "abnormal": "normal"},
        {"name": "淋巴细胞百分比", "value": "32", "unit": "%", "reference_range": "20-50", "abnormal": "normal"},
    ]
    _BLOOD_ABNORMAL = {
        "呼吸科": [("白细胞计数", "12.5", "high"), ("中性粒细胞百分比", "82", "high"), ("淋巴细胞百分比", "12", "low")],
        "心内科": [("白细胞计数", "12.8", "high"), ("红细胞计数", "3.1", "low"), ("血红蛋白", "95", "low")],
        "消化内科": [("红细胞计数", "3.0", "low"), ("血红蛋白", "88", "low"), ("平均红细胞体积", "72", "low")],
        "神经内科": [("红细胞计数", "3.2", "low"), ("血红蛋白", "98", "low"), ("白细胞计数", "11.2", "high")],
        "骨科": [("白细胞计数", "15.8", "high"), ("血小板计数", "345", "high"), ("中性粒细胞百分比", "88", "high")],
        "儿科": [("白细胞计数", "18.2", "high"), ("中性粒细胞百分比", "78", "high"), ("淋巴细胞百分比", "14", "low")],
        "皮肤科": [("嗜酸性粒细胞百分比", "8", "high"), ("白细胞计数", "10.8", "high")],
        "眼科": [],
    }

    spec = _LAB_DATA.get(task_label)
    if spec:
        items = [dict(it) for it in spec["items"]]
        abnormal_overrides = spec["abnormal_by_dept"].get(dept, [])
        abnormal_count = 0
        for it in items:
            for name, val, abn in abnormal_overrides:
                if it["name"] == name:
                    it["value"] = val
                    it["abnormal"] = abn
                    break
            if it.get("abnormal") and it["abnormal"] != "normal":
                abnormal_count += 1
        summary = spec["summary_abnormal"] if abnormal_count > 0 else spec["summary_normal"]
        total = len(items)
    elif task_label == "血常规":
        items = [dict(it) for it in _BLOOD_BASE]
        # 添加性别/年龄特异指标
        if gender == "女":
            items[1]["value"] = "4.2"
            items[2]["value"] = "125"
            items[2]["reference_range"] = "110-150"
        if age < 14:
            items[2]["reference_range"] = "110-160"
        abnormal_overrides = _BLOOD_ABNORMAL.get(dept, [])
        abnormal_count = 0
        for it in items:
            for name, val, abn in abnormal_overrides:
                if it["name"] == name:
                    it["value"] = val
                    it["abnormal"] = abn
                    break
            if it.get("abnormal") and it["abnormal"] != "normal":
                abnormal_count += 1
        summary = "各项指标基本正常" if abnormal_count == 0 else f"检出 {abnormal_count} 项异常，提示可能存在{dept}相关问题"
        total = len(items)
    else:
        # 未知检验类型，生成占位
        items = [{"name": task_label, "value": "正常", "unit": "", "reference_range": "—", "abnormal": "normal"}]
        abnormal_count = 0
        summary = f"{task_label} 检测完成"
        total = 1

    ts = now()
    result = {
        "items": items,
        "summary": summary,
        "abnormal_count": abnormal_count,
        "total_count": total,
        "entered_by": "u_lab_01",
        "entered_by_name": "林检验",
        "entered_at": ts,
    }
    report = {
        "report_no": f"LAB-{uid('blrpt')}",
        "report_id": uid("blrpt"),
        "patient_id": pid,
        "patient_name": pname,
        "gender": gender,
        "age": age,
        "department": dept,
        "attending_doctor_id": doctor_id,
        "attending_doctor_name": doctor_name,
        "task_label": task_label,
        "task_id": "",
        "created_by_name": doctor_name,
        "specimen": "静脉血" if task_label != "尿常规" else "晨尿",
        "draw_time": ts,
        "completed_at": ts,
        "issued_at": ts,
        "entered_by": "u_lab_01",
        "entered_by_name": "林检验",
        "entered_at": ts,
        "items": [dict(it) for it in items],
        "summary": summary,
        "abnormal_count": abnormal_count,
        "total_count": total,
        "status": "finalized",
    }
    return {"result": result, "report": report}


def _fill_lab_results():
    """后处理：为所有患者补充已完成检验报告数据。

    策略：
    - pending/ordered 任务 → 部分转为 done（补充 result + report）
    - 无任务的患者 → 按科室添加 1-2 个已完成检验报告
    - p001/p002 已手动填充，跳过
    """
    # 科室默认检验项目（用于无任务患者）
    _DEPT_DEFAULT_TESTS = {
        "呼吸科": ["血常规", "C反应蛋白"],
        "心内科": ["血常规", "心肌酶谱", "血脂四项"],
        "消化内科": ["血常规", "肝功能", "肾功能"],
        "神经内科": ["血常规", "凝血功能", "电解质四项"],
        "骨科": ["血常规", "血沉", "C反应蛋白"],
        "儿科": ["血常规", "C反应蛋白", "尿常规"],
        "眼科": ["血常规"],
        "皮肤科": ["血常规", "C反应蛋白"],
    }

    for pid, state in list(store.patients.items()):
        if pid in ("p001", "p002"):
            continue

        pname = state.get("patient_name", "")
        gender = state.get("gender", "")
        age = state.get("age", 0)
        dept = ""
        doctor_id = ""
        doctor_name = ""

        # 从最近就诊提取科室和医生
        for b in reversed(state.get("bookings", [])):
            if b.get("department"):
                dept = b["department"]
                doctor_id = b.get("doctor_id", "")
                doctor_name = b.get("doctor_name", "")
                break

        if not dept:
            # 从 emr 内容猜测
            emr = state.get("emr_main", {})
            if isinstance(emr, dict):
                content = emr.get("content", "")
                for d in _DEPT_DEFAULT_TESTS:
                    if d in content:
                        dept = d
                        break
        if not dept:
            continue

        tasks = state.get("check_tasks", [])
        existing_labels = {t.get("task_label") for t in tasks}

        # 补全 pending/ordered 任务为 done
        for task in tasks:
            if task.get("status") in ("pending", "ordered") and not task.get("result"):
                lab = _mock_lab_result(
                    task["task_label"], dept, gender, age,
                    pid, pname, doctor_id, doctor_name,
                )
                task["status"] = "done"
                task["completed_at"] = now()
                task["result"] = lab["result"]
                task["report"] = lab["report"]

        # 无任务或只有少量已完成的患者，补充科室默认检验
        if len([t for t in tasks if t.get("status") == "done"]) < 2:
            default_tests = _DEPT_DEFAULT_TESTS.get(dept, ["血常规"])
            for test_label in default_tests:
                if test_label in existing_labels:
                    continue
                lab = _mock_lab_result(
                    test_label, dept, gender, age,
                    pid, pname, doctor_id, doctor_name,
                )
                task_id = uid("tsk")
                tasks.append({
                    "task_id": task_id,
                    "task_type": "blood",
                    "task_label": test_label,
                    "status": "done",
                    "created_at": now(),
                    "created_by": doctor_id,
                    "created_by_name": doctor_name,
                    "completed_at": now(),
                    "result": lab["result"],
                    "report": lab["report"],
                })
                existing_labels.add(test_label)

        store.upsert_patient(state)


def _fill_clinical_data():
    """后处理：为所有患者补充问诊数据（主诉/既往史/过敏史/现病史）。

    按科室生成临床一致的症状描述，与检验报告异常模式匹配，
    供病历 Agent 起草 SOAP 病历时使用。
    """
    # 按科室的临床数据模板：(主诉, 现病史, 既往史, 过敏史)
    _DEPT_CLINICAL = {
        "呼吸科": (
            "咳嗽、咳痰伴发热3天",
            "3天前受凉后出现咳嗽，咳黄白色黏痰，量中等，伴发热，体温最高38.5℃。自服感冒药效果不佳。今起胸闷加重，活动后气短。",
            "慢性支气管炎10年，每年冬春季节发作。高血压5年，规律服用氨氯地平。否认结核、肝炎病史。",
            "否认药物及食物过敏史",
        ),
        "心内科": (
            "胸闷气短伴心悸2天",
            "2天前无明显诱因出现胸骨后压迫感，范围约拳头大小，向左肩放射，持续5-10分钟，休息后可缓解。伴心悸、出汗，活动后气短加重。夜间可平卧，无端坐呼吸。",
            "高血压3年，最高160/100mmHg。高脂血症1年。否认冠心病、糖尿病病史。吸烟20年，每日1包。",
            "否认药物及食物过敏史",
        ),
        "消化内科": (
            "上腹胀痛伴恶心1周",
            "1周前出现上腹部胀痛，呈持续性，进食后加重，伴恶心、反酸，无呕吐。无畏寒发热，无腹泻。大便每日1次，成形，色黄。近1周食欲下降，体重无明显变化。",
            "胆囊结石2年，未治疗。否认消化性溃疡、肝炎病史。不嗜烟酒。",
            "否认药物及食物过敏史",
        ),
        "神经内科": (
            "头痛伴头晕3天",
            "3天前无明显诱因出现左侧搏动性头痛，伴恶心、畏光，持续2-4小时，休息后稍缓解。伴头晕，无旋转感，无视物模糊。无意识障碍，无肢体麻木无力。睡眠差。",
            "偏头痛病史5年，间断发作。否认脑血管病、癫痫病史。",
            "否认药物及食物过敏史",
        ),
        "骨科": (
            "腰背痛伴活动受限1周",
            "1周前搬重物后出现腰部疼痛，呈酸痛，弯腰及起坐时加重，平卧后稍缓解。疼痛向右下肢放射至小腿外侧。无大小便障碍。行走约200米后下肢酸胀加重。",
            "腰椎间盘突出症3年，L4-L5节段，经保守治疗后好转。否认骨折、手术史。",
            "否认药物及食物过敏史",
        ),
        "儿科": (
            "发热伴咳嗽2天（家长代述）",
            "2天前患儿出现发热，体温最高39.0℃，伴咳嗽、流涕，食欲下降，精神稍差。无呕吐腹泻，无抽搐。尿量正常。家长自测体温38.5℃后来诊。既往体健，按时接种疫苗。",
            "既往体健。出生足月顺产，生长发育正常。",
            "否认药物及食物过敏史",
        ),
        "眼科": (
            "视力下降伴眼部异物感1周",
            "1周前自觉双眼视力模糊，以右眼为甚，伴眼部干涩、异物感，偶有流泪。无眼痛、畏光，无眼红分泌物。长期使用电脑工作，每日8小时以上。",
            "近视20年（右-4.50D，左-3.75D）。否认青光眼、白内障病史。无眼部手术史。",
            "否认药物及食物过敏史",
        ),
        "皮肤科": (
            "全身皮疹伴瘙痒1周",
            "1周前四肢出现红色丘疹，逐渐蔓延至躯干，伴明显瘙痒，夜间为甚。无发热、关节痛。未使用新药物或食物。外用润肤乳效果不佳。",
            "湿疹5年，每年春秋季发作。否认银屑病、荨麻疹病史。",
            "磺胺类药物过敏（皮疹史）",
        ),
    }

    # p001/p002 手动设定科室（无 bookings）
    _MANUAL_DEPT = {"p001": "消化内科", "p002": "消化内科"}

    for pid, state in list(store.patients.items()):
        dept = _MANUAL_DEPT.get(pid, "")
        if not dept:
            for b in state.get("bookings", []):
                if b.get("department"):
                    dept = b["department"]
                    break
        if not dept:
            emr = state.get("emr_main", {})
            if isinstance(emr, dict):
                content = emr.get("content", "")
                for d in _DEPT_CLINICAL:
                    if d in content:
                        dept = d
                        break
        if not dept:
            continue

        clinical = _DEPT_CLINICAL.get(dept)
        if not clinical:
            continue

        chief, illness, past, allergy = clinical

        # 只在为空时填充，不覆盖已有数据
        if not state.get("chief_complaint"):
            state["chief_complaint"] = chief
        if not state.get("medical_history"):
            state["medical_history"] = past
        if not state.get("allergy_history"):
            state["allergy_history"] = allergy

        # 补充现病史到 emr_main（供病历 Agent 提取上下文）
        emr = state.get("emr_main", {})
        if isinstance(emr, dict):
            content = emr.get("content", "")
            # locked 病历不覆盖；只在空或极短时填充
            if not emr.get("locked") and (not content or len(content) < 60 or "主诉" not in content):
                emr["content"] = (
                    f"患者{state.get('patient_name','')}，{state.get('gender','')}，"
                    f"{state.get('age','')}岁。\n"
                    f"主诉：{chief}\n"
                    f"现病史：{illness}\n"
                    f"既往史：{past}\n"
                    f"过敏史：{allergy}\n"
                    f"（病历 Agent 可基于此信息起草 SOAP 病历）"
                )
                emr.setdefault("locked", False)
                emr.setdefault("locked_at", None)
                emr.setdefault("locked_by", None)
                emr.setdefault("locked_by_name", None)
                emr.setdefault("reports", [])
                state["emr_main"] = emr

        store.upsert_patient(state)


def _fill_imaging_results():
    """后处理：为所有患者补充影像检查报告（CT/B超/X光/MRI）。

    按科室生成临床一致的影像报告，findings/impression 文本含关键词
    以触发 image_interpretation_subagent 的疾病信号匹配规则。
    """
    # 按科室的影像模板：(task_type, task_label, organ, findings, impression)
    _DEPT_IMAGING = {
        "呼吸科": [
            ("ct", "胸部CT", "胸部",
             "双肺纹理增多，右肺下叶可见斑片状密度增高影，边界模糊。双肺未见明显占位。心影不大，双侧胸腔未见积液。",
             "右肺下叶斑片影，考虑炎症性病变；建议抗炎治疗后复查。"),
        ],
        "心内科": [
            ("ultrasound", "心脏彩超", "心脏",
             "各房室大小正常范围。室壁运动协调，未见明显节段性运动异常。主动脉根部内径正常。LVEF 58%。心包腔未见积液。",
             "心脏结构及功能大致正常。LVEF 58%。"),
            ("ct", "胸部CT", "胸部",
             "双肺未见明显斑片影及占位。主动脉弓可见钙化。心影增大，以左心室为主。双侧胸腔未见积液。",
             "主动脉硬化；左心室增大，建议结合临床。"),
        ],
        "消化内科": [
            ("ultrasound", "腹部B超", "腹部",
             "肝脏大小形态正常，实质回声均匀。胆囊大小正常，胆囊颈部可见强回声光团，直径约 12mm，伴声影。胆总管内径正常。胰腺、脾脏未见异常。",
             "胆囊结石（单发，约 12mm）；肝、胰、脾未见异常。"),
        ],
        "神经内科": [
            ("ct", "头颅CT", "头部",
             "双侧大脑半球对称，脑实质内未见明显异常密度影。脑室系统无扩张或受压。中线结构居中。颅骨骨质连续。",
             "头颅CT未见明显异常。"),
        ],
        "骨科": [
            ("xray", "腰椎正侧位", "腰椎",
             "腰椎生理曲度存在。L4-L5 椎间隙略变窄，椎体前缘可见骨质增生。未见明显滑脱。",
             "腰椎退行性变；L4-L5 椎间隙变窄，考虑椎间盘病变可能。"),
        ],
        "儿科": [
            ("xray", "胸部正位", "胸部",
             "双肺纹理增多，右肺中叶可见斑片状密度增高影。心影不大。双侧肋膈角锐利。",
             "右肺斑片影，考虑支气管肺炎可能。"),
        ],
        "眼科": [
            ("ultrasound", "眼部B超", "眼部",
             "双眼玻璃体腔内未见明显混浊。双眼球壁光滑，未见视网膜脱离。视神经乳头回声正常。",
             "双眼B超未见明显异常。"),
        ],
        "皮肤科": [
            ("xray", "胸部正位", "胸部",
             "双肺未见明显斑片影及占位。心影不大。双侧胸腔未见积液。",
             "胸部X光未见明显异常。"),
        ],
    }

    # p001 手动科室映射
    _MANUAL_DEPT_I = {"p001": "消化内科", "p002": "消化内科"}

    for pid, state in list(store.patients.items()):
        dept = _MANUAL_DEPT_I.get(pid, "")
        if not dept:
            for b in state.get("bookings", []):
                if b.get("department"):
                    dept = b["department"]
                    break
        if not dept:
            continue

        imaging_specs = _DEPT_IMAGING.get(dept)
        if not imaging_specs:
            continue

        tasks = state.get("check_tasks", [])
        existing_labels = {t.get("task_label") for t in tasks}
        ts = now()
        # 影像技师 actor
        img_tech = {"user_id": "u_img_01", "name": "周影像"}

        # 1. 补全已有的影像 pending/ordered 任务
        for task in tasks:
            if task.get("task_type") in ("ct", "ultrasound", "xray", "mri"):
                if task.get("status") in ("pending", "ordered") and not task.get("result"):
                    # 找匹配的影像模板
                    for spec in imaging_specs:
                        if spec[1] == task.get("task_label"):
                            findings, impression = spec[3], spec[4]
                            task["status"] = "done"
                            task["completed_at"] = ts
                            task["result"] = {
                                "findings": findings,
                                "impression": impression,
                                "summary": "影像报告已发布",
                                "entered_by": img_tech["user_id"],
                                "entered_by_name": img_tech["name"],
                                "entered_at": ts,
                            }
                            task["report"] = {
                                "report_no": f"IMG-{uid('imgrpt')}",
                                "report_id": uid("imgrpt"),
                                "patient_id": pid,
                                "patient_name": state.get("patient_name", ""),
                                "exam_type": spec[0],
                                "exam_label": spec[1],
                                "organ": spec[2],
                                "findings": findings,
                                "impression": impression,
                                "entered_by": img_tech["user_id"],
                                "entered_by_name": img_tech["name"],
                                "entered_at": ts,
                                "status": "finalized",
                            }
                            break

        # 2. 补充不存在的影像检查（按科室默认）
        for spec in imaging_specs:
            task_type, label, organ, findings, impression = spec
            if label in existing_labels:
                continue
            task_id = uid("tsk")
            tasks.append({
                "task_id": task_id,
                "task_type": task_type,
                "task_label": label,
                "status": "done",
                "created_at": ts,
                "created_by": img_tech["user_id"],
                "created_by_name": img_tech["name"],
                "completed_at": ts,
                "result": {
                    "findings": findings,
                    "impression": impression,
                    "summary": "影像报告已发布",
                    "entered_by": img_tech["user_id"],
                    "entered_by_name": img_tech["name"],
                    "entered_at": ts,
                },
                "report": {
                    "report_no": f"IMG-{uid('imgrpt')}",
                    "report_id": uid("imgrpt"),
                    "patient_id": pid,
                    "patient_name": state.get("patient_name", ""),
                    "exam_type": task_type,
                    "exam_label": label,
                    "organ": organ,
                    "findings": findings,
                    "impression": impression,
                    "entered_by": img_tech["user_id"],
                    "entered_by_name": img_tech["name"],
                    "entered_at": ts,
                    "status": "finalized",
                },
            })
            existing_labels.add(label)

        store.upsert_patient(state)


# 导入即播种（M1 幂等护栏：DB 已有数据则跳过，重启不重灌）
if not store._db_loaded:
    seed_all(store)
    store.persist_all()
    store.mark_seeded()
