# Stage 0 restaurant onboarding template

Contract version: `restaurant-onboarding/v1`

The official workbook captures configuration for a real-restaurant Stage 0 rehearsal. It is a
capture contract, not a domain authority, and it does not import or persist data. Later analysis and
import must apply values through the existing ECIP application/domain authorities.

Generate the workbook from the repository root after installing API development dependencies:

```bash
python3 scripts/generate-stage0-onboarding-template.py
```

The output is
`docs/operations/templates/ECIP_Stage0_Restaurant_Onboarding_v1.xlsx`. It contains Instructions,
Metadata and 32 dependency-ordered capture sheets covering restaurant identity, staff metadata,
resources, preparation, menu/commercial structure, inventory configuration, suppliers, recipes,
tax classification and payment-method selection. Optional capability sheets may remain empty when
the restaurant confirms they do not apply.

Dark blue headers are required and gray headers are optional. Header comments contain types,
formats, references and allowed values. Cross-sheet references use existing business codes where
the platform has them. `product_key`, `menu_key`, `section_key`, `choice_group_key`,
`promotion_key`, `recipe_key` and `tax_rule_key` are workbook-local capture keys because those
authorities do not currently expose an operator-safe code. They are not database IDs and must not
be persisted as invented domain identifiers.

Do not enter passwords, hashes, tokens, access codes, provider credentials, generated IDs,
timestamps, stock movements, lots, receipts, losses, preparation batches, transfers or valuation
history. Opening stock must later use an authorized inventory operation and is intentionally absent
from the workbook.

This workstream performs no XLSX upload, analyze/preview, import, user/RBAC provisioning, tax
provisioning or POS access/integration. Those remain later controlled workstreams.

Known later-application dependencies are intentionally preserved: staff/RBAC and tax records have
no general provisioning API; named warehouses have a model/business code but the current API only
lists them and changes policy; and several commercial authorities lack a persistent operator-safe
code. B1.2 may analyze their capture data, but a later confirmed-import workstream must resolve
these authority gaps before persistence. Opening stock remains a separate authorized inventory
operation.
