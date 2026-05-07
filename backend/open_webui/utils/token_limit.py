import asyncio
import datetime as dt
import logging

from fastapi import HTTPException
from open_webui.internal.db import get_async_db_context
from open_webui.models.chat_messages import ChatMessages
from open_webui.models.groups import Groups
from open_webui.models.users import UserModel

log = logging.getLogger(__name__)


def get_period_start(period: str) -> int:
    """Return UTC epoch seconds for the start of the current period."""
    now = dt.datetime.now(dt.timezone.utc)
    if period == 'daily':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'weekly':
        start = (now - dt.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'monthly':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp())


def get_next_period_start(period: str) -> int:
    """Return UTC epoch seconds for the start of the next period (= reset time)."""
    now = dt.datetime.now(dt.timezone.utc)
    if period == 'daily':
        reset = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'weekly':
        days_until_monday = (7 - now.weekday()) % 7 or 7
        reset = (now + dt.timedelta(days=days_until_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'monthly':
        if now.month == 12:
            reset = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            reset = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        reset = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(reset.timestamp())


async def get_token_usage_info(user: UserModel, db=None) -> dict:
    """
    Return token usage for all three periods (daily/weekly/monthly),
    regardless of whether a limit is configured.
    """
    async with get_async_db_context(db) as db:
        limit_config = await get_effective_token_limit(user, db)

        daily_start = get_period_start('daily')
        weekly_start = get_period_start('weekly')
        monthly_start = get_period_start('monthly')

        daily_used, weekly_used, monthly_used = await asyncio.gather(
            ChatMessages.get_user_token_usage_since(user.id, daily_start, db),
            ChatMessages.get_user_token_usage_since(user.id, weekly_start, db),
            ChatMessages.get_user_token_usage_since(user.id, monthly_start, db),
        )

        def _build_period(used: int, period: str) -> dict:
            active = limit_config is not None and limit_config.get('period') == period
            limit = limit_config.get('limit', 0) if active else 0
            remaining = max(0, limit - used) if active else -1
            return {
                'used': used,
                'limit': limit,
                'remaining': remaining,
                'reset_at': get_next_period_start(period),
            }

        return {
            'daily': _build_period(daily_used, 'daily'),
            'weekly': _build_period(weekly_used, 'weekly'),
            'monthly': _build_period(monthly_used, 'monthly'),
            'limit_config': limit_config,
        }


async def get_effective_token_limit(user: UserModel, db=None) -> dict | None:
    """
    Return the token limit config that applies to this user, or None if unlimited.
    User's personal setting takes priority over group settings.
    Among groups, the most permissive (highest limit) applies.
    """
    user_info = user.info or {}
    user_token_limit = user_info.get('token_limit', {})
    if user_token_limit.get('enabled'):
        return user_token_limit

    groups = await Groups.get_groups_by_member_id(user.id, db)
    best: dict | None = None
    for group in groups:
        group_permissions = group.permissions or {}
        cfg = group_permissions.get('token_limit', {})
        if cfg.get('enabled'):
            if best is None or cfg.get('limit', 0) > best.get('limit', 0):
                best = cfg

    return best


async def check_token_limit(user: UserModel) -> None:
    """Raise HTTP 429 if the user has exceeded their token quota for the current period."""
    async with get_async_db_context() as db:
        limit_config = await get_effective_token_limit(user, db)
        if limit_config is None:
            return

        limit = limit_config.get('limit', 0)
        period = limit_config.get('period', 'daily')

        if limit <= 0:
            return

        start_time = get_period_start(period)
        usage = await ChatMessages.get_user_token_usage_since(user.id, start_time, db)

        if usage >= limit:
            period_label = {'daily': '每日', 'weekly': '每週', 'monthly': '每月'}.get(period, period)
            raise HTTPException(
                status_code=429,
                detail=f'Token 使用額度已達上限（已用 {usage:,} / 上限 {limit:,} tokens，{period_label}額度）。請等待下個周期後再試。',
            )
