# Consultative Outreach Sequences

Draft gradual, evidence-based outreach. Be transparent about the intent to explore fit or cooperation, but confirm relevance before presenting products in detail.

## Contents

- Language Policy
- Outreach Scenarios
- Sequence Length by Final Priority
- Account-Level Role Orchestration
- P1 and P2 Sequence
- P3 Sequence
- Output Fields
- Response and Stop Rules
- Pre-send QA

## Language Policy

- Write the analysis in the user's current language unless requested otherwise.
- Infer the prospect-local sendable language from the contact's location, relevant business unit, official website, and user instruction.
- If the local language cannot be determined reliably, use English. Do not invent a local-language assumption.
- Always provide an English sendable version.
- If the local language is English, provide one polished English sendable sequence rather than duplicating it.
- If neither sendable version is Chinese, add a Chinese internal-reference translation. Label it `Internal reference - not the primary send version`.
- If the local language is Chinese, provide Chinese and English sendable versions; do not add a third duplicate.
- Localize formality, terminology, honorifics, spelling, dates, and time zones. Translate meaning rather than sentence structure.

## Outreach Scenarios

| Scenario | First-message posture |
|---|---|
| End-customer development | Ask about the workflow, project priority, or evaluation criteria. |
| OEM supply | Ask whether the relevant platform or component category is evaluated for equipment designs. |
| Systems-integrator partnership | Ask whether the team evaluates platform or hardware partners for customer projects. |
| Channel or distributor cooperation | Ask whether the company reviews complementary product lines or supplier partnerships. |
| Technical partnership | Ask whether comparing technical approaches would be useful. |
| Event follow-up | Reference only an event or interaction explicitly provided by the user. |
| Short business message | Use 2-4 short sentences and one question. |
| Business chat | Ask permission before sending details; do not paste a full email pitch. |
| Phone opener | Use a 20-40 second opener and one routing or qualification question. |

## Sequence Length by Final Priority

| Final priority | Default output |
|---|---|
| P1 | No more than four total account touches across all contacts. |
| P2 | No more than four total account touches across all contacts. |
| P3 | One research/routing email and one clearly labeled optional follow-up. |
| P4 | No outreach. If the user explicitly insists, one neutral research note only. |

Use the final priority after all readiness, evidence, status, and industry caps.

## Account-Level Role Orchestration

- Load `contact-discovery-and-routing.md` when more than one role or channel is available.
- Keep one active thread per account. Do not duplicate the initial message across procurement, engineering, product, partnership, and general channels.
- Select the first role from the primary opportunity path, not from email availability alone.
- For end-customer, OEM, and systems-integration opportunities, a technical owner usually validates relevance before procurement handles supplier qualification.
- For channel opportunities, product/category or partnership ownership usually precedes procurement administration.
- For an official tender, RFQ, or supplier-onboarding process, follow the named procurement entry point first.
- A role switch replaces the remaining sequence to the first contact; it does not create an additional cadence.
- State the target role, channel verification status, contact rank, switch condition, and reason for every touch.

## P1 and P2 Sequence

### Touch 1: Initial Email to Primary Role - Day 0

- Mention one specific, non-sensitive observation supported by the evidence ledger.
- State the intent to explore cooperation or determine whether a solution area is relevant.
- Ask one low-pressure qualifying question.
- Do not include a product catalog, pricing, unsupported ROI, attachment, aggressive demo request, or meeting request as the main CTA unless the user explicitly asks.
- P1 may name the strongest solution area. P2 should verify the scenario before describing offerings.

### Touch 2: Follow-Up to Primary Role - Day 4

- Refer to the initial question without implying it was read.
- Add one useful operational or technical consideration relevant to the prospect.
- Ask whether the topic is owned by the recipient or another team.

### Touch 3: Secondary Role or Continued Thread - Day 9

- If a credible second role exists and the first thread remains unanswered, pause the first thread and send a role-adapted routing message to the second role.
- Explain only the business or technical topic relevant to the second role; do not imply that the first recipient ignored the message.
- If no credible second role exists, continue the original thread only when there is one new, evidence-based consideration to add.
- Connect at most one demonstrated user-company capability using conditional language such as `if this is relevant`.
- Ask one routing, relevance, or context-exchange question; do not ask for a purchase decision.

### Touch 4: Final Follow-Up - Day 14

- Acknowledge that the topic may not be a current priority.
- Offer to reconnect later or be routed to the correct owner.
- Include a natural stop-contact line, such as `If this is not relevant, I will not follow up further.`
- Do not use guilt, urgency, false scarcity, or pressure.

## P3 Sequence

### Research or Routing Email - Day 0

- Explain the topic being researched and ask whether it is relevant or who owns it.
- Do not recommend a product or claim a confirmed pain point.
- Keep the CTA to permission, relevance, or routing.

### Optional Follow-Up - 7-10 Business Days Later

- Label this message `Optional - send only if there is a credible reason to continue`.
- Ask one final routing or timing question and state that no further follow-up will be sent if the topic is not relevant.
- Do not add a new sales claim.
- Do not switch to a second person unless the first recipient explicitly routes the inquiry.

## Output Fields

For every permitted message provide:

- Subject
- Body
- Target contact or fixed role label
- Role family and sequence rank
- Channel type and verification status
- Role Value Score, Channel Quality Score, and Contact Priority Index when contact discovery was performed
- Personalization basis and evidence-ledger reference
- Primary CTA
- Recommended send timing and time-zone assumption
- Follow-up interval
- Switch or stop condition
- Draft status: `Ready for review` or `Needs input`

If sender name, role, company identity, signature details, or another required field is missing, use an obvious bracketed placeholder, list it under missing inputs, and mark the draft `Needs input`. Never label a draft with unresolved placeholders as ready to send.

## Response and Stop Rules

- Pause the planned sequence after any reply and switch to the reply playbook.
- Stop and suppress future outreach after opt-out, explicit refusal, complaint, or permanent bounce.
- For a wrong-person reply, thank the recipient and ask for routing at most once.
- For an out-of-office reply, wait until after the stated return date and resume with no more than one appropriate message.
- Do not restart an initial sequence for an account already in an active cadence.
- A switch to another role pauses the first thread and stays within the account's total touch limit.

## Pre-send QA

Check every sendable message and report pass/fail. Revise before returning when possible.

- One primary CTA.
- Usually 80-150 words for email; shorter for social or chat.
- Subject accurately reflects the message and is not deceptive.
- Specific personalization is traceable to the evidence ledger.
- Facts, third-party context, weak signals, and inferences are not conflated.
- No fake relationship, referral, prior conversation, urgency, or scarcity.
- No unsupported ROI, savings, performance, certification, customer-logo, compatibility, or procurement claim.
- No private contact data or sensitive personal attribute.
- No attachment, product catalog, meeting pressure, or aggressive demo request in the first email unless requested.
- Sequence length and posture match final P1/P2/P3/P4 priority.
- The target channel is `Official public`, `Corroborated public`, `Role inbox`, or `General routing`; no `Third-party unverified` or `Prohibited` address is used.
- Role and channel scores support the documented contact order; email convenience does not override role ownership.
- No duplicate initial message is sent to multiple people and the account-level touch count does not exceed the permitted sequence.
- Sender identity and signature requirements are satisfied or clearly flagged as missing.
- No unresolved placeholder appears in a draft marked `Ready for review`.
- Language reads naturally for the intended region and is not a literal translation.
- Sensitive industries use restrained, exploratory wording.
- Final or optional last follow-up contains a natural stop-contact line.
