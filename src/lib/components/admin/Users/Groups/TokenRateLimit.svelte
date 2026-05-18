<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import Switch from '$lib/components/common/Switch.svelte';

	export let permissions: any = {};
</script>

<div class="space-y-2 pr-1">
	<div class="flex items-start justify-between mb-3">
		<div>
			<div class="text-sm font-medium">{$i18n.t('Token Rate Limiting')}</div>
			<div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
				{$i18n.t('Limit the number of tokens this group can consume per period.')}
			</div>
		</div>
		<a
			href="/admin/group-token-usage"
			class="text-xs text-blue-500 hover:underline shrink-0 mt-0.5"
		>
			{$i18n.t('View Usage')} →
		</a>
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
					<div class="self-center text-xs font-medium">
						{$i18n.t('Token Limit')}
					</div>
					<input
						type="number"
						min="1"
						class="w-32 rounded-lg text-sm bg-transparent outline-none border border-gray-100 dark:border-gray-600 px-2 py-1 text-right dark:text-gray-300"
						bind:value={permissions.token_limit.limit}
					/>
				</div>

				<div class="flex w-full items-center justify-between">
					<div class="self-center text-xs font-medium">
						{$i18n.t('Period')}
					</div>
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
