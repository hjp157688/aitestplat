# -*- coding: utf-8 -*-
# 手工编写迁移：以 WeKnora 彻底替换自研 ChromaDB 知识库。
# - 新增 weknora_configs / weknora_project_bindings
# - 删除 knowledge_documents / knowledge_entries
# - AIModelConfig.role 移除 embedding/tokenizer；PromptConfig.prompt_type 移除 knowledge_*
# - 历史数据：禁用 embedding/tokenizer 配置、删除 knowledge_* 提示词行
# 提示：请以 `python manage.py makemigrations requirement_analysis --check` 核对该迁移
# 与模型一致；若有差异以 makemigrations 生成为准。

from django.db import migrations, models
import django.db.models.deletion


def disable_legacy_roles(apps, schema_editor):
    AIModelConfig = apps.get_model('requirement_analysis', 'AIModelConfig')
    AIModelConfig.objects.filter(role__in=['embedding', 'tokenizer']).update(is_active=False)


def delete_legacy_prompts(apps, schema_editor):
    PromptConfig = apps.get_model('requirement_analysis', 'PromptConfig')
    PromptConfig.objects.filter(
        prompt_type__in=['knowledge_structure', 'knowledge_section', 'knowledge_rerank']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('requirement_analysis', '0015_testcase_generation_task_requirement_fk'),
    ]

    operations = [
        migrations.RunPython(disable_legacy_roles, migrations.RunPython.noop),
        migrations.RunPython(delete_legacy_prompts, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='aimodelconfig',
            name='role',
            field=models.CharField(choices=[('writer', '测试用例编写专家'), ('reviewer', '测试评审专家'), ('browser_use_text', 'Browser Use - 文本模式'), ('api_testcase_generator', '接口测试用例生成'), ('doc_extractor', 'API文档提取'), ('naming', '参数命名规范化'), ('mock_data', '模拟数据生成'), ('description', '参数描述补全')], max_length=30, verbose_name='角色'),
        ),
        migrations.AlterField(
            model_name='promptconfig',
            name='prompt_type',
            field=models.CharField(choices=[('writer', '用例编写提示词'), ('reviewer', '用例评审提示词'), ('requirement_parse', '需求解析提示词'), ('api_testcase_generator', '接口测试用例生成'), ('browser_use_task', 'Browser Use-执行任务'), ('browser_use_breakdown', 'Browser Use-任务拆分')], max_length=30, verbose_name='提示词类型'),
        ),
        migrations.CreateModel(
            name='WeKnoraConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('base_url', models.CharField(default='http://localhost:8080', max_length=255, verbose_name='WeKnora Base URL')),
                ('api_key', models.CharField(blank=True, default='', max_length=500, verbose_name='API Key')),
                ('timeout', models.IntegerField(default=30, verbose_name='超时(秒)')),
                ('default_agent_id', models.CharField(blank=True, default='', max_length=100, verbose_name='默认智能体ID')),
                ('default_agent_name', models.CharField(blank=True, default='', max_length=200, verbose_name='默认智能体名称')),
                ('knowledge_base_ids', models.JSONField(blank=True, default=list, verbose_name='默认知识库ID列表')),
                ('enabled', models.BooleanField(default=False, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'db_table': 'weknora_configs',
                'verbose_name': 'WeKnora 配置',
                'verbose_name_plural': 'WeKnora 配置',
            },
        ),
        migrations.CreateModel(
            name='WeKnoraProjectBinding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('agent_id', models.CharField(max_length=100, verbose_name='WeKnora 智能体ID')),
                ('agent_name', models.CharField(blank=True, default='', max_length=200, verbose_name='智能体名称')),
                ('knowledge_base_ids', models.JSONField(blank=True, default=list, verbose_name='知识库ID列表')),
                ('enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('project', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='weknora_binding', to='projects.project', verbose_name='项目')),
            ],
            options={
                'db_table': 'weknora_project_bindings',
                'verbose_name': 'WeKnora 项目绑定',
                'verbose_name_plural': 'WeKnora 项目绑定',
            },
        ),
        migrations.DeleteModel(
            name='KnowledgeEntry',
        ),
        migrations.DeleteModel(
            name='KnowledgeDocument',
        ),
    ]
