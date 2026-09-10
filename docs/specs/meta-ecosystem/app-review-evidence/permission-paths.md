# Permission-by-permission review paths

These instructions are written in English so they can be pasted into Meta App Review. Replace bracketed values only in the private submission. Do not place credentials, tokens, customer data or private recording links in this repository.

All paths start from a clean browser session at `[STAGING_URL]/login`. The reviewer signs in with the supplied **App Review Admin** CRM account. Spanish UI labels are preserved exactly as displayed.

## `business_management`

**Use case.** Captame lets an authorized real-estate brokerage administrator connect the brokerage's Meta business assets. The application uses this access only to discover and bind the selected WABA, Pages, ad accounts and conversion datasets to that brokerage tenant.

**Path.**

1. Sign in at `/login`, open **Mis canales**, and locate **Meta Business**.
2. Select **Conectar cuenta** and complete the full Meta Business authorization for `[AR META BUSINESS]`, granting the requested access.
3. Return to **Canales Meta** and confirm the success message **Cuenta Meta conectada y activos descubiertos**.
4. In **Conexiones**, show the active corporate connection. In **Identidades y activos**, show the discovered business-owned Page and ad account with their Meta IDs.
5. Select **Sincronizar** and show the successful asset count without exposing any access token.

**Expected proof.** The authorized business assets appear only inside the isolated App Review broker and can be synchronized; no unrelated business assets are displayed.

## `whatsapp_business_management`

**Use case.** Captame discovers and manages the brokerage's WhatsApp Business Account and registered business phone numbers so each CRM conversation is routed through the exact approved number.

**Path.**

1. From **Mis canales**, locate **WhatsApp Business** and select **Conectar cuenta**.
2. Complete WhatsApp Embedded Signup for `[AR WABA]` and select `[AR WA PHONE]`.
3. After redirect, show the active connection under **Conexiones**.
4. Under **Identidades y activos**, show the WABA/phone identity, its Meta ID, `whatsapp` channel, `Aprobado` state and `active` state.
5. Select **Sincronizar** and confirm the WABA assets refresh successfully.

**Expected proof.** The selected WABA and phone number are discovered and represented as auditable corporate assets; credentials are never displayed.

## `whatsapp_business_messaging`

**Use case.** Captame receives customer-initiated WhatsApp messages and allows an assigned human agent to reply from the unified CRM inbox using the same approved business number.

**Path.**

1. From `[AR EXTERNAL WA NUMBER]`, send `AR-WA-001 interested in Parque Norte` to `[AR WA PHONE]`.
2. In Captame, open **Bandeja Meta**, filter the channel to **WhatsApp**, and open the new `AR-WA-001` conversation.
3. Show the inbound message, the linked CRM lead, and the exact WhatsApp asset name in the conversation header.
4. Enter `AR-WA-001 reply from Captame` and send it within the customer-service window.
5. Show the reply in the external WhatsApp client, then return to Captame and show its sent/delivered/read state when available.

**Expected proof.** A real inbound message creates or links the correct tenant lead, and a human reply reaches the same user through the same WhatsApp business number.

## `instagram_business_basic`

**Use case.** With Instagram Login, Captame reads the minimum profile identity of a professional Business/Creator account so the user can recognize and authorize the correct account before messaging.

**Path.**

1. From **Mis canales**, locate **Instagram** and select **Conectar cuenta**.
2. Complete the full Instagram authorization using `[AR DIRECT IG PROFESSIONAL]` and grant the requested access.
3. Return to Captame and confirm the successful connection.
4. Under **Identidades y activos**, show the professional Instagram username and Meta account ID, plus its owner and approval state.
5. Show that no posts, personal profile fields or unrelated Instagram accounts are displayed.

**Expected proof.** Captame displays the authorized professional account's username and ID solely to identify the messaging asset.

## `instagram_business_manage_messages`

**Use case.** With Instagram Login, Captame receives messages addressed to an authorized professional account and lets its assigned user reply from the unified inbox.

**Path.**

1. Ensure `[AR DIRECT IG PROFESSIONAL]` is connected and approved under **Mis canales**.
2. From `[AR EXTERNAL IG USER]`, send `AR-IG-DIRECT-001` to that professional account.
3. Open **Bandeja Meta**, filter to **Instagram**, and open the new conversation.
4. Show the inbound message, linked lead and exact Instagram asset in the header.
5. Send `AR-IG-DIRECT-001 reply from Captame`, then show the reply arriving in the external Instagram client.

**Expected proof.** A user-initiated Instagram DM enters the correct brokerage inbox and the human reply is delivered through the directly authorized professional account.

## `pages_show_list`

**Use case.** Captame lists only Facebook Pages the authorizing person can access so the brokerage can identify the Page used for Messenger, linked Instagram messaging and Lead Ads.

**Path.**

1. From **Mis canales**, locate **Messenger** and select **Conectar cuenta**.
2. Complete full Meta authorization with `[AR META USER]`, selecting `[AR FACEBOOK PAGE]`.
3. Return to **Canales Meta** and show the successful connection.
4. Under **Identidades y activos**, show `[AR FACEBOOK PAGE]`, its Page ID, owner and approval state.
5. Confirm that an unselected control Page is not shown.

**Expected proof.** The application lists the Page selected during authorization and uses its stable ID to bind messages to the correct tenant asset.

## `pages_read_engagement`

**Use case.** Captame reads the selected Page's basic identity and the Page-scoped conversation context required to present Messenger conversations to authorized brokerage staff.

**Path.**

1. Connect `[AR FACEBOOK PAGE]` through **Mis canales → Messenger → Conectar cuenta**, including the complete authorization screen.
2. Under **Identidades y activos**, show the Page name and Page ID obtained from Meta.
3. From `[AR EXTERNAL FB USER]`, send `AR-FB-ENGAGEMENT-001` to the Page.
4. Open **Bandeja Meta**, filter to **Messenger**, and show the Page identity and inbound conversation context.
5. Open **Ver lead** to show that the interaction is tied to the isolated CRM lead, not exposed to another broker.

**Expected proof.** The selected Page's identity and user-initiated engagement are readable only by authorized users of the matching brokerage.

## `pages_manage_metadata`

**Use case.** Captame subscribes the selected Page to the `messages`, `messaging_postbacks`, `message_deliveries`, `message_reads` and, for a corporate Page, `leadgen` webhook fields so events reach the CRM reliably.

**Path.**

1. Start with `[AR FACEBOOK PAGE]` absent from **Mis canales**.
2. Select **Messenger → Conectar cuenta** and complete the full Meta authorization.
3. Return to Captame and show the Page under **Identidades y activos** in active state; this connection step performs the Page webhook subscription server-side.
4. From `[AR EXTERNAL FB USER]`, send `AR-FB-WEBHOOK-001` to the Page without manually refreshing or importing data.
5. Open **Bandeja Meta** and show the event-created conversation. Reply once and show the later delivery/read status update when available.

**Expected proof.** The Page begins delivering real webhook events after connection, and Captame processes messages and status changes without manual polling.

## `pages_messaging`

**Use case.** Captame lets an authorized human agent respond to people who initiate Messenger conversations with the brokerage's selected Facebook Page.

**Path.**

1. From `[AR EXTERNAL FB USER]`, send `AR-FB-MSG-001 interested in Parque Norte` to `[AR FACEBOOK PAGE]`.
2. In Captame, open **Bandeja Meta**, filter to **Messenger**, and select the new conversation.
3. Show the inbound message, the linked lead and `[AR FACEBOOK PAGE]` in the header.
4. Send `AR-FB-MSG-001 reply from Captame` within the allowed response window.
5. Show the reply in the external Messenger client, then show its status in Captame.

**Expected proof.** A human reply is sent only in an existing user-initiated conversation and uses the same Page that received the message.

## `instagram_basic`

**Use case.** In the Meta Business/Facebook Login flow, Captame reads the minimum identity of the professional Instagram account linked to an authorized Facebook Page so the brokerage can select the correct corporate identity.

**Path.**

1. From **Mis canales**, locate **Meta Business** and select **Conectar cuenta**.
2. Complete the full Meta authorization for `[AR META BUSINESS]` and select `[AR FACEBOOK PAGE]`, which is linked to `[AR PAGE-LINKED IG]`.
3. Return to Captame and show the successful corporate connection.
4. Under **Identidades y activos**, show `[AR PAGE-LINKED IG]`, its Instagram account ID, `instagram` channel and corporate ownership.
5. Also show the parent Facebook Page to make the Page-linked authorization relationship unambiguous.

**Expected proof.** Captame discovers only the Page-linked professional Instagram identity and displays its username/ID for correct routing.

## `instagram_manage_messages`

**Use case.** In the Meta Business/Facebook Login flow, Captame receives and replies to DMs for the professional Instagram account linked to the brokerage's authorized Page.

**Path.**

1. Ensure `[AR PAGE-LINKED IG]` is active under **Mis canales** after the Meta Business connection.
2. From `[AR EXTERNAL IG USER]`, send `AR-IG-LINKED-001` to `[AR PAGE-LINKED IG]`.
3. Open **Bandeja Meta**, filter to **Instagram**, and open the new conversation.
4. Show the inbound message, linked lead and exact Page-linked Instagram asset.
5. Send `AR-IG-LINKED-001 reply from Captame` and show the result in the external Instagram client.

**Expected proof.** A user-initiated DM to the Page-linked professional account is received and answered by an authorized human through the same account.

## `ads_read`

**Use case.** Captame reads authorized ad-account metadata and performance insights to provide brokerage-only campaign reporting and traceable CRM outcome analytics.

**Path.**

1. Connect `[AR META BUSINESS]` through **Mis canales → Meta Business → Conectar cuenta** with full authorization.
2. Under **Identidades y activos**, show `[AR AD ACCOUNT]`, its `act_…` ID and active state.
3. Open **Meta Ads → Resultados** and select `[AR AD ACCOUNT]` in the **Cuenta publicitaria** filter.
4. Select the prepared date range, choose `[AR READ CAMPAIGN]`, and select **Aplicar filtros**.
5. Show investment, impressions, clicks and **Rendimiento por campaña**; select a lead KPI to show the traceable CRM drill-down.

**Expected proof.** The app displays read-only performance data for the explicitly authorized ad account and isolates it to the App Review broker.

## `ads_management`

**Use case.** Captame allows a brokerage executive to draft a housing campaign and requires management approval before creating it in Meta in a fully paused state. Spend cannot begin without a separate explicit confirmation.

**Path.**

1. Ensure `[AR AD ACCOUNT]`, `[AR FACEBOOK PAGE]`, a project and App Review budget limits are configured.
2. As the supplied App Review Admin, open **Meta Ads → Nueva campaña** and complete the four-step wizard using the `AR-ADS-MANAGE-001` values in the runbook.
3. Save the draft, select **Enviar**, then **Aprobar** and confirm **Aprobar snapshot**.
4. Select **Publicar pausada** and accept the confirmation that the remote campaign will be created fully paused.
5. Show the resulting remote campaign ID and paused state in Captame, then open Meta Ads Manager and show the same campaign paused. Do not select **Activar gasto**.

**Expected proof.** Captame creates the reviewed campaign structure in the authorized ad account with all delivery entities paused and without incurring spend.

## `leads_retrieval`

**Use case.** Captame retrieves leads submitted to an authorized Page's Lead Ads form, normalizes the selected form fields and creates a deduplicated CRM lead for brokerage follow-up.

**Path.**

1. Connect `[AR META BUSINESS]`, then open **Meta Ads → Formularios** and select **Sincronizar**.
2. Locate `[AR LEAD FORM]`, select **Configurar**, map name/phone/email to the CRM fields, select **Previsualizar lead**, and show the normalized preview before saving.
3. In Meta's Lead Ads testing tool, submit the marker `AR-LEAD-001` to `[AR LEAD FORM]` using synthetic contact data from the runbook.
4. Return to Captame and open the newly created `AR-LEAD-001` lead; show the Meta campaign/form attribution and selected project.
5. Reconcile/synchronize again and show that no duplicate CRM lead is created.

**Expected proof.** A real test submission is retrieved from the authorized form, normalized into one tenant-scoped CRM lead and remains idempotent on reconciliation.
