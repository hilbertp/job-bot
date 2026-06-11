# Profile Fact Base

Last updated: 2026-06-11. Extend immediately when new facts surface.

## Identity & contact (canonical document header)

Philipp Hilbert · Berlin, Germany · hilbert@true-north.berlin · +357 94101644 · www.true-north.berlin
LinkedIn: linkedin.com/in/philipp-hilbert-34032275 · GitHub: github.com/hilbertp
German native, English C2. Phone is Cypriot; business interests in Cyprus (construct8, Cloud9 Limassol); applications present Berlin as base.

## Ventures (founder track record)

- **Kvitt Payment Solutions (2013-2018), Founder & CFO.** Mobile, group-based P2P payments platform built from zero: PSP integration, payment/settlement flows, onboarding, complete UX/UI, mobile prototype. **Acquired and operated by Sparkasse** (= girocard institutional ecosystem; the single strongest hook for German banking/payment roles). As CFO owned accounting and financial planning.
- **Qcrypt AG (2016-2018), Co-Founder & PO.** Quantum-secure encryption, three-layer hardware/software architecture: (1) TRNG hardware modules for true-random key material, (2) Linux OTP endpoint machines, (3) server relay for decryption/re-encryption. Shipped to B2B enterprise clients under a sub-two-minute setup constraint. Deputy IT Security Officer.
- **Smart Soil Technologies (2016-2021), Co-Founder, CDO & CFO.** Nanotechnology fertiliser/substrate for vertical indoor farming; lab to investor rounds; owned financial planning, accounting, investor reporting.
- **Cloud9 / cloud-nine.store (2026-present, live).** Premium on-demand lifestyle-services platform for Cyprus (Limassol): multi-tenant storefronts (per-vendor subpages and scoped admin), live Stripe payments, Google Ads with Consent Mode v2 cookie banner, first-party analytics, Telegram order-alert bot. Real vendors: hookahlounge.cy (shisha delivery, live) and calisthenics coach Ruben Veres (rubenveres.com). Pivoted from pure shisha delivery to multi-service platform to satisfy Google Ads tobacco policy. Stack: Node/Express + better-sqlite3 + EJS behind Caddy on an IONOS VPS (AlmaLinux, systemd, rsync deploys). Built AI-first (Claude Code et al.). Also owns phoenix882.com.
- **HyperMVP (private repo hilbertp/hypermvp, active through 2025-07).** Python/DuckDB/Polars pipeline for the current aFRR balancing market: provider bids (4h buckets, regelleistung.net) + activation deltas (15-min, netztransparenz.de), idempotent re-imports, merit-order engine reconstructing marginal prices; `filter_negative_50hertz` targets the 50Hertz control zone. Purpose: economic evaluation of grid-balancing flexibility (frame as "Elektrolyse oder flexible Rechenlast" for conservative audiences). ~5.7k LOC, tests, Streamlit viewer. Clone via `gh repo clone hilbertp/hypermvp` (404 on plain web).
- **construct8 (Cyprus).** Construction labour leasing model: hire workers, lend to contractors, ~20% wage markup, ~15.4% CY employer costs. Business-model stage.

## Employment stations (deep facts beyond the CV bullet)

- **Rohde & Schwarz (2024-2025), PM/PO AI Data Platform, FCAS.** Central AI/data platform for the European defence programme; multimodal datasets feeding ML training/evaluation pipelines. Canonical claims: full lifecycle ownership discovery→GitOps rollout (ArgoCD, Argo Workflows); reproducible pipelines with provenance + audit trails (SafeAI/ExplainableAI); deployment times cut from days to 20-40 minutes; personally resolved an OpenShift infrastructure blocker engineering had not cracked in over a year; led multinational cross-functional team (architect, data scientists, BE/FE engineers, QA). Stack: Kotlin (Spring Boot), Python, PostgreSQL, MongoDB, Redpanda (Kafka), Kubernetes, ArgoCD, OpenShift, GitLab.
- **Bundesagentur für Arbeit (2023-2024), PM Public Data Analytics.** Arbeitsmarktmonitor: analytics platform on a warehouse-grade ETL stack for regional labour-market data, serving policymakers and researchers across Germany. Introduced Dagster for automated ETL + indicator generation (dbt models alongside); standardised CI/CD; **Deputy IT Security Officer** (compliance, governance, data lineage). Stack: Python, Django, PostgreSQL, dbt, Dagster, DuckDB, Kubernetes.
- **EMIL Group (2022), PM InsurTech SaaS.** B2B platform for insurers, reinsurers, MGAs, brokers, underwriters; time-to-market for insurance products from >1 year to <1 week. Modules: product configuration (master-data models), pricing, underwriting, policy issuance, document workflow automation; shipped Claims Center concept→production. **Restructured a bloated 17-person team into effective Scrum units**, restored velocity and client trust. The go-to story for "structure in fragmented domains".
- **CLINET Platforms (2021-2022), PO Mobile Healthcare App.** Early-stage HealthTech startup. Hospital pilot app iOS+Android: **digital anamnesis** (he shipped the exact product category), meal/therapy plans, transport, chat, patient document storage. **Implemented the CGM (CompuGroup Medical) interface himself** and integrated it into hospital KIS workflows. **Developed custom health product offers based on anonymized patient data** (privacy-preserving product work, DSGVO-relevant). Stack: AngularJS, Ionic, Python, Kubernetes.
- **Bundesdruckerei (2021), PO COVID-19 Data Platform.** Secure data structures + identity management for RKI projects **DIM** (Digitales Impfquotenmonitoring) and **DESH** (Einreisemanagement/Surveillance). National health infrastructure, highest privacy requirements.
- **AOK ITSCare (2019-2020), literal title: Proxy Product Owner.** Between Krankenkassen-Fachbereich and dev team; migration of internal webshop to Shopware with complex catalogue/API integration into legacy systems.
- **Enercon (2019), Project Lead.** Full IT modernisation of a manufacturing site (wind energy). Energy-sector credential; SAP exposure unverified (asked 2026-06-11, no answer yet).

## Education & the Studienarbeit asset

**Diplom-Wirtschaftsingenieur, TU Berlin, Vertiefung Logistik.**
Studienarbeit (April 2014, with **Siemens AG Energy Service Berlin**): "Profitabilitätsanalyse schneller Lastgradienten aus Kraftwerksbetreibersicht". Covers PRL/SRL/MRL incl. reaction/delivery times; deep model of the SRL market (negative control, Hauptzeit). Self-written VBA pipeline over **131 weekly Merit-Order-Listen** (regelleistung.net, mid-2011 to end-2013); reconstructed the **unpublished Grenzarbeitspreis for ~41,900 15-min intervals** (cumulate awarded bid volumes down the merit order until actual Abrufleistung is reached); `abrufHT()` maps any Arbeitspreis to empirical weekly activation frequency; revenue-optimal price 2013 = **-29 EUR/MWh**; explains the **-37 EUR/MWh market bid floor** (below ~45% plant load the payment to the ÜNB exceeds the gas saving); **explicitly excluded Kernanteilsregelung awards (a 50Hertz-zone mechanism) from averages**. Headline economics: 2013 NEG_HT mean Leistungspreis 752,88 EUR/MW; upgrade NPV 2,1-2,9 Mio EUR after 2 years; amortisation in 7-8 operating weeks. PDF: `~/Downloads/Studienarbeit-Profitabilitat-schneller-Lastgradienten-aus-Kraftwerksbetreibersicht-1.pdf`.

## AI-native practice (headline asset for AI-first employers)

Works **8-10 hours/day** with Claude Code, Codex, Cursor, GitHub Copilot, Claude Cowork, Lovable; regularly hits his EUR 90 Max plan capacity. Built and operates his own autonomous job-application agent infrastructure (this repo) and shipped Cloud9 production e-commerce AI-first. Knows LLM failure modes hands-on: "when standard workflows arent reliably rigid enough even the frontier models today struggle with staying in bounds or even progressing at all" (his words; great line for conversational-AI / agent roles). Uses Gemini image generation for marketing assets. Android user.

## Web3 / DeFi

Eight years hands-on practitioner: hot/cold wallets, DEXes + aggregators, perpetuals, cross-chain bridging, liquidity provision; CEX mechanics, AMMs, concentrated liquidity, margin/funding/liquidation models, bridge risk, oracle pricing. Use for trading/settlement credibility; CUT the standalone section for conservative German corporates (banking DWH, TSO) where it reads risk-affine.

## Constraints & conditions

- **Permanent salary floor: 125k EUR** (countered HCL's 110k float with 125k).
- **Freelance rate precedent: 80 EUR/h all-in** (set 2026-06-11 for healthcare proxy-PO and girocard PO; my market read was 95-110, he priced to win the screen).
- Remote strongly preferred; `on_site_ok: false` in profile.yaml BUT willing to relocate/commute for the right role (AllUnity Frankfurt, 50Hertz Berlin onsite share, HCL Frankfurt hybrid all accepted).
- Available at short notice (between engagements since R&S ended 2025; gap covered on CVs by "True North · Independent Product & Delivery Consultant, 2025-present").
- Scalable Capital blocker: TU Berlin Diplom-Urkunde not digitised (their form demands a degree certificate scan).

## The 13-years framing rule (verified by adversarial review)

Total career since founding Kvitt (2013) = 13 years: OK as "13 years of end-to-end delivery as founder, product manager, and project lead". NEVER attach the 13 years to a specific domain (data platforms, payments); domain-scope honestly ("the last seven years focused on...", 2019-2026). The general CV says "nearly ten years" for employed PM work.

## Known hard gaps (do not paper over)

- **No SAP anywhere** (SAP IDM / Cloud Identity Services mandates = skip; scored 35/48 on 2026-06-11).
- **No operational PPA settlement / Bilanzkreis day-to-day** (capped Otark at 90; prep question for energy-market interviews).
- **No shipped production chatbot/voicebot** (counter-story: the agentic job-bot infrastructure as product case study).
- **No PM certifications** (no PMP/PRINCE2/SAFe/CSPO). Mitigation: "Methods" line listing Scrum/Kanban/hybrid delivery in regulated programmes.
- **No literal "IT Project Manager" titles recently** (PM/PO titles 2019-2025); mitigate with dual-form headline ("IT Project & Product Manager") when JD demands PM.
