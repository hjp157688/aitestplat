def repoint_gtc_requirement(apps, schema_editor):
    """把 GeneratedTestCase.requirement_id 从 BusinessRequirement.id 重指向到迁移后的 Requirement.id。

    此时 GTC.requirement FK 在 DB 层仍指向 business_requirements 表（AlterField 尚未执行），
    故临时禁用 FK 检查以允许写入 Requirement ID；随后的 AlterField 会把 FK 约束改为指向 requirements 表。
    """
    from django.db import connection
    GTC = apps.get_model('requirement_analysis', 'GeneratedTestCase')
    BR = apps.get_model('requirement_analysis', 'BusinessRequirement')
    Requirement = apps.get_model('requirement_analysis', 'Requirement')

    with connection.cursor() as c:
        c.execute('SET FOREIGN_KEY_CHECKS=0')
    try:
        for gtc in GTC.objects.all():
            try:
                br = BR.objects.get(id=gtc.requirement_id)
            except BR.DoesNotExist:
                continue
            req = Requirement.objects.filter(
                requirement_id=br.requirement_id, source_type='ai_import'
            ).first()
            if req:
                gtc.requirement_id = req.id
                gtc.save(update_fields=['requirement_id'])
    finally:
        with connection.cursor() as c:
            c.execute('SET FOREIGN_KEY_CHECKS=1')


def unpoint_gtc_requirement(apps, schema_editor):
    """反向迁移：把 GTC.requirement_id 从 Requirement.id 还原为原 BusinessRequirement.id。

    AlterField 反转（FK 改回 business_requirements）会先于本函数执行（Django 逆序回滚），
    故此处需禁用 FK 检查；还原后 GTC.requirement_id 为合法 BR.id。
    """
    from django.db import connection
    GTC = apps.get_model('requirement_analysis', 'GeneratedTestCase')
    BR = apps.get_model('requirement_analysis', 'BusinessRequirement')
    Requirement = apps.get_model('requirement_analysis', 'Requirement')

    with connection.cursor() as c:
        c.execute('SET FOREIGN_KEY_CHECKS=0')
    try:
        for gtc in GTC.objects.all():
            try:
                req = Requirement.objects.get(id=gtc.requirement_id)
            except Requirement.DoesNotExist:
                continue
            br = BR.objects.filter(
                requirement_id=req.requirement_id
            ).first()
            if br:
                gtc.requirement_id = br.id
                gtc.save(update_fields=['requirement_id'])
    finally:
        with connection.cursor() as c:
            c.execute('SET FOREIGN_KEY_CHECKS=1')