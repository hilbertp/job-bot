# Philipp Hilbert. *Product Owner · Healthcare-Plattformen & regulierte Domänen.*

Berlin · hilbert@true-north.berlin · +357 94101644 · www.true-north.berlin

[LinkedIn](https://www.linkedin.com/in/philipp-hilbert-34032275/) · [GitHub](https://github.com/hilbertp)

---

## Profil

Product Owner mit zehn Jahren Erfahrung in der Übersetzung komplexer fachlicher Anforderungen in strukturierte Epics, Features und User Stories, davon dreimal im Gesundheitswesen: digitale Anamnese bei CLINET, nationale Gesundheitsdaten-Infrastruktur bei der Bundesdruckerei (RKI), Krankenkassen-Umfeld bei der AOK. Zweimal stellvertretender IT-Sicherheitsbeauftragter: Datenschutz und regulatorische Anforderungen verantworte ich, statt sie nur zu kennen. Erfahren in skalierten Multi-Team-Programmen mit domänenübergreifenden Abhängigkeiten und im Greenfield-Aufbau domänengetriebener Plattformprodukte. Deutsch Muttersprache, Englisch C2.

---

## Schwerpunkte

- **Anforderungsübersetzung:** komplexe medizinische und fachliche Anforderungen in Epics, Features, User Stories und prüfbare Akzeptanzkriterien; aktive Refinement-Begleitung
- **Gesundheitswesen und Datenschutz:** digitale Anamnese, KIS-Integration, RKI-Datenplattformen; DSGVO und Compliance aus der Verantwortungsrolle (2x stellv. IT-Sicherheitsbeauftragter)
- **Multi-Team-Koordination:** Synchronisation domänenübergreifender Abhängigkeiten zwischen Fachbereich, Architektur, Entwicklung und QA; skalierte agile Zusammenarbeit in internationalen Programmen
- **Technisches Fundament:** REST-APIs, eventgetriebene Systeme (Kafka/Redpanda), Kubernetes, CI/CD; enge Zusammenarbeit mit Softwarearchitekten auf Augenhöhe
- **AI-native Delivery:** eigenes autonomes Software-Delivery-Framework (Denorios) mit voller DevOps-Kette von CI-Gates bis Rollback; Integration von AI-Agenten und Vibe Codern in professionelle, testgetriebene Entwicklungsprozesse unter menschlicher Governance
- **Domänenstrukturierung:** fachliche Abgrenzung und Strukturierung von Plattform-Domänen entlang der Geschäftslogik, auch im Greenfield; von Versicherungs-Underwriting bis Verteidigungsdaten

---

## Berufserfahrung

### CLINET Platforms · Product Owner, Mobile Healthcare-Plattform
*2021 – 2022 · Berlin*

Krankenhaus-Pilotplattform für iOS und Android mit tiefer Integration in Krankenhausinformationssysteme; Greenfield-Produktaufbau im HealthTech-Startup.

- **Digitale Anamnese** konzipiert und ausgeliefert, dazu Therapie- und Essenspläne, Transport, Chat und Patienten-Dokumentenablage
- **CGM-Schnittstelle implementiert** und in die KIS-Workflows der Kliniken integriert; fachliche Anforderungen aus Klinik-Fachbereichen in umsetzbare User Stories übersetzt
- **Individualisierte Gesundheitsprodukt-Angebote auf Basis anonymisierter Patientendaten** konzipiert: Produktentwicklung auf sensiblen Gesundheitsdaten, datenschutzkonform von Anfang an
- Datenschutzsensible Patientendaten-Workflows unter DSGVO-Anforderungen strukturiert

*AngularJS, Ionic, Python, Kubernetes, CGM-API-Integration*

### Rohde & Schwarz · Product Owner, KI- und Datenplattform (FCAS)
*2024 – 2025 · München / Remote*

Zentrale Datenplattform des europäischen Verteidigungsprogramms FCAS: fachlich hochkomplexes, domänengetriebenes Plattformprodukt, im Greenfield aufgebaut im Multi-Team-Setup.

- Komplexe Anforderungen multinationaler Fachstakeholder in strukturierte Epics, Features und User Stories übersetzt
- Domänenübergreifende Abhängigkeiten mit Softwarearchitekt, Data Science, Entwicklung und QA synchronisiert; tägliche Zusammenarbeit mit der Architektur
- Akzeptanzkriterien definiert und Umsetzungsergebnisse fachlich bewertet; Audit-Trails und Datenprovenienz sichergestellt
- Deployment-Zeiten von mehreren Tagen auf 20-40 Minuten reduziert

*Kotlin, Python, PostgreSQL, MongoDB, Redpanda (Kafka), Kubernetes, ArgoCD, OpenShift*

### Bundesagentur für Arbeit · Product Manager, Daten- und Analyseplattform
*2023 – 2024 · Remote*

- Öffentlicher Sektor: Analyseplattform für Arbeitsmarktdaten mit strengen Datenschutz- und Governance-Anforderungen
- Stellvertretender IT-Sicherheitsbeauftragter: Compliance, Governance, Data Lineage
- Automatisierte ETL mit Dagster eingeführt; CI/CD standardisiert

### EMIL Group · Product Manager, InsurTech-SaaS-Plattform
*2022 · Berlin*

- Hochregulierte Versicherungsdomäne (Produktkonfiguration, Pricing, Underwriting) fachlich strukturiert und in Software übersetzt
- 17-köpfige Delivery-Organisation in funktionierende Scrum-Einheiten restrukturiert; Zusammenarbeit mehrerer PO-Rollen koordiniert

---

## Frühere Stationen (Auswahl)

- **Product Owner, COVID-19-Datenplattform, Bundesdruckerei (2021):** Sichere Datenstrukturen und Identity Management für die RKI-Projekte DIM und DESH; nationale Gesundheitsinfrastruktur unter höchsten Datenschutzanforderungen
- **Proxy Product Owner, AOK ITSCare (2019–2020):** Proxy-PO zwischen Fachbereich der Krankenkasse und Entwicklungsteam; Migration des internen Webshops mit komplexer Katalog- und API-Integration
- **Projektleitung, Enercon (2019):** IT-Modernisierung eines Produktionsstandorts

---

## Gründungen & eigene Projekte

- **Denorios · Creator & Operator (2026–heute):** Autonomes Software-Delivery-Framework: AI-Agenten planen, implementieren, reviewen und testen Code in einer menschlich governten Pipeline; das Framework hat 350+ Arbeitspakete seines eigenen Codebestands durch die eigene Pipeline ausgeliefert und wird aktuell als installierbares npm-Framework paketiert
  - Volle DevOps-Kette eigenhändig gebaut und betrieben: Node.js-Orchestrator (~7.000 LOC ohne Runtime-Dependencies), AI-Coding-Agenten in isolierten Git-Worktrees, unabhängiger AI-Review-Agent, fail-closed GitHub-Actions-Gate (komplette Regression- plus Playwright-Browser-Suite, Fast-Forward auf main nur bei Grün, Rollback als Revert-Forward), Operations-Dashboard mit One-Click Promote/Rollback und Token-Kosten pro Deliverable
  - Guardrails gegen AI-spezifische Fehlermodi: Test-Update-Gate trennt gewollte Teständerungen von maskierten Regressionen; Akzeptanzkriterien-Hoheit liegt ausschließlich beim Menschen (ein Agent, der Anforderungen aufweicht, stoppt die Pipeline); Write-Locks auf Quellpfade; Liveness-Monitoring, das agentengeschriebenen Timestamps grundsätzlich misstraut
  - Brücke zwischen Vibe Coding und professioneller Engineering-Praxis: derselbe gated Prozess integriert AI-Agenten und menschliche Entwickler, mit maschinenlesbaren Akzeptanzkriterien in Merge-Trailern und einem QA-Agenten, der fehlende Guard-Tests zur menschlichen Freigabe vorschlägt
- **construct8 · Gründer und Product Owner (2026–heute):** Zweiseitiger B2B2C-Marktplatz, der Bauunternehmen auf Zypern mit geprüften, dokumentierten Bauarbeitern verbindet; als Solo-Gründer mit AI-gestützter Entwicklung von der Idee bis zur Zahlungsreife in Monaten statt Jahren geführt
  - Mehrsprachige Produktionsplattform (Englisch, Griechisch, Russisch, Arabisch inkl. Rechts-nach-links-Layout); Stripe-Payments mit automatisierter Rechnungsstellung; WhatsApp-Messaging-Relay mit Übersetzung über die Sprachgrenze hinweg
  - Conversion-Funnel stufenweise entschärft: anonymes Katalog-Browsing ohne Account, Fünf-Felder-Signup beim Erstkontakt, Rechnungsdaten erst im Zahlungsmoment; Identitätsschutz beider Seiten als serverseitig erzwungene Geschäftsregel (Anonymität bis zur Buchung, 399 EUR Einmalgebühr)
  - DSGVO-bewusster Umgang mit Arbeiterdokumenten und personenbezogenen Daten; internes CRM für Leads, Vetting-Pipeline, Chat-Moderation, Umsatz-Tracking und Team-Zugriffe; Self-Service-Portal für Arbeiter
- **Kvitt Payment Solutions · Gründer und CFO (2013–2018):** P2P-Payments-Plattform, von der Sparkasse übernommen und weiterbetrieben
- **Qcrypt AG · Mitgründer und Product Owner (2016–2018):** Quantensichere Verschlüsselung; stellvertretender IT-Sicherheitsbeauftragter
- **Smart Soil Technologies · Mitgründer, CDO und CFO (2016–2021):** Nanotechnologie vom Labor bis zu Investorenrunden

---

## Ausbildung

**Diplom-Wirtschaftsingenieur**, Technische Universität Berlin · Vertiefung Logistik

---

## Sprachen

Deutsch (Muttersprache) · Englisch (C2)
