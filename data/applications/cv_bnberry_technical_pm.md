# Philipp Hilbert - *Senior Technical Product Manager · Integration Platforms, Reliability and Product Debt*

hilbert@true-north.berlin · +357 94101644 · www.true-north.berlin · [LinkedIn](https://www.linkedin.com/in/philipp-hilbert-34032275/) · [GitHub](https://github.com/hilbertp)

10+ years of XP · **resident in Limassol, Cyprus** · integration-heavy B2B SaaS, production forensics, platform stewardship · German native, English C2 · available at short notice

---

## Keeping an integration platform healthy is a product job

- **Integration-heavy systems are my core, not my adjacency.** Product Owner of the integration team at Scheidt & Bachmann, turning research outcomes into releasable integration across site and head-office systems. Catalogue and API integration into legacy systems at AOK ITSCare for roughly 20,000 users. At CLINET I implemented the interface into the incumbent system landscape myself, which still gives me a realistic sense of what an integration truly costs, and what it costs to keep one alive.
- **Production forensics with my own hands.** I investigate incidents through logs, dashboards and SQL myself, daily, on systems I operate: self-built Python and DuckDB data pipelines, a live marketplace, and a multi-agent automation whose traces I read when quality drifts. Root cause over symptom is a habit, not a slogan: at Rohde & Schwarz I resolved an infrastructure blocker engineering had not cracked in over a year, by treating it as a product problem and getting the right people in one room.
- **Product debt, quantified rather than lamented.** The time from spotting a defect to shipping the fix is a product metric, not an engineering detail. I put numbers on debt: deployment times at R&S went from several days to 20 to 40 minutes, and the business case for that work was made in hours saved and release risk, not in engineering aesthetics.
- **Mental models of complex existing systems.** I inherited every platform I ever ran; none was greenfield. At EMIL I took over a stalled 17-person delivery organisation and a multi-tenant platform, mapped what actually existed, and rebuilt team structure and priorities around reality rather than around the architecture diagram.
- **Revenue and retention thinking from a CFO's chair.** Eight years as a startup CFO across three companies I co-founded. When a flaky integration shows up, I price it in churn and support load before I prioritise it, because I have owned the P&L that pays for the fix.
- **Partner ecosystems.** BidSwitch-style middle position is familiar: construct8, the two-sided marketplace I run in Limassol, lives or dies on making the match reliable while staying invisible, and its external dependencies (payment provider, messaging channels) are exactly the kind of partner integrations that fail at 2 a.m.

---

## How I work / My strengths

**I leave my ego at home.**
Stakeholder conversations are not the place for one's own sensitivities. I want the decision, not the last word, and I stay unemotional when the room does not.

**I fall in love with the problem, not the solution.**
The best way to satisfy customers is to never be in love with your own solution you thought was so clever. A design I am attached to is a design I will defend past its expiry date, which is how organisations end up shipping the wrong thing in a beautiful, convincing way.

**On greenfield, I buy information before I make software.**
Unknown territory requires quick, inexpensive discovery bets that resolve the largest uncertainty first. Cheap experiments make expensive decisions safe(r).

**I keep the whole value chain in view, not just the backlog.**
A product decision is not finished when the story is refined. After discovery and requirements, a coherent development and test-automation setup has to exist: a branching and merging strategy that allows a hotfix on the same day, regression tests the team genuinely trusts at release, and GitOps processes that turn rollout and rollback into a non-event. Building and owning that chain is the work of architects and DevOps engineers, not mine. What I bring is understanding it well enough to steer it into the right lanes and to notice when discovery, requirements, testing and delivery start drifting apart.

---

## The problems I am usually brought in to solve

Nobody knows which solution the market actually needs. Not us, not the customer, and not the highest-paid opinion in the room. Almost every expensive product failure begins with an organisation that pretends somebody does.

The alternative is to treat each product decision as a bet. Continuous discovery and cheap, fast prototyping move us toward the answer internally, in small increments, and pilot customers and stakeholders then verify prototypes and MVPs externally, or buy us very valuable information about a failure mode as cheaply as possible. That is how you arrive at products people genuinely love, rather than products that merely exist (with zero revenues).

**1. Discovery is treated as a phase, and a short one.**

Someone has an idea, it enters a roadmap, a specification is written, and the team starts building. Discovery, where it happens at all, is a number of workshops and a slide deck. The wrong thing then gets built efficiently, which is the most expensive failure mode there is, because it takes a full delivery cycle before anyone finds out.

*How I solve it:* discovery is continuous, never a phase. My working assumption is that most product decisions will produce no revenue at all (at least 50 percent of the time, maybe 75), so the only rational response is to keep every bet small and cheap enough that being wrong is survivable and fast to detect. I resolve the largest uncertainty first, with the cheapest instrument that can settle it: a prototype, a few real customer conversations, a click-through mockup, sometimes only a spreadsheet.

**2. Discovery happens without the two people who make solutions good.**

The product manager goes off with stakeholders and returns with requirements. The engineers first see the idea at refinement, when its shape is already fixed. The designer is handed a flow to make presentable. Both are then expected to be committed to a solution they had no part in finding, and the best technical option, the one only the lead engineer could have proposed, never surfaces at all.

*How I solve it:* I keep a standing core discovery team of at least myself, a product designer and the lead engineer. Not a ceremony, a habit. Engineers who see the customer problem early bring solutions nobody would have specified, and designers who are present when the problem is framed stop producing decoration.

**3. Work arrives as a decree instead of a problem to solve.**

A feature list comes down from the executive floor or from the loudest stakeholders. The team is told what to build rather than what to achieve, the output versus outcome conundrum, and nobody is invited to come back with something better, or with the finding that it should not be built at all.

*How I solve it:* I bring the team the problem, the customer and the evidence, and I negotiate on outcomes instead of output. That requires being able to hold an unemotional conversation with a stakeholder whose pet feature I am declining, which is a discipline rather than a personality trait. It also requires measurement, because without metrics decisions are not falsifiable, and the loudest voice wins by default.

**4. The result is mercenaries instead of missionaries.**

Teams that ship tickets without conviction. Nobody pushes back on a weak idea, because pushing back has never once changed the outcome. The strongest engineers leave first, since they are the ones with options.

*How I solve it:* by handing teams the problem and enough context to own it, and by repairing the structure that turned them into mercenaries in the first place. At EMIL I inherited a 17-person delivery organisation that had stalled and was losing its senior engineers. I restructured it into teams that could genuinely own something end to end. Velocity returned, client trust returned, and an almost complete exodus stopped at a single departure.

**5. Nobody can say afterwards whether it worked.**

The feature shipped, the release note went out, the team moved on. Six months later nobody can tell you whether anything changed, so the same argument starts again with the same opinions and no new evidence.

*How I solve it:* I define what would count as success before we build, and I instrument the product so the answer can be observed instead of debated. At Rohde & Schwarz I pushed to be part of the customer workshops until I was finally invited. It became clear within one session that the customers' developers worked completely differently from what we had assumed. So we built a small alternative, code-heavy workflow alongside the intended one and measured which of the two got used. Our originally intended workflow received exactly zero clicks. Learning that in a week beats learning it after a year of building.

---

## Experience

### construct8 · Product Manager, B2B Marketplace
*2025 to present · Limassol and remote*

Two-sided B2B marketplace matching construction firms with construction workers, operated live.

- Zero to one: product vision, strategy and principles, with continuous discovery
- Partner integrations (payments, messaging channels) owned end to end, including their failure modes
- AI assistance across the full funnel, so one person can run the entire day-to-day operation

### Rohde & Schwarz · Product Manager, AI and Data Platform
*2024 to 2025 · Munich and remote*

Owned a module of a central AI and data platform whose consumers were other teams.

- Full ownership from discovery to production: requirements, backlog, release definition, rollout
- Deployment times reduced from several days to 20 to 40 minutes; resolved an infrastructure blocker engineering had not cracked in over a year
- Led a cross-functional squad of architects, data scientists, engineers and QA across several countries

*Kubernetes, OpenShift, GitOps (ArgoCD), Kotlin, Python, PostgreSQL, Kafka*

### Bundesagentur für Arbeit (German Federal Employment Agency) · Product Manager, Data and Analytics Platform
*2023 to 2024 · remote*

National analytics platform on a warehouse-grade ETL stack.

- Introduced automated ETL orchestration and standardised CI/CD
- Deputy IT security officer: compliance, governance and data lineage under a recurring audit cycle

*Python, PostgreSQL, Dagster, dbt, Kubernetes*

### EMIL Group · Product Manager, B2B SaaS Platform
*2022 · Berlin*

Multi-tenant platform for insurers, reinsurers, brokers and underwriters.

- Inherited a stalled platform and a 17-person delivery organisation; rebuilt structure and priorities around what actually existed
- Instrumented the flow so that churn per process step became the leading prioritisation metric
- Built a claims module from zero with no specification, running discovery directly with a pilot customer's specialists

### CLINET Platforms · Product Owner, Mobile Application (iOS and Android)
*2021 to 2022 · Berlin*

- Shipped a native product across two platforms; implemented the interface into the incumbent system landscape myself

### Bundesdruckerei · Product Owner, National Health Data Platform
*2021 · Berlin*

Secure data structures and identity management under the highest privacy requirements.

### Scheidt & Bachmann · Product Owner, Integration Team
*2020 to 2021 · Mönchengladbach*

- Product Owner of the integration team: turning research outcomes into productive, releasable integration across site and head-office systems, in a fully SAFe organisation

### AOK ITSCare · Proxy Product Owner
*2019 to 2020 · Germany*

Migration of a procurement platform serving roughly 20,000 employees, with catalogue and API integration into legacy systems.

---

## Founder track record

- **Kvitt Payment Solutions · Founder and CFO (2013 to 2018).** Mobile payments platform built from zero; payment service provider integration, settlement flows, onboarding. Acquired and operated by Sparkasse.
- **Qcrypt AG · Co-Founder and Product Owner (2016 to 2018).** Quantum-secure encryption shipped to enterprise customers under a sub-two-minute installation constraint.
- **Smart Soil Technologies · Co-Founder, CDO and CFO (2016 to 2021).** Nanotechnology product from laboratory to investor rounds.

---

## AI-first as a working mode

My approach is AI-first, and it changes the economics of product work measurably. With AI development tools and a human in the loop I deliver, part-time, the output a small team needed full-time a year ago. I do not write the production code myself, I own it. For that I built and run a multi-agent framework in which coordinator, implementer and evaluator agents work a shared queue under guardrails I designed. Familiarity with AI-powered products, your stated nice-to-have, is in my case familiarity with operating them in production, including the failure modes.

---

## Education and languages

**Diplom-Wirtschaftsingenieur** (Industrial Engineering and Business Administration), Technische Universität Berlin.

German (native) · English (C2).
