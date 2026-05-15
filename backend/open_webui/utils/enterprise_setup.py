import logging
import time

log = logging.getLogger(__name__)

_TOKEN_RATE_LIMIT_FILTER_ID = 'enterprise-token-rate-limit'

# Filter code stored in DB; imports from token_limit.py which lives in our codebase.
_TOKEN_RATE_LIMIT_FILTER_CODE = '''\
"""
Token Rate Limit Filter (Enterprise)
Enforces per-user and group token quotas configured via Admin UI.
Do not delete or disable this filter — it is required for token rate limiting.
"""
import asyncio
from fastapi import HTTPException
from open_webui.models.users import UserModel
from open_webui.utils.token_limit import get_remaining_token_budget

# Per-user locks to serialize concurrent inlet checks for the same user,
# preventing race conditions where two simultaneous requests both pass the limit check.
_user_locks: dict[str, asyncio.Lock] = {}


def _get_user_lock(user_id: str) -> asyncio.Lock:
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


class Filter:
    async def inlet(self, body: dict, __user__: dict) -> dict:
        if not __user__:
            return body
        user = UserModel(**__user__)

        lock = _get_user_lock(user.id)
        async with lock:
            try:
                budget = await get_remaining_token_budget(user)
            except HTTPException as e:
                raise Exception(e.detail)

            if budget is not None:
                # Cap this response to the remaining budget so a single reply cannot overshoot.
                existing_max = body.get(\'max_tokens\') or budget
                body[\'max_tokens\'] = min(existing_max, budget)

        # Inject stream_options so OpenAI-compatible providers always return usage data.
        # Ollama payloads are converted server-side and this key is stripped automatically.
        if body.get(\'stream\', True):
            so = body.get(\'stream_options\') or {}
            if not so.get(\'include_usage\'):
                body[\'stream_options\'] = {**so, \'include_usage\': True}

        return body
'''


async def seed_enterprise_filters() -> None:
    """
    Ensure enterprise built-in filters are present and active in the database.
    Called once at application startup; safe to run on every restart.
    """
    from open_webui.models.functions import Functions, FunctionForm, FunctionMeta

    existing = await Functions.get_function_by_id(_TOKEN_RATE_LIMIT_FILTER_ID)
    if existing:
        # Always sync code + ensure global/active so changes here take effect on restart.
        update: dict = {}
        if existing.content != _TOKEN_RATE_LIMIT_FILTER_CODE:
            update['content'] = _TOKEN_RATE_LIMIT_FILTER_CODE
        if not existing.is_global or not existing.is_active:
            update['is_global'] = True
            update['is_active'] = True
        if update:
            await Functions.update_function_by_id(_TOKEN_RATE_LIMIT_FILTER_ID, update)
        return

    result = await Functions.insert_new_function(
        user_id='system',
        type='filter',
        form_data=FunctionForm(
            id=_TOKEN_RATE_LIMIT_FILTER_ID,
            name='Token Rate Limit (Enterprise)',
            content=_TOKEN_RATE_LIMIT_FILTER_CODE,
            meta=FunctionMeta(description='Enforces token rate limits configured per user and group.'),
        ),
    )
    if result:
        await Functions.update_function_by_id(
            _TOKEN_RATE_LIMIT_FILTER_ID,
            {'is_global': True, 'is_active': True},
        )
        log.info('Enterprise filter installed: %s', _TOKEN_RATE_LIMIT_FILTER_ID)
    else:
        log.warning('Failed to install enterprise filter: %s', _TOKEN_RATE_LIMIT_FILTER_ID)
