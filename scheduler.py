"""
Scheduled AI reports sent to Telegram.
Configurable via AppSetting:
  - scheduler_daily_report: 'true'/'false'  (default true)
  - scheduler_report_hour: '8'              (hour in 24h, default 8)
  - scheduler_weekly_report: 'true'/'false' (default true)
  - scheduler_weekly_day: '0'              (0=Monday … 6=Sunday, default 1=Tuesday)
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)
_scheduler = None


def _daily_report(app):
    try:
        with app.app_context():
            from models import AppSetting
            if AppSetting.get('scheduler_daily_report', 'true') != 'true':
                return

            from ai_engine import get_sales_summary, get_stock_summary
            from notifications import notify_async

            sales = get_sales_summary()
            stock = get_stock_summary()
            notify_async(
                f"🌅 <b>Daily Business Report</b>\n\n"
                f"<b>Sales Today:</b>\n{sales}\n\n"
                f"<b>Stock Alert:</b>\n{stock}"
            )
    except Exception as e:
        log.warning(f"Daily report failed: {e}")


def _weekly_report(app):
    try:
        with app.app_context():
            from models import AppSetting
            if AppSetting.get('scheduler_weekly_report', 'true') != 'true':
                return

            from ai_engine import get_insights, get_predictions
            from notifications import notify_async

            insights = get_insights()
            health = insights.get('health_rating', 'N/A')
            health_icon = {'GREEN': '🟢', 'AMBER': '🟡', 'RED': '🔴'}.get(health, '⚪')
            top = '\n'.join(f"• {i}" for i in insights.get('top_insights', [])[:5])
            urgent = '\n'.join(f"⚡ {a}" for a in insights.get('urgent_actions', [])[:3])

            predictions = get_predictions()

            notify_async(
                f"📊 <b>Weekly Business Summary</b>\n\n"
                f"{health_icon} <b>Health:</b> {health} — {insights.get('health_reason', '')}\n\n"
                f"<b>Top Insights:</b>\n{top}\n\n"
                f"<b>Urgent Actions:</b>\n{urgent or 'None this week ✅'}\n\n"
                f"<b>Forecast:</b>\n{predictions}"
            )
    except Exception as e:
        log.warning(f"Weekly report failed: {e}")


def init_scheduler(app):
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    from models import AppSetting

    with app.app_context():
        hour = int(AppSetting.get('scheduler_report_hour', '8'))
        weekly_day = int(AppSetting.get('scheduler_weekly_day', '1'))

    _scheduler = BackgroundScheduler(daemon=True)

    # Daily at configured hour
    _scheduler.add_job(
        _daily_report,
        trigger=CronTrigger(hour=hour, minute=0),
        args=[app],
        id='daily_report',
        replace_existing=True,
    )

    # Weekly on configured day
    day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    _scheduler.add_job(
        _weekly_report,
        trigger=CronTrigger(day_of_week=day_names[weekly_day % 7], hour=hour, minute=30),
        args=[app],
        id='weekly_report',
        replace_existing=True,
    )

    _scheduler.start()
    log.info(f"Scheduler started — daily at {hour}:00, weekly on {day_names[weekly_day % 7]}")


def shutdown_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
