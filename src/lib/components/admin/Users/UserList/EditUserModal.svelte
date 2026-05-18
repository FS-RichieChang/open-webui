<script lang="ts">
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';
	import { createEventDispatcher } from 'svelte';
	import { onMount, getContext } from 'svelte';

	import { goto } from '$app/navigation';

	import {
		updateUserById,
		getUserGroupsById,
		getUserTokenLimit,
		updateUserTokenLimit,
		getUserTokenUsage
	} from '$lib/apis/users';

	import Modal from '$lib/components/common/Modal.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import localizedFormat from 'dayjs/plugin/localizedFormat';
	import XMark from '$lib/components/icons/XMark.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import UserProfileImage from '$lib/components/chat/Settings/Account/UserProfileImage.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();
	dayjs.extend(localizedFormat);

	export let show = false;
	export let selectedUser;
	export let sessionUser;

	$: if (show) {
		init();
	}

	const init = () => {
		if (selectedUser) {
			_user = selectedUser;
			_user.password = '';
			loadUserGroups();
			loadTokenLimit();
			loadTokenUsage();
		}
	};

	let _user = {
		profile_image_url: '',
		role: 'pending',
		name: '',
		email: '',
		password: ''
	};

	let userGroups: any[] | null = null;

	let tokenLimit = { enabled: false, limit: 0, period: 'daily' };
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

	const submitHandler = async () => {
		const res = await updateUserById(localStorage.token, selectedUser.id, _user).catch((error) => {
			toast.error(`${error}`);
		});

		await updateUserTokenLimit(localStorage.token, selectedUser.id, tokenLimit).catch((error) => {
			toast.error(`${error}`);
		});

		if (res) {
			dispatch('save');
			show = false;
		}
	};

	const loadUserGroups = async () => {
		if (!selectedUser?.id) return;
		userGroups = null;

		userGroups = await getUserGroupsById(localStorage.token, selectedUser.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
	};

	const loadTokenLimit = async () => {
		if (!selectedUser?.id) return;
		const res = await getUserTokenLimit(localStorage.token, selectedUser.id).catch(() => null);
		tokenLimit = res ?? { enabled: false, limit: 0, period: 'daily' };
	};

	const loadTokenUsage = async () => {
		if (!selectedUser?.id) return;
		tokenUsage = await getUserTokenUsage(localStorage.token, selectedUser.id).catch(() => null);
	};

	const formatNumber = (n: number) => n.toLocaleString();

	const formatResetAt = (epoch: number) => {
		return new Date(epoch * 1000).toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
	};
</script>

<Modal size="sm" bind:show>
	<div>
		<div class=" flex justify-between dark:text-gray-300 px-5 pt-4 pb-2">
			<div class=" text-lg font-medium self-center">{$i18n.t('Edit User')}</div>
			<button
				class="self-center"
				aria-label={$i18n.t('Close')}
				on:click={() => {
					show = false;
				}}
			>
				<XMark className={'size-5'} />
			</button>
		</div>

		<div class="flex flex-col md:flex-row w-full md:space-x-4 dark:text-gray-200">
			<div class=" flex flex-col w-full sm:flex-row sm:justify-center sm:space-x-6">
				<form
					class="flex flex-col w-full"
					on:submit|preventDefault={() => {
						submitHandler();
					}}
				>
					<div class=" px-5 pt-3 pb-5 w-full">
						<div class="flex self-center w-full">
							<div class=" self-start h-full mr-6">
								<UserProfileImage
									imageClassName="size-14"
									bind:profileImageUrl={_user.profile_image_url}
									user={_user}
								/>
							</div>

							<div class=" flex-1">
								<div class="overflow-hidden w-ful mb-2">
									<div class=" self-center capitalize font-medium truncate">
										{selectedUser.name}
									</div>

									<div class="text-xs text-gray-500">
										{$i18n.t('Created at')}
										{dayjs(selectedUser.created_at * 1000).format('LL')}
									</div>
								</div>

								<div class=" flex flex-col space-y-1.5">
									{#if (userGroups ?? []).length > 0}
										<div class="flex flex-col w-full text-sm">
											<div class="mb-1 text-xs text-gray-500">{$i18n.t('User Groups')}</div>

											<div class="flex flex-wrap gap-1 my-0.5 -mx-1">
												{#each userGroups as userGroup}
													<span
														class="px-1.5 py-0.5 rounded-xl bg-gray-100 dark:bg-gray-850 text-xs"
													>
														<a
															href={'/admin/users/groups?id=' + userGroup.id}
															on:click|preventDefault={() =>
																goto('/admin/users/groups?id=' + userGroup.id)}
														>
															{userGroup.name}
														</a>
													</span>
												{/each}
											</div>
										</div>
									{/if}

									<div class="flex flex-col w-full">
										<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Role')}</div>

										<div class="flex-1">
											<select
												class="w-full text-sm bg-transparent disabled:text-gray-500 dark:disabled:text-gray-500 outline-hidden"
												bind:value={_user.role}
												aria-label={$i18n.t('Role')}
												disabled={_user.id == sessionUser.id}
												required
											>
												<option value="admin">{$i18n.t('Admin')}</option>
												<option value="user">{$i18n.t('User')}</option>
												<option value="pending">{$i18n.t('Pending')}</option>
											</select>
										</div>
									</div>

									<div class="flex flex-col w-full">
										<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Name')}</div>

										<div class="flex-1">
											<input
												class="w-full text-sm bg-transparent outline-hidden"
												type="text"
												bind:value={_user.name}
												aria-label={$i18n.t('Name')}
												placeholder={$i18n.t('Enter Your Name')}
												autocomplete="off"
												required
											/>
										</div>
									</div>

									<div class="flex flex-col w-full">
										<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Email')}</div>

										<div class="flex-1">
											<input
												class="w-full text-sm bg-transparent disabled:text-gray-500 dark:disabled:text-gray-500 outline-hidden"
												type="email"
												bind:value={_user.email}
												aria-label={$i18n.t('Email')}
												placeholder={$i18n.t('Enter Your Email')}
												autocomplete="off"
												required
											/>
										</div>
									</div>

									{#if _user?.oauth}
										<div class="flex flex-col w-full">
											<div class=" mb-1 text-xs text-gray-500">{$i18n.t('OAuth ID')}</div>

											<div class="flex-1 text-sm break-all mb-1 flex flex-col space-y-1">
												{#each Object.keys(_user.oauth) as key}
													<div>
														<span class="text-gray-500">{key}</span>
														<span class="">{_user.oauth[key]?.sub}</span>
													</div>
												{/each}
											</div>
										</div>
									{/if}

									<div class="flex flex-col w-full">
										<div class=" mb-1 text-xs text-gray-500">{$i18n.t('New Password')}</div>

										<div class="flex-1">
											<SensitiveInput
												class="w-full text-sm bg-transparent outline-hidden"
												type="password"
												aria-label={$i18n.t('New Password')}
												placeholder={$i18n.t('Enter New Password')}
												bind:value={_user.password}
												autocomplete="new-password"
												required={false}
											/>
										</div>
									</div>
								</div>
							</div>
						</div>

						<hr class="my-3 border-gray-100 dark:border-gray-800" />

						<div class="flex flex-col w-full">
							<div class="mb-2 text-xs font-medium text-gray-500">{$i18n.t('Token Usage')}</div>

							{#if tokenUsage}
								<div class="flex flex-col gap-1.5 text-xs">
									{#each [['daily', $i18n.t('Today')], ['weekly', $i18n.t('This Week')], ['monthly', $i18n.t('This Month')]] as [period, label]}
										{@const info = tokenUsage[period as 'daily' | 'weekly' | 'monthly']}
										{@const isLimited = info.limit > 0}
										{@const displayUsed = info.is_group_limit ? (info.group_used ?? 0) : info.used}
										{@const displayRemaining = info.is_group_limit ? (info.group_remaining ?? 0) : info.remaining}
										<div class="flex flex-col gap-0.5">
											<div class="flex items-center justify-between">
												<span class="text-gray-500">{label}</span>
												<span class="font-medium dark:text-gray-300">
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
												<div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1">
													<div
														class="h-1 rounded-full transition-all {displayUsed >= info.limit
															? 'bg-red-500'
															: displayUsed / info.limit > 0.8
																? 'bg-yellow-400'
																: 'bg-blue-500'}"
														style="width: {Math.min(100, (displayUsed / info.limit) * 100).toFixed(1)}%"
													></div>
												</div>
												<div class="flex justify-between text-gray-400">
													<span>{$i18n.t('Remaining')}: {formatNumber(displayRemaining)}</span>
													<span>{$i18n.t('Resets at')}: {formatResetAt(info.reset_at)}</span>
												</div>
												{#if info.is_group_limit}
													<div class="text-gray-400">
														{$i18n.t('Personal')}: {formatNumber(info.used)} {$i18n.t('tokens')} &nbsp;·&nbsp; {info.group_name}
													</div>
												{/if}
											{/if}
										</div>
									{/each}
								</div>
							{:else}
								<div class="text-xs text-gray-400">{$i18n.t('Loading...')}</div>
							{/if}
						</div>

						<hr class="my-3 border-gray-100 dark:border-gray-800" />

						<div class="flex flex-col w-full">
							<div class="mb-1.5 text-xs font-medium text-gray-500">
								{$i18n.t('Token Rate Limiting (Override)')}
							</div>

							<div class="flex flex-col gap-2">
								<div class="flex w-full items-center justify-between">
									<div class="text-xs font-medium">{$i18n.t('Enable Token Rate Limit')}</div>
									<Switch bind:state={tokenLimit.enabled} />
								</div>

								{#if tokenLimit.enabled}
									<div class="ml-2 flex flex-col gap-2">
										<div class="flex w-full items-center justify-between">
											<div class="text-xs font-medium">{$i18n.t('Token Limit')}</div>
											<input
												type="number"
												min="1"
												class="w-fit rounded-sm px-2 p-1 text-xs bg-transparent outline-hidden text-right"
												bind:value={tokenLimit.limit}
											/>
										</div>

										<div class="flex w-full items-center justify-between">
											<div class="text-xs font-medium">{$i18n.t('Period')}</div>
											<select
												class="w-fit pr-8 rounded-sm px-2 p-1 text-xs bg-transparent outline-hidden text-right"
												bind:value={tokenLimit.period}
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

						<div class="flex justify-end pt-3 text-sm font-medium">
							<button
								class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full flex flex-row space-x-1 items-center"
								type="submit"
							>
								{$i18n.t('Save')}
							</button>
						</div>
					</div>
				</form>
			</div>
		</div>
	</div>
</Modal>

<style>
	input::-webkit-outer-spin-button,
	input::-webkit-inner-spin-button {
		/* display: none; <- Crashes Chrome on hover */
		-webkit-appearance: none;
		margin: 0; /* <-- Apparently some margin are still there even though it's hidden */
	}

	.tabs::-webkit-scrollbar {
		display: none; /* for Chrome, Safari and Opera */
	}

	.tabs {
		-ms-overflow-style: none; /* IE and Edge */
		scrollbar-width: none; /* Firefox */
	}

	input[type='number'] {
		-moz-appearance: textfield; /* Firefox */
	}
</style>
