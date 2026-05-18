import { WEBUI_API_BASE_URL } from '$lib/constants';

export type GroupTokenUsageEntry = {
	group_id: string;
	group_name: string;
	period: string;
	limit: number;
	used: number;
	remaining: number;
	reset_at: number;
};

export const getGroupsTokenUsage = async (token: string): Promise<GroupTokenUsageEntry[]> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/enterprise/groups/token-usage`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) {
		const err = await res.json().catch(() => ({}));
		throw err?.detail ?? 'Failed to fetch group token usage';
	}

	return res.json();
};
