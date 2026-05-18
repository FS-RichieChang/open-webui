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

export type GroupTokenUsagePeriod = {
	used: number;
	limit: number;
	remaining: number | null;
	reset_at: number;
};

export type GroupTokenUsageMember = {
	user_id: string;
	name: string;
	email: string;
	daily: number;
	weekly: number;
	monthly: number;
};

export type GroupTokenUsageDetail = {
	group_id: string;
	group_name: string;
	limit_config: { enabled: boolean; period: string; limit: number } | null;
	daily: GroupTokenUsagePeriod;
	weekly: GroupTokenUsagePeriod;
	monthly: GroupTokenUsagePeriod;
	members: GroupTokenUsageMember[];
};

export const getGroupTokenUsage = async (
	token: string,
	groupId: string
): Promise<GroupTokenUsageDetail | null> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/enterprise/groups/${groupId}/token-usage`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) return null;
	return res.json();
};
