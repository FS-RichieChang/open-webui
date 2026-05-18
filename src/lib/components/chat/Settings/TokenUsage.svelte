<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { getSelfTokenUsage } from '$lib/apis/users';

	const i18n = getContext('i18n');

	type PeriodInfo = {
		used: number;
		limit: number;
		remaining: number;
		reset_at: number;
		is_group_limit?: boolean;
		group_used?: number;
		group_remaining?: number;
		group_name?: string;
	};
	let tokenUsage: {
		daily: PeriodInfo;
		weekly: PeriodInfo;
		monthly: PeriodInfo;
		limit_config: { enabled: boolean; limit: number; period: string } | null;
	} | null = null;

	let loading = true;

	const formatNumber = (n: number) => n.toLocaleString();

	const formatResetAt = (epoch: number) => {
		return new Date(epoch * 1000).toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
	};

	onMount(async () => {
		tokenUsage = await getSelfTokenUsage(localStorage.token).catch(() => null);
		loading = false;
	});
</script>

<div id="tab-token_usage" class="flex flex-col h-full text-sm">
	<div class="space-y-1 mb-4">
		<div class="text-base font-medium">{$i18n.t('Token Usage')}</div>
		<div class="text-xs text-gray-500">
			{$i18n.t('Your token consumption for each time period.')}
		</div>
	</div>

	{#if loading}
		<div class="text-xs text-gray-400">{$i18n.t('Loading...')}</div>
	{:else if tokenUsage}
		<div class="flex flex-col gap-4">
			{#each [['daily', $i18n.t('Today')], ['weekly', $i18n.t('This Week')], ['monthly', $i18n.t('This Month')]] as [period, label]}
				{@const info = tokenUsage[period as 'daily' | 'weekly' | 'monthly']}
				{@const isLimited = info.limit > 0}
				{@const displayUsed = info.is_group_limit ? (info.group_used ?? 0) : info.used}
				{@const displayRemaining = info.is_group_limit ? (info.group_remaining ?? 0) : info.remaining}
				<div class="flex flex-col gap-1 p-3 rounded-xl bg-gray-50 dark:bg-gray-850">
					<div class="flex items-center justify-between">
						<span class="font-medium text-gray-700 dark:text-gray-300">{label}</span>
						<span class="font-medium dark:text-gray-200">
							{#if info.is_group_limit}
								{$i18n.t('Group')}: {formatNumber(info.group_used ?? 0)}
							{:else}
								{formatNumber(info.used)}
							{/if}
							{$i18n.t('tokens')}
							{#if isLimited}
								/ {formatNumber(info.limit)}
							{/if}
						</span>
					</div>
					{#if isLimited}
						<div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1">
							<div
								class="h-1.5 rounded-full transition-all {displayUsed >= info.limit
									? 'bg-red-500'
									: displayUsed / info.limit > 0.8
										? 'bg-yellow-400'
										: 'bg-blue-500'}"
								style="width: {Math.min(100, (displayUsed / info.limit) * 100).toFixed(1)}%"
							></div>
						</div>
						<div class="flex justify-between text-xs text-gray-400 mt-0.5">
							<span>{$i18n.t('Remaining')}: {formatNumber(displayRemaining)}</span>
							<span>{$i18n.t('Resets at')}: {formatResetAt(info.reset_at)}</span>
						</div>
						{#if info.is_group_limit && info.group_name}
							<div class="text-xs text-gray-400 mt-0.5">
								{info.group_name} &nbsp;·&nbsp; {$i18n.t('Personal')}: {formatNumber(info.used)} {$i18n.t('tokens')}
							</div>
						{/if}
					{/if}
				</div>
			{/each}
		</div>
	{:else}
		<div class="text-xs text-gray-400">{$i18n.t('Failed to load token usage.')}</div>
	{/if}
</div>
