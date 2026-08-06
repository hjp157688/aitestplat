def migrate_business_requirements(apps, schema_editor):
    Requirement = apps.get_model('requirement_analysis', 'Requirement')
    BusinessRequirement = apps.get_model('requirement_analysis', 'BusinessRequirement')
    Project = apps.get_model('projects', 'Project')
    User = apps.get_model('users', 'User')

    owner, _ = User.objects.get_or_create(
        username='ai_migration_default',
        defaults={'is_active': False},
    )
    project, _ = Project.objects.get_or_create(
        name='AI分析需求默认项目',
        defaults={
            'description': '迁移自 BusinessRequirement 的 AI 分析需求',
            'owner': owner,
        },
    )

    id_map = {}
    for br in BusinessRequirement.objects.all():
        r = Requirement.objects.create(
            project=project,
            source_type='ai_import',
            title=br.requirement_name or br.requirement_id,
            spec=br.description or '',
            category=br.requirement_type or '',
            requirement_id=br.requirement_id or '',
            requirement_level=br.requirement_level or '',
            acceptance_criteria=br.acceptance_criteria or '',
            module_name=br.module or '',
            analysis_id=br.analysis_id,
        )
        id_map[br.id] = r.id

    # 重指向 parent_requirement
    for br in BusinessRequirement.objects.all():
        if br.parent_requirement_id and br.parent_requirement_id in id_map:
            new_id = id_map[br.id]
            new_parent = id_map[br.parent_requirement_id]
            Requirement.objects.filter(id=new_id).update(parent_requirement_id=new_parent)


def remove_business_requirements(apps, schema_editor):
    # 回滚：删除迁移过来的 AI 来源 Requirement（不可完全还原，仅删 source_type=ai_import）
    Requirement = apps.get_model('requirement_analysis', 'Requirement')
    Requirement.objects.filter(source_type='ai_import').delete()