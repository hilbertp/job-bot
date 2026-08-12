# Profil-Mapping: Helsing Product Manager (Munich/Berlin) — Interviewvorbereitung

Quellen: `PROFILE.md` (Faktenbasis), `STORIES_AND_VOICE.md` (Stories/Zitate), `cv_helsing_defence_pm.md` (eingereichter CV), `cl_helsing_defence_pm.md` (eingereichtes Anschreiben). Alle Pfade unter `/Users/phillyvanilly/job_bot/data/applications/`.

---

## 1. Anforderungs-Mapping (stark / dünn / Gap)

### STARK

**Defence AI aus erster Hand (Kernanforderung, stärkster Trumpf).**
FCAS-Programm 2024-2025 bei Schönhöfer Sales & Engineering (SSE, 100% R&S-Tochter). Produkt: **KI-Backbone Data Transformation Module** — Transformation multimodaler Datenquellen in ML-Trainings-/Evaluationsdatensätze. Voller Lifecycle Discovery→GitOps-Rollout (ArgoCD, Argo Workflows), Provenance + Audit Trails (SafeAI/ExplainableAI). Direkte Zusammenarbeit mit Helsing (Pohnke/Banasch). [PROFILE.md Z.31-32]

**Discovery/Co-Creation in komplexen Problemräumen.**
Die "exactly zero clicks"-Story: Er hat sich bei R&S trotz Defence-Geheimhaltung in die Kundenworkshops gekämpft, festgestellt, dass die Entwickler des Kunden völlig anders arbeiten als angenommen, einen alternativen code-lastigen Workflow parallel gebaut und gemessen — der ursprünglich geplante Workflow bekam exakt null Klicks. Dazu seine Discovery-Doktrin: stehendes Kern-Discovery-Trio PM + Product Designer + Lead Engineer, "not a ceremony, a habit". [STORIES Z.84-88, Z.93, Z.105-110]

**Cross-funktionale Koordination Prototyp→Produktion.**
R&S: multinationales Team aus Architekt, Data Scientists, BE/FE, QA geführt (fachlich, ohne Weisungsbefugnis); Deployment-Zeiten von Tagen auf 20-40 Minuten. EMIL: Claims Center 0→1 Konzept→Produktion; 17-Personen-Organisation in stabile Scrum-Teams restrukturiert, Senior-Dev-Exodus auf einen einzigen Abgang gestoppt. [PROFILE.md Z.32, Z.34, Z.73]

**Schnelles Lernen fremder Domänen.**
Domänensprünge belegt: Payments (Kvitt), Encryption (Qcrypt), AgTech, Versicherung (EMIL), Krankenhaus (CLINET), Bundesbehörden (Bundesdruckerei, BA), Fuel Retail (S&B), Defence (FCAS). EMIL-CEO-Referenz wörtlich: "Trotz des relativ komplexen Products hat sich Philipp extrem schnell eingearbeitet und hat sich innerhalb kürzester Zeit das notwendige Fachwissen angeeignet." [PROFILE.md Z.29-39; STORIES Z.71]

**Erfolgsmetriken definieren.**
"Without metrics, decisions are not falsifiable!" (seine Doktrin). EMIL: Matomo-Instrumentierung, Churn pro Schritt des Claim-Handling-Flows als Leitmetrik, Priorisierung entlang gemessener Nutzung. R&S: Nutzungsmessung entschied den Workflow-Streit (zero clicks). Vierte Stärke: "Die Zeit vom Entdecken eines Defects bis zum ausgerollten Fix ist eine Produktmetrik, kein Engineering-Detail." [STORIES Z.40-41, Z.94; PROFILE.md Z.128-132]

**Deutsch UND Englisch.** Deutsch Muttersprache, Englisch C2; YouTube-Sample existiert. [PROFILE.md Z.9, Z.63]

**Nice-to-haves voll erfüllt:** Deutscher Staatsbürger, SÜ-Eignung; Behördenerfahrung Bundesdruckerei (RKI-Projekte DIM/DESH), Bundesagentur für Arbeit (stellv. IT-Sicherheitsbeauftragter, Audit alle 2 Jahre), AOK. [PROFILE.md Z.33, Z.36, Z.38; CV Z.11]

### SOLIDE, ABER MIT FLANKEN

**Commercial Strategy / Go-to-Market.**
Beleg ist der Founder-Track, nicht die Angestellten-Karriere: Kvitt (P2P-Payments, von Sparkasse übernommen und betrieben), Qcrypt (B2B-Verschlüsselung an Enterprise-Kunden geliefert), Cloud9 (live, Stripe, Google Ads, Pivot wegen Tobacco Policy), construct8 (Geschäftsmodell mit 399-EUR-Booking-Fee). ABER: keine dokumentierte kommerzielle Strategiearbeit im Defence-Kontext, keine Bid-/Angebotserfahrung, keine dokumentierte GTM-Arbeit auf Konzern-/Senior-Leadership-Ebene. Interview-Frame: konkrete Pricing-/Modellentscheidungen aus den Ventures erzählen, nicht abstrakt "commercial strategy" behaupten. [PROFILE.md Z.13-16, Z.27]

**Product Design.**
Kvitt: "complete UX/UI" selbst gebaut; heute shippt er solo inkl. UX/UI AI-native. Kein formaler Design-Background, keine Design-Titel. Ausreichend für PM-Anspruch, nicht für Design-Tiefenfragen. [PROFILE.md Z.13, Z.48]

**Discovery-Sessions mit MILITÄRISCHEN Kunden.**
Wichtige Nuance: Seine dokumentierten FCAS-"Kunden" waren die **Entwickler des Kunden** (Plattform-Nutzer), nicht uniformierte Operateure/Endnutzer im Einsatz. Er hat also Discovery im Defence-Programm unter Geheimhaltungsbedingungen gemacht — aber nicht mit Soldaten im Feld. Ehrlich halten; die Übertragungslogik (sich Zugang zu echten Nutzern erkämpfen, Annahmen an Realität sterben lassen) trägt trotzdem. [STORIES Z.84-88]

### ECHTE GAPS (nicht schönreden)

1. **Defence Procurement operativ:** Kein Beleg für eigene Arbeit an Vergabeverfahren, BAAINBw-Prozessen, Angebotserstellung. Die JD listet es als zu erlernende Domäne — er sollte es als solche benennen und mit seiner Domänen-Lerngeschwindigkeit kontern. [keine Quelle = kein Beleg]
2. **Kein militärischer Hintergrund / kein Dienst** (nirgends dokumentiert). Kontern mit: FCAS-Innensicht + CLINET-Erfahrung mit steilen Statushierarchien (Chefarzt-Dynamik als Analogie zu militärischen Hierarchien). [STORIES Z.116-139]
3. **Kein AI-Research-Hintergrund:** Er hat die Datenpipeline FÜR ML-Training verantwortet, ist aber kein ML-Praktiker. Kontern mit: Auditability-/Provenance-Tiefe (zwei Teams nur für Auditierbarkeit) und täglicher AI-native-Praxis inkl. LLM-Failure-Modes aus erster Hand. [STORIES Z.34; PROFILE.md Z.48]
4. **Keine PM-Zertifikate** ("NO CERTS") — nie behaupten; Methoden-Zeile (Scrum/Kanban/hybrid in regulierten Programmen) als Mitigation. [PROFILE.md Z.183]
5. **Wohnsitz-Logistik:** Er lebt in Limassol; CV sagt Berlin (bewusste Doktrin für DE-Markt), Berlin-Penthouse ist zur Vermietung inseriert. CL verspricht Umzugsbereitschaft München/Berlin — das muss er im Interview glaubwürdig konkretisieren können. [PROFILE.md Z.9, Z.60; CL Z.17]

---

## 2. STORY-BANK (STAR-Kurzformat, gemappt auf Interview-Dimensionen)

**S1 — Zero Clicks (Discovery + Metriken + Kundenzugang).**
S: FCAS/R&S, Defence-Geheimhaltung hielt das Produktteam von Kundenworkshops fern. A: Direkten Zugang zu den echten Nutzern (Entwickler des Kunden) erhalten. A: So lange gedrängt, bis er eingeladen wurde; nach dem Realitätsschock einen alternativen code-lastigen Workflow parallel gebaut und Nutzung instrumentiert. R: Der ursprünglich geplante Workflow bekam exakt null Klicks; Messung statt Meinung entschied. [STORIES Z.84-88]

**S2 — OpenShift-Blocker (technische Tiefe + Bias to Action).**
S: Ein Feature bei R&S hing über ein Jahr an einem OpenShift-Infrastruktur-Blocker. A: Entsperren, was Engineering nicht knackte. A: OpenShift selbst beigebracht, Lösung eigenständig gebaut. R: In einer Woche geliefert; Projektleiter wörtlich: "Auf dieses Feature habe ich mehr als ein Jahr bei den Entwicklern gepocht und du hast es alleine innerhalb einer Woche geliefert!" [PROFILE.md Z.32, Z.72; STORIES Z.92]

**S3 — Deployment-Zeiten (Delivery + Prototyp→Produktion).**
S: FCAS-Modul mit tagelangen Deployments, sovereignty-kritische Auditanforderungen. A: Verlässliche, nachvollziehbare Delivery-Kette. A: GitOps-Rollout (ArgoCD/Argo Workflows) als Produktentscheidung getrieben; reproduzierbare Pipelines mit Provenance/Audit-Trails. R: Deployment-Zeiten von mehreren Tagen auf 20-40 Minuten. [PROFILE.md Z.32]

**S4 — Auditability-Overhead (AI-Produkt-Urteilsvermögen).**
S: R&S-Plattform mit Kundeninteraktion und hoher Fehleranfälligkeit im ML-Datenkontext. A: KI end-to-end auditierbar und transparent halten. A: Volle Provenance als Produktanforderung durchgesetzt. R: Ein, faktisch zwei Teams arbeiteten dediziert an Auditierbarkeit — sein Beleg dafür, was Alignment/Überwachbarkeit von KI wirklich kostet. Bonus-Zitat: Defence-Plattformen müssen beweisen können "it was your fault". [STORIES Z.34, Z.96]

**S5 — EMIL Claims Center (0-zu-1 + Metriken + Discovery).**
S: EMIL, kein Spec, kein interner Präzedenzfall für ein Claims-Modul. A: Modul von null bauen. A: Discovery mit den Claims-Spezialisten eines Pilotkunden; Matomo-Events/Funnels; Churn pro Prozessschritt als Leitmetrik; ungenutzte Flows depriorisiert. R: Fokussiertes Modul statt breitem in Produktion geshippt. [STORIES Z.40-41; PROFILE.md Z.34]

**S6 — EMIL 17-Personen-Restrukturierung (Führung ohne Weisungsbefugnis + Mercenaries→Missionaries).**
S: Aufgeblähte 17-Personen-Organisation, Velocity am Boden, Senior-Devs kurz vor Massenexodus, Kundenvertrauen beschädigt. A: Liefertempo und Vertrauen wiederherstellen. A: Schnitt in exakt 2 stabile Scrum-Teams konzipiert und mit der Geschäftsführung durchgesetzt. R: Attrition von Beinahe-Exodus auf einen einzigen Abgang; Velocity und Client Trust wiederhergestellt; CEO-Referenz: "Zielkonflikte immer zur Zufriedenheit von allen Stakeholdern". [PROFILE.md Z.34, Z.73; STORIES Z.71]

**S7 — EMIL Kapazitätskonflikt (Stakeholder-Konflikt + Tradeoff). NUR in der polierten Fassung erzählen.**
S: Überladene Roadmap, unterbesetztes Team, ein Kunde drohte faktisch verloren zu gehen, während andere priorisiert wurden. A: Kunde halten ohne Management-Rückhalt zu verlieren. A: Strukturierte, eng getaktete Kommunikation, Erwartungssteuerung über 8 Monate. R: Kunde blieb, bis Engineering-Kapazität frei wurde. WARNUNG: Die Rohfassung ("pretend we were progressing") ist als INTERNAL ONLY markiert — niemals so erzählen. [STORIES Z.32]

**S8 — CLINET Roadmap-Schnitt (Priorisierung + Fokus).**
S: Early-Stage HealthTech, 3-Personen-Devteam, überambitionierte Roadmap, Stakeholder = Krankenhausleitung und mittleres Management. A: Shippbaren Kern finden. A: Roadmap auf die wichtigsten 10% der Features geschnitten. R: Hospital-Pilot-App (iOS+Android, digitale Anamnese, Pläne, Chat, Dokumente) kam in den Piloten. [PROFILE.md Z.35, Z.74]

**S9 — CLINET Chefarzt-Hierarchie (schwierige Stakeholder — die Militär-Analogie).**
S: Krankenhaus-Systemlandschaft, CGM-Schnittstelle in KIS-Workflows, Ober-/Chefärzte mit extremem Statusverhalten auf der Gegenseite. A: Entscheidungen aus Gesprächen holen, in denen das Gegenüber das letzte Wort beansprucht. A: Mechanik statt Disposition: Statusbedürfnis der Person von der anstehenden Entscheidung trennen; kein Bedürfnis nach dem letzten Wort. R: Integration kam durch. Für Helsing: exakt übertragbar auf Diskussionen mit ranghohen Militärs. [STORIES Z.116-139; PROFILE.md Z.35]

**S10 — Kvitt (0-zu-1 + Commercial/Exit).**
S: 2013, mobile P2P-Gruppenzahlungen existierten im deutschen Markt nicht. A: Plattform von null bauen und tragfähig machen. A: PSP-Integration, Zahlungs-/Settlement-Flows, Onboarding, komplette UX/UI, Mobile-Prototyp; als CFO Finanzplanung. R: Von der Sparkasse übernommen und betrieben. [PROFILE.md Z.13]

**S11 — Qcrypt (Hardware/Software-Produkt + Security-GTM).**
S: Quantum-sichere Verschlüsselung für B2B-Enterprise-Kunden; Einstiegshürde = Installationsaufwand. A: Sicherheitsprodukt marktfähig machen. A: Dreischichtige Architektur (TRNG-Hardware, Linux-OTP-Endpoints, Server-Relay) unter der harten Constraint "Setup unter zwei Minuten" produktisiert; stellv. IT-Sicherheitsbeauftragter. R: An Enterprise-Kunden ausgeliefert. Für Helsing die zweite Security-Kredenz neben FCAS. [PROFILE.md Z.14]

**S12 — Cloud9 Pivot (Fehler/Learning + Adaptionsgeschwindigkeit).**
S: Cloud9 startete als reine Shisha-Lieferung; Google Ads blockte wegen Tobacco Policy den Wachstumskanal. A: Geschäftsmodell retten. A: Pivot zur Multi-Service-Plattform mit Mandanten-Storefronts, Consent Mode v2, First-Party-Analytics. R: Live mit echten Vendors und Stripe-Zahlungen. Learning-Frame: Der Kanal-Constraint war eine Produktentscheidung, keine Marketing-Fußnote. [PROFILE.md Z.16]

**S13 — Bundesdruckerei DIM/DESH (regulierte Umgebung + nationale Infrastruktur).**
S: COVID-Pandemie, RKI-Projekte Digitales Impfquotenmonitoring und Einreisemanagement. A: Sichere Datenstrukturen + Identity Management unter höchsten Datenschutzanforderungen. A: PO-Arbeit auf nationaler Gesundheitsinfrastruktur. R: Lieferung in beiden RKI-Projekten; Baustein des Behörden-Tracks für die SÜ-Story. [PROFILE.md Z.36]

**S14 — Siemens-Studienarbeit (analytische Tiefe + Origin Story "warum technisch").**
S: 2014, Profitabilitätsanalyse schneller Lastgradienten; der benötigte Grenzarbeitspreis war unveröffentlicht. A: Analyse trotzdem rechnen. A: Sich selbst VBA beigebracht, Pipeline über 131 wöchentliche Merit-Order-Listen gebaut, Grenzpreis für ~41.900 15-Minuten-Intervalle rekonstruiert. R: Belastbare Wirtschaftlichkeitsrechnung (NPV 2,1-2,9 Mio EUR); Beginn seiner These, dass ein PM die technische Kette verstehen muss. [PROFILE.md Z.44, Z.144-152]

**S15 — Schnelles Einarbeiten EMIL (Domänenlernen, mit Drittbeleg).**
S: Komplexe B2B-InsurTech-Plattform, er kam ohne Versicherungshintergrund. A: In Wochen sprechfähig werden. A: Discovery mit Fachanwendern, Backlog vollständig übernommen. R: CEO-Referenz wörtlich: "extrem schnell eingearbeitet... innerhalb kürzester Zeit das notwendige Fachwissen angeeignet"; gesamtes Engagement nur ~8 Monate mit geliefertem Claims Center. [STORIES Z.71; PROFILE.md Z.34, Z.78]

---

## 3. KONSISTENZ-CHECK: CV/CL-Behauptungen vs. Faktenbasis

Sortiert nach Risiko. Prinzip der ehrlichen Formulierung: "wir" für Teamleistung, "ich" nur für Rolle/Verantwortung; nichts frontal dementieren, nichts Falsches stehen lassen.

**K1 (HOCH) — CV Z.80: "Implemented the CGM (CompuGroup Medical) interface myself".**
Korrektur vom 2026-07-28: Er hat die Entwickler angeleitet, nicht selbst implementiert. (PROFILE.md Z.35/Z.163 trägt noch die alte Fassung — die Datei selbst ist hier veraltet.) Interview-Formulierung: "Ich habe die CGM-Integration in die KIS-Workflows verantwortet, die Schnittstellenlogik selbst spezifiziert und die Umsetzung mit unserem Drei-Personen-Team eng geführt — bei der Teamgröße hieß das: tief im Detail, bis hin zum Testen der Aufrufe." Nicht sagen: "den Code habe ich geschrieben."

**K2 (HOCH) — CL Z.11: "worked closely with Christopher Pohnke... and Jonas Banasch" / "We have worked together before".**
PROFILE.md Z.31 stützt "close working relationship", aber Helsing wird die beiden intern fragen. Vor dem Interview rekonstruieren: konkrete gemeinsame Meetings/Artefakte/Entscheidungen mit beiden. Formulierung: die Zusammenarbeit über konkrete Berührungspunkte beschreiben (Architektur-Abstimmungen mit Pohnke, Delivery-Schnittstellen mit Banasch), Nähe nicht über das hinaus behaupten, was die beiden bestätigen würden.

**K3 (HOCH) — CV Z.11/18/28 + CL Z.15: "hands-on AI-native building", "building full-stack myself", "I still build across the full stack myself".**
Kanonische Positionierung (PROFILE.md Z.101-163): Er ist KEIN Entwickler, fasst Python/Code nicht an; niemals behaupten, eine Sprache sei seine Arbeitssprache. Der CV-Claim ist als AI-native-Solo-Shipping verteidigbar, aber ein Helsing-Engineer wird bohren ("zeig mir Code, den du geschrieben hast"). Formulierung: "Ich shippe komplette Produkte solo — Anforderungen, UX, Architektur, QA, Infra, GitOps — AI-native. Ich schreibe den Code nicht Zeile für Zeile selbst; ich halte das für die richtige Arbeitsteilung, und genau diese Kette zu strukturieren ist aus meiner Sicht die technische Leistung eines PM." Live-Beweise: cloud-nine.store, phoenix882.com, job_bot, Liberation of Bajor.

**K4 (MITTEL-HOCH) — CV Z.11: "eligible for the Sicherheitsüberprüfung".**
Nur Eignung behauptet — korrekt. Aber in den Dateien ist NICHT dokumentiert, ob er bei SSE/FCAS eine formale SÜ durchlaufen hat oder welche Stufe. Vor dem Interview mit Philipp klären. Formulierung bis dahin: "Deutscher Staatsbürger, keine Hindernisse für die SÜ; im FCAS-Umfeld habe ich bereits unter Geheimschutzbedingungen gearbeitet" — keine vorhandene Freigabe behaupten.

**K5 (MITTEL-HOCH) — CV Z.3 "Berlin, Germany" + CL Z.17 "ready to relocate to Munich or Berlin".**
Faktisch lebt er in Limassol (Zypern), die Telefonnummer ist zypriotisch (steht im CV!), das Berliner Penthouse ist zur Vermietung inseriert [PROFILE.md Z.9, Z.60]. Berlin-als-Basis ist bewusste Doktrin für den DE-Markt, aber ein aufmerksamer Interviewer sieht die +357-Nummer. Formulierung: "Ich bin zwischen Berlin und Limassol mobil — daher die Nummer — und für diese Rolle ziehe ich nach München oder Berlin; verfügbar ab sofort." Keine Vollzeit-Berlin-Präsenz behaupten, wenn nach Logistik gebohrt wird.

**K6 (MITTEL) — CV Z.11: "nearly ten years across defence, national infrastructure, and regulated platforms".**
Die ~10 Jahre sind die PM/PO-Gesamtzahl (inkl. Versicherung, Payments); Defence konkret nur 2024-2025. Die Formulierung koppelt die Jahreszahl an Domänen — genau das verbietet die kalibrierte Regel [PROFILE.md Z.176]. Formulierung: "Knapp zehn Jahre Produktverantwortung insgesamt; Defence davon konkret die FCAS-Zeit, davor nationale Infrastruktur, Gesundheits- und Versicherungsplattformen."

**K7 (MITTEL) — CV Z.39/CL Z.11: Titel "Product Manager" bei SSE.**
PROFILE.md Z.31-32 führt die Rolle als "PM/PO"; "Product Manager" ist die für das Helsing-Paket gewählte Variante. Falls nach dem Vertragstitel gefragt: über Verantwortung sprechen ("Produktverantwortung für das Modul, Backlog und Release-Spezifikationen end-to-end"), nicht auf einem Titel-Etikett beharren.

**K8 (MITTEL) — CV Z.63: "EMIL Group · Product Manager".**
Das CEO-Referenzschreiben sagt "Product Owner", Dauer ~8 Monate [STORIES Z.71-73; PROFILE.md Z.78]. Formulierung: "Formal Product Owner — die Referenz sagt PO — mit PM-Schnitt: Discovery, Analytics, Restrukturierung; insgesamt acht Monate."

**K9 (MITTEL) — CV Z.66: "reduced time-to-market for insurance products from over a year to under a week".**
Das ist die Plattform-Value-Prop von EMIL als Unternehmen, nicht seine persönliche Leistung in 8 Monaten [PROFILE.md Z.34]. Formulierung: "Das ist das Leistungsversprechen der Plattform, an der ich mitgebaut habe; mein konkreter Beitrag waren die Module Produktkonfiguration bis Dokumenten-Workflow und das Claims Center von null."

**K10 (MITTEL) — CV Z.47: "Reduced deployment times... resolved an OpenShift infrastructure blocker".**
Beide kanonisch belegt [PROFILE.md Z.32, Z.72], aber der Satz mischt Team- und Einzelleistung. Formulierung: "Die Deployment-Verkürzung war Teamleistung, die ich als Produktentscheidung (GitOps-Umbau) getrieben habe; den OpenShift-Blocker habe ich tatsächlich persönlich gelöst — selbst beigebracht, eine Woche, das Projektleiter-Zitat dazu gibt es." Vorsicht: Diese Solo-Story reibt sich mit K3 ("kein Entwickler") — als historische Ausnahme im Infrastruktur-/Config-Bereich rahmen, nicht als Coding-Praxis.

**K11 (MITTEL) — CV Z.71: "Restructured a bloated 17-person organisation".**
Belegt [PROFILE.md Z.34, Z.73], aber: Hatte ein externer PO nach wenigen Monaten das Mandat dafür? Formulierung: "Ich habe den Schnitt in zwei stabile Teams konzipiert und mit der Geschäftsführung durchgesetzt — entschieden hat die Geschäftsführung, das Design und das Momentum kamen von mir."

**K12 (NIEDRIG-MITTEL) — CV Z.24: "Eight years as startup CFO".**
Kvitt-CFO 2013-2018 (5-6 Jahre) + Smart Soil CFO bis 2021, überlappend; die 8 Jahre sind die Spanne 2013-2021 über zwei Ventures [PROFILE.md Z.13, Z.15]. Formulierung: "Acht Jahre CFO-Verantwortung über zwei Ventures hinweg, 2013 bis 2021, zeitweise parallel."

**K13 (NIEDRIG-MITTEL) — CV Z.18/108: "Kvitt, acquired by Sparkasse" + Commercial-Strategy-Claim.**
Kanonische Formel ist exakt "acquired and operated by Sparkasse" (Singular, keine Details zu Kaufpreis/Struktur in den Dateien) [PROFILE.md Z.13, Z.88]. Bei Nachfragen zu Dealgröße/GTM-Zahlen: nichts erfinden; auf die belegbaren kommerziellen Artefakte ausweichen (Cloud9-Pricing live, construct8-Geschäftsmodell mit 399-EUR-Fee und ~20% Markup-Ökonomie).

**K14 (NIEDRIG) — CV Z.48: "Led a multinational cross-functional team".**
Fachliche Führung ohne Weisungsbefugnis [PROFILE.md Z.32]. Formulierung: "Geführt heißt hier: fachlich, über Backlog, Priorisierung und Architektur-Entscheidungen — disziplinarisch hatte ich niemanden."

**K15 (NIEDRIG) — CV Z.145: "Python, SQL, Kotlin (Spring Boot)" unter Methods & Tools.**
Erlaubt als "Stack, den er verantwortet hat", aber lädt zu "Rate your Kotlin" ein. Formulierung: "Das sind die Stacks meiner Produkte — ich kann sie lesen, einordnen und mit Engineers auf Augenhöhe diskutieren; geschrieben haben sie meine Teams." [PROFILE.md Z.86, Z.158-161]

**K16 (NIEDRIG) — CV Z.40: SSE "Munich / Remote".**
Der Standort des SSE-Engagements ist in PROFILE.md nicht explizit dokumentiert (R&S sitzt in München). Kurz mit Philipp verifizieren, wo das Projekt formal lief.

**K17 (NIEDRIG) — CV Z.11: "Full-scope PM: commercial strategy and go-to-market as a founder".**
Stimmig, solange er GTM-Fragen mit Founder-Beispielen beantwortet und nicht suggeriert, er habe bei R&S/EMIL kommerzielle Strategie verantwortet (dafür gibt es keinen Beleg).

---

## 4. FCAS/Helsing-Munition ("Warum Helsing" + technische Tiefe)

**Die Beziehungsebene (einzigartiger Vorteil):**
- Er saß auf der SSE-Seite des FCAS-Programms, Helsing "across the table". Für Helsing-Adressaten IMMER SSE nennen (nicht R&S) — die kennen die echte Entität. [PROFILE.md Z.31; CL Z.11]
- Namen: **Christopher Pohnke** (Helsing-Architekt, Zusammenarbeit auf Architekturseite) und **Jonas Banasch** (Projektleiter, Delivery-Seite). [PROFILE.md Z.31; CL Z.11]
- Kultur-Beobachtung aus dem CL, wiederverwendbar für "Warum Helsing": das Helsing-Team als "young, energetic, and genuinely wired to get things done"; er teilt "that directness, sometimes bluntness, and the same impatience to ship". [CL Z.11]
- Sein Angebots-Frame im CL: Was schnell wachsenden Firmen mit viel jungem Talent verloren geht, ist Struktur — "the connective tissue between discovery, commercial strategy, technical architecture, and delivery" — und er bringt sie, "without slowing anyone down". [CL Z.15]

**Das Produkt (technische Tiefe, präzise benennen):**
- **KI-Backbone Data Transformation Module**: Transformation multimodaler Datenquellen in Datensätze für ML-Trainings- und Evaluationspipelines. Exakter Produktname nur für Helsing; anderswo generisch. [PROFILE.md Z.31]
- Voller Lifecycle: Discovery → GitOps-Rollout (ArgoCD, Argo Workflows); reproduzierbare Pipelines mit Provenance + Audit-Trails (SafeAI/ExplainableAI). [PROFILE.md Z.32]
- Stack sprechfähig: Kotlin (Spring Boot), Python, PostgreSQL, MongoDB, Redpanda (Kafka), Kubernetes, ArgoCD, OpenShift, GitLab. [PROFILE.md Z.32]
- Ergebnisse: Deployments von Tagen auf 20-40 Minuten; OpenShift-Blocker nach über einem Jahr Stillstand persönlich in einer Woche gelöst (Projektleiter-Zitat als Drittbeleg). [PROFILE.md Z.32, Z.72; STORIES Z.92]

**Die drei besten Defence-spezifischen Gesprächslinien:**
1. **Zero-Clicks-Story** — beweist Kampf um Kundenzugang unter Geheimhaltung, Annahmen-Falsifikation, Instrumentierung als Schiedsrichter. Direkt auf Helsings "structured discovery sessions with military customers" mappbar. [STORIES Z.84-88]
2. **Auditability-Overhead** — "ein, faktisch zwei Teams" nur für Auditierbarkeit/Provenance; er kennt die reale Kostenseite von vertrauenswürdiger KI in Defence. Dazu der Kontrast: Defence-Plattformen müssen beweisen können "it was your fault", offene AI-Plattformen brauchen maximale Transparenz für Netzwerkeffekte. [STORIES Z.34, Z.96]
3. **Skeptische-Nutzer-Playbook** (aus dem ApprovalMax-Screener, ursprünglich auf R&S-Defence-Nutzer gemünzt): KI-Use-Cases nach größtem Workflow-Risiko wählen, nicht nach spannendster Capability; jede KI-Aktion exponiert Input, Reasoning und One-Click-Override; advisory→default-on erst, wenn die Override-Rate stabil niedrig ist. [STORIES Z.39]

**Flankierende Glaubwürdigkeit:**
- SÜ-Eignung als deutscher Staatsbürger + Behörden-Track: Bundesdruckerei (RKI DIM/DESH), Bundesagentur für Arbeit (stellv. IT-Sicherheitsbeauftragter), AOK — deckt das Nice-to-have "deutsche Behörden/Public Sector" vollständig. [PROFILE.md Z.33, Z.36, Z.38]
- Qcrypt als zweite Security-Kredenz: quantum-sichere Verschlüsselung, TRNG-Hardware, B2B-Enterprise, stellv. IT-Sicherheitsbeauftragter. [PROFILE.md Z.14]
- Root-These für die Produktphilosophie-Frage: Niemand kennt die benötigte Lösung — nicht wir, nicht der Kunde, nicht die höchstbezahlte Meinung im Raum; deshalb Bets + kontinuierliche Discovery + billiges schnelles Prototyping, extern verifiziert mit Pilotkunden. Plus das 75%-Axiom: "It is a good assumption that 75% of the product decisions turn into absolutely zero revenues." [STORIES Z.95, Z.101]

**Vorbereitungs-Todos vor dem Interview (aus den Lücken):**
1. Mit Philipp klären: formale SÜ bei SSE ja/nein, welche Stufe (K4).
2. Konkrete Pohnke/Banasch-Berührungspunkte rekonstruieren (K2).
3. Defence-Procurement-Grundwissen aufbauen (BAAINBw, Vergaberecht-Basics, FCAS-Programmstruktur) — als "lerne ich gerade aktiv" framen, nicht als vorhanden.
4. Standort-Antwort festlegen (K5).

## KEY FACTS
- FCAS-Produkt exakt benennen: KI-Backbone Data Transformation Module (multimodale Daten zu ML-Trainings-/Eval-Datensätzen) bei SSE — für Helsing IMMER SSE sagen, nicht Rohde & Schwarz (PROFILE.md Z.31)
- Direkte Helsing-Kontakte aus FCAS: Christopher Pohnke (Architekt) und Jonas Banasch (Projektleiter); Helsing wird beide intern fragen — konkrete Berührungspunkte vor dem Interview rekonstruieren
- Beste Discovery-Story: 'exactly zero clicks' — in Kundenworkshops gekämpft trotz Defence-Geheimhaltung, Alternativ-Workflow gemessen, geplanter Workflow bekam null Klicks (STORIES Z.84-88)
- Stärkster Drittbeleg: R&S-Projektleiter-Zitat 'mehr als ein Jahr gepocht... du hast es alleine innerhalb einer Woche geliefert' (OpenShift-Blocker, selbst beigebracht)
- Kanonische R&S-Zahlen: Deployments von Tagen auf 20-40 Minuten; Provenance/Audit-Trails (SafeAI/ExplainableAI); ein bis zwei Teams nur für Auditierbarkeit
- KRITISCHER Konsistenzpunkt: CV sagt 'Implemented the CGM interface myself' — tatsächlich Entwickler angeleitet (Korrektur 2026-07-28); Formulierung: Integration verantwortet, Schnittstellenlogik spezifiziert, Umsetzung mit dem 3-Personen-Team eng geführt
- Kanonische Positionierung: technischer PM, KEIN Entwickler — niemals behaupten, dass er Code schreibt; AI-native-Solo-Shipping über die ganze Kette ist die erlaubte Rahmung (PROFILE.md Z.101-163)
- CV-Claim 'nearly ten years across defence...' koppelt Jahreszahl an Domänen — korrekt ist: knapp zehn Jahre PM/PO gesamt, Defence konkret nur 2024-2025
- EMIL: Referenzschreiben sagt 'Product Owner', ~8 Monate; 'time-to-market von >1 Jahr auf <1 Woche' ist Plattform-Value-Prop, nicht seine persönliche Leistung
- EMIL-Restrukturierung belegt: 17 Personen in 2 stabile Scrum-Teams, Senior-Exodus auf einen Abgang gestoppt — Formulierung: konzipiert und mit Geschäftsführung durchgesetzt
- Sicherheitsüberprüfung: nur Eignung ist belegt; ob er bei SSE eine formale SÜ durchlief, ist in den Dateien NICHT dokumentiert — vor dem Interview mit Philipp klären
- Standort-Risiko: CV sagt Berlin, er lebt in Limassol (+357-Nummer steht im CV), Berlin-Penthouse zur Vermietung inseriert; Antwort auf Umzugslogistik München/Berlin vorbereiten
- Echte Gaps: keine operative Defence-Procurement-Erfahrung, kein Militärdienst, kein AI-Research-Hintergrund, keine PM-Zertifikate — als lernbare Domänen framen, nicht verstecken
- Nice-to-haves voll erfüllt: Bundesdruckerei (RKI DIM/DESH), Bundesagentur für Arbeit (stellv. IT-Sicherheitsbeauftragter), AOK = deutscher Behörden-Track komplett
- Discovery-Nuance ehrlich halten: seine FCAS-'Kunden' waren die Entwickler des Kunden, keine uniformierten Endnutzer/Operateure
- Defence-KI-Gesprächslinie: Defence-Plattformen müssen beweisen können 'it was your fault' (Provenance-Kontrast-Zitat); skeptische Nutzer = Use-Cases nach Workflow-Risiko, jede KI-Aktion mit Input+Reasoning+Override
- EMIL-Tradeoff-Story NUR in polierter Fassung erzählen — die Rohfassung ('pretend we were progressing') ist explizit INTERNAL ONLY (STORIES Z.32)
- Story-Bank deckt alle PM-Dimensionen: Discovery (Zero Clicks), Priorisierung (CLINET 10%), Stakeholder (EMIL/Chefarzt), Technik (OpenShift), Metriken (Matomo Churn-per-Step), 0-zu-1 (Kvitt/Claims Center), Commercial (Qcrypt/Cloud9)
- Chefarzt-Analogie als Militär-Hierarchie-Antwort: CLINET-Erfahrung mit Ober-/Chefärzten, Mechanik = Statusbedürfnis von der Entscheidung trennen, kein letztes Wort nötig
- Kulturargument aus dem CL wiederverwenden: Helsing-Team als 'young, energetic, wired to get things done'; sein Angebot = Struktur als 'connective tissue' ohne zu verlangsamen

## SOURCES
- /Users/phillyvanilly/job_bot/data/applications/PROFILE.md
- /Users/phillyvanilly/job_bot/data/applications/STORIES_AND_VOICE.md
- /Users/phillyvanilly/job_bot/data/applications/cv_helsing_defence_pm.md
- /Users/phillyvanilly/job_bot/data/applications/cl_helsing_defence_pm.md
