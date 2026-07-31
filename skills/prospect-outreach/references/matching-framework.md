# Prospect Matching Framework

Score strategic account quality separately from the ability to contact the account now. Do not lower strategic fit merely because a contact is missing.

## Contents

- Account Fit Score
- Outreach Readiness Score
- Priority Algorithm
- Hard Caps
- Contact-Status Gates
- Evidence Labels
- Scoring Discipline

## Account Fit Score

Score out of 100.

| Dimension | Max | Evaluate |
|---|---:|---|
| Product / scenario fit | 30 | Direct overlap between the prospect's products, workflows, applications, or customers and the user's demonstrated scope. |
| Technical solution fit | 25 | Compatibility between visible architecture, integration needs, operating constraints, and demonstrated user-company capabilities. |
| Pain and need relevance | 20 | Credible operational needs or pain hypotheses that the user's capability could address. Do not treat a hypothesis as a confirmed pain. |
| Commercial cooperation path | 15 | A plausible route as end customer, OEM, systems integrator, channel/distributor, or technical partner. |
| Evidence confidence | 10 | Current, specific evidence supports the account and capability claims. |

Use this proportional rubric within each dimension:

- `0%`: no evidence, no relevance, or a clear mismatch.
- `25%`: weak signal or broad category overlap only.
- `50%`: plausible fit supported by indirect evidence.
- `75%`: strong fit supported by specific evidence, with some unknowns.
- `100%`: direct, current evidence supports the full claimed fit.

## Outreach Readiness Score

Score out of 100.

| Dimension | Max | Evaluate |
|---|---:|---|
| Contact role relevance | 25 | The named role owns, influences, evaluates, or can route the topic. |
| Trigger and timing | 25 | Current expansion, launch, hiring, modernization, tender, event, partnership, or other credible reason to contact now. |
| Evidence freshness | 20 | The evidence needed for the email is current and not contradicted. |
| Usable business contact channel | 15 | A public, business-relevant individual, role, department, or general channel is available. |
| Personalization sufficiency | 15 | There is enough safe, specific context to write a relevant message without inventing claims. |

If no contact role is available, assign no more than `5/25` for contact role relevance and cap total Outreach Readiness at `49`. A public role inbox may improve channel availability but does not establish role ownership.

## Priority Algorithm

1. Derive base priority from Account Fit.

| Account Fit | Base priority | Meaning |
|---:|---|---|
| 80-100 | P1 | Strong strategic target. |
| 60-79 | P2 | Worth developing; verify remaining fit. |
| 40-59 | P3 | Nurture or research target. |
| 0-39 | P4 | Not a current development target. |

2. Apply the Outreach Readiness cap.

| Outreach Readiness | Maximum final priority | Handling |
|---:|---|---|
| 70-100 | No readiness downgrade | Use the sequence allowed by base priority. |
| 50-69 | P2 | Verify fit early and keep outreach consultative. |
| 30-49 | P3 | Use research or routing outreach only. |
| 0-29 | P4 | Research only; do not start an active sequence. |

3. Apply hard caps and contact-status gates. The lowest permitted result becomes the final priority. Always show Account Fit, Outreach Readiness, base priority, each cap, final priority, and downgrade reason.

## Hard Caps

| Condition | Maximum final priority | Required handling |
|---|---|---|
| No official prospect source can be found | P2 | Mark evidence confidence low; avoid strong claims. |
| Prospect identity or website cannot be verified | P4 | Return research-only treatment unless credible information is supplied. |
| No product, service, solution, or workflow evidence | P3 | Do not claim fit; ask a routing or research question. |
| Only broad industry overlap exists | P3 | Do not recommend a product. |
| No contact role is provided | P3 through Readiness <=49 | Preserve Account Fit; use role-neutral routing copy. |
| Contact role appears unrelated | P3 through Readiness <=49 | Ask for the correct owner. |
| No public business-relevant contact channel exists | P4 through Readiness <=29 | Recommend contact enrichment without guessing addresses. |
| No credible current trigger exists | P2 | Do not label the account urgent. |
| Low evidence would require strong technical claims | P3 | Remove unsupported promises and mark high risk. |
| Sensitive industry has weak evidence | P3 | Use restrained, exploratory wording. |
| User company information is missing | No score | Return only the missing-information checklist. |
| Prospect information is missing | No score | Return only a generic ICP hypothesis and checklist. |

## Contact-Status Gates

- `do not contact`, opt-out, explicit refusal, complaint, or permanent bounce: preserve Account Fit for internal strategy but set action priority to P4 and suppress outreach.
- `paused`: preserve scores but do not draft a new active sequence before the resume date or condition.
- `contacted`: do not create another initial email while a cadence is active. Continue only from the recorded stage.
- `long-term nurture`: generate research actions and reactivation signals, not an immediate sales sequence.

## Evidence Labels

Use only these labels:

- **Official fact:** Directly supported by an official user-company or prospect source.
- **Third-party fact:** Supported by a credible independent public source.
- **Weak signal:** Relevant but insufficient to support a sales claim.
- **Reasonable inference:** A conclusion used to guide questions, not stated as fact.
- **Unknown:** Material information is unavailable.

Mark unconfirmed user input as `User-provided, not independently verified` in the source field and choose the evidence label that reflects its reliability.

## Scoring Discipline

- Require a prospect workflow and a demonstrated user-company capability for high product or technical scores.
- Penalize missing evidence instead of inventing facts.
- Treat pain points and buying intent as hypotheses unless directly sourced.
- Do not infer procurement intent from industry overlap, downloads, hiring, or technology use alone.
- Prefer the lower priority when evidence conflicts with apparent fit.
- Use the final priority, not the raw Account Fit score, to select email posture and sequence length.
