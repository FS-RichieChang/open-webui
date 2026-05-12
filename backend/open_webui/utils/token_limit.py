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

    NOTE: 'used' reflects the individual user's personal usage.
    When a group shared-pool limit applies, the 'limit' shown is the group limit
    but 'remaining' is computed against personal usage (not group total).
    This is a known display limitation; enforcement in check_token_limit is accurate.
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
    Return a representative token limit config for UI display purposes, or None if unlimited.

    Priority:
    1. User's personal override (if enabled) — individual limit.
    2. Group limits — for each period, the group with the highest limit (most permissive)
       is selected. Returns the config with the smallest limit among those winners
       (most likely to be the binding constraint) for display.
    """
    user_info = user.info or {}
    user_token_limit = user_info.get('token_limit', {})
    if user_token_limit.get('enabled'):
        return user_token_limit

    period_best = _get_best_group_per_period(
        await Groups.get_groups_by_member_id(user.id, db)
    )
    if not period_best:
        return None

    # Return the config with the smallest limit (most binding) for display
    return min(period_best.values(), key=lambda cfg: cfg['limit'])


def _get_best_group_per_period(groups) -> dict[str, dict]:
    """
    For each period, return the group config with the highest limit (most permissive).
    Groups without token limits enabled are ignored.
    Returns: { period: cfg_dict }
    """
    period_best: dict[str, dict] = {}
    for group in groups:
        cfg = (group.permissions or {}).get('token_limit', {})
        if not cfg.get('enabled') or cfg.get('limit', 0) <= 0:
            continue
        period = cfg.get('period', 'daily')
        if period not in period_best or cfg['limit'] > period_best[period]['limit']:
            period_best[period] = {'group': group, **cfg}
    return period_best


async def check_token_limit(user: UserModel) -> None:
    """
    Raise HTTP 429 if the user has exceeded any applicable token quota.

    Rules:
    - Personal override takes priority over group limits (individual usage check).
    - Group limits use a shared pool: all group members' usage is summed.
    - When a user belongs to multiple groups with limits for the same period,
      only the most permissive group (highest limit) is checked for that period.
      Groups without token limits enabled are ignored entirely.
    - Different periods are independent: a user can be checked against both a
      daily limit and a monthly limit simultaneously.
    """
    async with get_async_db_context() as db:
        # 1. Personal override — individual usage check, takes priority
        user_info = user.info or {}
        user_token_limit = user_info.get('token_limit', {})
        if user_token_limit.get('enabled'):
            limit = user_token_limit.get('limit', 0)
            period = user_token_limit.get('period', 'daily')
            if limit > 0:
                usage = await ChatMessages.get_user_token_usage_since(
                    user.id, get_period_start(period), db
                )
                if usage >= limit:
                    _raise_limit_exceeded(usage, limit, period)
            return

        # 2. Group limits — per period, check only the most permissive group (shared pool)
        groups = await Groups.get_groups_by_member_id(user.id, db)
        period_best = _get_best_group_per_period(groups)

        for period, cfg in period_best.items():
            group = cfg['group']
            limit = cfg['limit']
            member_ids = await Groups.get_group_user_ids_by_id(group.id, db)
            if not member_ids:
                continue
            group_usage = await ChatMessages.get_group_token_usage_since(
                member_ids, get_period_start(period), db
            )
            if group_usage >= limit:
                period_label = {'daily': '每日', 'weekly': '每週', 'monthly': '每月'}.get(period, period)
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f'群組「{group.name}」Token 使用額度已達上限'
                        f'（已用 {group_usage:,} / 上限 {limit:,} tokens，{period_label}額度）。'
                        f'請等待下個周期後再試。'
                    ),
                )


def _raise_limit_exceeded(usage: int, limit: int, period: str) -> None:
    period_label = {'daily': '每日', 'weekly': '每週', 'monthly': '每月'}.get(period, period)
    raise HTTPException(
        status_code=429,
        detail=f'Token 使用額度已達上限（已用 {usage:,} / 上限 {limit:,} tokens，{period_label}額度）。請等待下個周期後再試。',
    )
