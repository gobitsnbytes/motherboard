import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import get_sessionmaker
from app.provisioning.client import DiscordClient
from app.provisioning.sync import run_sync

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def run_sync_job(guild_id: str, bot_token: str) -> None:
    """Job wrapper that obtains a new DB session and runs the sync."""
    logger.info("Executing scheduled Discord sync job...")
    session_factory = get_sessionmaker()
    discord_client = DiscordClient(bot_token)

    async with session_factory() as session:
        try:
            await run_sync(
                db=session,
                discord_client=discord_client,
                guild_id=guild_id,
                trigger="scheduled",
            )
        except Exception as e:
            logger.error("Scheduled Discord sync job failed: %s", e)


async def start_scheduler(interval_minutes: int, guild_id: str, bot_token: str) -> None:
    """Start the periodic Discord sync scheduler."""
    global _scheduler
    if _scheduler is not None:
        logger.warning("Discord sync scheduler is already running.")
        return

    if not guild_id or not bot_token:
        logger.error("Cannot start Discord sync scheduler: missing guild_id or bot_token configuration.")
        return

    logger.info("Starting Discord sync scheduler (interval: %d minutes)", interval_minutes)
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_sync_job,
        "interval",
        minutes=interval_minutes,
        args=[guild_id, bot_token],
        id="discord_sync_job",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Discord sync scheduler started.")


async def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler is None:
        logger.warning("Discord sync scheduler is not running.")
        return

    logger.info("Shutting down Discord sync scheduler...")
    _scheduler.shutdown()
    _scheduler = None
    logger.info("Discord sync scheduler shut down.")
