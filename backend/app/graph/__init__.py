"""graph 子包：LangGraph State / Nodes / Workflow / OAG 底座。"""

from .ontology import (
    EntityType,
    RelType,
    TBoxNode,
    TBoxEdge,
    AxiomViolation,
    validate_entity_fields,
    validate_rel_type,
    validate_valid_time,
    validate_belong_to_uniqueness,
    validate_visit_cardinality,
    validate_identity_mutex,
)

from .abox import OGraph, get_ograph, reset_ograph

from .temporal_query import (
    patient_full_chain,
    visit_context_isolation,
    doctor_on_duty,
    graph_health_check,
)
