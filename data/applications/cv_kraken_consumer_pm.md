# Philipp Hilbert - *Senior Product Manager · Consumer Trading, Crypto and AI-Native Product Work*

hilbert@true-north.berlin · +357 94101644 · www.true-north.berlin · [LinkedIn](https://www.linkedin.com/in/philipp-hilbert-34032275/) · [GitHub](https://github.com/hilbertp)

10+ years of XP · **resident in Limassol, Cyprus** · crypto, trading and banking, all three from the inside · daily Claude Code practice · German native, English C2 · available at short notice

---

## Crypto, trading, banking: required, and covered from the inside

- **Trading, eight years of it, with my own capital.** Equities and crypto, spot and derivatives, on Kraken among other venues. I built my own strategy backtesting environment (phoenix882.com) because I refuse to risk money on an idea I have not tested. I know the retail trading landscape the way only a user with skin in the game can: which order flows feel safe, where a liquidation notice reads as a betrayal, and which one click too many makes a trader leave.
- **Banking, built and sold.** Founded Kvitt, a mobile payments platform, from zero: payment service provider integration, settlement flows, onboarding, the complete consumer experience. Acquired and operated by Sparkasse, one of Germany's most conservative banking groups. Eight years as a startup CFO on top, so financial operations, reconciliation and reporting are familiar terrain, not adjacent ones.
- **AI prototyping is not a skill I list, it is how I work.** Eight to ten hours a day in Claude Code and similar tools, with a human in the loop. I built and run a multi-agent framework in which coordinator, implementer and evaluator agents work a shared queue under guardrails I designed. Your posting asks whether I am comfortable prototyping with Claude Code; my honest answer is that I ship production software through it, and a clickable prototype of a disputed flow costs me a day, not a sprint.
- **Data as the deciding instrument.** SQL daily; self-built Python and DuckDB market-data pipelines (German balancing-power market: provider bids, activation data, a merit-order engine); warehouse-grade analytics platforms at the Federal Employment Agency (Dagster, dbt, PostgreSQL). At EMIL I instrumented the product so churn per process step became the leading prioritisation metric.
- **Experimentation with receipts.** At Rohde & Schwarz we shipped a second workflow alongside the intended one and measured which got used: the intended one received exactly zero clicks. I define success before we build, so the answer can be observed instead of debated.
- **Market microstructure as a habit.** University thesis with Siemens Energy reconstructing roughly 41,900 unpublished marginal prices from 131 weekly merit-order lists. The difference between a quoted and a cleared price has interested me for fifteen years.

---

## How I work / My strengths

**I leave my ego at home.**
Stakeholder conversations are not the place for one's own sensitivities. I want the decision, not the last word, and I stay unemotional when the room does not.

**I fall in love with the problem, not the solution.**
The best way to satisfy customers is to never be in love with your own solution you thought was so clever. A design I am attached to is a design I will defend past its expiry date, which is how organisations end up shipping the wrong thing in a beautiful, convincing way.

**On greenfield, I buy information before I make software.**
Unknown territory requires quick, inexpensive discovery bets that resolve the largest uncertainty first. Cheap experiments make expensive decisions safe(r).

**I keep the whole value chain in view, not just the backlog.**
A product decision is not finished when the story is refined. After discovery and requirements, a coherent development and test-automation setup has to exist: a branching and merging strategy that allows a hotfix on the same day, regression tests the team genuinely trusts at release, and GitOps processes that turn rollout and rollback into a non-event. Building and owning that chain is the work of architects and DevOps engineers, not mine. What I bring is understanding it well enough to steer it into the right lanes and to notice when discovery, requirements, testing and delivery start drifting apart. The time from spotting a defect to shipping the fix is a product metric, not an engineering detail.

---

## The problems I am usually brought in to solve

Nobody knows which solution the market actually needs. Not us, not the customer, and not the highest-paid opinion in the room. Almost every expensive product failure begins with an organisation that pretends somebody does.

The alternative is to treat each product decision as a bet. Continuous discovery and cheap, fast prototyping move us toward the answer internally, in small increments, and pilot users and stakeholders then verify prototypes and MVPs externally, or buy us very valuable information about a failure mode as cheaply as possible. That is how you arrive at products people genuinely love, rather than products that merely exist (with zero revenues).

**1. Discovery is treated as a phase, and a short one.**

Someone has an idea, it enters a roadmap, a specification is written, and the team starts building. Discovery, where it happens at all, is a number of workshops and a slide deck. The wrong thing then gets built efficiently, which is the most expensive failure mode there is, because it takes a full delivery cycle before anyone finds out.

*How I solve it:* discovery is continuous, never a phase. My working assumption is that most product decisions will produce no revenue at all (at least 50 percent of the time, maybe 75), so the only rational response is to keep every bet small and cheap enough that being wrong is survivable and fast to detect. I resolve the largest uncertainty first, with the cheapest instrument that can settle it: a prototype, a few real user conversations, a click-through mockup, sometimes only a spreadsheet.

**2. Discovery happens without the two people who make solutions good.**

The product manager goes off with stakeholders and returns with requirements. The engineers first see the idea at refinement, when its shape is already fixed. The designer is handed a flow to make presentable. Both are then expected to be committed to a solution they had no part in finding, and the best technical option, the one only the lead engineer could have proposed, never surfaces at all.

*How I solve it:* I keep a standing core discovery team of at least myself, a product designer and the lead engineer. Not a ceremony, a habit. Engineers who see the user problem early bring solutions nobody would have specified, and designers who are present when the problem is framed stop producing decoration.

**3. Work arrives as a decree instead of a problem to solve.**

A feature list comes down from the executive floor or from the loudest stakeholders. The team is told what to build rather than what to achieve, the output versus outcome conundrum, and nobody is invited to come back with something better, or with the finding that it should not be built at all.

*How I solve it:* I bring the team the problem, the user and the evidence, and I negotiate on outcomes instead of output. That requires being able to hold an unemotional conversation with a stakeholder whose pet feature I am declining, which is a discipline rather than a personality trait. It also requires measurement, because without metrics decisions are not falsifiable, and the loudest voice wins by default.

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

Two-sided B2B marketplace matching construction firms with construction workers.

- Zero to one: product vision, strategy and principles, with continuous discovery
- Acquisition, activation and retention owned as one funnel rather than as separate teams
- AI assistance across the full operational funnel, so one person can run the day-to-day business

### Rohde & Schwarz · Product Manager, AI and Data Platform
*2024 to 2025 · Munich and remote*

Owned a module of a central AI and data platform, turning multimodal sources into datasets for machine learning training and evaluation.

- Full ownership from discovery to production: requirements, backlog, release definition, rollout
- Led a cross-functional squad of architects, data scientists, engineers and QA across several countries
- Deployment times reduced from several days to 20 to 40 minutes; resolved an infrastructure blocker engineering had not cracked in over a year

### Bundesagentur für Arbeit (German Federal Employment Agency) · Product Manager, Data and Analytics Platform
*2023 to 2024 · remote*

National analytics platform on a warehouse-grade ETL stack, used by policy makers and researchers across Germany.

- Introduced automated ETL orchestration and standardised CI/CD
- Deputy IT security officer: compliance, governance and data lineage under a recurring audit cycle

*Python, PostgreSQL, Dagster, dbt, Kubernetes*

### EMIL Group · Product Manager, B2B SaaS Platform
*2022 · Berlin*

Multi-tenant platform for insurers, reinsurers, brokers and underwriters.

- Built a claims module from zero, with no specification and no internal precedent, running discovery directly with a pilot customer's specialists
- Instrumented the flow so that churn per process step became the leading prioritisation metric
- Restructured a 17-person delivery organisation into effective teams; restored velocity and client trust

### CLINET Platforms · Product Owner, Consumer App (iOS and Android)
*2021 to 2022 · Berlin*

- Shipped a native mobile product across two platforms for several distinct user groups
- Cut an overambitious roadmap to the most important ten percent of features, and shipped
- Implemented the interface into the incumbent system landscape myself

### Bundesdruckerei · Product Owner, National Health Data Platform
*2021 · Berlin*

Secure data structures and identity management under the highest privacy requirements.

### Scheidt & Bachmann · Product Owner, Integration Team
*2020 to 2021 · Mönchengladbach*

- Product Owner of the integration team: turning research outcomes into releasable integration across site and head-office systems, in a fully SAFe organisation

### AOK ITSCare · Proxy Product Owner
*2019 to 2020 · Germany*

Migration of a procurement platform serving roughly 20,000 employees across three regional health insurers.

---

## Founder track record

- **Kvitt Payment Solutions · Founder and CFO (2013 to 2018).** Mobile payments platform built from zero: payment service provider integration, settlement flows, onboarding, full consumer experience. Acquired and operated by Sparkasse. As CFO owned accounting, financial planning and investor reporting.
- **Qcrypt AG · Co-Founder and Product Owner (2016 to 2018).** Quantum-secure encryption across a three-layer hardware and software architecture, shipped to enterprise customers under a sub-two-minute installation constraint.
- **Smart Soil Technologies · Co-Founder, CDO and CFO (2016 to 2021).** Nanotechnology product from laboratory to investor rounds; owned finance, HR and the ERP rollout.

---

## AI-first as a working mode

My approach is AI-first, and it changes the economics of product work measurably. With Claude Code and similar tools, human in the loop, I deliver part-time the output a small team needed full-time a year ago: requirements, interface design, frontend and backend, automated regression and end-to-end testing, architecture, infrastructure and operations. I do not write the production code myself, I own it. For that I built and run a multi-agent framework in which coordinator, implementer and evaluator agents work a shared queue under guardrails I designed.

The practical consequence for a consumer trading team: a disagreement about a flow gets settled with a clickable prototype in a day rather than with opinions in a meeting, and User Acceptance Testing starts from a PM who has already walked the build.

---

## Education and languages

**Diplom-Wirtschaftsingenieur** (Industrial Engineering and Business Administration), Technische Universität Berlin.

German (native) · English (C2).
