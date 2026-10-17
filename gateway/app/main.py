import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, SessionLocal, Base
from app.routers import health, auth, agent, admin, hermes, alerts, dashboard, fbr
from app.alert_engine import check_offline_devices, purge_expired_metrics
from app.notifications import notify_daily_summary
from app.models import Alert

logger = logging.getLogger("hbk.gateway")

async def offline_detection_worker():
    """Background task running every 15s to detect offline devices and fire agent_offline alerts."""
    logger.info("Starting background offline detection worker (interval: 15s)...")
    while True:
        try:
            await asyncio.sleep(15)
            db = SessionLocal()
            try:
                check_offline_devices(db)
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in offline detection worker: {e}")

async def daily_maintenance_worker():
    """Background task running once per minute for daily retention purge and 20:00 daily summary."""
    last_summary_date = None
    last_purge_date = None

    while True:
        try:
            await asyncio.sleep(60)
            now = datetime.now(timezone.utc)
            today_str = now.strftime("%Y-%m-%d")

            # Daily metric retention purge
            if last_purge_date != today_str:
                db = SessionLocal()
                try:
                    deleted = purge_expired_metrics(db)
                    logger.info(f"Daily retention job: purged {deleted} metrics older than {settings.METRICS_RETENTION_DAYS} days.")
                    last_purge_date = today_str
                except Exception as e:
                    logger.error(f"Daily retention purge error: {e}")
                finally:
                    db.close()

            # Daily summary notification at 20:00 server time
            if now.hour == 20 and last_summary_date != today_str:
                db = SessionLocal()
                try:
                    start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)
                    fired_today = db.query(Alert).filter(Alert.fired_at >= start_of_day).count()
                    resolved_today = db.query(Alert).filter(Alert.resolved_at >= start_of_day).count()
                    active_now = db.query(Alert).filter(Alert.state.in_(["FIRING", "ACKNOWLEDGED"])).count()
                    notify_daily_summary(fired_today, resolved_today, active_now)
                    last_summary_date = today_str
                except Exception as e:
                    logger.error(f"Daily summary error: {e}")
                finally:
                    db.close()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in daily maintenance worker: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    task_offline = asyncio.create_task(offline_detection_worker())
    task_maint = asyncio.create_task(daily_maintenance_worker())
    
    yield
    
    task_offline.cancel()
    task_maint.cancel()
    await asyncio.gather(task_offline, task_maint, return_exceptions=True)

app = FastAPI(
    title="HBK IT Monitoring Gateway",
    version="1.0.0",
    description="Centralized telemetry ingestion and IT control plane for HBK retail hypermarkets.",
    lifespan=lifespan
)

# Configure CORS with explicit support for http://localhost:3000
origins = settings.cors_origins_list
has_wildcard = "*" in origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if has_wildcard else origins,
    allow_credentials=not has_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(agent.router)
app.include_router(admin.router)
app.include_router(hermes.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)
app.include_router(fbr.router)

@app.get("/")
def root():
    return {
        "service": "HBK IT Monitoring Gateway",
        "version": "1.0.0",
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
