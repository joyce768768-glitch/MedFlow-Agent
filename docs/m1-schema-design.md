# M1 · MedFlow 落底座 —— SQLite 表结构设计（评审稿）

> 状态：**已实施 ✅**（2026-10-28，全部验证通过，见文末偏差记录）
> 依据：`semantic-contract/examples/medflow-exam-report.yaml` 的 physical_mapping + storage.py / graph/state.py / mock_data.py 全量实审（2026-10-28）
> 原则：**routers 零改动**（Store 接口 100% 兼容）、exam 域关系表为唯一真相源、其余域文档化存储

---

## 一、现状结论（实审，非印象）

| 现状 | 事实 |
|---|---|
| KG 侧已有底座 | `chinese-medical-kg-main/ontology/data/medical_kg.db`（entities/relations/aliases + L0 溯源/L1a 参考/L2 本体镜像/L3 审核队列），**不动** |
| 业务侧无底座 | storage.py 1815 行，进程内单例 Store，重启全丢 |
| 写路径已收敛 | check_tasks / mdt_comments / notify_queue 的全部运行时写操作都经 `store.patch_patient(全量列表替换)` 或专用方法——写穿透有统一抓手 |
| 读路径发散 | graph/abox.py、temporal_query.py、多个 router 直接读 `store.patients` / `store.users` 等 dict 属性——**属性必须保留** |
| 种子在 import 时灌入 | mock_data.py 末行 `seed_all(store)`，部分直接改 `store.patients[pid]` dict |
| venv | Python 3.9.6，无 SQLAlchemy（需安装 2.0.x） |

## 二、设计总纲

```
┌─────────────────────────────────────────────────────┐
│  Store（接口层 · 170 方法签名不变 + dict 属性保留）      │
│  内存 dict = 读写缓存，重启时从 SQLite 全量加载           │
├─────────────────────────────────────────────────────┤
│  写穿透（Write-Through）                               │
│  ① 通用 mutation 方法 → 单行 upsert/delete             │
│  ② patch_patient 拦截器：check_tasks → exam_reports    │
│     + exam_items；mdt_comments → mdt_comments；        │
│     notify_queue → notifications（全量替换语义）        │
│  ③ persist_all() 兜底：种子灌完后整体落盘               │
├─────────────────────────────────────────────────────┤
│  SQLite（backend/data/medflow_app.db · WAL 模式）      │
│  与 KG 库 medical_kg.db 物理分离                        │
└─────────────────────────────────────────────────────┘
ABox（OGraph）不建新表：build_from_store 读 SQLite-backed
Store，仍是内存投影——业务表为唯一真相源，图是派生物。
```

**patient 文档 + 剥离表的回填模型**（这是本设计的关键决策）：

- `patients.state_json` 存 PatientState 全量文档，但 **check_tasks / mdt_comments / notify_queue / audit_log 四个集合不存**（它们已升格为关系表）
- `get_patient()` 每次从关系表回填这四个集合 → 上层代码（subagents/nodes/routers）看到的仍是完整 PatientState dict，**零感知**
- 结果：exam 域、MDT 域、通知、审计的唯一真相源是 SQL 表——契约的 tat_hours 公式可以直接对表跑

## 三、表清单（23 张 = A 档 4 + B 档 9 + C 档 9 + KV 1）

### A 档 · 医疗流程域（契约对齐，M2 指标直接消费）

**1. `patients`** — 患者主表 + PatientState 文档

```sql
CREATE TABLE patients (
    patient_id          TEXT PRIMARY KEY,
    patient_name        TEXT NOT NULL,
    gender              TEXT,
    age                 TEXT,
    department          TEXT,
    status              TEXT,              -- waiting / in_progress / archived
    hitl_pending        INTEGER DEFAULT 0,
    attending_doctor_ids TEXT,             -- JSON 数组
    state_json          TEXT NOT NULL,     -- PatientState 文档（不含四个已剥离集合）
    created_at          TEXT,
    updated_at          TEXT
);
CREATE INDEX idx_patients_status ON patients(status);
```

**2. `exam_reports`** — 契约 primary 表（源：CheckTask 流转）

```sql
CREATE TABLE exam_reports (
    task_id         TEXT PRIMARY KEY,      -- = CheckTask.task_id
    patient_id      TEXT NOT NULL,
    task_type       TEXT NOT NULL,         -- blood / ct / ultrasound
    task_label      TEXT,
    status          TEXT NOT NULL,         -- ordered / pending / done（见决策点 1）
    ordered_at      TEXT,                  -- = created_at；契约 tat_hours 公式引用此列名
    created_by      TEXT,
    created_by_name TEXT,
    completed_at    TEXT,
    flag            TEXT,                  -- normal / abnormal / critical（从 result 提取）
    result_json     TEXT,                  -- 完成后结构化结果整体保留
    source          TEXT DEFAULT 'flow',   -- seed / flow
    created_at      TEXT,
    updated_at      TEXT
);
CREATE INDEX idx_exam_reports_patient ON exam_reports(patient_id);
CREATE INDEX idx_exam_reports_status  ON exam_reports(status, completed_at);
```

**3. `exam_items`** — 契约 detail 表（源：result 内项目拆行）

```sql
CREATE TABLE exam_items (
    item_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id  TEXT NOT NULL,              -- → exam_reports.task_id
    code       TEXT,
    name       TEXT,
    value_text TEXT,                       -- 结果值（字符串宽容存）
    unit       TEXT,
    ref_range  TEXT,
    flag       TEXT,                       -- normal / abnormal / critical
    sort_no    INTEGER DEFAULT 0
);
CREATE INDEX idx_exam_items_report ON exam_items(report_id);
```

**4. `exam_item_dict`** — 检验项目字典（现 `store.exam_items`；**命名刻意避开契约 detail 表 exam_items**，字典属主数据不进契约）

```sql
CREATE TABLE exam_item_dict (
    item_id    TEXT PRIMARY KEY,
    code       TEXT,
    name       TEXT,
    category   TEXT,                       -- blood / ct / ultrasound
    spec       TEXT,
    ref_range  TEXT,
    created_at TEXT
);
```

### B 档 · 主数据与资源（每行一实体 + extra_json 兜底列）

| # | 表 | 主键 | 关键列（其余进 extra_json） |
|---|---|---|---|
| 5 | `users` | user_id | username(UNIQUE) password name role department title dept_lead active |
| 6 | `patient_users` | patient_id | patient_name medical_card_number phone gender age |
| 7 | `departments` | dept_id | name |
| 8 | `buildings` | building_id | name, floors_json（楼层/房间层级整体 JSON——空间主数据低频聚合，不拆表） |
| 9 | `kb_entries` | kb_id | category title content tags_json |
| 10 | `rag_docs` | doc_id | title category content status chunks_json(含 Mock 向量) |
| 11 | `prompt_resources` | prompt_id | name agent_key department content versions_json(版本历史) created_by |
| 12 | `schema_resources` | schema_id | name agent_key department json_schema versions_json created_by |
| 13 | `model_resources` | model_id | provider model base_url api_key timeout bound_agents_json |

> 所有 B 档表统一加 `created_at / updated_at / extra_json` 三列；列只建「被方法签名显式使用」的字段，其余进 extra_json——**避免列清单追着 dict 字段跑**。

### C 档 · 事件 / 会话 / 审计（追加型，只增不删）

| # | 表 | 主键 | 关键列 | 收敛说明 |
|---|---|---|---|---|
| 14 | `mdt_comments` | comment_id | patient_id(索引) author_id author_name author_role content is_adopted adopted_by adopted_at created_at | 从 state_json 升格（M2「MDT 会诊量」指标直接 SQL） |
| 15 | `treatment_versions` | version_id | patient_id(索引) version_no content created_by created_by_name created_at | 从 state_json 升格（病案归档 list_archived_cases 要统计） |
| 16 | `audit_log` | log_id | patient_id(索引) action actor_id actor_name detail created_at | 患者级审计，append_audit 写表 |
| 17 | `notifications` | notify_id | patient_id target_user_id(索引) type message read created_at | list_notifications 从全患者遍历变单表索引查询 |
| 18 | `system_audit_log` | log_id | operator_id operator_name action target_kind target_id detail created_at | 跨患者系统审计 |
| 19 | `patient_events` | event_id | patient_id(索引) event_type payload_json created_at | 患者端埋点 |
| 20 | `chat_messages` | msg_id | channel(emr/prediction/unified/research) owner_id(索引) role content extra_json created_at | **四类会话 dict 收敛一张表**——channel 区分，消灭四个平行 dict |
| 21 | `adoption_records` | id(auto) | patient_id(索引) agent_type msg_id content created_at | 统一对话采纳留痕 |
| 22 | `memory_cards` | card_id | owner_type(doctor/patient/system) owner_id(索引) card_type frozen card_json created_at | L2 医生/患者记忆 + L3 crystallized 同表（owner_type='system'），list_crystallized 免遍历 |

> `triage_sessions / bookings / visit_timeline / nurse_requests / consultation_*` 等低频大字段**留在 state_json 文档内**，M1 不升格（无跨患者聚合需求，升格无收益）。

### KV 档

**23. `app_kv`** — 单例配置统一收口

```sql
CREATE TABLE app_kv (
    key        TEXT PRIMARY KEY,   -- subagent_config / permission_matrix / agent_config
                                   -- / agent_resource_ids / chat_status:{patient_id} / seed_done
    value_json TEXT NOT NULL,
    updated_at TEXT
);
```

> agent_config（8 个 Agent 的灰度/模型/Prompt 引用）整体一个 key 存 JSON——它是低频写、整体读的配置块，拆行无收益。

## 四、Store 兼容策略（routers 零改动的保证）

1. **属性保留**：`store.users` / `store.patients` / `store.departments` 等仍是 dict——启动时从 SQLite 全量加载进内存（演示级数据量 < 10MB），此后作为读写缓存
2. **方法签名不变**：170 个方法全部保留，内部 mutation 方法末尾追加 `_persist_*()` 写穿透 hook（每个 1-3 行）
3. **patch_patient 拦截器**（本设计核心机关）：
   ```
   patch_patient(pid, patch):
       state.update(patch)                        # 原语义不变
       if "check_tasks"   in patch: sync_exam_reports(pid, patch["check_tasks"])    # 全量替换
       if "mdt_comments"  in patch: sync_mdt_comments(pid, patch["mdt_comments"])
       if "notify_queue"  in patch: sync_notifications(pid, patch["notify_queue"])
       write patients.state_json（不含三个剥离集合）
   ```
   实测全库 `patch["check_tasks"] / ["mdt_comments"] / ["notify_queue"]` 均为**全量列表替换**语义（nodes.py / mdt.py / lab_worklist.py），无增量 append patch——全量替换写法成立
4. **get_patient() 回填**：读 state_json 后从 exam_reports / mdt_comments / notifications / audit_log 四表回填对应集合，上层零感知
5. **persist_all() 兜底**：种子灌完后整体落盘（mock_data 存在直接改 `store.patients[pid]` 的路径，run-at-import 的种子代码不改逻辑，靠兜底保证落库）
6. **幂等种子**：app_kv 存 `seed_done` 标记；DB 已有数据则跳过 seed_all——**重启不重灌**（持久化的前提）

## 五、新增/改动文件清单

| 文件 | 动作 | 内容 |
|---|---|---|
| `app/database.py` | 新建 | engine（WAL + busy_timeout + check_same_thread=False）、Session 工厂、23 张表 SQLAlchemy 模型、ensure_schema() |
| `app/storage.py` | 改造 | Store 内部接 database.py；写穿透 + 回填 + persist_all + 启动加载；方法签名/属性全保留 |
| `app/mock_data.py` | 微改 | 末行 seed_all 包上幂等判断；`_fill_*` 系列收尾统一调 store.persist_all() |
| `main.py` | 微改 | 启动时 ensure_schema()（种子幂等逻辑在 mock_data 内） |
| `requirements.txt` | 追加 | SQLAlchemy>=2.0 |
| `docs/m1-schema-design.md` | 新建 | 本文档（评审后随代码 commit） |

**不动**：graph/ontology.py（TBox）、graph/abox.py（投影不改）、kg_adapter / kg_management（KG 库自成体系）、全部 routers/、前端。

## 六、验证计划（评审通过后执行）

1. `pip install sqlalchemy` → 启动 uvicorn 8002 → 首次启动建库 + 种子落库
2. **冒烟**：登录 attending/123456 → 工作台 → 患者列表 / 检验工作台 / MDT 正常
3. **持久性**：API 开立一个检查任务并流转到 done → 重启 uvicorn → 数据仍在；`sqlite3` 直查 `exam_reports` 有新行
4. **契约对齐实证**：对 medflow_app.db 跑契约 tat_hours 公式——
   `SELECT patient_id, avg((julianday(completed_at)-julianday(ordered_at))*24.0) FROM exam_reports WHERE completed_at IS NOT NULL GROUP BY patient_id;`
   （M2 编译器要生成的就是这条 SQL）
5. Playwright 复用 design-handoff 脚本模式做前端回归（channel:'chrome' + route abort 外部请求）

## 七、待拍板决策点（4 个）

1. **status 枚举口径**：DB 存现枚举 `ordered/pending/done` + 契约 YAML 补一行映射说明（`done→completed, pending→testing`，M2 编译器负责翻译）？——**推荐**，前端与全部 API 零改动。反方案（DB 直接换契约枚举）要动 mock_data/lab_worklist/前端渲染，M1 不值
2. **mdt_comments / treatment_versions 升格**：M1 顺手升格关系表（写路径已收敛，零额外成本，M2「MDT 会诊量」直接用）？——**推荐升格**
3. **SQLAlchemy vs 原生 sqlite3**：规划文档承诺 SQLAlchemy（作品集叙事一致），KG 侧 kg_adapter 用原生 sqlite3 两库互不影响——**推荐 SQLAlchemy 2.0**
4. **业务库位置**：`backend/data/medflow_app.db`（.gitignore 掉 db 文件，种子随时可重建）——**推荐**，与 KG 库物理分离

---

*评审通过 → 按「五、文件清单」顺序实施 → 六、验证 → commit 进 MedFlow-Agent 仓库。*

---

## 八、实施偏差记录（2026-10-28）

1. **写穿透机制降粒度**：设计稿为「逐 mutation 方法埋点（约 77 处 hook）」；实施改为 **请求边界统一 flush**——main.py HTTP 中间件在每个请求结束后调 `store.persist_all()`（全部业务表按域整体 DELETE+INSERT，单事务）。理由：种子灌库、后台路径、直接 dict 变更全部自动覆盖，零埋点遗漏风险；演示级数据量（<10MB）单次 flush 毫秒级。语义等价：内存 = 运行时真相源，SQLite = 重启恢复真相源。
2. **剥离集合扩为 6 个**：设计稿剥离 4 个（check_tasks / mdt_comments / notify_queue / audit_log），实施时 treatment_versions / memory_cards 一并剥离——后者本就在决策点 2 的升格清单内，统一走「关系表为磁盘真相源 + 加载回填」同一模式。
3. **新增 file**：`app/database.py`（engine + 23 张表模型 + row↔dict 通用转换 + ensure_schema 幂等建表）；`app/storage.py` 新增持久化层三方法（`_load_from_db` / `persist_all` / `mark_seeded`），原有 170 方法签名与 dict 属性零改动。
4. **患者表 department 允许 NULL**：种子实审发现 PatientState 顶层无 department（科室经由「患者 → 主治医生 → 科室」关系派生），NULL 是语义正确而非缺数据；M2 的 tat_by_department 视图按关系 join。
5. **契约 YAML 补注**（Ontology研究/semantic-contract 仓库）：exam_reports.status 落库沿用运行时枚举 ordered/pending/done，YAML 增加 runtime_enum/contract_enum/translator 三行映射说明（done→completed，pending→testing，M2 编译器负责）。

**验证结果**：首启建库+种子（22 users / 21 patients / 77 exam_reports / 290 exam_items 全落库）→ 进程 2 重启加载一致（`_db_loaded=True` 跳过种子、六集合回填正确）→ TestClient 开单 task_328e2f32 → **重启后仍在、exam_reports 77→78** → 契约 tat_hours 公式直接对表执行出数 → OAG 回归 26/26 通过 → uvicorn 8002 启动正常。
