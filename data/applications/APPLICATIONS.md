# Applications Ledger

Source of truth for scores/statuses: `data/jobbot.db`. Tables below are generated snapshots
(regenerate with the snippet at the bottom). Package map is maintained by hand: one row per
package built, appended in the same turn the package lands in ~/Downloads.

**Batch-Submission 2026-07-04 (größter Submission-Tag):** CMC, Qventus, 1&1 Dark Factory, skillbyte Cloud-PO, Revolut, PROSOZ, percision ConvAI, Payments TPM (Computer Futures), ROLAND — alle 9 als apply_submitted markiert. Crypto.com war bereits am 29.06 raus.

## Package map (PDF ↔ sources ↔ angle)

| Package (Downloads) | Sources (this dir) | Lang | Angle / notes | Rate / comp stated | Built |
|---|---|---|---|---|---|
| application_general.pdf + CV_Philipp_Hilbert_General.pdf | general_cv_clean.md + general_cl_clean.md (v2, komplett neu 17.07) | EN | GENERAL-Paket, generalistisch: Builder-PM-Through-line (founder/Kvitt-Sparkasse + full-stack solo + AI-native 8-10h), dual header Limassol/Berlin, "nearly ten years". WICHTIG: data/general CV.pdf (Pipeline-cv_pdf_path!) mit der sauberen CV-only-Version ÜBERSCHRIEBEN -> die dirty Juni-Version (projuncta+lovable) haengt ab jetzt NICHT mehr an Auto-Bewerbungen. Alte general_cv_clean.md (Em-Dashes, "Rohde and Schwarz", fehlende Umlaute) ersetzt | n/a | 2026-07-17 |
| application_helsing_defence_pm.pdf | cl/cv_helsing_defence_pm.md (CV aus cf_payments_tpm_en_full, defence-getailort) | EN | Helsing PM (Defence-AI, München/Berlin, "Confidential role"). Manual 82/93 — BESTER Permanent-Match der Session. Direktester Domain-Match: er war PO der FCAS-Verteidigungs-KI-Plattform bei R&S. BEIDE Nice-to-haves getroffen: deutscher Staatsbürger -> Sicherheitsüberprüfung eligible + Public-Sector-Track (Bundesdruckerei/BA/AOK). Full-scope PM (Gründer-Commercial/GTM + technische Architektur + AI-native Builder), DE+EN fluent. v2 (25.07, User-Präzisierung): FCAS-Arbeitgeber KORREKT als Schönhöfer Sales & Engineering (SSE), R&S-Tochter, PM-Titel (nicht direkt R&S) — in CV + KB. CL komplett neu: führt mit gemeinsamer FCAS-Historie, dropt elegant Christoph Pohnke (Architekt) + Jonas Banasch (Projektleiter), trägt Philipps Voice (Direktheit/Bluntness, "get-it-done", Struktur für die junge schnellgewachsene Org, Startup-Kultur auf Scale-up-Level). Header Berlin/German-citizen (Clearance). Relocation Mü/Berlin ok. Apply via Greenhouse (boards helsing) | Competitive salary + VSOP | 2026-07-25 |
| application_waynice_config_lifecycle.pdf | cl/cv_waynice_config_lifecycle.md | DE | Manager Product Configuration & Lifecycle, freiberuflich, Kunde RHEINMETALL via waynice GmbH (Felix Frey, felix.frey@waynice.de). Manual 55/68 — UNTER Schwelle, auf ausdrücklichen Wunsch gebaut. Gap real und im CL EXPLIZIT benannt (keine CM2/CMPIC-Zertifizierung, keine Berufsjahre im formalen KM nach Rüstungsstandard: Baselines/ECR-ECO/SAP-Materialstammdaten) — konsistent mit Philipps eigener Mail an Frey. Angrenzende Substanz echt: FCAS-Verteidigungsprogramm, GitOps/ArgoCD = revisionssichere Konfigurationsstände + Audit-Trails, 2x stellv. ITSB (BA: 2-Jahres-Auditzyklus), Qcrypt 3-schichtige HW/SW-Produktstruktur, Enercon Hardware-Infrastruktur | 80 EUR/h all-in; 4-5 Tage/Woche | 2026-07-24 |
| application_stripe_payments_pm.pdf | cl/cv_stripe_payments_pm.md (CV aus cf_payments_tpm_en_full) | EN | Stripe Staff PM Payments (remote, US-Comp ~220-290k > 150k-Bar, sponsert). Manual 84/90: exzellenter Domain-Match — Payments-Gründer Kvitt->Sparkasse + betreibt LIVE Stripe-Checkout auf Cloud9 (ist ihr Nutzer) + AI-native. CL-Opener "I build on Stripe, and before that I built a payments company". CAVEATS: Staff-Level FAANG-kompetitiv (Cold-Apply-Long-Shot ohne Referral), Cyprus-Remote-Eligibility offen -> Relocation-Play. Verwandt in DB: Stripe PM Payments (86, niedrigeres Level als Fallback), Stripe ML/GenAI (82), Coinbase Sr PM Help Center (86, Crypto+CX-AI) | US-Band | 2026-07-20 |
| application_randstad_ki_po_freelance.pdf | cl/cv_randstad_ki_po.md (adaptiert aus roland_ki_po) | DE | PO KI, Versicherung Köln, FREELANCE via Randstad Professional (ex GULP), 60% remote, 5 Mo. Pre/Post: base 84 / tailored 92 — bester Score seit Wochen. Must-haves 1:1 (PO in AI/data-driven products = R&S KI-Plattform; AI/ML-Methoden; agil/Jira; sehr gutes Deutsch), Nice-to-have "Versicherung Vertrag/Schaden" = EMIL Claims Center 0->1. Header Limassol/Berlin, 80 EUR/h. HINWEIS: evtl. selber Endkunde wie ROLAND (Köln/Versicherung) — kein Konflikt (ROLAND direkt, dies freelance via Randstad) | 80 EUR/h all-in | 2026-07-19 |
| application_cf_proxy_po_ecom.pdf | cl/cv_cf_proxy_po_ecom.md (CV aus digitale_plattformen) | DE | Proxy PO E-Commerce/Shopware-Migration (Computer Futures/Anna Kuhre, 100% remote, bis 31.12.26, 40% Teilzeit). Pre/Post: base 78 / tailored 90. Killer-Match: literaler "Proxy Product Owner"-Titel (ITSCare) + AOK-ITSCare WAR Shopware-Migration (deren Nice-to-have = sein Projekt) + Cloud9 E-Commerce. Nur PSPO/CSPO nice-to-have fehlt (keine Certs) | 80 EUR/h all-in | 2026-07-17 |
| application_fundraiseup_checkout_po.pdf | cl/cv_fundraiseup_checkout_po.md (CV aus cf_payments_tpm_en_full) | EN | Fundraise Up PO Checkout Modal — CYPRUS-ONLY hiring, remote, CET. Manual 85/90: er wohnt in Limassol (winziger Pool!), Checkout/Payments = Kvitt+Cloud9-Stripe (betreibt selbst live Checkout), Spec-Writing = R&S, Funnel-Metriken = EMIL/Matomo, AI-Fluency expected. FLOOR-AUSNAHME genehmigt 14.07 ("okay apply"): 5.9-6.5k EUR/Mo (~71-78k/J) unter 90k-Floor, Zypern-Kontext. Header Limassol-only. Apply via himalayas-Listing -> fundraiseup.com Careers | Band 5.9-6.5k/Mo | 2026-07-14 |
| application_holepunch_pear_pm.pdf | cl/cv_holepunch_pear_pm.md (CV aus qventus-Basis) | EN | Holepunch Product/Technical PM Pear Platform (Tether/Bitfinex-Ökosystem, Keet). 100% REMOTE WORLDWIDE. Manual 82/88: P2P-Karrierefaden (Kvitt P2P-Payments + Qcrypt encrypted comms = Keet-adjacent!) + R&S-Plattform-Ownership + solo full-stack/AI-native; stable-vs-experimental-Disziplin. Comp ungenannt. EXPIRED 14.07: Recruitee-ATS 404 (User-Screenshot), WWR-Listing war stale; Paket behalten falls Repost | offen | 2026-07-14 |
| CV_Philipp_Hilbert_Mobile_PO.pdf (CV-only) | cv_progressive_mobile_po.md + email_reply_progressive_mobile_po.md | DE | Freelance PO Mobile Apps iOS/Android (Progressive/SThree Outreach, Markus Kopriwa, m.kopriwa@progressive.de, Endkunde anonym; 24.08.26-31.01.27, ~713h). Manual 78/85: CLINET = iOS+Android-App als Zugangskanal für mehrere Zielgruppen (fast wörtlich die JD) + Kvitt mobile payments. Einsatzort/Remote-Split unbekannt -> Rückfrage in Reply. Raten: 80/h remote all-in, 95/h onsite all-in VORSCHLAG (95 = meine Setzung wg. Reisekosten, von Philipp nicht bestätigt) | 80 remote / 95 onsite | 2026-07-14 |
| application_qventus_agentic_ai_pm.pdf | cl/cv_qventus_agentic_pm.md (CV adapted from cmc_ai_pm) | EN | Qventus Senior/Lead PM Agentic AI Platform (healthcare ops AI). 160-200k USD (clears US-Bar), Region "Anywhere in the World" (E-Verify deutet US-Payroll an, geflaggt). Manual 84/92: seltene Doppel-Tiefe healthcare (CLINET CGM/KIS, Bundesdruckerei RKI, AOK 20k) x agentic AI daily (LoB, job_bot) x Plattform-Lifecycle (R&S); Voice/ConvAI ehrlich partial. Apply by JUL 30 via Greenhouse boards.greenhouse.io/qventus/jobs/4079109009. FUND durch neu ergänzte WWR-Product-Kategorie. v2: Header auf "Limassol, Cyprus / Berlin" umgestellt + CL-Satz "based in Limassol (EU), remote ohne Visum, open to relocating" (Wohnsitz-Korrektur 04.07) | their band | 2026-07-04 |
| application_cmc_ai_pm.pdf | cl/cv_cmc_ai_pm.md (CV adapted from cryptocom_trading) | EN | CoinMarketCap (Binance-owned) Technical AI Product Manager. 100% REMOTE WORLDWIDE (no visa/location issue). Manual 84/92 = strongest remote fit in a while: crypto AI products x Python prototyping x prompt/context engineering + guardrails x evaluation loops (Liberation of Bajor evaluator role) x 0-to-1 x built-portfolio (their explicit "point to things you built" preference = phoenix882/cloud-nine/construct8/LoB/job_bot). Apply by Jul 30 via weworkremotely | not stated (crypto full-time) | 2026-07-04 |
| application_revolut_wealth_trading.pdf | cl/cv_revolut_wealth_trading.md (CV adapted from cryptocom_trading) | EN | Revolut PO Wealth & Trading. US-based BUT relocation zu London/Barcelona/Madrid/Dubai/Kraków dann remote-hybrid (user relocation-willing). 138-193k USD. Manual 82/88: exakte Lane (Kvitt/Sparkasse payments + 8y Trader Binance/Kraken/perps + crypto), entrepreneurial, technisch; Leadership via R&S-Team + EMIL-Restrukturierung. Apply via LinkedIn (jobs/view/...4429349651) | their band >floor | 2026-07-04 |
| application_skillbyte_cloud_po.pdf | cl/cv_skillbyte_cloud_po.md | DE | Technical PO Cloud-Plattform (skillbyte GmbH, Köln, Endkunde Vertriebsprozesse). 100% REMOTE, 75-80 EUR/h netto all-in, bis 31.12.26. Manual 82/90: R&S-Lane exakt (Kubernetes/OpenShift, ArgoCD-GitOps, Microservices, REST, CI/CD, Spring Boot in Kotlin, Vue-Umfeld). CV adaptiert aus digitale_plattformen | 80 EUR/h all-in | 2026-07-04 |
| application_cf_payments_tpm.pdf | cl/cv_cf_payments_tpm.md | DE | Technical PM Payments/E-Commerce (Computer Futures/SThree, Hamburg 90% remote, 6 Mo). Manual 80/88: Kvitt PSP/Sparkasse-Payments-Gründer + cloud-nine.store E-Commerce/Stripe/SaaS + GDPR (CLINET/Bundesdruckerei/2x ITSO); KYC leichter. Business/Eng-Schnittstelle = R&S. + EN-Vollversion CV_Philipp_Hilbert_Payments_ECommerce_TPM_EN.pdf (cv_cf_payments_tpm_en_full.md, komplette Historie, 5 S.) | 80 EUR/h all-in | 2026-07-04 |
| application_fractional_cpo.pdf | cl/cv_fractional_cpo.md | EN | Fractional CPO Complex Tech Transformations (100% remote, Berlin, senior/C-level). Manual 80/85: C-level/Gründer (Kvitt CFO, Smart Soil CDO/CFO, Head of Product); ERP/E-Com/BI alle berührt; managed refactoring via Liberation of Bajor. RATE-KONFLIKT: 80/h unterbietet C-level massiv -> CL lässt Satz offen ("rate against scope"), USER muss Tagessatz setzen (Vorschlag: 900-1200 EUR/Tag) | offen, per Scope | 2026-07-04 |
| application_deichmann_agentic_ai.pdf | cl/cv_deichmann_agentic_ai.md (CV adapted from 1und1_darkfactory) | DE | Deichmann SE PO Agentic AI (Essen, Homeoffice, Anschreiben nicht erforderlich). Manual 82/90: agentic-AI use-case PO = exakt sein Portfolio (Liberation of Bajor, job_bot); Bewertung nach Wertbeitrag/Machbarkeit/Risiko = sein 3-Kriterien-Framework; EU AI Act + SafeAI + 2x ITSO; hands-on PoCs; Capability-Library = ADR-Slices. Comp Retail unbefristet, keine Angabe | 125k falls gefragt | 2026-07-03 |
| application_prosoz_po.pdf | cl/cv_prosoz_po.md | DE | PROSOZ Herten PO (Software für öffentliche Verwaltung/Soziales). Manual 80/88: REMOTE bundesweit incl BERLIN (beste Location der Woche); SGB-Kenntnis via Bundesagentur (Arbeitsförderung) + AOK-Verwaltungsportal 20k MA; generic-PO-Reqs ohne Spezialisten-Gate; Diplom-Wing deckt "Studium Wiwi/Winf". WARN: Comp Mittelstand ~70-90k, evtl unter Floor | keine Angabe; Floor 125k intern | 2026-07-03 |
| application_1und1_dark_factory.pdf | cl/cv_1und1_darkfactory.md | DE | 1&1 PO Dark Factory (AI Agents automatisieren SDLC), Festanstellung, Karlsruhe/FRANKFURT/Krefeld/Montabaur + Homeoffice. Manual 82/93, BESTER Direktarbeitgeber-AI-Fit der Session: er betreibt privat seine eigene Dark Factory (Liberation of Bajor Multi-Agent-Coding-Framework + job_bot als CL-Opener; "zeige Ihnen mein Agent-Framework live im Gespräch"); alle 10 Anforderungen erfüllt inkl. GenAI/Developer Tooling; SafeAI/2x ITSO für AI-Code-Compliance; EMIL-Restrukturierung für Change. Inserat 3h alt, "einer der ersten Bewerber". WARN: Stepstone-SCHÄTZUNG 61-92k (keine Arbeitgeberangabe) -> per Doktrin 125k im Formular angeben | 125k falls gefragt | 2026-07-03 |
| application_percision_convai_po.pdf | cl/cv_percision_convai.md | DE | PO Conversational AI Customer Service (freelancermap Projekt 9491, percision services GmbH / Sebastian Leja, Endkunde anonym). 100% remote (gelegentlich München), Start August, 5 Mo + Option. Manual 80/88: PO-Kern + Customer Service (EMIL Claims, CLINET Chat, Cloud9 Telegram-Bot) + agentische Praxis (job_bot, Liberation of Bajor, 3-Kriterien-Use-Case-Framework). EHRLICH: AWS Bedrock/AgentCore/Cognigy explizit als nicht vorhanden benannt (nice-to-have); kein Voicebot-Claim | 80 EUR/h all-in; ab sofort/August | 2026-07-02 |
| application_roland_ki_po.pdf | cl/cv_roland_ki_po.md | DE | ROLAND Rechtsschutz (Köln) PO KI, Festanstellung Voll-/Teilzeit, mobiles Arbeiten (hybrid). Manual 82/88: seltene Kombi KI-PO (R&S ML-Pipelines, SafeAI/ExplainableAI, AI Governance, 2x Deputy ITSO) x Versicherungspraxis (EMIL Claims Center 0->1 = deren "idealerweise Vertrags-/Schadenumfeld"); Matomo/Churn-Outcome-Messung; "fast zehn Jahre". WARN: Vergütung nach TARIFVERTRAG + Erfolgsbeteiligung -> wahrscheinlich unter 125k-Floor (wie Atruvia); Köln hybrid nicht full-remote. Apply via Stepstone "Jetzt bewerben" Upload | Floor 125k intern; keine Angabe im Inserat | 2026-07-02 |
| application_cryptocom_trading_pm.pdf | cl/cv_cryptocom_trading.md | EN | Crypto.com Senior PM Trading (US-based, USD 180-220k; user willing to relocate 2026-06-29). Crypto-forward + AI-native package (OPPOSITE of conservative German CVs: Web3/DeFi front and center). Hooks: 8y hands-on trader Binance/Kraken/perp DEXes (Hyperliquid/Jupiter/1inch), AI-tools-required = Claude Code 8-10h/day (their hard requirement, near-bespoke match), poker + lifelong gaming = gamification, Kvitt = financial product at scale. "Direct crypto build experience" = builder projects, framed honestly as power-user+builder not at-scale exchange PM. v2 (29.06): added full-delivery-chain solo-builder pitch (PRD->UX->FE/BE->QA/Playwright->arch->infra->DevOps) + live portfolio (phoenix882.com trading backtester, cloud-nine.store, construct8.com, Liberation of Bajor, job_bot) + full AI toolbelt. Manual 85/90. SUBMITTED 2026-06-29 via Lever (jobs.lever.co/crypto/4ba44d94…); form Qs answered (crypto/blockchain experience, why-interested). | apply via Lever; comp their band 180-220k USD (>floor) | 2026-06-29 |
| application_fm_digitale_plattformen_6444.pdf | cl/cv_fm_digitale_plattformen.md | DE | freelancermap Senior PO Digitale Plattformen (6444), Auftraggeber anonym (öffentl. Sektor, München-Client, 100% remote, 6 Mo ab 13.07). Manual 82/90: kein Nischen-Tech-Gate, all-core match (Plattform-Weiterentwicklung, Discovery, MVP unter Zeitdruck, Backlog/Stakeholder-Moderation), Multi-Tenant=Cloud9. CV adaptiert aus tatara_safepo; + Word-Version CV_Philipp_Hilbert_Senior_Product_Owner.docx (Recruiter will Profil "vorzugsweise in Word"). v2 (29.06): Cloud9 -> construct8 (zweiseitige Matching-Plattform Bauunternehmen<->Bauarbeiter, www.construct8.com); Scheidt&Bachmann/SAFe-Station entfernt (für diese Rolle nicht Pflicht; bleibt in KB + Tatara); "13 Jahre" -> "fast zehn Jahre" PO/PM. Recruiter: mindheads GmbH / Gerd Blumenschein, Bamberg, Project ID 3016536, apply via mindheads.de "Bewerben" oder E-Mail; 2 POs gesucht. DEADLINE beim Kunden 30.06.2026 (URGENT). Badge "Certified Scrum Product Owner" = NICHT Pflicht (kein Must-have), Philipp hat keine Certs -> nicht behaupten. WARN: anon end-client = harvesting-Risiko, cheap halten | 80 EUR/h all-in; avail ASAP | 2026-06-29 |
| application_tatara_safepo.pdf | cl/cv_tatara_safepo.md | DE | Freiberuflicher Technical PO, Sozialversicherung + Data Engineering; Emmanuel Tatara (Recruiter, Kunde anonym, Frankfurt hybrid). ITSCare AOK (März 2019–Mai 2020) = Sozialversicherung-Must-have; BA = öffentliche Verwaltung + BI (MicroStrategy); R&S = Data-platform-Beweis. SAFe (Must-have 6) jetzt VOLL ERFÜLLT: neue Station Scheidt & Bachmann (Fuel & Convenience Retail, 2020-2021, 12 Mo, PO Integration Team, vollständig SAFe, Matrixorg) ergänzt 2026-06-16 — der einzige echte SAFe-Kontext im Profil, auch in PROFILE.md. Passed adversarial 4-lens review: fixed EMIL→EMIT typo, 69 Umlaut-Transliterationen, Teambzw./Policymakers slips, recycled deployment metric. Alle 7 Must-haves abgedeckt | 80 EUR/h all-in; avail ASAP; Frankfurt hybrid ok | 2026-06-16 |
| application_50hertz_scada.pdf | cl/cv_50hertz_scada.md + email_50hertz_studienarbeit.md | DE | MCCS Master Data System = R&S profile 1:1; Studienarbeit + HyperMVP Grenzpreis story; addressed to Katharina Haß, Job-ID 10847. SUBMITTED | 125k EUR p.a. | 2026-06-11 |
| application_otark_energy_pm.pdf | cl/cv_otark_energy.md | DE | PPA/energy-trading PM (real employer Otark GmbH via Grizzly Peak posting); double market-modelling + 8-10h AI toolbelt + Max-plan line; honest PPA-ops gap sentence | none | 2026-06-11 |
| application_iso_healthcare_proxy_po.pdf | cl/cv_iso_healthcare_po.md | DE | Digital-anamnesis exact match (CLINET, CGM implemented, anonymized-data offers); literal Proxy-PO title; ISO Recruiting, Projekt 3009610, Leona Günther | 80 EUR/h all-in; avail 01.08.26 | 2026-06-11 |
| application_girocard_inapp_po.pdf | cl/cv_girocard_po.md (+cl_girocard_po_v2.md) | DE | Kvitt/Sparkasse mobile-payments founder angle; 3-month agency variant. DO NOT also submit the 6m variant to same end client | open ("klären wir direkt") | 2026-06-11 |
| application_girocard_inapp_po_6m.pdf | cl/cv_girocard_6m.md | DE | Same end-mandate, 2nd agency, fully distinct wording on purpose; PREFERRED channel (6 months) | 80 EUR/h all-in; avail 15.06.26 | 2026-06-11 |
| application_riverty_conversational_ai.pdf | cl/cv_riverty_convai.md | EN | PM Conversational AI, BU Collection (Bertelsmann); debt-domain CFO empathy + agentic-LLM failure-mode credibility; recruiter Sarah König; comp band risk noted | none (floor 125k internally) | 2026-06-11 |
| application_hcl_tech_dwh_pm.pdf | cl/cv_hcl_dwh.md + email_reply_hcl.md | EN | IT PM DWH migration, banking client Frankfurt via HCL; CFO/booking-data reconciliation angle; True North 2025-present gap line added; Web3 section cut | 125k countered vs 110k float | 2026-06-10 |
| application_cimpco_cloud_platform.pdf | cl/cv_cloud_platform.md + anschreiben_cimpco.md | EN cv+cl, DE form | PO Cloud Platform K8s/GitOps (CIMPCO, Kristin Zwicker); R&S GitOps/SLO story | on request | 2026-06-10 |
| application_teksystems_devops_cicd.pdf | cl/cv_devops_cicd.md (+DE Anschreiben in chat) | EN/DE | Senior Domain PO DevOps/CI-CD (Allegis/TEKsystems, Benjamin Knodt); Frankfurt 60% remote | on request | 2026-06-10 |
| application_iam_identity_provider.pdf | cl/cv_iam_identity.md | EN | PO IAM/Identity Provider (freelance.de 1271216); Qcrypt 3-layer + Bundesdruckerei identity angle | on request | 2026-06-10 |
| application_allunity.pdf | cl_allunity.md (+general CV) | EN | EURAU euro-stablecoin PM, Frankfurt on-site; relocation-willing line; DeFi depth front and center | none | 2026-06-09 |
| application_congrify.pdf | cl_congrify.md (+general CV) | EN | PO Payments & Data; Kvitt + Dagster/dbt data angle | none | 2026-06-09 |
| (sent via email) | cl_computerfutures_letter.md, cl_computerfutures_cv.md | EN | Freelance PM Retail Banking via Veronika/Computer Futures; honest "payments not retail-breadth" caveat | rate "welcome a conversation" | 2026-06-04 |
| (not packaged) | cl_visable.md + visable_cv.md | EN | Senior PM B2B Marketplace Connections; connection/integration thesis | 4 weeks notice | 2026-06-04 |
| (not packaged) | cl_mitek.md | EN | PO ML Identity & Fraud; Qcrypt + Bundesdruckerei identity angle | 4 weeks notice | 2026-06-04 |
| application_1komma5.pdf | (PDF only) | EN | 1KOMMA5° PM Energy: Smart Soil sustainability founder + energy interest; open to Hamburg | none, 4 wks | 2026-06-08 |
| application_adsquare.pdf | (PDF only) | EN | PO Data & Integrations: integrations career core (CLINET/EMIL/R&S) | none, 4 wks | 2026-06-08 |
| application_jetbrains.pdf | (PDF only) | EN | PM Dev Tools: builder-and-user, Kotlin/JVM at FCAS, own agent frameworks | none, 4 wks | 2026-06-08 |
| application_legartis.pdf | (PDF only) | EN | PM Legal AI: ExplainableAI/SafeAI trust bar; document-heavy regulated delivery | none, 4 wks | 2026-06-08 |
| application_mamahealth.pdf | (PDF only) | EN | Senior PM patient community: CLINET + BA community + Bundesdruckerei | none, 4 wks | 2026-06-08 |
| application_solactive.pdf | (PDF only) | EN | PM Financial Market Data: 8y market microstructure + provenance pipelines | none, 4 wks, Frankfurt travel OK | 2026-06-08 |
| application_tibber.pdf | (PDF only) | EN | PM Energy & Markets: market-microstructure instinct, dynamic pricing | none, 4 wks | 2026-06-08 |
| application_wemolo.pdf | (PDF only) | EN | PM IoT: Qcrypt shipped-hardware angle ("Most PMs never shipped a physical device"); Munich relocation offered | none, 4 wks | 2026-06-08 |
| application_zabel.pdf | (PDF only) | EN | PO DataOps (regulated finance): BA ETL + ITSO compliance; sent to c.clodius@zabelglobal.com, led to interview invite | none | 2026-06-02 |
| application_retail_banking_freelance.pdf | cl_computerfutures_*.md | EN | via Veronika Igic; honest payments-vs-retail caveat | rate deferred | 2026-06-04 |
| application_chili_piper.pdf | (PDF only) | EN | Senior PM B2B SaaS; score 88; APPLIED with 6 screener answers (see STORIES_AND_VOICE.md); Lovable tool-mention only | 125000 USD | 2026-06-02 |
| application_hannoverde_internet_gm.pdf | (PDF only) | EN | Platform PO civic CMS, to Pia Fuchs (note: EN letter to German municipal employer); Lovable tool-mention | none | 2026-06-02 |
| application_olly_olly.pdf | (PDF only) | EN | PM execution-first; AI toolbelt; Lovable tool-mention | none | 2026-06-02 |
| application_ratbacher_gmbh.pdf | (PDF only) | EN | AI-native PO via Ratbacher (t.ade@ratbacher.com); Lovable tool-mention | none | 2026-06-02 |
| application_robots_and_pencils.pdf | (PDF only) | EN | Embedded PM AI Pod; "no handoffs" R&S story; Lovable tool-mention | none | 2026-06-02 |
| application_rulemapping_group.pdf | (PDF only) | EN | PO rule-driven regulated platforms; governance-to-backlog angle | none, 4 wks | 2026-06-02 |
| application_instaffo_gmbh.pdf | (PDF only) | EN | Growth PM (asellerate via Instaffo); CV says "AOK (via projuncta)" brand mention | none, 4 wks | 2026-06-02 |
| application_package*.pdf (ETERNO, GTO Wizard x2, procilon x2, xpate) | (PDF only) | EN | 2026-05 era full packages; GTO = semi-pro poker angle; procilon = honest eIDAS-gap framing; package_proc.pdf has localhost print artifacts (UNSENDABLE); Lovable tool-mentions | none | 2026-05 |
| cv/cover_letter packmatic.pdf | (PDF only) | EN | PO Packmatic; WARNING: CV claims "Master of Science" (wrong, it is a Diplom) and CL is dated "May 12, 2025"; fix both before any reuse | none, 4 wks | 2026-06-08 |
| **DIRTY 2-3 June batch** (16 PDFs, see audit below) | (PDF only) | EN | buzz_solutions, charles, chefslist, cresta, delivery_hero, envisio, epilot, flix, general, infront, ixopay, merantix, nooxit, revizto, scalable_capital, shyftplan | none, 4 wks | 2026-06-02/03 |

## ⚠️ Dirty-CV audit (completed 2026-06-11, all 55 Downloads PDFs scanned)

**16 packages from 2-3 June 2026 contain the old dirty CV** (cover letter clean, but the attached
"CURRICULUM VITAE PRODUCT MANAGER" carries `philipp@projuncta.com`, `true-north-cy.lovable.app`,
and `lovable.dev/projects/...` print URLs):
buzz_solutions, charles, chefslist, cresta, delivery_hero, envisio, epilot, flix, **general**,
infront, ixopay, merantix, nooxit, revizto, scalable_capital, shyftplan.
Several were sent before the 2026-06-08 clean rebuild and cannot be unsent. NEVER reuse these
PDFs; `application_general.pdf` is the highest reuse risk (generic package). If any of these
companies re-engage, render a fresh clean package first.

**Minor flags (tool-mention only, acceptable):** chili_piper, hannoverde, olly_olly, otark,
ratbacher, robots_and_pencils, application_package* files, cv packmatic ("Lovable" listed as a
prototyping tool; no URLs).

**Quality bugs:** application_package_proc.pdf has 127.0.0.1:5001 print headers and an ALL-CAPS
paragraph (unsendable); cover_letter packmatic.pdf misdated "May 12, 2025"; cv packmatic.pdf
claims "Master of Science" instead of Diplom-Wirtschaftsingenieur.

**Clean (26):** everything rendered 8-11 June 2026 with the rebuilt CV.

## Market signals

- **2026-06-12 (Philipp):** "all projects rejecting interview. they arent really hiring" — the freelance-portal
  mandates (freelancermap/freelance.de wave of early June) are coming back as rejections without interviews;
  his read is that many of these agency postings are profile-harvesting, not live hiring. Implication: keep
  freelance applications cheap (no deep custom work beyond the template library), prioritise direct-employer
  permanent roles (50Hertz-class) and recruiter conversations that show a real mandate (named end client,
  concrete start date, interview within days).

## Open items (need Philipp or external access)

- ~~Recommendation letters~~ DONE 2026-06-12: both captured verbatim in STORIES_AND_VOICE.md (EMIL: Chris
  Maslowski, Geschäftsführer; ITSCare: Hartmut Brand, Geschäftsführer, dated 31.01.2022). Originals in
  `~/Library/CloudStorage/Dropbox/00 projuncta/01 Bewerbungen/archive/` and attached to his freelancermap
  profile. Still unmined in that archive: Oct 2025 CV sources (`philipp_hilbert_cv_deutsch_okt2025.md` +
  english variant) and older profile exports.
- Interview outcomes untracked: ZABEL/Clodius call result, Project Q/Digital Eleven follow-up, Computer
  Futures/Veronika status.

## Channel & etiquette notes

- One agency per end-mandate; if materials for two variants are demanded anyway, write fully distinct texts (girocard precedent).
- No paywalled apply links (dailyremote/linkedin/xing premium walls do not count as canonical).
- CAPTCHA-walled applies: attach to real Brave via CDP (port 9222), not bundled Chromium.
- "Submitted" requires a success indicator or confirmation email, not just a URL change.

### Submitted / awaiting review (45)

| Date | Company | Role | Status | Base | Tailored |
|---|---|---|---|---|---|
| 2026-06-11 | 50Hertz Transmission GmbH | Product Owner – SCADA Engineering Platform (w/m/d) | apply_submitted | 80 | 90 |
| 2026-05-29 | Robots and Pencils | Product Manager | apply_submitted | 82 | 88 |
| 2026-05-29 | Rulemapping Group | Product Owner (d/w/m) - Plattform & Produkte | apply_submitted | 82 | 88 |
| 2026-05-29 | ZABEL | Product Owner | apply_submitted | 82 | 93 |
| 2026-05-28 | Chili Piper | Product Manager | apply_submitted | 88 | 92 |
| 2026-05-28 | Olly Olly | Product Manager | apply_submitted | 88 | 92 |
| 2026-05-26 | Ratbacher GmbH | Product Owner AI (m/w/d) - KI Produkt Manager | apply_submitted | 88 | 92 |
| 2026-05-22 | A.Team | Senior Independent Product Manager / Product Designer | apply_submitted | 88 |  |
| 2026-05-22 | freelancermap (Auftraggeber an | Senior Product Owner für europäische Live-Streaming-Pla | apply_submitted | 78 | 88 |
| 2026-05-22 | freelancermap (Auftraggeber an | Senior Product Owner (Streaming / AI / B2C Platform) | apply_submitted | 80 | 92 |
| 2026-05-22 | OP Labs | Sr. Product Manager, Fintechs and Exchanges | apply_submitted | 92 |  |
| 2026-05-22 | Symbiotic | Product Manager, Ecosystem | apply_submitted | 92 |  |
| 2026-05-21 | CRB Cunninghams | Product Owner | apply_needs_review | 72 |  |
| 2026-05-20 | Primer.io | Product Manager | apply_submitted | 88 | 91 |
| 2026-05-19 | Accurate Background | Product Manager | apply_submitted | 78 | 88 |
| 2026-05-19 | Betsson Group | Product Owner | apply_submitted | 72 |  |
| 2026-05-19 | Packmatic | Product Owner (m/f/d) – B2B SaaS / Berlin (hybrid) | apply_submitted | 78 | 91 |
| 2026-05-19 | Parto Group GmbH | Product Manager (m/w/d) | apply_submitted | 78 |  |
| 2026-05-19 | topi | Senior Product Manager (d/f/m) | apply_submitted | 78 | 93 |
| 2026-05-15 | Arcanys | Product Manager | apply_needs_review | 72 | 92 |
| 2026-05-15 | Betsson Group | Product Owner | apply_submitted | 72 |  |
| 2026-05-14 | Accurate Background | Product Owner | apply_submitted | 72 |  |
| 2026-05-14 | Traversal | Product Manager | apply_submitted | 72 | 72 |
| 2026-05-13 | xpate | Product Manager | apply_submitted | 88 | 91 |
| 2026-05-12 | Backblaze External Website | Product Manager | apply_submitted | 72 | 82 |
| 2026-05-12 | Daimler Buses GmbH | Product Owner (w/m/d) - Digitale Services fürs Daimler  | apply_submitted | 78 | 78 |
| 2026-05-12 | ETERNO | Product Manager:in - ETERNO Cloud | apply_submitted | 82 | 85 |
| 2026-05-12 | GALVANY | (Senior) Product Manager (m/w/d) | apply_submitted | 72 | 72 |
| 2026-05-12 | GetYourGuide | Senior Product Manager, B2B | apply_submitted | 72 | 72 |
| 2026-05-12 | HERO Software | Senior Product Manager (w/m/d) | apply_submitted | 88 | 88 |
| 2026-05-12 | Insurgo GmbH | Product Manager (m/w/d) / Remote | apply_needs_review | 82 | 92 |
| 2026-05-12 | nox Germany GmbH | Product Owner Alternative Delivery Solution (m/w/d) | apply_submitted | 72 | 85 |
| 2026-05-12 | opus | Founding Product Manager | apply_submitted |  |  |
| 2026-05-12 | procilon GROUP | Product Owner (m/w/d) | apply_submitted | 82 | 92 |
| 2026-05-12 | Schwarz Digits | Product Owner - Data & AI Plattform - STACKIT (m/w/d) | apply_submitted | 78 | 78 |
| 2026-05-12 | STACKIT | Product Owner - Data & AI Plattform - STACKIT (m/w/d) | apply_needs_review | 72 | 82 |
| 2026-05-11 | Agility PR Solutions | Product Owner | apply_submitted | 72 |  |
| 2026-05-11 | Nylas | Product Manager | apply_submitted | 78 |  |
| 2026-05-11 | Poland and Eastern Europe | Product Manager | apply_submitted | 82 | 92 |
| 2026-05-11 | Sweed | Product Owner | apply_submitted | 82 | 88 |
| 2026-05-11 | The Descartes | Product Manager | apply_submitted | 78 | 82 |
| 2026-05-10 | EnopAI | Senior Product Owner (all genders) | apply_submitted | 72 |  |
| 2026-05-10 | Haufe Group SE | Product Owner (d/m/w) - Bescheinigungswesen und Abwesen | apply_submitted | 74 |  |
| 2026-05-10 | N26 GmbH | Product Manager - Lending | apply_submitted | 72 |  |
| 2026-05-10 | Rulemapping Group GmbH | Product Owner - Plattform & Produkte (m/w/d) | apply_submitted | 72 |  |

### Rejected (15)

| Date | Company | Role | Status | Base | Tailored |
|---|---|---|---|---|---|
| 2026-05-29 | Hannover.de Internet GmbH | Product Manager:in (m/w/d) | rejected | 72 | 88 |
| 2026-05-29 | Instaffo GmbH | Product Manager Growth (m/w/d) – SaaS, E-Commerce, Stut | rejected | 73 | 82 |
| 2026-05-25 | EMIL Group | Senior Product Manager (w/m/d) | rejected | 92 | 97 |
| 2026-05-22 | autarc (YC S24) | Product Manager (Services) | rejected | 72 | 88 |
| 2026-05-22 | Elastic | Product Manager | rejected | 72 | 88 |
| 2026-05-22 | Giesecke+Devrient | Product Owner - Digital Systems (m/f/d) | rejected | 78 | 91 |
| 2026-05-22 | Instaffo GmbH | Product Owner (m/w/d) | rejected | 72 | 82 |
| 2026-05-22 | ista SE | Process Manager / Product Owner Heizkostenabrechnung (m | rejected | 72 | 82 |
| 2026-05-22 | Liebherr-International Deutsch | Product Manager MyLiebherr Core (m/w/d) | rejected | 72 | 88 |
| 2026-05-22 | Neumann Kaffee Gruppe (NKG) | (Senior) Product Owner Reporting (f/m/d) | rejected | 72 | 88 |
| 2026-05-21 | BLS Beteiligungs GmbH | Product Owner (gn) | rejected | 82 | 88 |
| 2026-05-21 | freelancermap (Auftraggeber an | Team gesucht (3× Senior Engineer, 1× BA/PO, 1× Scrum Ma | rejected | 72 | 88 |
| 2026-05-19 | 50Hertz Transmission GmbH | Product Owner (w/m/d) – IT Collaboration & Digital Work | rejected | 72 | 88 |
| 2026-05-14 | ApprovalMax | Product Manager | rejected | 82 | 92 |
| 2026-05-12 | GTO Wizard | Product Manager | rejected | 78 | 97 |

### Apply failed (retry candidates) (20)

| Date | Company | Role | Status | Base | Tailored |
|---|---|---|---|---|---|
| 2026-05-22 | Front | Product Manager | apply_failed | 72 | 96 |
| 2026-05-22 | Superchat | Product Manager / Integrations (m/f/d) | apply_failed | 72 | 93 |
| 2026-05-21 | Cerpro GmbH | Product Owner (m/w/d) | apply_failed | 72 | 82 |
| 2026-05-21 | Cortea | AI Product Manager (m/f/x) | apply_failed | 78 | 88 |
| 2026-05-21 | Siemens Energy | Product Owner (f/m/d) Issue Management for ProjectHub/i | apply_failed | 72 | 88 |
| 2026-05-21 | Superchat | Product Manager / Core (m/f/d) | apply_failed | 72 | 82 |
| 2026-05-21 | Trilitech | Product Manager | apply_failed | 72 | 93 |
| 2026-05-21 | Vesta Software Group | Product Owner | apply_failed | 72 |  |
| 2026-05-19 | Trading 212 | Senior / Product Owner | apply_failed | 78 | 91 |
| 2026-05-15 | Bjak | Product Manager | apply_failed | 72 | 82 |
| 2026-05-15 | Dental21.de | Product Owner | apply_failed | 85 | 91 |
| 2026-05-14 | Zylun Philippines, Inc. | Product Owner | apply_failed | 78 | 88 |
| 2026-05-13 | Accesa | Product Owner | apply_failed | 78 | 88 |
| 2026-05-12 | endios GmbH | (Senior) Product Owner (m/w/d) | apply_failed | 72 | 72 |
| 2026-05-12 | TeamViewer | (Senior) Product Owner - Frontline (all genders) | apply_failed | 78 | 82 |
| 2026-05-12 | TeamViewer | (Senior) Product Owner - Frontline (all genders) | apply_failed | 78 | 82 |
| 2026-05-11 | Bullhorn | Product Owner | apply_failed | 72 |  |
| 2026-05-11 | Interop Labs | DevOps Lead | apply_failed |  |  |
| 2026-05-11 | Kobie Marketing | Product Owner | apply_failed | 72 |  |
| 2026-05-11 | Social Discovery Group | Product Owner | apply_failed | 72 | 88 |

### Scored with tailored assessment, not yet submitted (8)

| Date | Company | Role | Status | Base | Tailored |
|---|---|---|---|---|---|
| 2026-06-11 | (Banking-Kunde anonym) | Product Owner Girocard InApp, 6 Monate remote (Agentur- | scored | 80 | 89 |
| 2026-06-11 | 50Hertz Transmission GmbH | Product Owner – SCADA Engineering Platform (w/m/d) | scored | 80 | 90 |
| 2026-06-11 | freelancermap (Auftraggeber an | Product Owner (m/w/d) – Mobiles Bezahlen - 6 Monate - 1 | scored | 78 | 88 |
| 2026-06-11 | freelancermap (Auftraggeber an | Proxy Product Owner (m/w/d) Plattformprojekt im Gesundh | scored | 82 | 93 |
| 2026-06-11 | Grizzly Peak Software | Senior Product Manager - PPA & Energy Trading Platform  | scored | 60 | 90 |
| 2026-06-11 | Riverty Group GmbH | Product Manager Conversational AI (m/f/d) | scored | 75 | 85 |
| 2026-05-16 | Nexford University | Product Manager | scored | 62 | 88 |
| 2026-05-12 | Tanso | Technical Product Manager (f/m/x) | scored | 72 | 72 |
## Regenerating the DB tables

```bash
.venv/bin/python - <<'EOF'
# see git history of this file; query seen_jobs grouped by status buckets:
# apply_submitted/apply_needs_review; rejected; apply_failed; scored w/ tailored
EOF
```
