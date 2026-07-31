# Profile Fact Base

Last updated: 2026-06-11. Extend immediately when new facts surface.

## Identity & contact (canonical document header)

Philipp Hilbert · Berlin, Germany · hilbert@true-north.berlin · +357 94101644 · www.true-north.berlin
LinkedIn: linkedin.com/in/philipp-hilbert-34032275 · GitHub: github.com/hilbertp
German native, English C2 — confirmed complete 2026-06-12 ("only en and german"), never list other languages. **LIVES IN LIMASSOL, CYPRUS** (confirmed 2026-07-04: "ich lebe in limassol, wie du sicher weißt!"); phone is Cypriot; businesses in Cyprus (construct8, Cloud9 Limassol); Berlin penthouse is listed for rent. **Location doctrine:** German-market applications present Berlin as base (existing choice, keep); international/remote-worldwide applications use the dual header "Limassol, Cyprus / Berlin, Germany" (0G precedent) — and remote-from-Cyprus (EU) means NO US visa is needed for US-remote roles unless he actually relocates.

## Ventures (founder track record)

- **Kvitt Payment Solutions (2013-2018), Founder & CFO.** Mobile, group-based P2P payments platform built from zero: PSP integration, payment/settlement flows, onboarding, complete UX/UI, mobile prototype. **Acquired and operated by Sparkasse** (= girocard institutional ecosystem; the single strongest hook for German banking/payment roles). As CFO owned accounting and financial planning.
- **Qcrypt AG (2016-2018), Co-Founder & PO.** Quantum-secure encryption, three-layer hardware/software architecture: (1) TRNG hardware modules for true-random key material, (2) Linux OTP endpoint machines, (3) server relay for decryption/re-encryption. Shipped to B2B enterprise clients under a sub-two-minute setup constraint. Deputy IT Security Officer.
- **Smart Soil Technologies (2016-2021), Co-Founder, CDO & CFO.** Nanotechnology fertiliser/substrate for vertical indoor farming; lab to investor rounds; owned financial planning, accounting, investor reporting.
- **Cloud9 / cloud-nine.store (2026-present, live).** Premium on-demand lifestyle-services platform for Cyprus (Limassol): multi-tenant storefronts (per-vendor subpages and scoped admin), live Stripe payments, Google Ads with Consent Mode v2 cookie banner, first-party analytics, Telegram order-alert bot. Real vendors: hookahlounge.cy (shisha delivery, live) and calisthenics coach Ruben Veres (rubenveres.com). Pivoted from pure shisha delivery to multi-service platform to satisfy Google Ads tobacco policy. Stack: Node/Express + better-sqlite3 + EJS behind Caddy on an IONOS VPS (AlmaLinux, systemd, rsync deploys). Built AI-first (Claude Code et al.).

## Self-built product portfolio (his "I build across the whole stack" proof, 2026-06-29)

Live, shipped solo end-to-end. Use as the AI-native-builder evidence set for any AI/dev-tools/crypto role:
- **phoenix882.com** = **trading-strategy backtesting platform** (Hyperliquid/Jupiter/1inch); the old "crypto backtest engine" now has this domain. Direct credibility for trading-product PM roles.
- **cloud-nine.store (Cloud9)** = live multi-service marketplace platform (multi-tenant, live Stripe, analytics).
- **construct8.com** = two-sided workforce-matching platform (Bauunternehmen <-> Bauarbeiter). See [[project-construct8-business-model]].
- **Liberation of Bajor** = multi-agent **team-compatible "vibecoder" framework** (agent orchestration over a shared work queue).
- **job_bot** = autonomous job-application agent (this repo).
- **HyperMVP (private repo hilbertp/hypermvp, active through 2025-07).** Python/DuckDB/Polars pipeline for the current aFRR balancing market: provider bids (4h buckets, regelleistung.net) + activation deltas (15-min, netztransparenz.de), idempotent re-imports, merit-order engine reconstructing marginal prices; `filter_negative_50hertz` targets the 50Hertz control zone. Purpose: economic evaluation of grid-balancing flexibility (frame as "Elektrolyse oder flexible Rechenlast" for conservative audiences). ~5.7k LOC, tests, Streamlit viewer. Clone via `gh repo clone hilbertp/hypermvp` (404 on plain web).
- **construct8 (www.construct8.com).** Zweiseitige Matching-Plattform für Bauunternehmen und Bauarbeiter; Philipp = Gründer mit Produktverantwortung über beide Nutzergruppen. AI-first gebaut. Underlying business model: construction labour leasing (hire workers, lend to contractors, ~20% wage markup, ~15.4% CY employer costs). USE as the multi-tenant / multi-user-groups platform proof for "Digitale Plattformen" / marketplace JDs (confirmed by Philipp 2026-06-29; supersedes earlier "business-model stage only" framing).

## Employment stations (deep facts beyond the CV bullet)

- **FCAS employer — DEFAULT IS "Rohde & Schwarz", by Philipp's deliberate choice (confirmed emphatically 2026-07-25: "ich wähle bewusst rohde und schwarz als mutter weil der name bekannt ist. lass das!").** Keep writing **Rohde & Schwarz** on ALL CVs/CLs — do NOT "correct" it to SSE. The underlying legal entity was Schönhöfer Sales & Engineering (SSE), a wholly-owned R&S subsidiary, but R&S is the intended, brand-recognised name and stays. **The ONLY exception is applications to people who cooperated directly with SSE on FCAS (Helsing) — there, name SSE exactly** because they know it was SSE, not R&S. The exact product Philipp owned on FCAS was the **KI-Backbone Data Transformation Module** (transforming multimodal data sources into ML training/eval datasets) — name it precisely for Helsing; generic "central AI/data platform" framing stays fine on all other CVs. For the Helsing package only: title was **Product Manager**, and Philipp had a close working relationship with Helsing's architect **Christopher Pohnke** and project lead **Jonas Banasch** (drop both names). Everywhere else: R&S, and PO/PM title as fits the role, unchanged.
- **Rohde & Schwarz (2024-2025), PM/PO AI Data Platform, FCAS.** Central AI/data platform for the European defence programme; multimodal datasets feeding ML training/evaluation pipelines. Canonical claims: full lifecycle ownership discovery→GitOps rollout (ArgoCD, Argo Workflows); reproducible pipelines with provenance + audit trails (SafeAI/ExplainableAI); deployment times cut from days to 20-40 minutes; personally resolved an OpenShift infrastructure blocker engineering had not cracked in over a year; led multinational cross-functional team (architect, data scientists, BE/FE engineers, QA). Stack: Kotlin (Spring Boot), Python, PostgreSQL, MongoDB, Redpanda (Kafka), Kubernetes, ArgoCD, OpenShift, GitLab.
- **Bundesagentur für Arbeit (2023-2024), PM Public Data Analytics.** Arbeitsmarktmonitor: analytics platform on a warehouse-grade ETL stack for regional labour-market data, serving policymakers and researchers across Germany. Introduced Dagster for automated ETL + indicator generation (dbt models alongside); standardised CI/CD; **Deputy IT Security Officer** (compliance, governance, data lineage). Stack: Python, Django, PostgreSQL, dbt, Dagster, DuckDB, Kubernetes.
- **EMIL Group (2022), PM InsurTech SaaS.** B2B platform for insurers, reinsurers, MGAs, brokers, underwriters; time-to-market for insurance products from >1 year to <1 week. Modules: product configuration (master-data models), pricing, underwriting, policy issuance, document workflow automation; shipped Claims Center concept→production. **Restructured a bloated 17-person team into effective Scrum units**, restored velocity and client trust. The go-to story for "structure in fragmented domains".
- **CLINET Platforms (2021-2022), PO Mobile Healthcare App.** Early-stage HealthTech startup. Hospital pilot app iOS+Android: **digital anamnesis** (he shipped the exact product category), meal/therapy plans, transport, chat, patient document storage. **Implemented the CGM (CompuGroup Medical) interface himself** and integrated it into hospital KIS workflows. **Developed custom health product offers based on anonymized patient data** (privacy-preserving product work, DSGVO-relevant). Stack: AngularJS, Ionic, Python, Kubernetes.
- **Bundesdruckerei (2021), PO COVID-19 Data Platform.** Secure data structures + identity management for RKI projects **DIM** (Digitales Impfquotenmonitoring) and **DESH** (Einreisemanagement/Surveillance). National health infrastructure, highest privacy requirements.
- **Scheidt & Bachmann, Fuel & Convenience Retail (2020-2021, ~12 Monate), Product Owner Integration Team.** Liefer-/Entwicklungsorganisation **vollständig nach SAFe** organisiert (ARTs, PI-Planning, Release Train). PO für das **Integration Team, dem Research Team nachgelagert**: Überführung von Research-Ergebnissen in die produktive Integration über eine **komplexe Matrixorganisation** hinweg, über geografische und fachliche Bereiche. POS-/Bezahl- und Forecourt-Systeme für Tankstellen und Convenience-Retail; Mönchengladbach. **KEY ASSET: der einzige belegte echte SAFe-Kontext (>=1 Jahr) im Profil** — nutze für jede JD mit Must-have "SAFe-Umfeld" / "skaliert-agil" (confirmed by Philipp 2026-06-16; fills the post-ITSCare 2020-21 gap). NB: distinct from the scraped S&B Parking/camos-CPQ job posting in the corpus, which is NOT his history.
- **AOK ITSCare (2019-2020), literal title: Proxy Product Owner.** Between Krankenkassen-Fachbereich and dev team; migration of internal webshop to Shopware with complex catalogue/API integration into legacy systems.
- **Enercon (2019), Project Lead.** Full IT modernisation of a manufacturing site (wind energy). Energy-sector credential; SAP exposure unverified (asked 2026-06-11, no answer yet).

## Education & the Studienarbeit asset

**Diplom-Wirtschaftsingenieur, TU Berlin, Vertiefung Logistik.**
Studienarbeit (April 2014, with **Siemens AG Energy Service Berlin**): "Profitabilitätsanalyse schneller Lastgradienten aus Kraftwerksbetreibersicht". Covers PRL/SRL/MRL incl. reaction/delivery times; deep model of the SRL market (negative control, Hauptzeit). Self-written VBA pipeline over **131 weekly Merit-Order-Listen** (regelleistung.net, mid-2011 to end-2013); reconstructed the **unpublished Grenzarbeitspreis for ~41,900 15-min intervals** (cumulate awarded bid volumes down the merit order until actual Abrufleistung is reached); `abrufHT()` maps any Arbeitspreis to empirical weekly activation frequency; revenue-optimal price 2013 = **-29 EUR/MWh**; explains the **-37 EUR/MWh market bid floor** (below ~45% plant load the payment to the ÜNB exceeds the gas saving); **explicitly excluded Kernanteilsregelung awards (a 50Hertz-zone mechanism) from averages**. Headline economics: 2013 NEG_HT mean Leistungspreis 752,88 EUR/MW; upgrade NPV 2,1-2,9 Mio EUR after 2 years; amortisation in 7-8 operating weeks. PDF: `~/Downloads/Studienarbeit-Profitabilitat-schneller-Lastgradienten-aus-Kraftwerksbetreibersicht-1.pdf`.

## AI-native practice (headline asset for AI-first employers)

Works **8-10 hours/day** with Claude Code, Cowork, and Design, plus Codex (ChatGPT), Cursor, GitHub Copilot, Manus, Lovable, Higgsfield, Perplexity; regularly hits his EUR 90 Max plan capacity. **Ships entire products SOLO across the full delivery chain (his headline self-pitch, confirmed 2026-06-29):** requirements/PRDs -> UX/UI -> frontend + backend -> QA (regression + Playwright e2e smoke tests) -> architecture decisions -> infra setup -> DevOps. The rare combination is understanding AND building across the whole stack; the live portfolio is the proof (see "Self-built product portfolio" below). Built and operates his own autonomous job-application agent infrastructure (this repo) and shipped Cloud9 production e-commerce AI-first. Knows LLM failure modes hands-on: "when standard workflows arent reliably rigid enough even the frontier models today struggle with staying in bounds or even progressing at all" (his words; great line for conversational-AI / agent roles). Uses Gemini image generation for marketing assets. Android user.

## Web3 / DeFi

Eight years hands-on practitioner: hot/cold wallets, DEXes + aggregators, perpetuals, cross-chain bridging, liquidity provision; CEX mechanics, AMMs, concentrated liquidity, margin/funding/liquidation models, bridge risk, oracle pricing. Side project: self-built crypto backtest engine (Hyperliquid/Jupiter/1inch) plus a self-hosted agentic dev framework for crypto research. Use for trading/settlement credibility; CUT the standalone section for conservative German corporates (banking DWH, TSO) where it reads risk-affine.

## Side facts & misc assets

- **Semi-professional poker player** (PokerStrategy, PokerTracker, Hold'em Manager) — the GTO Wizard application angle; reusable for gaming/probability/decision-under-uncertainty roles.
- Online-marketing hands-on: Google lead campaigns (stated to Digital Eleven), Google Ads + Consent Mode v2 + conversion tracking in production (Cloud9); evaluates marketing through Dan Kennedy's Magnetic Marketing lens.
- CV tool lists historically include II-Agent, Antigravity, n8n, Manus, Lovable, Framer; a "CV Suri Ventures" variant exists in data/corpus/cvs/.
- Application document archive: Dropbox `000 True North/Bewerbungen`; `opus CV.pdf` there is the design reference ("design king").
- Landlord: 76 sqm Berlin penthouse (5th floor, listed on ImmoScout24, available from 1 June 2026).
- Physically in Limassol (Cyprus) periodically; construct8 diligence done on the ground; his key insight: the venture needs native Cypriot connections ("meson"), his local network is Russian-speaking.
- Sought human CV review on r/EngineeringResumes (blocked by flair requirements).
- **YouTube English sample** (also Qcrypt product proof): https://www.youtube.com/watch?v=nt06f71lgfE
- Has positioned at **Head of Product** level before (FeDi/DeFi base CVs: "Head of Product and UX | 0 to 1 under ambiguity | Security vs usability").
- Dual-location header precedent: 0G application listed "Berlin, Germany / Limassol, Cyprus".

## Station details mined from legacy corpus (2026-06-12)

- **Hospital Chain WiFi rollout (early career, in 5 CV variants):** supervised IT rollout equipping 9 hospitals with full WiFi coverage. Pre-dates the AOK/Enercon era; healthcare-infrastructure proof point.
- **Liberation of Bajor** (github.com/hilbertp/liberation-of-bajor): self-built multi-agent AI orchestration over a local file queue; agents Kira (coordinator), O'Brien (implementor via Claude Code CLI) plus evaluator; 669+ commits across 298 thin slices, ADR-driven refactors, mutex-gated merges, real-time dashboard. Strongest agentic-engineering proof besides job_bot.
- **in_vis:** founder-level structuring engagement incl. virtual stock option plan design; he personally holds VSOP options.
- **R&S detail:** self-taught OpenShift, delivered the year-blocked feature SOLO within one week (project-leader quote in STORIES_AND_VOICE.md).
- **EMIL detail:** 17-person org split into exactly 2 stable teams; senior-dev attrition went from near-total exodus to a single departure.
- **CLINET detail:** 3-person dev team, overambitious roadmap cut to "the most important 10% of features"; stakeholders = hospital leadership and middle management. The opus CV titles this "Founding Product Owner".
- **BA detail:** based Nürnberg; formal training on attack vectors/mitigation as deputy ITSO; IT Security Concept audited bi-annually. Stack also included JavaScript, MicroStrategy, Jenkins, Bitbucket.
- **AOK detail (per ITSCare reference letter):** engagement März 2019 bis Mai 2020 as "Proxy Product Owner", Projekt **"AMSys#neo 1.0"** (Anwendungsentwicklung, PL Andy Saß): webshop for internal IT/hardware procurement serving **three AOK organisations, ~20,000 employees**; customizable approval policies per branch; webshop still in production per the letter. **Enercon detail:** scope included hardware racks, servers, switches, comm lines.
- **DOB: 13.11.1984** (from the ITSCare letter; for application forms that require it).
- **EMIL duration: ~8 months** as PO (per CEO reference letter).
- **Smart Soil phases (Suri CV):** 2016-2019 Projektmanager & Business Development (nanotech, investor relations); 2020-2021 CFO & Projektleiter (finance, HR, ERP-Einführung); 2021 Co-Founder, CDO & **Head of HR**.
- **Additional tools claimed in legacy CVs:** Replit, Clawdbot, Kimi K2.5, Gamma.app, Helm, Terraform, Prometheus, Grafana, Docker, MicroStrategy, Jenkins, Bitbucket.
- **Past application targets (corpus):** 0G Labs (Sr PM, Web3 AI infra), BCB Group (crypto payments PM), Fedi (Head of Product & UX, bitcoin wallet), Suri Ventures (DE freelance PO/BA, insurance + agentic AI), Upwind (cloud security PM), N26 (lending PM), opus (Founding PM, procurement AI; the PRIMARY design-reference package).

## Open conflicts to resolve with Philipp (do not propagate either side until confirmed)

1. ~~R&S CI/CD~~ RESOLVED (2026-06-12, from Philipp): **R&S = ArgoCD** (GitOps, with Argo Workflows); **Jenkins was at the Bundesagentur für Arbeit**. Never claim GitLab or Jenkins at R&S.
2. ~~EMIL stack~~ RESOLVED (2026-06-12): **Java**. His caveat: "i am not the developer. so what does it matter?" — stack lines on PM CVs are context, not authorship claims; keep them short and never let a stack keyword carry the application.
3. ~~Smart Soil~~ RESOLVED (2026-06-12): **Co-founder 2016-2021 is correct.** The Suri CV's phase-titles framing (co-founder only from 2021) is deprecated; do not reuse.
4. Kvitt exit wording: canonical is "acquired and operated by Sparkasse" (singular); Suri's "an Banken verkauft" (plural) must NOT be propagated.
5. Years framing: legacy CVs say "more than ten years product leadership"; calibrated rule is 13 years total delivery / ~7 years data-platform domain / "nearly ten" employed PM. Use the calibrated framing.
6. PRIMARY opus CV + 0G PDF contain banned contact data (projuncta, lovable.app URL, versioned GPT names): fact sources ONLY, never copy sources.

## Salary & rate doctrine (his rules, verbatim where quoted)

- **Permanent anchor: 125k EUR/year.** "for any future application take 125k per year okay?" Rule: "if they provide one themselve, use the lower end. if they dont provide apply with 125k."
- **Hard floor: filter out sub-90k** ("absolutely LAUGHABLE for a strong international PM"). Profile range recorded as 125k-170k.
- **Currency calibration:** UK = 107k GBP (ApprovalMax precedent after "is 125000 GBP viable?"); German Mittelstand calibrated down case-by-case (procilon at 105k); USD roles 125000 USD (Chili Piper).
- **Freelance: 80 EUR/h all-in, remote** ("then use freelancermap as PO freelance position only. thats fine at 80 EUR per hour remote!"; reaffirmed "offer me for 80 EUR allin"). freelancermap is for freelance PO gigs only.
- **Availability: always ASAP** ("enter asap availability always").
- **Apply threshold: tailored score 80+ triggers package creation** ("if higher than 80, create application package").

## Other constraints

- Remote strongly preferred (remote or Berlin/Munich per his PRD); willing to relocate/commute for the right role (AllUnity Frankfurt, 50Hertz Berlin onsite share, HCL Frankfurt hybrid, Wemolo Munich, autarc Berlin-Mitte hybrid all accepted).
- **Willing to relocate to the US for at least $150k base salary** (2026-07-04, verbatim: "i am willing to move to the US for at least 150k salary"; supersedes the same-day "if the salary is high" phrasing). Also willing to relocate internationally for strong roles (Crypto.com US, Revolut hubs London/Barcelona/Madrid/Dubai/Kraków). US caveat: work authorization / visa sponsorship is the real gate; prioritise US roles where his domain is exceptional (payments/crypto/trading) and the employer sponsors, over cold generic FAANG PM applies. See [[feedback-score-everything-scraped]].
- Available at short notice (between engagements since R&S ended 2025; gap covered on CVs by "True North · Independent Product & Delivery Consultant, 2025-present").
- **He owns no degree certificate at all** ("never has anybody EVER asked for it... i dont own one") — any portal demanding a Urkunde scan (Scalable Capital) is blocked, period.
- Email applications can bounce on data-compliance grounds (ETERNO precedent): prefer career-portal submission.

## The 13-years framing rule (verified by adversarial review)

**DEFAULT FRAMING (corrected by Philipp 2026-06-29): "fast zehn Jahre" als Product Owner / Product Manager.** The 13-years total framing is RETIRED ("13 jahre ist auch zu viel, fast zehn jahre ist korrekt, der rest waren selbständige projekte und gründerarbeit"). So: lead with ~10 years PO/PM, and present founder + independent project work as a SEPARATE additional track, not folded into the PM count. NEVER attach the year count to a specific domain; domain-scope honestly ("zuletzt / die letzten Jahre fokussiert auf...").

## Known hard gaps (do not paper over)

- **No SAP anywhere** (SAP IDM / Cloud Identity Services mandates = skip; scored 35/48 on 2026-06-11).
- **No operational PPA settlement / Bilanzkreis day-to-day** (capped Otark at 90; prep question for energy-market interviews).
- **No shipped production chatbot/voicebot** (counter-story: the agentic job-bot infrastructure as product case study).
- **No PM certifications** — confirmed by Philipp 2026-06-12 ("NO CERTS"); never claim any. Mitigation: "Methods" line listing Scrum/Kanban/hybrid delivery in regulated programmes.
- **No literal "IT Project Manager" titles recently** (PM/PO titles 2019-2025); mitigate with dual-form headline ("IT Project & Product Manager") when JD demands PM.
