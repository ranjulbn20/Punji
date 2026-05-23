"""
APScheduler job definitions.
All jobs are async and use their own database sessions.
"""
from datetime import date, datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import AsyncSessionLocal


async def _take_portfolio_snapshots():
    """Daily midnight — record portfolio value and allocation for every active user."""
    async with AsyncSessionLocal() as db:
        from models import User, Holding, PortfolioSnapshot
        from services.portfolio_service import compute_allocation, compute_portfolio_xirr

        users_result = await db.execute(select(User).where(User.is_active == True, User.onboarding_step >= 1))
        users = users_result.scalars().all()

        for user in users:
            alloc = await compute_allocation(db, user.id)
            total = alloc.get("total_value", 0)
            if total == 0:
                continue

            xirr = await compute_portfolio_xirr(db, user.id)

            # Upsert snapshot for today
            existing = await db.execute(
                select(PortfolioSnapshot).where(
                    PortfolioSnapshot.user_id == user.id,
                    PortfolioSnapshot.snapshot_date == date.today(),
                )
            )
            snap = existing.scalar_one_or_none()
            if snap:
                snap.total_value = total
                snap.equity_value = alloc.get("by_class", {}).get("equity", 0)
                snap.debt_value = alloc.get("by_class", {}).get("debt", 0)
                snap.gold_value = alloc.get("by_class", {}).get("gold", 0)
                snap.equity_pct = alloc.get("equity", 0)
                snap.debt_pct = alloc.get("debt", 0)
                snap.portfolio_xirr = xirr
            else:
                snap = PortfolioSnapshot(
                    user_id=user.id,
                    snapshot_date=date.today(),
                    total_value=total,
                    equity_value=alloc.get("by_class", {}).get("equity", 0),
                    debt_value=alloc.get("by_class", {}).get("debt", 0),
                    gold_value=alloc.get("by_class", {}).get("gold", 0),
                    equity_pct=alloc.get("equity", 0),
                    debt_pct=alloc.get("debt", 0),
                    portfolio_xirr=xirr,
                )
                db.add(snap)

        await db.commit()
        print(f"[Scheduler] Portfolio snapshots taken for {len(users)} users at {datetime.now(timezone.utc)}")


async def _run_proactive_alerts():
    """Daily 8 AM IST — run proactive alert agent for all active users."""
    async with AsyncSessionLocal() as db:
        from models import User
        from agents.proactive_alert import run_proactive_alerts_for_user

        users_result = await db.execute(select(User).where(User.is_active == True, User.onboarding_step >= 1))
        users = users_result.scalars().all()

        for user in users:
            try:
                await run_proactive_alerts_for_user(db, str(user.id))
            except Exception as e:
                print(f"[Scheduler] Alert agent error for user {user.id}: {e}")


async def _run_monte_carlo_weekly():
    """Weekly Sunday — Monte Carlo simulation for all active goals."""
    async with AsyncSessionLocal() as db:
        from models import Goal
        from services.portfolio_service import run_monte_carlo_for_goal

        goals_result = await db.execute(select(Goal).where(Goal.is_active == True))
        goals = goals_result.scalars().all()

        for goal in goals:
            try:
                await run_monte_carlo_for_goal(db, goal, goal.user_id)
            except Exception as e:
                print(f"[Scheduler] Monte Carlo error for goal {goal.id}: {e}")

        print(f"[Scheduler] Monte Carlo complete for {len(goals)} goals")


async def _refresh_amfi_compositions():
    """Monthly 1st — refresh AMFI fund portfolio compositions."""
    async with AsyncSessionLocal() as db:
        from models import Holding, FundComposition
        import httpx

        # Get all unique scheme codes held by any user
        result = await db.execute(
            select(Holding.metadata_).where(
                Holding.instrument_type == "mutual_fund",
                Holding.is_active == True,
            )
        )
        scheme_codes = set()
        for (meta,) in result:
            sc = meta.get("scheme_code")
            if sc:
                scheme_codes.add(int(sc))

        print(f"[Scheduler] Refreshing AMFI compositions for {len(scheme_codes)} scheme codes")
        # Note: AMFI portfolio disclosure fetching requires parsing
        # their monthly disclosure files. This is a stub that logs intent.
        # Full implementation fetches from AMFI and populates fund_compositions.


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

    # Daily midnight: portfolio snapshots
    scheduler.add_job(_take_portfolio_snapshots, CronTrigger(hour=0, minute=5))

    # Daily 8 AM IST: proactive alerts
    scheduler.add_job(_run_proactive_alerts, CronTrigger(hour=8, minute=0))

    # Weekly Sunday 2 AM: Monte Carlo
    scheduler.add_job(_run_monte_carlo_weekly, CronTrigger(day_of_week="sun", hour=2, minute=0))

    # Monthly 1st 3 AM: AMFI composition refresh
    scheduler.add_job(_refresh_amfi_compositions, CronTrigger(day=1, hour=3, minute=0))

    return scheduler
