# Token Rate Limiting for Users and Groups

**日期**：2026-05-07（持續更新至 2026-05-18）
**分支**：`claude/add-user-group-settings-Ci255`
**Commits**：
- `fdb5c4c6` — feat: add token rate limiting for users and groups
- `1400ba04` — docs: add ai-changelog for token rate limiting feature
- `c6d69c6a` — feat: add token usage display for all three periods in admin user modal
- `8ccc9bc4` — docs: update ai-changelog to include token usage display changes
- `ca249ad3` — i18n: add German translations for token rate limiting keys
- `7b1a6e2a` — docs: update ai-changelog to include de-DE German translation
- `b71377d6` — refactor: move token rate limit enforcement from chat.py to Global Filter
- `79795feb` — feat: group token limit uses shared pool with independent period checks
- `b334967c` — fix: group token limit uses most permissive group per period
- `0b005aa1` — fix: inject stream_options include_usage in enterprise filter inlet
- `b8b4523d` — feat: add token usage settings tab for regular users
- `b4b465b9` — feat: enforce token limit immediately with per-user lock and max_tokens cap
- `8cfa1c0e` — feat: fix group token usage display and add admin overview page
- `9be06b9c` — feat: move token rate limiting to separate tab in group edit modal
- `fd612dae` — feat: add inline token usage display with per-member breakdown in group settings

---

## 1. 修改摘要

新增對使用者與群組的 Token 用量**限流**與**用量顯示**功能。管理員可在群組權限設定或使用者編輯頁面，設定每個周期（每日／每週／每月）的 Token 上限。當使用者累計用量達到上限時，系統拒絕新的聊天請求並回傳 HTTP 429。此外，管理員編輯任一使用者時，可直接看到該使用者今日／本週／本月的 Token 用量，有設限時並顯示進度條與重置時間。一般使用者也可在個人設定頁查看自己的用量。

### 新增檔案

| 檔案 | 說明 |
|------|------|
| `backend/open_webui/utils/token_limit.py` | 核心限流邏輯：計算有效限制、查詢用量、拋出 429、回傳三周期用量、計算剩餘預算 |
| `backend/open_webui/utils/enterprise_setup.py` | 企業 Filter 自動部署：啟動時將限流 Filter 寫入 DB，確保永遠存在 |
| `backend/open_webui/routers/enterprise.py` | Enterprise API router：`GET /api/v1/enterprise/groups/token-usage` 群組用量總覽端點；`GET /api/v1/enterprise/groups/{id}/token-usage` 單一群組三周期用量 + per-member 細項 |
| `src/lib/apis/enterprise/index.ts` | 前端 Enterprise API client |
| `src/routes/(app)/admin/group-token-usage/+page.svelte` | 管理員群組 Token 用量總覽頁（period 篩選、進度條、重置時間） |
| `src/lib/components/chat/Settings/TokenUsage.svelte` | 使用者個人設定頁的 Token 用量顯示元件（每日／本週／本月） |
| `docs/ai-changelog/2026-05-07-token-rate-limiting.md` | 本文件 |

### 修改檔案

| 檔案 | 變更說明 |
|------|---------|
| `backend/open_webui/models/chat_messages.py` | 新增 `get_user_token_usage_since()`、`get_group_token_usage_since()` 方法 |
| `backend/open_webui/models/users.py` | 新增 `UserTokenLimitForm` Pydantic schema |
| `backend/open_webui/routers/users.py` | 新增 `GET/PUT /{user_id}/token-limit`、`GET /{user_id}/token-usage` 共三個 Admin API 端點；新增 `GET /me/token-usage` 供一般使用者查詢自身用量 |
| `backend/open_webui/main.py` | lifespan 加入 `seed_enterprise_filters()` 啟動呼叫；新增 enterprise router 掛載 |
| `src/lib/constants/permissions.ts` | `DEFAULT_PERMISSIONS` 加入 `token_limit` 預設值 |
| `src/lib/apis/users/index.ts` | 新增 `getUserTokenLimit()`、`updateUserTokenLimit()`、`getUserTokenUsage()`、`getMyTokenUsage()` |
| `src/lib/components/admin/Users/Groups/Permissions.svelte` | 群組權限頁原有 Token Rate Limiting 區塊（已移至獨立 tab） |
| `src/lib/components/admin/Users/Groups/TokenRateLimit.svelte` | Token Limit 獨立 tab：設定 → 群組彙總用量 → per-member 用量表格 |
| `src/lib/components/admin/Users/Groups/EditGroupModal.svelte` | 新增 Token Limit tab；修正新增群組時 tab 不顯示的問題 |
| `src/lib/components/admin/Users/UserList/EditUserModal.svelte` | 使用者編輯 modal 新增 Token Usage 顯示區塊；群組限流時改用共享池用量計算進度條，個人用量列為次要參考 |
| `src/lib/components/chat/Settings/TokenUsage.svelte` | 群組限流時改用共享池用量計算進度條 |
| `src/lib/components/chat/SettingsModal.svelte` | 個人設定 modal 新增「Token Usage」頁籤 |
| `src/lib/i18n/locales/en-US/translation.json` | 新增翻譯鍵值 |
| `src/lib/i18n/locales/zh-TW/translation.json` | 新增繁體中文翻譯 |
| `src/lib/i18n/locales/zh-CN/translation.json` | 新增簡體中文翻譯 |
| `src/lib/i18n/locales/de-DE/translation.json` | 新增德文翻譯 |
| 其餘 57 個語系 `translation.json` | 批次插入空字串佔位鍵值 |

### 重構變更（`chat.py` 回歸 upstream）

限流執行原本直接插入 `utils/chat.py`，重構後改為透過 open-webui 原生 **Global Filter** 機制執行：

- `chat.py`：移除我們的修改，完全回歸 upstream 原始狀態
- `enterprise_setup.py`：啟動時自動在 DB 安裝 `enterprise-token-rate-limit` Global Filter，Filter 的 `inlet` hook 執行限流檢查
- 好處：`chat.py` 未來 rebase 不再有衝突風險

### Bug Fix：Token 用量永遠顯示 0

**根本原因**：OpenAI-compatible streaming 預設不回傳 usage 資料，需在請求中帶 `stream_options: {include_usage: true}` 才會包含。前端僅在 model 設定 `capabilities.usage: true` 時才加這個參數，導致多數 model 的 `chat_message.usage` 永遠是 NULL，Token 計數顯示 0。

**修復**：在 Enterprise Filter 的 `inlet` 自動注入 `stream_options: {include_usage: true}`（僅 stream 模式）：
- **OpenAI-compatible / LiteLLM**：provider 收到參數後回傳 usage，middleware 正確存入 DB
- **Ollama**：payload 轉換函式 `convert_payload_openai_to_ollama` 只複製已知欄位，此參數自動被忽略（Ollama 天生在 final chunk 回傳 `eval_count`）

同步機制升級：`seed_enterprise_filters()` 現在每次啟動都比對 filter code，有變更即自動更新 DB，不需手動刪除紀錄。

### 使用者自助查詢用量（`b8b4523d`）

一般使用者現在可在個人設定頁的「Token Usage」頁籤查看自己三個周期的用量，無需聯繫管理員。

- 後端新增 `GET /api/v1/users/me/token-usage` 端點，權限為已登入使用者（無需 admin）
- 前端新增 `TokenUsage.svelte` 元件，顯示每日／本週／本月用量，有設限時同步顯示進度條與重置時間
- `SettingsModal.svelte` 加入「Token Usage」頁籤，設限使用者才看得到此頁籤

### 並發安全 + max_tokens 防超支（`b4b465b9`）

原本的 inlet 僅做「進門前檢查」，在高並發下兩個同時送出的請求可能都通過檢查，然後雙雙消耗 Token 直到超限。此次升級分兩層封堵：

1. **Per-user asyncio.Lock**：同一使用者的並發請求在 inlet 序列化，確保兩個同時進來的請求不會都通過配額檢查。
2. **注入 `max_tokens`**：在 inlet 計算剩餘預算（`get_remaining_token_budget()`），將值注入請求的 `max_tokens`，即使 LLM 生成速度快於計費回報，單次回應的 Token 量也被硬性封頂。

`token_limit.py` 新增 `get_remaining_token_budget()`，與 `check_token_limit` 共用查詢邏輯，只做一次 DB round-trip 即可同時完成「是否超限」與「剩餘多少」兩個判斷。

### Token Rate Limiting 獨立為群組編輯的專屬 Tab（`9be06b9c`）

原本的群組限流設定混在「Permissions」tab 底部，不易察覺。此次將其獨立出來：

- `Permissions.svelte`：移除 Token Rate Limiting 區塊
- 新增 `TokenRateLimit.svelte` 元件，專責 enable switch + token limit + period 設定
- `EditGroupModal.svelte`：新增 `Token Limit` tab（ChartBar 圖示），預設 tabs 加入 `token_limit`
- **Bug Fix**：`Groups.svelte` 建立新群組的 modal 硬編碼 `tabs={['general', 'permissions']}`，導致 Token Limit tab 不出現。修正方式：移除自訂 `tabs` prop，沿用 `EditGroupModal` 預設值。

---

### 群組 Token Limit tab 內嵌用量顯示 + per-member 細項（`fd612dae`）

管理員在群組 Token Limit tab 中，無需跳轉至其他頁面即可掌握該群組的完整用量資訊。

**版面三層結構：**

1. **設定**（最上方）：Enable 開關 + Token Limit 數值 + Period 選擇
2. **群組彙總用量**（中間）：Today / This Week / This Month；有設限的 period 顯示進度條 + Remaining + Resets at
3. **成員用量表格**（最下方）：列出所有群組成員的三個周期用量，按 configured period 用量降序排列，configured period 欄位加粗

**後端新增 `GET /enterprise/groups/{group_id}/token-usage`：**
- 永遠回傳（無論有無啟用限流）
- 三個 period 的彙總用量
- `members` 陣列：每位成員的 daily / weekly / monthly 用量（使用 `ChatMessages.get_token_usage_by_user()` with `group_id` filter，共三次查詢）

**新增群組（groupId=null）**：自動不顯示用量區塊，僅顯示設定。

---

### 修正群組用量顯示 + 管理員總覽頁（`8cfa1c0e`）

**問題背景**：UI 顯示的進度條和剩餘量基於使用者**個人**用量計算，但群組限流的配額是**群組共享池（所有成員加總）**，導致使用者看到的剩餘量偏高，不反映真實狀況。

**修正方式**：

重構 `get_token_usage_info()`——群組限流 period 現在額外查詢群組共享池用量，回傳新欄位：
- `is_group_limit: true`：本 period 的 limit 來自群組
- `group_used`：群組所有成員的總 Token 用量
- `group_remaining`：群組實際剩餘額度
- `group_name`：生效的群組名稱

前端 `EditUserModal.svelte` 與 `TokenUsage.svelte` 改用 `group_used / limit` 計算進度條；剩餘量顯示 `group_remaining`。admin 視角額外顯示個人用量（`Personal: X tokens · GroupName`）供追蹤個人貢獻。

**新增管理員群組總覽頁**（全新檔案，不影響 upstream rebase）：
- `backend/open_webui/routers/enterprise.py`：新 `GET /api/v1/enterprise/groups/token-usage` 端點，回傳所有啟用限流的群組及其當期共享池用量
- `src/lib/apis/enterprise/index.ts`：前端 API client
- `src/routes/(app)/admin/group-token-usage/+page.svelte`：表格顯示群組名稱、period、已用 / 上限、進度條、重置時間；支援 period 篩選
- `Permissions.svelte` Token Rate Limiting 標題旁新增「查看用量 →」連結

---

## 2. 修改原因

管理員反映使用者可能在不知情的狀況下大量消耗 Token，導致 API 費用失控。需要一個機制讓管理員可以針對不同群組或特定使用者設定用量上限，避免誤用。

---

## 3. Business Rule

1. **限流層級**：支援群組層級與使用者個人層級兩種設定。
2. **優先順序**：使用者個人設定（Override）優先於群組設定。個人設定啟用時，不再套用任何群組限制。
3. **群組共享池**：群組的 Token 限額由群組內**所有成員的用量加總**計算，非每人獨立配額。
4. **多群組規則**：使用者同時屬於多個有限流設定的群組時，針對**同一 period**，以**限額最高（最寬鬆）的群組**為準。未設定限流的群組完全忽略。
5. **不同 Period 獨立計算**：daily、weekly、monthly 分別套用不同群組的共享池，互不影響。使用者須同時通過所有有效 period 的群組檢查。
6. **周期選項**：每日（daily）、每週（weekly）、每月（monthly），周期從 UTC 時間的自然邊界起算（午夜、週一、每月一日）。
7. **超限行為**：拒絕請求，回傳 HTTP 429，錯誤訊息明確告知群組名稱、已用量、上限與周期。
8. **Admin 不豁免**：所有角色（包含 Admin）均受限流管控。
9. **無設定即無限**：若使用者與所屬群組均未啟用限流，不做任何限制。
10. **Token 計算來源**：從 `chat_message` 表的 `usage` JSON 欄位加總，只計算 `role = 'assistant'` 的訊息，並以 `input_tokens + output_tokens` 為準。

---

## 4. 影響範圍

### 後端
- 限流檢查透過 Global Filter 的 `inlet` hook 執行，涵蓋所有走 `process_filter_functions` 的聊天請求（OpenAI、Ollama、Anthropic 等所有 LLM Provider）。
- 直接連接（direct connection）的請求走 `generate_direct_chat_completion()`，**不經過** Filter inlet，不受限流影響。
- 群組用量查詢：每次聊天請求對有效 period 執行群組成員 ID 查詢 + 群組用量加總查詢。

### 資料庫
- **無新增資料表**，設定存於現有 JSON 欄位：
  - 群組限流設定：`group.permissions.token_limit`
  - 使用者限流設定：`user.info.token_limit`
  - 限流 Filter 程式碼：`function` 表（id: `enterprise-token-rate-limit`）
- 每次聊天請求新增 `chat_message` 表的聚合查詢（`SUM` of tokens since period start）。

### 前端
- Admin → Users → Groups → 群組編輯 modal 新增獨立「Token Limit」tab：設定、群組彙總用量（三周期）、成員個別用量表格。
- Admin → Users → Edit User modal 新增「Token Usage」用量顯示區塊（群組限流時顯示共享池用量與進度條；個人用量列為次要參考）。
- Admin → Users → Edit User modal 新增「Token Rate Limiting (Override)」個人限流覆蓋設定區塊。
- Settings modal 新增「Token Usage」頁籤，供一般使用者自助查看三個周期用量（群組限流時顯示共享池用量）。
- `/admin/group-token-usage` 新管理員頁面，顯示所有啟用限流的群組及其當期共享池使用情況（各群組詳情可直接在群組 Token Limit tab 查看）。

---

## 5. 注意事項

1. **效能**：每次聊天請求都會查詢 `chat_message` 表加總 Token，群組模式下還需查詢群組成員 ID。資料量大時查詢可能變慢，建議屆時加 Redis 快取。
2. **SQLite 並發**：預設使用 SQLite，單一寫入鎖在高並發情況下可能造成排隊。使用者規模超過 50-100 人時建議切換 PostgreSQL。
3. **直接連接不受限**：`generate_direct_chat_completion()` 路徑不經過 Filter inlet，目前不受限流影響。
4. ~~**UI 顯示限制**~~：已修正（`8cfa1c0e`）。群組限流時 UI 現在正確顯示群組共享池用量。
5. **時區**：周期起算以 UTC 為準，若使用者在不同時區，「每日」重置時間會有差異。
6. **Token 估算誤差**：`chat_message.usage` 的數值來自 LLM Provider 回報，部分 Provider 的計算方式與實際計費可能有落差。
7. **Filter 保護**：`enterprise_setup.py` 在每次啟動時確認 Filter 存在且為 active/global，即使管理員誤刪或停用，下次重啟會自動恢復。

---

## 6. 後續待辦

- [ ] **Redis 快取**：將當前周期累計用量快取至 Redis，減少 DB 查詢次數，提升高流量下的效能。
- [ ] **直接連接限流**：`generate_direct_chat_completion()` 路徑目前不受限，若有需要需另行加入。
- [x] **UI 群組用量顯示**：EditUserModal 與 TokenUsage.svelte 改用群組共享池用量計算進度條；新增管理員群組總覽頁。（`8cfa1c0e`）
- [x] **使用者自助查詢**：在個人設定頁新增「Token Usage」頁籤，讓使用者不必等到 429 才知道快超限。（`b8b4523d`）
- [x] **群組 Token 設定獨立 Tab**：Token Rate Limiting 從 Permissions 分離為專屬 tab；修正新增群組時 tab 不顯示的 bug。（`9be06b9c`）
- [x] **群組 Token Limit tab 內嵌用量 + 成員細項**：設定上方直接顯示三周期彙總，下方列出所有成員的個別用量表格。（`fd612dae`）
- [ ] **其他語言 i18n**：en-US、zh-TW、zh-CN、de-DE 已完整翻譯；其餘 57 個語系為空字串佔位，需各語系貢獻者補譯。
- [ ] **自動重置通知**：周期重置後可考慮透過 WebSocket 推播通知給受限使用者。
- [ ] **用量報表整合**：在 Admin Analytics 儀表板整合限流設定與實際用量的對照視圖。
