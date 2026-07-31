# Prospect Research and Evidence

Use current public information to establish company identity, workflows, technical context, commercial paths, triggers, and safe personalization. Research only what is necessary for the account decision.

## Source Priority

Prefer sources in this order:

1. Official company pages: about, products, services, solutions, industries, support, partners, downloads, certifications, and contact pages.
2. Official datasheets, manuals, case studies, press releases, annual reports, investor material, and sustainability reports.
3. Official hiring pages when they reveal current technology, expansion, or project direction.
4. Official social channels and verified company profiles.
5. Credible third parties: reputable news, trade publications, public databases, tender portals, patent records, conference listings, and official partner directories.
6. Lower-confidence material: scraped directories, marketplace reposts, SEO pages, old PDFs, forums, and unverifiable copies.

Do not use a lower-confidence source for a strong outreach claim when a primary source is available.

## Evidence Ledger

Record each material conclusion before scoring.

| Field | Requirement |
|---|---|
| Claim | One testable statement, not a compound conclusion. |
| Evidence label | Official fact, third-party fact, weak signal, reasonable inference, or unknown. |
| Source owner | User company, prospect, third party, user-provided, or none. |
| Page title | Exact or concise page title. |
| URL | Direct public page URL when available. |
| Published date | Use the visible publication/update date; otherwise `Not shown`. |
| Accessed date | Record the research date. |
| Freshness | Current, stable-undated, stale, conflicting, or unknown. |
| Score impact | Account Fit or Outreach Readiness dimension affected. |
| Outreach use | Direct observation, contextual support, question only, or do not mention. |

For user-provided information that cannot be publicly confirmed, set source owner to `User-provided, not independently verified`. Do not silently upgrade it to an official fact.

## Freshness and Conflict Rules

- Prefer recent official evidence.
- Treat undated pages as stable only for broad product categories, locations, and longstanding services.
- Mark evidence older than 24 months as stale unless the fact is structurally stable.
- When sources conflict, state the conflict and use the more authoritative and recent source.
- Do not infer procurement intent from industry overlap, a product download, a job post, or technology use alone.
- Keep pain points, budgets, projects, and technical constraints as hypotheses unless directly stated.

## Missing Information Behavior

| Missing input | Required behavior |
|---|---|
| User-company website or description | Stop; return only a missing-information checklist. |
| Prospect website, company name, or description | Return a generic ICP hypothesis and checklist; do not score or draft outreach. |
| Prospect website inaccessible but identity verified elsewhere | Continue with low evidence confidence and apply caps. |
| Prospect identity cannot be verified | Use P4/research-only treatment. |
| Contact name missing | Continue when account evidence is sufficient; use role-neutral language. |
| Contact role missing | Preserve Account Fit, cap Outreach Readiness at 49, and use routing outreach. |
| Public business contact channel missing | Cap Outreach Readiness at 29; recommend enrichment without guessing an address. |
| Sender identity missing | Draft with explicit placeholders and mark messages `Needs input`. |
| Local language unclear | Use English as the sendable fallback and provide Chinese internal reference when required. |

## Research Questions

- What does each company sell, build, integrate, operate, or support?
- Which specific workflow creates a plausible match?
- Which user-company capability is publicly demonstrated, and what proof supports it?
- What technical environment is visible: industrial computing, automation, robotics, HMI, SCADA, MES, machine vision, edge AI, cloud, embedded systems, networks, compliance, or lifecycle services?
- Which commercial path is plausible: end customer, OEM, systems integrator, channel/distributor, technical partner, or nurture?
- What current trigger is visible, and how strong is it?
- Which roles likely own, influence, evaluate, buy, or route the topic?
- What must be verified before a product, compatibility, performance, or ROI statement would be safe?

## Batch Entity Resolution

Before scoring a batch:

- Normalize case, spacing, punctuation, legal suffixes, and obvious transliteration variants for comparison.
- Merge exact company duplicates and name variants, but retain all source names.
- Keep parent companies, subsidiaries, brands, and regional business units separate when they have distinct websites, buying teams, or contact status.
- Flag uncertain matches instead of merging them.
- Preserve the most restrictive contact status across duplicates: `do not contact` over `paused`, `contacted`, `long-term nurture`, and `not contacted`.
- Do not generate a new initial message for an account already contacted or suppressed.
- Record the last research date, last contact stage, next action, and next review date.
