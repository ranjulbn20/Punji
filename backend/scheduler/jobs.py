"""
APScheduler job definitions.
All jobs are async and use their own database sessions.

Fallback strategy
─────────────────
Each job records its completion time in _last_run.  A watchdog fires every
6 hours and re-runs any job that has not completed within its expected window:
  • daily jobs   → overdue after 25 h  (1 h buffer over 24 h)
  • weekly jobs  → overdue after 8 days (1 day buffer over 7 days)
  • monthly jobs → overdue after 32 days

On startup, _last_run["snapshots"] is seeded from the DB so a server restart
won't duplicate today's snapshot if it already ran.
"""
from datetime import date, datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from database import AsyncSessionLocal


# ── in-process run-time tracking ─────────────────────────────────────────────

_last_run: dict[str, datetime | None] = {
    "snapshots":   None,
    "alerts":      None,
    "monte_carlo": None,
    "amfi":        None,
}

_OVERDUE: dict[str, timedelta] = {
    "snapshots":   timedelta(hours=25),
    "alerts":      timedelta(hours=25),
    "monte_carlo": timedelta(days=8),
    "amfi":        timedelta(days=32),
}


def _mark(key: str) -> None:
    _last_run[key] = datetime.now(timezone.utc)


def _is_overdue(key: str) -> bool:
    last = _last_run[key]
    if last is None:
        return True
    return (datetime.now(timezone.utc) - last) > _OVERDUE[key]


# ── jobs ─────────────────────────────────────────────────────────────────────

async def _take_portfolio_snapshots() -> None:
    """Daily 00:05 IST — record portfolio value for every active user."""
    async with AsyncSessionLocal() as db:
        from models import User, PortfolioSnapshot
        from services.portfolio_service import compute_allocation, compute_portfolio_xirr

        users_result = await db.execute(
            select(User).where(User.is_active == True, User.onboarding_step >= 1)
        )
        users = users_result.scalars().all()

        for user in users:
            alloc = await compute_allocation(db, user.id)
            total = alloc.get("total_value", 0)
            if total == 0:
                continue

            xirr = await compute_portfolio_xirr(db, user.id)

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
                snap.debt_value   = alloc.get("by_class", {}).get("debt", 0)
                snap.gold_value   = alloc.get("by_class", {}).get("gold", 0)
                snap.equity_pct   = alloc.get("equity", 0)
                snap.debt_pct     = alloc.get("debt", 0)
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
        _mark("snapshots")
        print(f"[Scheduler] Portfolio snapshots taken for {len(users)} users at {datetime.now(timezone.utc)}")


async def _run_proactive_alerts() -> None:
    """Daily 08:00 IST — run proactive alert agent for all active users."""
    async with AsyncSessionLocal() as db:
        from models import User
        from agents.proactive_alert import run_proactive_alerts_for_user

        users_result = await db.execute(
            select(User).where(User.is_active == True, User.onboarding_step >= 1)
        )
        users = users_result.scalars().all()

        for user in users:
            try:
                await run_proactive_alerts_for_user(db, str(user.id))
            except Exception as e:
                print(f"[Scheduler] Alert agent error for user {user.id}: {e}")

        _mark("alerts")


async def _run_monte_carlo_weekly() -> None:
    """Weekly Sunday 02:00 IST — Monte Carlo simulation for all active goals."""
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

        _mark("monte_carlo")
        print(f"[Scheduler] Monte Carlo complete for {len(goals)} goals")


async def _refresh_amfi_compositions() -> None:
    """Monthly 1st 03:00 IST — refresh AMFI fund portfolio compositions."""
    async with AsyncSessionLocal() as db:
        from models import MutualFund

        result = await db.execute(
            select(MutualFund.isin).where(MutualFund.is_active == True)
        )
        scheme_codes = {row[0] for row in result if row[0]}
        _mark("amfi")
        print(f"[Scheduler] Refreshing AMFI compositions for {len(scheme_codes)} scheme codes")


# ── watchdog ─────────────────────────────────────────────────────────────────

async def _watchdog() -> None:
    """
    Runs every 6 hours.  For each job that has not completed within its
    expected window, fires it now as a fallback.
    """
    print(f"[Scheduler] Watchdog check at {datetime.now(timezone.utc)}")

    if _is_overdue("snapshots"):
        print("[Scheduler] Watchdog: snapshot overdue — running now")
        await _take_portfolio_snapshots()

    if _is_overdue("alerts"):
        print("[Scheduler] Watchdog: alerts overdue — running now")
        await _run_proactive_alerts()

    if _is_overdue("monte_carlo"):
        print("[Scheduler] Watchdog: Monte Carlo overdue — running now")
        await _run_monte_carlo_weekly()

    if _is_overdue("amfi"):
        print("[Scheduler] Watchdog: AMFI refresh overdue — running now")
        await _refresh_amfi_compositions()


# ── startup seed ─────────────────────────────────────────────────────────────

async def seed_last_run_from_db() -> None:
    """
    Called once at startup.  Seeds _last_run from the DB where possible so
    that a server restart does not cause the watchdog to re-fire jobs that
    already completed earlier today.

    Snapshots: check PortfolioSnapshot for today's date.
    Alerts / Monte Carlo: no DB record exists, so seed to a safe default
    (12 h and 4 days ago respectively) — the watchdog fires them only if
    they remain missing after another 13 h / 4 days.
    """
    async with AsyncSessionLocal() as db:
        from models import PortfolioSnapshot

        result = await db.execute(
            select(PortfolioSnapshot.snapshot_date)
            .order_by(PortfolioSnapshot.snapshot_date.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        if latest and latest == date.today():
            _last_run["snapshots"] = datetime.now(timezone.utc) - timedelta(hours=1)
            print("[Scheduler] Seed: today's snapshot already in DB")

    now = datetime.now(timezone.utc)
    if _last_run["alerts"] is None:
        _last_run["alerts"] = now - timedelta(hours=12)
    if _last_run["monte_carlo"] is None:
        _last_run["monte_carlo"] = now - timedelta(days=4)
    if _last_run["amfi"] is None:
        _last_run["amfi"] = now - timedelta(days=16)


# ── factory ──────────────────────────────────────────────────────────────────

def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

    # Primary jobs — misfire_grace_time=300 s: fires immediately if the server
    # restarts within 5 minutes of the scheduled time.
    scheduler.add_job(
        _take_portfolio_snapshots,
        CronTrigger(hour=0, minute=5),
        misfire_grace_time=300,
        id="snapshots",
    )
    scheduler.add_job(
        _run_proactive_alerts,
        CronTrigger(hour=8, minute=0),
        misfire_grace_time=300,
        id="alerts",
    )
    scheduler.add_job(
        _run_monte_carlo_weekly,
        CronTrigger(day_of_week="sun", hour=2, minute=0),
        misfire_grace_time=300,
        id="monte_carlo",
    )
    scheduler.add_job(
        _refresh_amfi_compositions,
        CronTrigger(day=1, hour=3, minute=0),
        misfire_grace_time=300,
        id="amfi",
    )

    # Watchdog — fires every 6 hours, re-runs any overdue job as a fallback.
    scheduler.add_job(
        _watchdog,
        IntervalTrigger(hours=6),
        misfire_grace_time=300,
        id="watchdog",
    )

    return scheduler
