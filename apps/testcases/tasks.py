from celery import shared_task

from .services import execute_import_record


@shared_task(bind=True)
def import_testcases_from_excel(self, record_id: int):
    """用例 Excel 导入（异步）。实际逻辑在 services.execute_import_record，
    便于 Redis/Celery 不可用时在请求内同步降级复用。"""
    return execute_import_record(record_id, celery_task_id=self.request.id or '')
