# Philipp Hilbert. *Product Manager · AI Platforms, Agent Architectures and AI Governance.*

hilbert@true-north.berlin · +357 94101644 · www.true-north.berlin · [LinkedIn](https://www.linkedin.com/in/philipp-hilbert-34032275/) · [GitHub](https://github.com/hilbertp)

10+ years of XP · internal AI platforms, LLM and agent systems, AI compliance · fintech and payments · German native, English C2 · available at short notice

---

## AI platform, agents and governance

- **An internal AI platform serving other teams:** at Rohde & Schwarz I owned a module of a central AI and data platform whose customers were internal teams, not end users. Requirements, backlog, release definition and rollout, working directly with data scientists and AI engineers.
- **LLMs, prompt design, agent architectures, evaluation:** I build and operate these, not only specify them. My multi-agent framework runs coordinator, implementer and evaluator agents over a shared work queue under guardrails I designed, and I spend eight to ten hours a day in AI development tools with a human in the loop. Evaluation loops, golden sets and regression checks are where I put the most care, because an agent without them is a demo.
- **Trace analysis and agent performance:** I read my own agents' traces to find where they drift, stall or quietly produce plausible nonsense. That is also the honest source of my scepticism: I know these systems from operating them, not from a vendor deck.
- **AI compliance and data governance:** reproducible pipelines with complete provenance and audit trails on a safety-critical programme; deputy IT security officer twice, owning data lineage and governance under a recurring audit cycle; privacy-critical product work on national health data and on anonymised patient data.
- **Deciding which use cases are worth it:** I triage on three questions before anything is built. How critical is correctness, which sets the human fallback. How repetitive and high in volume is the work, which is where AI actually earns its keep. How much does the process depend on a personal relationship, because automating a valued human touchpoint erodes trust while automating unvalued friction is pure gain.
- **Fintech and markets:** founded a mobile payments platform acquired and operated by Sparkasse; eight years as a startup CFO; eight years trading spot and derivatives on Binance and Kraken and perpetuals on decentralised exchanges; built my own trading-strategy backtesting platform.

## How I work / My strengths

**I leave my ego at home.**
Stakeholder conversations are not the place for one's own sensitivities. I want the decision, not the last word, and I stay unemotional when the room does not.

**I fall in love with the problem, not the solution.**
The best way to satisfy customers is to never be in love with your own solution you thought was so clever. A design I am attached to is a design I will defend past its expiry date, which is how organisations end up shipping the wrong thing in a beautiful, convincing way.

**On greenfield, I buy information before I make software.**
Unknown territory requires quick, inexpensive discovery bets that resolve the largest uncertainty first. Cheap experiments make expensive decisions safe(r).

---

## The problems I am usually brought in to solve

Nobody knows which solution the market actually needs. Not us, not the customer, and not the highest-paid opinion in the room. Almost every expensive product failure begins with an organisation that pretends somebody does.

The alternative is to treat each product decision as a bet. Continuous discovery and cheap, fast prototyping move us toward the answer internally, in small increments, and pilot customers and stakeholders then verify prototypes and MVPs externally, or buy us very valuable information about a failure mode as cheaply as possible. That is how you arrive at products people genuinely love, rather than products that merely exist (with zero revenues).

The five problems below are what happens when an organisation skips that. They are not specific to any industry. They are specific to how software gets built badly almost everywhere, and they bite hardest where software is bought as a project with a start and an end date instead of owned as a product.

**1. Discovery is treated as a phase, and a short one.**

Someone has an idea, it enters a roadmap, a specification is written, and the team starts building. Discovery, where it happens at all, is a number of workshops and a slide deck. The wrong thing then gets built efficiently, which is the most expensive failure mode there is, because it takes a full delivery cycle before anyone finds out.

*How I solve it:* discovery is continuous, never a phase. My working assumption is that most product decisions will produce no revenue at all (at least 50 percent of the time, maybe 75), so the only rational response is to keep every bet small and cheap enough that being wrong is survivable and fast to detect. I resolve the largest uncertainty first, with the cheapest instrument that can settle it: a prototype, a few real customer conversations, a click-through mockup, sometimes only a spreadsheet.

**2. Discovery happens without the two people who make solutions good.**

The product manager goes off with stakeholders and returns with requirements. The engineers first see the idea at refinement, when its shape is already fixed. The designer is handed a flow to make presentable. Both are then expected to be committed to a solution they had no part in finding, and the best technical option, the one only the lead engineer could have proposed, never surfaces at all.

*How I solve it:* I keep a standing core discovery team of at least myself, a product designer and the lead engineer. Not a ceremony, a habit. Engineers who see the customer problem early bring solutions nobody would have specified, and designers who are present when the problem is framed stop producing decoration. Both of them, designer as well as engineer, are regularly invited to stakeholder workshops and jour fixes.

**3. Work arrives as a decree instead of a problem to solve.**

A feature list comes down from the executive floor or from the loudest stakeholders. The team is told what to build rather than what to achieve, the output versus outcome conundrum, and nobody is invited to come back with something better, or with the finding that it should not be built at all.

*How I solve it:* I bring the team the problem, the customer and the evidence, and I negotiate on outcomes instead of output. That requires being able to hold an unemotional conversation with a stakeholder whose pet feature I am declining, which is a discipline rather than a personality trait. It also requires measurement, because without metrics decisions are not falsifiable, and the loudest voice wins by default.

**4. The result is mercenaries instead of missionaries.**

Teams that ship tickets without conviction. Nobody pushes back on a weak idea, because pushing back has never once changed the outcome. The strongest engineers leave first, since they are the ones with options.

*How I solve it:* by handing teams the problem and enough context to own it, and by repairing the structure that turned them into mercenaries in the first place. At EMIL I inherited a 17-person delivery organisation that had stalled and was losing its senior engineers. I restructured it into teams that could genuinely own something end to end. Velocity returned, client trust returned, and an almost complete exodus stopped at a single departure.

**5. Nobody can say afterwards whether it worked.**

The feature shipped, the release note went out, the team moved on. Six months later nobody can tell you whether anything changed, so the same argument starts again with the same opinions and no new evidence.

*How I solve it:* I define what would count as success before we build, and I instrument the product so the answer can be observed instead of debated. At Rohde & Schwarz I pushed to be part of the customer workshops until I was finally invited, which in a defence context takes some insisting. It became clear immediately that the customers' developers worked completely differently from what we had assumed. So we built a small alternative, code-heavy workflow alongside the intended one and measured which of the two got used. Our originally intended workflow received exactly zero clicks.

---

## Experience

### construct8 · Product Manager, B2B Marketplace for the Construction Industry
*2025 to present · Limassol and remote*

Two-sided B2B marketplace matching construction firms with construction workers.

- Zero to one marketplace: product vision, strategy and principles, with ongoing discovery
- An innovative B2B marketplace designed to remove the headhunter as middleman entirely
- A difficult messaging reality, because the business has to run inside the channels its users actually live in, WhatsApp and Telegram
- User journey optimisation across all three sides: the contractors, the workers and the internal operations staff
- Full AI assistance from interview through selection and vetting, to keep internal cost minimal: one person can run the entire day-to-day business operation

### Rohde & Schwarz · Product Manager, AI and Data Platform (FCAS defence programme)
*2024 to 2025 · Munich and remote*

Owned a module of the central AI backbone for a European defence programme: an internal platform whose consumers were other teams, turning multimodal data sources into datasets for machine learning training and evaluation.

- Full ownership from discovery to production: requirements, backlog, release definition, rollout
- Translated business goals into actionable work for data scientists and AI engineers
- Reproducible pipelines with complete provenance and audit trails, because in that environment an unexplainable output is a defect
- Deployment times reduced from several days to 20 to 40 minutes; resolved an infrastructure blocker engineering had not cracked in over a year
- Steered a multinational team of architects, data scientists, engineers and QA

*Kubernetes, OpenShift, GitOps (ArgoCD), Kotlin, Python, PostgreSQL, Kafka*

### Bundesagentur für Arbeit (German Federal Employment Agency) · Product Manager, Data and Analytics Platform
*2023 to 2024 · remote*

National analytics platform on a warehouse-grade ETL stack, used by policy makers and researchers across Germany.

- Introduced automated ETL orchestration and standardised CI/CD
- Deputy IT security officer: compliance, governance and data lineage under a recurring audit cycle

*Python, PostgreSQL, Dagster, dbt, Kubernetes*

### EMIL Group · Product Manager, B2B SaaS Platform
*2022 · Berlin*

B2B platform for insurers, reinsurers, brokers and underwriters.

- Delivered modules across product configuration, pricing, underwriting, policy issuance and document workflow automation
- Built a claims module from zero, with no specification and no internal precedent, running discovery directly with a pilot customer's claim specialists
- Restructured a 17-person delivery organisation into effective teams; restored velocity and client trust
- Instrumented the claim flow so that churn per process step became the leading prioritisation metric

### CLINET Platforms · Product Owner, Mobile Application (iOS and Android)
*2021 to 2022 · Berlin*

- Shipped a hospital application across two platforms for several distinct user groups
- Implemented the interface into the incumbent clinical system landscape myself
- Cut an overambitious roadmap to the most important ten percent of features

### Bundesdruckerei · Product Owner, National Health Data Platform
*2021 · Berlin*

Secure data structures and identity management for national pandemic monitoring programmes, under the highest privacy requirements.

### Scheidt & Bachmann · Product Owner, Integration Team (Fuel and Convenience Retail)
*2020 to 2021 · Mönchengladbach*

Point of sale, payment and forecourt systems for petrol stations and convenience retail.

- Product Owner of the integration team, downstream of research: turning research outcomes into productive, releasable integration across site and head-office systems
- Backlog ownership in a fully SAFe organisation: PI planning, release train coordination, cross-team dependency management
- Worked across a complex matrix organisation spanning geographies and disciplines

### AOK ITSCare · Proxy Product Owner
*2019 to 2020 · Germany*

Migration of an internal procurement platform serving roughly 20,000 employees across three regional health insurers, with catalogue and API integration into legacy systems and approval workflows per organisational unit.

### Enercon · Project Lead, IT Modernisation
*2019 · Germany*

Full IT modernisation of a manufacturing site in the wind energy sector, covering hardware racks, servers, switches and communication lines.

---

## Founder track record

- **Kvitt Payment Solutions · Founder and CFO (2013 to 2018).** Mobile payments platform built from zero: payment service provider integration, settlement flows, onboarding, full user experience. Acquired and operated by Sparkasse. As CFO owned accounting, financial planning and investor reporting.
- **Qcrypt AG · Co-Founder and Product Owner (2016 to 2018).** Quantum-secure encryption across a three-layer hardware and software architecture, shipped to enterprise customers under a sub-two-minute installation constraint.
- **Smart Soil Technologies · Co-Founder, CDO and CFO (2016 to 2021).** Nanotechnology product from laboratory to investor rounds; owned finance, HR and the ERP rollout.

---

## AI-native practice

I work eight to ten hours a day with AI development tools, with a human in the loop, and I ship production software that way across the full delivery chain: requirements, interface design, frontend and backend, automated regression and end-to-end testing, architecture, infrastructure and operations. I built and run a multi-agent framework in which coordinator, implementer and evaluator agents work a shared queue under guardrails I designed. This is why I can hold a credible technical conversation with engineers and researchers instead of translating between them, and why prototyping an idea is cheap enough for me to do it before asking anyone to commit to it.

---

## Education and languages

**Diplom-Wirtschaftsingenieur** (Industrial Engineering and Business Administration), Technische Universität Berlin, specialisation in logistics.

German (native) · English (C2).
