# Stories & Voice

Last updated: 2026-06-11 (phase 2: transcript mining complete). Quotes verbatim from Philipp unless marked.

## Hard document rules (zero tolerance)

1. **No Lovable URLs ever** (`*.lovable.app`, `*.lovable.dev`) in any document, footer, link. Scan every source for `lovable` before rendering. The tool name "Lovable" in an AI-skills list is allowed. Canonical site citation: **www.true-north.berlin** (always with www). Origin: "there must never be lovable links at the bottom or anywhere else" / "all documents must have www.true-north.berlin with www".
2. **Contact line everywhere:** `hilbert@true-north.berlin · +357 94101644 · www.true-north.berlin`. Never projuncta.com (see APPLICATIONS.md dirty-CV audit).
3. **No em-dashes** in any generated artefact (AI tell). Origin: "you have to remove all mdashes from all application package and save to memory to nevr use them" (the sweep hit 333 output files). En-dash in year ranges is fine.
4. **Dates:** English docs "11 June 2026" ("youre 1. Mai 2026 is badly done, why would you enumerate a month looking like first of may?"). German docs: "Berlin, 11. Juni 2026".
5. German proper nouns with umlauts; "Rohde & Schwarz" with ampersand; "Diplom-Wirtschaftsingenieur" with hyphen. NEVER "Master of Science" (a packmatic CV mistakenly claimed this).
6. AI tools in documents: say just "GPT", never a version number ("remove gpt 4o everywhere... version errelevant, just GPT").
7. **Design reference:** `opus CV.pdf` in Dropbox `000 True North/Bewerbungen` is "the design king reference"; "use this for all tailored CVs and CLs". Application documents archive lives in that Dropbox folder.
8. Verify rendered PDFs by extracting text (whitespace-normalized) and checking key strings.

## Voice & style preferences

- "rewerite the hole parapgraph to make it more in my style and with human language": plain, human, direct; away from polished AI cadence. No "excited/passionate/delve", no "X is, at its core, a Y problem" openers.
- **Founder-first framing:** "highlight my foudner an startup experience in the CV and CL clearly" and "why dont you highlight more founder and startup experience in my cover ltter?". Kvitt/Qcrypt/Smart Soil (and now Cloud9) belong front and center, CLINET counts as startup experience too ("clinet was also a startup i worked for").
- Honesty over hype (his PRD principle verbatim: "Honesty over hype. Fit and gaps are shown plainly. No inflated 'match' language."). He volunteered "i never used it :(" rather than bluffing.
- Vary phrasing across documents; never recycle sentences verbatim between CV/CL/email.
- Workflow expectations: score + package + Downloads = ONE operation ("why do i have to ask so many times for this"); tailored scores never blank ("SCOREEEEEE!!!!!!!"); single merged PDF ("one application packages with CL and CL together in one pdf"); availability is always ASAP; mark expired listings proactively ("always mark expired ion the future yourself!").
- Pushback calibration: don't invent keyword gaps. Hygraph verbatim: "PIM i understand the rest is such bullshit requirements and callign it a gap is LAUGHABLE."

## Screener answer bank

### Chili Piper (PM, R&D, remote; applied at score 88; comp stated 125000 USD)

- **CRM/MAP question (his words, as submitted):** "Hubspot, Setup and Installation are usually only doable with coaching/consulting, company needs to adapt more to the CRM than the CRM adapts to them"
- **Difficult-tradeoff question, RAW INPUT (INTERNAL ONLY, never reuse verbatim):** "tradeoff: risk losing custeomer vs risk of losing hold of acceptence by my own managment. at emil i had to try and keep a customers happy enough not to sue us even though al we did is talk to him and pretend we where progressing with his problems while we fully served entirely diffrentet customers first. we needed to make that decsion since we were overworked and undercapacitated. the cat and mouse game wasted some time but we achieve keeping him until we finally after 8 months coudl find space for his requests in the engineering team." The submitted answer was a diplomatically polished rewrite (overloaded roadmap, structured communication, customer retained until capacity freed after 8 months).
- **AI-investment question, his 3 criteria:** "how critical is correctness, how repetitive and heavy on quantity is it and how important is personal relationship building with the customers". Near-final draft framework: (1) correctness criticality defines human-fallback share, (2) repetition/volume is where AI earns its keep (routing, classification, summarisation, first drafts), (3) relationship dependence: AI replacing a valued human touchpoint erodes trust, AI removing unvalued friction is a pure win. R&S example: dataset quality filtering (high volume, high error cost, no relationship dimension) with audit trails baked in from day one. His closing line: "when standard workflows arent reliably rigid enough even the frontier models todax struggle with staying in bounds or even progressing at all. web interface and browser automation are still weak."
- **R&S auditability story (raw):** "at rohde where we had like custoemr interaction and lots of error proneness, we needed to mitigate this with an entire time to make it auditable with full provenance. actually it was even two teams. this highlight the overhead of keeping AI aligned and surbveyable and transparent end to end" (one, actually two, teams dedicated to AI auditability = the overhead of keeping AI aligned and surveyable).
- **Used Chili Piper before?** "i never used it :(" (answered honestly).

### ApprovalMax (UK, comp offered 107k GBP after "is 125000 GBP viable?")

- **Q: AI use cases in SaaS + customer trust.** Approved answer anchored on R&S: sceptical defence users structurally like accountants; pick use cases by biggest workflow risk, not most exciting capability; n8n/Manus/Lovable/Claude Code as explicitly non-deterministic 10x discovery tools, engineering then ships deterministic production MVPs; Matomo instrumentation reviewed every morning; trust pattern = every AI action exposes input, reasoning, and one-click override; advisory→default-on only when override rate stabilises low. "The trust narrative is built into the feature surface, not pasted on as marketing copy."
- **Q: product analytics decision.** Approved answer: EMIL Claims Center, built 0→1 "with no spec and no internal precedent"; discovery with one pilot customer's claim specialists; Matomo events/funnels; "Churn rate at each step of the claim-handling flow was the primary metric"; deprioritised unused flows, "shipped a focused module rather than a wide one". Tools: Matomo, Figma, Jira/Confluence.
- Raw inputs behind it: "at emil i didnt make an approval decision. i made a claim module 0 to 1 with zero guidance from management..." and "matomo integrated to track user actions on the web UI, churn rate was the most important metric we tracked."

### Other screeners encountered

- OP Labs (Optimism, Sr PM Fintechs & Exchanges): "why are you interested in optimism?" + crypto-involvement/talents/favorite-book question. Applied/done.
- Symbiotic (PM Ecosystem): "Why are you interested in working at Symbiotic?". Done.
- GTO Wizard package angle: **semi-professional poker player** (PokerStrategy, PokerTracker, Hold'em Manager) + AI-native delivery; rejected after applying.

## Recruiter & interview log

- **ZABEL / Constantin Clodius** (Consultant, Zabel GmbH, Friedrichstraße 68, 10117 Berlin; c.clodius@zabelglobal.com; +49 1703660753; www.zabelglobal.com). Applied via email with application_zabel.pdf; he replied inviting a 45-min Google Meet; Philipp offered two slots (around 26 May); role = DataOps Product Owner, offered 85-100k vs 125k floor (flagged in German briefing).
- **Daniel Jahn / Digital Eleven** (dfj@digitaleleven.de, +49 175 484 5504): Project Q. PMM role scored 38, (Sr.) PM scored 78; German email replies dictated; Qcrypt 3-layer correction originated here ("i do have hardware experienced with integrated software hardware solutions at qcrypt, shipping a b2b encryption device that installs in less than 2min setup time" + TRNG/Linux-OTP/server-relay detail).
- **Veronika Igic / Computer Futures** (v.igic@computerfutures.at): freelance PM Retail Banking, Frankfurt + remote, 3 months; honest payments-not-retail caveat in CL; same mandate later seen on freelancermap (apply direct next time).
- **Sarah König / Riverty**, **Katharina Haß / 50Hertz** (work@50hertz.com; do NOT use sbv@50hertz.com, that's the disability representative), **Leona Günther + Tomasz Login / ISO Recruiting**, **Kristin Zwicker / CIMPCO**, **Benjamin Knodt / TEKsystems**, **Pia Fuchs / hannover.de** (fuchs@hannover.de), **t.ade@ratbacher.com / Ratbacher**, **Sabrina Rösch / Breuninger**, **Louis (recruiter) + Etienne (CEO) / autarc**.
- **Rejections:** HERO Software (verbatim reason: "Leider weicht Deine Gehaltsvorstellung von unseren derzeitigen Budgetmöglichkeiten für die Position ab."), GTO Wizard (rejected after full apply incl. CAPTCHA saga + 6666-salary bug, later corrected to 125k standard).
- **Process lessons:** ETERNO refused email applications for data-compliance reasons → career-portal submission is the safe channel. Consensys/MetaMask expired between scoring and applying → origin of listing_expired status. Accesa expired (user spotted it first). Galvany finished manually after auto-fill gaps.

## Skip log (deliberate non-applications, with reasons)

- ChefsList: "sounds like a skip" (after review).
- Hygraph: keyword-gap analysis rejected as theater; only PIM conceded as real gap.
- IXOPAY Munich: salary from 75k, below floor.
- SAP IDM/Cloud Identity mandate (2026-06-11): no SAP anywhere, scored 35/48, skipped.
- Batch dismissal: "none of it is a real fit because of salary and on site".
- Girocard 3-month agency variant: skipped in favour of the 6-month variant (one agency per end-mandate).

## References (verbatim, quotable — both captured 2026-06-12)

### EMIL Group GmbH — Chris Maslowski, Geschäftsführer

> "Ich kann Philipp wärmsten empfehlen. Philipp hat uns ca. 8 Monate als Product Owner unterstützt. Trotz des relativ komplexen Products hat sich Philipp extrem schnell eingearbeitet und hat sich innerhalb kürzester Zeit das notwendige Fachwissen angeeignet. Die Kommunikation mit internen Stakeholdern und auch Kunden verlief hervorragend. Philipp hat das Product Backlog vollständig gemanaged und konnte selbst bei knappsten Resourcen Zielkonflikte immer zur Zufriedenheit von allen Stakeholdern lösen. Ich kann Philipp uneingeschränkt weiterempfehlen!"

Best pull-quotes: "das Product Backlog vollständig gemanaged", "Zielkonflikte immer zur Zufriedenheit von allen Stakeholdern" (bei knappsten Ressourcen), "uneingeschränkt weiterempfehlen". CEO-level reference; EMIL engagement duration: ~8 months.

### ITSCare GbR — Hartmut Brand, Geschäftsführer (letter dated 31.01.2022; file: Dropbox archive Empfehlungsschreiben ITSCare.pdf, scanned)

- Engagement **März 2019 bis Mai 2020** as **"Proxy Product Owner"** (the literal title, now documented third-party), Geschäftsbereich Anwendungsentwicklung, **Projekt "AMSys#neo 1.0"**, under Projektleiter Andy Saß.
- Scope: modern webshop for internal procurement of IT services and hardware for **three regionally organised AOK organisations, ~20,000 employees total**.
- Outcome quote: contributed so "dass heute ein sehr gut funktionierender Webshop betrieben werden kann" (still in production).
- Soft quotes: "ausgesprochen engagiert und zuverlässig", "stets mit Ernsthaftigkeit und Kompetenz nachgekommen, ohne dabei den Humor zu verlieren", "Teamfähigkeit und freundliche Umgangsformen".
- ITSCare = GbR of AOK Baden-Württemberg, AOK Hessen, AOK Rheinland-Pfalz/Saarland. Reference contact on letter: Gerd Peter (Gerd.Peter@itscare.de).

## Diplomatie-Story: Umgang mit ärztlichen Fachbereichen (CLINET, 2026-07-28)

**Kontext:** Bei CLINET hat Philipp die Anforderungen direkt mit Ober- und Chefärzten geklärt und dort viel Erfahrung mit "Gebaren", Arroganz und Überheblichkeit gesammelt (seine Worte). Das ist sein **wichtigster Soft-Skill-Beleg für Healthcare-Mandate**.

**Die Kernbotschaft (seine Priorisierung, 2026-07-28): ego-freies Agieren und Manövrieren ohne die Erwartung, dass sich die Umgebung an einen selbst anpasst, sondern man sich selbst an die Umgebung.** Das ist der Satz, der in jedes Healthcare-/Konzern-Anschreiben und in jede Interview-Antwort zu Stakeholder-Konflikten gehört. Er erklärt implizit auch, woran Vorgänger in solchen Rollen scheitern: sie bringen ihr Vorgehen mit und erwarten, dass die gewachsene Organisation sich danach richtet.

**Sein Vorgehen (verbatim-nah):** Emotionen bleiben zu Hause, tief durchatmen, zu 100% sachlich bleiben und das Gespräch immer auf das zu lösende Problem zurücklenken. "Nicht in Lösungen verlieben, sondern in die Probleme" und dort ohne Ego pragmatisch zu schlanken Lösungen kommen, die Schritt für Schritt implementiert werden. Genau daraus entsteht Vertrauen, und auf dieser Vertrauensbasis lassen sich Herausforderungen gemeinsam angehen.

**Warum das zählt (ISO Proxy-PO-Mandat 3028163):** Bei diesem Endkunden sind bereits **mehrere Rollen zwischenmenschlich gescheitert** und nach kurzer Zeit ausgetauscht worden, sowohl ein interner als auch ein externer Mitarbeiter. Die Rolle wird also nicht nur fachlich, sondern vor allem zwischenmenschlich entschieden.

**Wie einsetzen:** Bewusstsein signalisieren, ohne über die gescheiterten Vorgänger zu sprechen (Gerüchte-Anmutung vermeiden, Recruiter nicht kompromittieren). Bewährte Formulierung aus `cl_iso_healthcare_po_v2.md`: "Die Position zwischen medizinischem Fachbereich und Entwicklung ist zwischenmenschlich mindestens so anspruchsvoll wie fachlich, und das ist mir sehr bewusst." Ärzte respektvoll beschreiben ("ausgeprägte fachliche Autorität, wenig Zeit, klare Hierarchien"), nie abwertend. Im Interview ist das die Antwort auf jede Stakeholder-Konflikt-Frage.

## Reusable quotes & method lines (mined from legacy corpus, 2026-06-12)

- **R&S project-leader quote (German, verbatim, strongest third-party proof he has):** "Auf dieses Feature habe [ich] mehr als ein Jahr bei den Entwicklern gepocht und du hast es alleine innerhalb einer Woche geliefert!" Context: self-taught OpenShift, solo feature development through to release.
- **Discovery doctrine (BCB letter):** "A smart product manager has an ever ongoing core discovery team of at least himself, a product designer and the lead engineer."
- **Metrics doctrine (BCB letter):** "Without metrics, decisions are not falsifiable!"
- **Small-bets axiom (0G essay):** "It is a good assumption that 75% of the product decisions turn into absolutely zero revenues" (Cagan-style portfolio framing).
- **Provenance contrast (0G essay):** defence platforms prove "it was your fault"; open AI platforms need "a maximum of transparency to enable a maximum of network effect and learning of the swarm."
- **opus package structure (the design-king reference):** Why-them / honest framing of the gap / AI-native stack / side project / 3-week onboarding plan (Week 1 listen-map, Week 2 prototype-slice, Week 3+ ship) / CL / CV. Reuse this structure for founding-PM applications.
