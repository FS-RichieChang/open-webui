<script lang="ts">
	import { getContext, onMount } from 'svelte';
	const i18n: any = getContext('i18n');

	import Switch from '$lib/components/common/Switch.svelte';
	import { getGroupTokenUsage, type GroupTokenUsageDetail } from '$lib/apis/enterprise';

	export let permissions: any = {};
	export let groupId: string | null = null;

	let usageData: GroupTokenUsageDetail | null = null;
	let usageLoading = false;

	const loadUsage = async () => {
		if (!groupId) return;
		usageLoading = true;
		usageData = await getGroupTokenUsage(localStorage.token, groupId);
		usageLoading = false;
	};

	onMount(loadUsage);

	const formatNumber = (n: number) => n.toLocaleString();

	const formatResetAt = (epoch: number) =>
		new Date(epoch * 1000).toISOString().slice(0, 16).replace('T', ' ') + ' UTC';

	$: configuredPeriod = usageData?.limit_config?.period ?? 'daily';
</script>

<div class="space-y-3 pr-1">
	<!-- Section 1: Settings -->
	<div>
		<div class="mb-3">
			<div class="text-sm font-medium">{$i18n.t('Token Rate Limiting')}</div>
			<div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
				{$i18n.t('Limit the number of tokens this group can consume per period.')}
			</div>
		</div>

		<div class="flex flex-col w-full">
			<div class="flex w-full justify-between my-1">
				<div class="self-center text-xs font-medium">
					{$i18n.t('Enable Token Rate Limit')}
				</div>
				<Switch bind:state={permissions.token_limit.enabled} />
			</div>

			{#if permissions.token_limit?.enabled}
				<div class="ml-2 mt-1 flex flex-col gap-2">
					<div class="flex w-full items-center justify-between">
						<div class="self-center text-xs font-medium">{$i18n.t('Token Limit')}</div>
						<input
							type="number"
							min="1"
							class="w-32 rounded-lg text-sm bg-transparent outline-none border border-gray-100 dark:border-gray-600 px-2 py-1 text-right dark:text-gray-300"
							bind:value={permissions.token_limit.limit}
						/>
					</div>

					<div class="flex w-full items-center justify-between">
						<div class="self-center text-xs font-medium">{$i18n.t('Period')}</div>
						<select
							class="rounded-lg text-sm bg-transparent outline-none border border-gray-100 dark:border-gray-600 px-2 py-1 dark:text-gray-300"
							bind:value={permissions.token_limit.period}
						>
							<option value="daily">{$i18n.t('Daily')}</option>
							<option value="weekly">{$i18n.t('Weekly')}</option>
							<option value="monthly">{$i18n.t('Monthly')}</option>
						</select>
					</div>
				</div>
			{/if}
		</div>
	</div>

	{#if groupId}
		<hr class="border-gray-100 dark:border-gray-800" />

		<!-- Section 2: Group aggregate usage -->
		<div>
			<div class="mb-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">
				{$i18n.t('Current Token Usage')}
			</div>

			{#if usageLoading}
				<div class="text-xs text-gray-400">{$i18n.t('Loading...')}</div>
			{:else if usageData}
				<div class="flex flex-col gap-1.5 text-xs">
					{#each [['daily', $i18n.t('Today')], ['weekly', $i18n.t('This Week')], ['monthly', $i18n.t('This Month')]] as [period, label]}
						{@const info = usageData[period as 'daily' | 'weekly' | 'monthly']}
						{@const isLimited = info.limit > 0}
						<div class="flex flex-col gap-0.5">
							<div class="flex items-center justify-between">
								<span class="text-gray-500">{label}</span>
								<span class="font-medium dark:text-gray-300">
									{formatNumber(info.used)}
									{$i18n.t('tokens')}
									{#if isLimited}/ {formatNumber(info.limit)}{/if}
								</span>
							</div>
							{#if isLimited}
								<div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1">
									<div
										class="h-1 rounded-full transition-all {info.used >= info.limit
											? 'bg-red-500'
											: info.used / info.limit > 0.8
												? 'bg-yellow-400'
												: 'bg-blue-500'}"
										style="width: {Math.min(100, (info.used / info.limit) * 100).toFixed(1)}%"
									></div>
								</div>
								<div class="flex justify-between text-gray-400">
									<span>{$i18n.t('Remaining')}: {formatNumber(info.remaining ?? 0)}</span>
									<span>{$i18n.t('Resets at')}: {formatResetAt(info.reset_at)}</span>
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{:else}
				<div class="text-xs text-gray-400">{$i18n.t('No usage data available.')}</div>
			{/if}
		</div>

		<!-- Section 3: Per-member usage -->
		{#if usageData && usageData.members.length > 0}
			<hr class="border-gray-100 dark:border-gray-800" />

			<div>
				<div class="mb-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">
					{$i18n.t('Member Usage')}
				</div>

				<div class="overflow-x-auto">
					<table class="w-full text-xs">
						<thead>
							<tr class="text-gray-400 border-b border-gray-100 dark:border-gray-800">
								<th class="text-left pb-1 font-medium">{$i18n.t('Name')}</th>
								<th
									class="text-right pb-1 font-medium {configuredPeriod === 'daily'
										? 'text-gray-600 dark:text-gray-300'
										: ''}">{$i18n.t('Today')}</th
								>
								<th
									class="text-right pb-1 font-medium pl-3 {configuredPeriod === 'weekly'
										? 'text-gray-600 dark:text-gray-300'
										: ''}">{$i18n.t('This Week')}</th
								>
								<th
									class="text-right pb-1 font-medium pl-3 {configuredPeriod === 'monthly'
										? 'text-gray-600 dark:text-gray-300'
										: ''}">{$i18n.t('This Month')}</th
								>
							</tr>
						</thead>
						<tbody>
							{#each usageData.members as member}
								<tr class="border-b border-gray-50 dark:border-gray-800/50 last:border-0">
									<td class="py-1 pr-2 truncate max-w-[100px] dark:text-gray-300" title={member.name}>
										{member.name}
									</td>
									<td
										class="text-right py-1 tabular-nums dark:text-gray-300 {configuredPeriod ===
										'daily'
											? 'font-semibold'
											: 'text-gray-500'}"
									>
										{formatNumber(member.daily)}
									</td>
									<td
										class="text-right py-1 pl-3 tabular-nums dark:text-gray-300 {configuredPeriod ===
										'weekly'
											? 'font-semibold'
											: 'text-gray-500'}"
									>
										{formatNumber(member.weekly)}
									</td>
									<td
										class="text-right py-1 pl-3 tabular-nums dark:text-gray-300 {configuredPeriod ===
										'monthly'
											? 'font-semibold'
											: 'text-gray-500'}"
									>
										{formatNumber(member.monthly)}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	{/if}
</div>

<style>
	input::-webkit-outer-spin-button,
	input::-webkit-inner-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}

	input[type='number'] {
		-moz-appearance: textfield;
	}
</style>
