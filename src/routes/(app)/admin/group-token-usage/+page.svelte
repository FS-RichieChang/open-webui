<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { user } from '$lib/stores';
	import { getGroupsTokenUsage, type GroupTokenUsageEntry } from '$lib/apis/enterprise';

	const i18n = getContext('i18n');

	let entries: GroupTokenUsageEntry[] = [];
	let loading = true;
	let error = '';
	let filterPeriod = 'all';

	const formatNumber = (n: number) => n.toLocaleString();

	const formatResetAt = (epoch: number) =>
		new Date(epoch * 1000).toISOString().slice(0, 16).replace('T', ' ') + ' UTC';

	const periodLabel = (p: string) => {
		if (p === 'daily') return $i18n.t('Daily');
		if (p === 'weekly') return $i18n.t('Weekly');
		if (p === 'monthly') return $i18n.t('Monthly');
		return p;
	};

	$: filtered = filterPeriod === 'all' ? entries : entries.filter((e) => e.period === filterPeriod);

	onMount(async () => {
		if ($user?.role !== 'admin') {
			goto('/');
			return;
		}
		try {
			entries = await getGroupsTokenUsage(localStorage.token);
		} catch (e) {
			error = typeof e === 'string' ? e : $i18n.t('Failed to load group token usage.');
		} finally {
			loading = false;
		}
	});
</script>

<div class="w-full max-w-4xl mx-auto px-4 py-6">
	<div class="mb-6">
		<h1 class="text-xl font-semibold">{$i18n.t('Group Token Usage')}</h1>
		<p class="text-sm text-gray-500 mt-1">
			{$i18n.t('Token consumption from the shared pool of each group with rate limiting enabled.')}
		</p>
	</div>

	<div class="flex items-center gap-2 mb-4">
		<span class="text-sm text-gray-500">{$i18n.t('Period')}:</span>
		{#each [['all', $i18n.t('All')], ['daily', $i18n.t('Daily')], ['weekly', $i18n.t('Weekly')], ['monthly', $i18n.t('Monthly')]] as [val, lbl]}
			<button
				class="px-3 py-1 rounded-full text-xs font-medium transition
					{filterPeriod === val
					? 'bg-black text-white dark:bg-white dark:text-black'
					: 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700'}"
				on:click={() => (filterPeriod = val)}
			>
				{lbl}
			</button>
		{/each}
	</div>

	{#if loading}
		<div class="text-sm text-gray-400">{$i18n.t('Loading...')}</div>
	{:else if error}
		<div class="text-sm text-red-500">{error}</div>
	{:else if filtered.length === 0}
		<div class="text-sm text-gray-400">
			{$i18n.t('No groups with token rate limiting enabled.')}
		</div>
	{:else}
		<div class="flex flex-col gap-3">
			{#each filtered as entry}
				{@const pct = Math.min(100, entry.limit > 0 ? (entry.used / entry.limit) * 100 : 0)}
				<div class="p-4 rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900">
					<div class="flex items-center justify-between mb-2">
						<div>
							<span class="font-medium text-sm">{entry.group_name}</span>
							<span
								class="ml-2 px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"
							>
								{periodLabel(entry.period)}
							</span>
						</div>
						<span class="text-sm font-medium dark:text-gray-200">
							{formatNumber(entry.used)} / {formatNumber(entry.limit)} {$i18n.t('tokens')}
						</span>
					</div>
					<div class="w-full bg-gray-100 dark:bg-gray-800 rounded-full h-2">
						<div
							class="h-2 rounded-full transition-all {pct >= 100
								? 'bg-red-500'
								: pct > 80
									? 'bg-yellow-400'
									: 'bg-blue-500'}"
							style="width: {pct.toFixed(1)}%"
						></div>
					</div>
					<div class="flex justify-between text-xs text-gray-400 mt-1.5">
						<span>{$i18n.t('Remaining')}: {formatNumber(entry.remaining)}</span>
						<span>{$i18n.t('Resets at')}: {formatResetAt(entry.reset_at)}</span>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
