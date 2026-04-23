"""
Scheduled AI reports sent to Telegram (Multi-Tenant).
Iterates through all active organisations to deliver personalised reports.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)
_scheduler = None

def _run_tenant_reports(app, report_type='daily'):
    """Iterates over all organisations and sends the requested report."""
    with app.app_context():
        from models import Organisation, AppSetting, TenantModule
        from ai_engine import get_sales_summary, get_stock_summary, get_insights, get_predictions
        from notifications import notify_async

        tenants = Organisation.query.filter_by(is_active=True).all()
        for t in tenants:
            try:
                # 1. Check if the AI module is enabled for this tenant
                if not TenantModule.is_enabled_for(t.id, 'ai_analytics'):
                    continue

                if report_type == 'daily':
                    if AppSetting.get('scheduler_daily_report', 'true', org_id=t.id) != 'true':
                        continue
                    
                    sales = get_sales_summary(t.id)
                    stock = get_stock_summary(t.id)
                    notify_async(t.id, 
                        f"🌅 <b>Daily Business Report</b>\n\n"
                        f"<b>Sales Summary:</b>\n{sales}\n\n"
                        f"<b>Stock Status:</b>\n{stock}"
                    )

                elif report_type == 'weekly':
                    if AppSetting.get('scheduler_weekly_report', 'true', org_id=t.id) != 'true':
                        continue

                    insights = get_insights(t.id)
                    predictions = get_predictions(t.id)
                    
                    health = insights.get('health_rating', 'AMBER')
                    health_icon = {'GREEN': '🟢', 'AMBER': '🟡', 'RED': '🔴'}.get(health, '⚪')
                    
                    summary = insights.get('summary', 'No summary available.')
                    urgent = '\n'.join(f"⚡ {a}" for a in insights.get('urgent_actions', [])[:3])
                    
                    notify_async(t.id,
                        f"📊 <b>Weekly Business Performance</b>\n\n"
                        f"{health_icon} <b>Health:</b> {health}\n"
                        f"{summary}\n\n"
                        f"<b>Urgent Actions:</b>\n{urgent or 'None ✅'}\n\n"
                        f"<b>Forecast:</b>\n{predictions}"
                    )
            except Exception as e:
                log.error(f"Failed to generate {report_type} report for org {t.id}: {e}")

def init_scheduler(app):
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(daemon=True)

    # Daily reports at 8:00 AM
    _scheduler.add_job(
        _run_tenant_reports,
        trigger=CronTrigger(hour=8, minute=0),
        args=[app, 'daily'],
        id='daily_reports',
        replace_existing=True,
    )

    # Weekly reports on Monday at 8:30 AM
    _scheduler.add_job(
        _run_tenant_reports,
        trigger=CronTrigger(day_of_week='mon', hour=8, minute=30),
        args=[app, 'weekly'],
        id='weekly_reports',
        replace_existing=True,
    )

    _scheduler.start()
    log.info("Multi-tenant scheduler started.")

def shutdown_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
