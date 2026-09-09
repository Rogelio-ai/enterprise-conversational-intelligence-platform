# Conekta TEST Certification

## Boundary and architecture

The authoritative path is direct:

```text
Diner browser -> Conekta hosted tokenizer -> opaque token
opaque token -> pryecip API -> ConektaPaymentExecutor -> Conekta Orders API
```

There is no Node adapter contract or service in the current runtime. Do not add
`NODE_ADAPTER_URL`, `INTERNAL_SHARED_SECRET`, `STRICT_WEBHOOK_DIGEST`, or a Node
adapter service.

`CONEKTA_ENVIRONMENT=test` is an application safety gate. Conekta selects the
provider account environment from the injected credential, so the operator must
verify that both keys belong to a Conekta TEST account. Production mode rejects
this TEST gate and the production Compose definition continues to hard-disable
electronic payments.

## Runtime inputs

Keep the private key outside the checkout in an owner-readable `0600` file. Do
not paste it into chat, a shell command, SQL, logs, a report, or frontend
configuration.

Set these non-secret values in the ignored local `.env` used by Compose:

```text
CONEKTA_CREDENTIAL_BINDING=pilot-location-conekta-test
CONEKTA_TEST_PRIVATE_KEY_FILE=/absolute/protected/path/conekta-test-private-key
```

Start the existing direct API with the TEST-only overlay:

```bash
docker compose -f compose.yaml -f compose.conekta-test.yaml up -d --build api
```

The overlay mounts the file as a read-only Compose secret. The API entrypoint
loads it into `CONEKTA_PRIVATE_KEY` without printing it; the settings object and
runtime resolver redact it. No provider credential is copied into an image.

## Pilot Location configuration

Create or update exactly one executor configuration for the authorized pilot
Location. Use verified IDs and the TEST public key supplied by the same Conekta
TEST account. The public key is intentionally client-visible; the binding is a
non-secret locator and must exactly match `CONEKTA_CREDENTIAL_BINDING`.

```sql
SET @tenant_id = OPERATOR_VERIFIED_TENANT_ID;
SET @organization_id = OPERATOR_VERIFIED_ORGANIZATION_ID;
SET @location_id = OPERATOR_VERIFIED_LOCATION_ID;
SET @test_public_key = 'OPERATOR_TEST_PUBLIC_KEY';
SET @credential_binding = 'pilot-location-conekta-test';

START TRANSACTION;
INSERT INTO location_payment_executor_configurations (
    tenant_id, organization_id, location_id, executor_key, display_name,
    adapter_kind, topology, status, credential_binding, client_public_key,
    selection_priority
) VALUES (
    @tenant_id, @organization_id, @location_id, 'conekta-test-card',
    'Conekta TEST card', 'CONEKTA', 'EXTERNAL', 'ACTIVE',
    @credential_binding, @test_public_key, 10
)
ON DUPLICATE KEY UPDATE
    id = LAST_INSERT_ID(id), display_name = VALUES(display_name),
    adapter_kind = 'CONEKTA', topology = 'EXTERNAL', status = 'ACTIVE',
    credential_binding = VALUES(credential_binding),
    client_public_key = VALUES(client_public_key),
    selection_priority = VALUES(selection_priority);
SET @executor_configuration_id = LAST_INSERT_ID();
INSERT INTO location_payment_executor_capabilities (
    executor_configuration_id, tenant_id, organization_id, location_id,
    method_category, currency
) VALUES (
    @executor_configuration_id, @tenant_id, @organization_id, @location_id,
    'CARD', 'MXN'
)
ON DUPLICATE KEY UPDATE currency = VALUES(currency);
COMMIT;
```

Before activation, query the Location row and both inserted rows and confirm the
tenant/organization/location tuple. Do not enable any other Location. On
completion or abort, set this executor configuration to `INACTIVE` and stop the
TEST overlay.

## Certification journey

Use only provider-published TEST cards and the normal Diner Web flow. PAN/CVV
must be entered only in Conekta's hosted iframe. The API client-configuration
response exposes only `provider`, `tokenization_mode`, TEST public key, and
locale. The API payment request contains an opaque provider token, never PAN or
CVV.

Record identifiers and states, never tokens or credentials:

1. Prove an authorized diner can see only the scoped `conekta-test-card`
   `CARD/MXN` executor and public client configuration.
2. Pay a Check with a provider success scenario. Record the existing
   `RestaurantPayment` ID, Conekta Order reference, attempt count, Settlement
   count, Check state, and provider dashboard result.
3. Replay the identical client idempotency key and payload. Confirm the same
   Payment, one provider Order, and one Settlement. Reuse with a changed payload
   must conflict.
4. On another payable Check, use a provider decline scenario. Confirm a
   `FAILED` or `REJECTED` Payment according to the provider response and no
   Settlement.
5. Reconcile amount/currency/status/order identity between Conekta TEST and
   pryecip. A successful partial payment need not settle the Check.
6. If a genuine provider/transport ambiguity occurs and a durable external
   reference exists, confirm `UNCERTAIN`, prove another charge is blocked, and
   invoke the existing authorized recovery endpoint. Recovery must retrieve the
   same Order and settle the same Payment at most once.

Do not deliberately create an unsafe network fault after submission merely to
manufacture `UNCERTAIN`. If the provider TEST environment cannot reproduce it,
retain the focused deterministic transport/recovery evidence and report live
`UNCERTAIN` as not executed.

## Webhook and 3DS boundary

The current implementation has no inbound Conekta webhook, digest verifier,
callback handler, or 3DS/3DS2 flow. It performs synchronous tokenized Order
creation and read-only Order recovery. Repository evidence does not establish
whether the provider currently requires webhooks or 3DS for this TEST account,
merchant configuration, or production use. Confirm those requirements with
Conekta before live TEST certification and again before any later production
design. Never weaken webhook verification as a workaround.

## Stop conditions

Stop and leave the executor `INACTIVE` if the key is not demonstrably TEST, the
public/private keys are from different accounts, the provider requires an
unimplemented 3DS/webhook path, PAN/CVV appears outside the hosted iframe, a
replay creates another Order or Settlement, scope authorization fails, or
provider and local evidence cannot be reconciled. Real-money activation remains
out of scope.
