from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import get_async_session
from open_webui.models.chat_messages import ChatMessages
from open_webui.models.groups import Groups
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
