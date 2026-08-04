# Public Business Contact Discovery and Routing

Load this reference only when the user requests contact discovery, email selection, procurement-versus-engineering analysis, channel evaluation, or a multi-role contact order. This is a research and drafting workflow, not a bulk contact-harvesting or delivery system.

## Scope and Limits

- Discover only public, business-relevant contacts connected to the matched product, workflow, business unit, or cooperation path.
- For each account retain no more than four targets: one technical evaluator, one procurement or supply-chain gatekeeper, one product/category/partnership owner when relevant, and one department or general router.
- Prefer quality over count. `Not found` is a valid result.
- Never infer an unpublished email pattern, guess an address from a name and domain, use breach data, expose a private mailbox, or collect unrelated personal details.
- Do not ping a mailbox, perform SMTP verification, bypass access controls, use credentials, or claim deliverability without sending evidence supplied by the user.
- A public individual corporate mailbox is business contact data, not permission to send. Apply regional rules, relevance, restraint, and stop-contact status.

## Source Order

Use sources in this order:

1. Official company contact, team, leadership, supplier, partner, product, office, or business-unit pages.
2. Official company PDFs, manuals, press releases, event materials, author biographies, and public filings.
3. The contact's own public professional page when it explicitly shows a current company role or business address.
4. Credible trade associations, conference organizers, partner directories, or professional publications that identify a current business role.
5. Public business directories only as a research lead. Never make a third-party-only address sendable.

Exclude scraped contact dumps, paywalled people-search previews, cached leak data, private profiles, personal sites unrelated to the role, forum posts, and guessed-pattern results.

## Discovery Procedure

1. Start from the primary opportunity path and matched workflow. Define the role families that could evaluate, specify, buy, approve, or route that exact category.
2. Search the prospect's official domain first using role, department, product-line, location, and supplier terms.
3. For a named person, confirm current employment and role from an official or self-published professional source before associating an address.
4. Confirm that an address is explicitly published. Do not construct it from examples or other employees' addresses.
5. Check whether the domain belongs to the prospect, relevant subsidiary, parent, or authorized business unit. Explain any domain difference.
6. Record source URL, page title, visible publication/update date, access date, source owner, role evidence, and address evidence separately.
7. Assign a verification status, score the role and channel, and determine whether the contact is sendable, routing-only, research-only, or prohibited.
8. Stop after the permitted role coverage is achieved. Do not collect extra names merely because they are available.

## Verification Status

| Status | Required evidence | Handling |
|---|---|---|
| `Official public` | The company, relevant business unit, or official document explicitly publishes the corporate address and role context. | May be recommended after regional and status checks. |
| `Corroborated public` | Two credible public sources agree on the corporate address and current role, with at least one source directly controlled by the company or contact. | May be recommended cautiously; explain the evidence. |
| `Third-party unverified` | A credible third party publishes a corporate-domain address, but official address evidence is absent. | Show as a research lead only; do not recommend sending until corroborated. |
| `Role inbox` | An official department, procurement, engineering, supplier, product, or partnership mailbox is published. | May be used for role-specific routing. |
| `General routing` | An official general mailbox, office mailbox, or contact form is available. | Use only for a concise routing question. |
| `Not found` | No qualifying public address or channel is located. | Recommend further official-source research; do not guess. |
| `Prohibited` | The address is personal, inferred, leaked, unrelated, access-controlled, or otherwise unsuitable. | Omit the address value and do not use it. |

An address from one third-party source never becomes `Corroborated public` merely because several directories copied the same record.

## Role Value Score

Score out of 100 for the current opportunity path.

| Dimension | Max | Evaluate |
|---|---:|---|
| Opportunity-path ownership | 35 | Whether the role owns or directly participates in the end-customer, OEM, integration, channel, or supplier decision. |
| Product and solution relevance | 25 | Whether the role evaluates the matched product, architecture, workflow, or commercial category. |
| Decision or technical influence | 15 | Ability to specify, approve, reject, sponsor, or qualify the offering. |
| Routing ability | 10 | Ability to identify the correct team when not the final owner. |
| Trigger alignment | 10 | Relevance to the current launch, project, expansion, tender, partnership, or other timing evidence. |
| Role-evidence freshness | 5 | Confidence that the role and company relationship are current. |

Use the lower score when the title is broad, scope is unknown, or employment evidence is stale.

## Channel Quality Score

Score out of 100 for the specific channel.

| Dimension | Max | Evaluate |
|---|---:|---|
| Public-source confidence | 30 | Strength and independence of the address or channel evidence. |
| Current company and role match | 25 | Whether the channel is tied to the current company, business unit, and role. |
| Corporate business relevance | 20 | Whether it is a corporate or official role channel rather than a personal address. |
| Directness or routing capacity | 15 | Ability to reach the intended role or reliably route the inquiry. |
| Privacy and regional suitability | 10 | Data-minimization, relevance, and regional cold-contact risk. |

Set Channel Quality to `0` for `Prohibited`. Cap `Third-party unverified` at `39`; it cannot be selected as a send channel. A `General routing` channel may score lower than a named corporate address but can still be the correct first channel when no role owner is verified.

## Contact Priority Index

Calculate:

`Contact Priority Index = Role Value Score * 0.60 + Channel Quality Score * 0.40`

Round to the nearest whole number. Rank only sendable or routing channels. Keep research-only records below all sendable records regardless of arithmetic score. Break ties in this order:

1. Better role ownership for the primary opportunity path.
2. Stronger official source evidence.
3. More current role evidence.
4. Lower privacy and regional risk.

Do not rank a convenient generic inbox above a verified technical or commercial owner solely because the inbox is easy to find.

## Procurement Versus Engineering

| Situation | First role | Second role | Reason |
|---|---|---|---|
| End-customer technical use | Engineering, automation, controls, IT/OT, or operations owner | Procurement after relevance is established | Technical need and architecture normally require validation before commercial qualification. |
| OEM component or platform supply | Product engineering, R&D, embedded systems, or platform owner | Strategic sourcing or procurement | Engineering controls specification; procurement controls supplier qualification and terms. |
| Systems-integration project | Solutions engineering, controls, or project engineering | Procurement or supplier management | The project team determines whether the platform belongs in a customer solution. |
| Channel or distributor cooperation | Product/category management, partnerships, or business unit owner | Procurement or vendor management | Portfolio fit and route-to-market precede purchase administration. |
| Public RFQ, tender, or supplier-onboarding event | Procurement, sourcing, or named bid contact | Technical evaluator | The documented process determines the permitted entry point. |
| Role ownership unknown | Official role inbox or general routing channel | Verified owner after routing | Avoids sending a product pitch to an unrelated employee. |

Procurement is not automatically the highest-value first contact. Engineering is not automatically better either. Select based on the opportunity path, decision stage, and current evidence.

## Channel Value Guidance

| Channel | Typical value | Main limitation | Default posture |
|---|---|---|---|
| Officially published named corporate email | High directness when role fit is confirmed | Individual may have changed role; regional cold-email rules still apply | One relevant question tied to the role. |
| Official role or department inbox | Strong continuity and routing | Less personal and may be triaged slowly | State the category and ask for the owner. |
| Official business-unit or regional office inbox | Useful when the account is decentralized | May not own the product category | Ask which team handles the topic. |
| Official contact form | Legitimate but low visibility into routing | Limited formatting and tracking | Use a short routing request. |
| Public professional messaging channel | Useful for permission or routing when no email is published | Platform rules and message limits vary | Ask permission before sending details. |
| Third-party-only corporate address | Research lead only | Staleness and provenance cannot be confirmed | Verify elsewhere; do not send yet. |
| Personal mailbox | Prohibited | Privacy, relevance, and consent risk | Do not use. |

Do not claim which channel will obtain a reply. Describe expected routing quality and evidence-based tradeoffs instead.

## Account-Level Contact Order

- Maintain one active thread per account. Never send the same initial message to multiple people at once.
- P1/P2 allow no more than four total touches across all contacts:
  - Day 0: contact the highest-ranked sendable role.
  - Day 4: one follow-up in the same thread.
  - Day 9: if still unanswered and a credible second role exists, pause the first thread and send a role-adapted routing message to the second role. Otherwise continue only when the original sequence has a justified next step.
  - Day 14: one final, low-pressure close in the currently active thread.
- P3 uses one routing target and one optional follow-up. Do not switch to a second person unless the first recipient explicitly routes the inquiry.
- P4, paused, suppressed, or do-not-contact accounts receive no contact sequence.
- Any reply pauses the entire account sequence. Explicit refusal, opt-out, complaint, or permanent bounce suppresses every contact and channel for that account.

## Required Contact Output

For each retained contact or channel report:

- Sanitized contact name or fixed role label
- Current public role and role family
- Public corporate email or channel type
- Address type: individual corporate, role inbox, department, office, form, professional message, research-only, or prohibited
- Verification status and confidence explanation
- Role source and address source, each with URL and date
- Role Value Score, Channel Quality Score, Contact Priority Index, and rank
- Recommended action: send, route, verify first, hold, or prohibit
- Message purpose, switch condition, and reason for the order

If no qualifying contact is found, say so explicitly and provide official-source research actions without constructing an address.
