# -*- coding: utf-8 -*-
"""项目⇄RAGFlow dataset 绑定计算与 embedding 一致性校验(纯逻辑,无 HTTP/view)

- global_dataset_name / project_dataset_name: 自动库命名约定
- dataset_ids_for: 检索用 dataset 集合 = 全局库 + 该项目 enabled 绑定;
  无 enabled 绑定时回退到项目自动库
- write_target_dataset: 写库 = is_write_target 的那一个,否则回退项目自动库
- validate_binding_embedding: 项目绑定集合内 embedding 一致性校验
  (global_embedding 参数为后续 Task 11 预留,把全局配置的 embedding 也纳入比较)
"""
from apps.requirement_analysis.models import RagflowBinding


def global_dataset_name():
    return "aitestplat_global"


def project_dataset_name(project_id):
    return f"aitestplat_proj_{project_id}"


def _enabled_bindings(project_id):
    return list(RagflowBinding.objects.filter(project_id=project_id, enabled=True).order_by("id"))


def dataset_ids_for(project_id):
    ids = [global_dataset_name()]
    bindings = _enabled_bindings(project_id)
    if bindings:
        ids.extend(b.dataset_id for b in bindings)
    else:
        ids.append(project_dataset_name(project_id))
    return ids


def write_target_dataset(project_id):
    bindings = _enabled_bindings(project_id)
    for b in bindings:
        if b.is_write_target:
            return b.dataset_id
    return project_dataset_name(project_id)


def validate_binding_embedding(project_id, global_embedding=""):
    """返回不一致说明列表;空=一致"""
    bindings = _enabled_bindings(project_id)
    if not bindings:
        return []
    models = {b.dataset_name or b.dataset_id: b.embedding_model for b in bindings if b.embedding_model}
    if not models:
        return []
    base = next(iter(models.values()))
    return [f"{name}:{model}" for name, model in models.items() if model != base]
