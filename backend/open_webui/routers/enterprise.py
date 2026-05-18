from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import get_async_session
from open_webui.models.chat_messages import ChatMessages
from open_webui.models.groups import Groups
from open_webui.models.users import Users
from open_webui.utils.auth import get_admin_user
from open_webui.utils.token_limit import get_period_start, get_next_period_start

router = APIRouter()


@router.get('/groups/token-usage')
async def get_groups_token_usage(
    admin_user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Return token usage for all groups that have token rate limiting enabled."""
    all_groups = await Groups.get_groups({}, db)
    result = []

    for group_response in all_groups:
        permissions = group_response.permissions or {}
        cfg = permissions.get('token_limit', {})
        if not cfg.get('enabled') or cfg.get('limit', 0) <= 0:
            continue

        period = cfg.get('period', 'daily')
        limit = cfg['limit']
        member_ids = await Groups.get_group_user_ids_by_id(group_response.id, db)
        used = (
            await ChatMessages.get_group_token_usage_since(
                member_ids, get_period_start(period), db
            )
            if member_ids
            else 0
        )
        result.append(
            {
                'group_id': group_response.id,
                'group_name': group_response.name,
                'period': period,
                'limit': limit,
                'used': used,
                'remaining': max(0, limit - used),
                'reset_at': get_next_period_start(period),
            }
        )

    return result


@router.get('/groups/{group_id}/token-usage')
async def get_group_token_usage(
    group_id: str,
    admin_user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Return token usage for all periods for a single group."""
    from fastapi import HTTPException

    group = await Groups.get_group_by_id(group_id, db)
    if not group:
        raise HTTPException(status_code=404, detail='Group not found')

    permissions = group.permissions or {}
    cfg = permissions.get('token_limit', {})
    limit_enabled = cfg.get('enabled', False)
    configured_period = cfg.get('period', 'daily')
    configured_limit = cfg.get('limit', 0) if limit_enabled else 0

    member_ids = await Groups.get_group_user_ids_by_id(group_id, db)
    group_members = await Users.get_users_by_group_id(group_id, db)

    per_period_usage = {}
    periods_result = {}
    for period in ('daily', 'weekly', 'monthly'):
        period_start = get_period_start(period)
        used = (
            await ChatMessages.get_group_token_usage_since(member_ids, period_start, db)
            if member_ids
            else 0
        )
        per_user = (
            await ChatMessages.get_token_usage_by_user(start_date=period_start, group_id=group_id, db=db)
            if member_ids
            else {}
        )
        per_period_usage[period] = per_user
        limit = configured_limit if (limit_enabled and period == configured_period) else 0
        periods_result[period] = {
            'used': used,
            'limit': limit,
            'remaining': max(0, limit - used) if limit > 0 else None,
            'reset_at': get_next_period_start(period),
        }

    sort_period = configured_period if limit_enabled else 'daily'
    members_list = sorted(
        [
            {
                'user_id': user.id,
                'name': user.name,
                'email': user.email,
                'daily': per_period_usage['daily'].get(user.id, {}).get('total_tokens', 0),
                'weekly': per_period_usage['weekly'].get(user.id, {}).get('total_tokens', 0),
                'monthly': per_period_usage['monthly'].get(user.id, {}).get('total_tokens', 0),
            }
            for user in group_members
        ],
        key=lambda m: m[sort_period],
        reverse=True,
    )

    return {
        'group_id': group_id,
        'group_name': group.name,
        'limit_config': {
            'enabled': limit_enabled,
            'period': configured_period,
            'limit': configured_limit,
        }
        if limit_enabled
        else None,
        'daily': periods_result['daily'],
        'weekly': periods_result['weekly'],
        'monthly': periods_result['monthly'],
        'members': members_list,
    }
