# Token Rate Limiting for Users and Groups

**日期**：2026-05-07（持續更新至 2026-05-13）
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

---

## 1. 修改摘要

新增對使用者與群組的 Token 用量**限流**與**用量顯示**功能。管理員可在群組權限設定或使用者編輯頁面，設定每個周期（每日／每週／每月）的 Token 上限。當使用者累計用量達到上限時，系統拒絕新的聊天請求並回傳 HTTP 429。此外，管理員編輯任一使用者時，可直接看到該使用者今日／本週／本月的 Token 用量，有設限時並顯示進度條與重置時間。

### 新增檔案

| 檔案 | 說明 |
|------|------|
| `backend/open_webui/utils/token_limit.py` | 核心限流邏輯：計算有效限制、查詢用量、拋出 429、回傳三周期用量 |
| `backend/open_webui/utils/enterprise_setup.py` | 企業 Filter 自動部署：啟動時將限流 Filter 寫入 DB，確保永遠存在 |
| `docs/ai-changelog/2026-05-07-token-rate-limiting.md` | 本文件 |

### 修改檔案

| 檔案 | 變更說明 |
|------|---------|
| `backend/open_webui/models/chat_messages.py` | 新增 `get_user_token_usage_since()`、`get_group_token_usage_since()` 方法 |
| `backend/open_webui/models/users.py` | 新增 `UserTokenLimitForm` Pydantic schema |
| `backend/open_webui/routers/users.py` | 新增 `GET/PUT /{user_id}/token-limit`、`GET /{user_id}/token-usage` 共三個 Admin API 端點 |
| `backend/open_webui/main.py` | lifespan 加入 `seed_enterprise_filters()` 啟動呼叫（2 行） |
| `src/lib/constants/permissions.ts` | `DEFAULT_PERMISSIONS` 加入 `token_limit` 預設值 |
| `src/lib/apis/users/index.ts` | 新增 `getUserTokenLimit()`、`updateUserTokenLimit()`、`getUserTokenUsage()` |
| `src/lib/components/admin/Users/Groups/Permissions.svelte` | 群組權限頁新增 Token Rate Limiting 區塊 |
| `src/lib/components/admin/Users/UserList/EditUserModal.svelte` | 使用者編輯 modal 新增 Token Usage 用量顯示區塊與個人限流覆蓋設定 |
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
- Admin → Users → Groups → Permissions 頁底部新增「Token Rate Limiting」設定區塊。
- Admin → Users → Edit User modal 新增「Token Usage」用量顯示區塊（今日／本週／本月，有設限時顯示進度條與重置時間）。
- Admin → Users → Edit User modal 新增「Token Rate Limiting (Override)」個人限流覆蓋設定區塊。

---

## 5. 注意事項

1. **效能**：每次聊天請求都會查詢 `chat_message` 表加總 Token，群組模式下還需查詢群組成員 ID。資料量大時查詢可能變慢，建議屆時加 Redis 快取。
2. **SQLite 並發**：預設使用 SQLite，單一寫入鎖在高並發情況下可能造成排隊。使用者規模超過 50-100 人時建議切換 PostgreSQL。
3. **直接連接不受限**：`generate_direct_chat_completion()` 路徑不經過 Filter inlet，目前不受限流影響。
4. **UI 顯示限制**：EditUserModal 的 Token Usage 顯示的是個人用量，但套用群組限流時限額是群組共享池總量。兩者基準不同，剩餘量顯示可能有誤差（實際執行以群組總用量為準）。
5. **時區**：周期起算以 UTC 為準，若使用者在不同時區，「每日」重置時間會有差異。
6. **Token 估算誤差**：`chat_message.usage` 的數值來自 LLM Provider 回報，部分 Provider 的計算方式與實際計費可能有落差。
7. **Filter 保護**：`enterprise_setup.py` 在每次啟動時確認 Filter 存在且為 active/global，即使管理員誤刪或停用，下次重啟會自動恢復。

---

## 6. 後續待辦

- [ ] **Redis 快取**：將當前周期累計用量快取至 Redis，減少 DB 查詢次數，提升高流量下的效能。
- [ ] **直接連接限流**：`generate_direct_chat_completion()` 路徑目前不受限，若有需要需另行加入。
- [ ] **UI 群組用量顯示**：EditUserModal 的「用量 / 上限」在群組限流模式下應顯示群組總用量，而非個人用量，需修改 `get_token_usage_info` 回傳結構與前端顯示邏輯。
- [ ] **使用者自助查詢**：在聊天介面或使用者個人設定頁顯示自己的用量，讓使用者不必等到 429 才知道快超限。
- [ ] **其他語言 i18n**：en-US、zh-TW、zh-CN、de-DE 已完整翻譯；其餘 57 個語系為空字串佔位，需各語系貢獻者補譯。
- [ ] **自動重置通知**：周期重置後可考慮透過 WebSocket 推播通知給受限使用者。
- [ ] **用量報表整合**：在 Admin Analytics 儀表板整合限流設定與實際用量的對照視圖。
