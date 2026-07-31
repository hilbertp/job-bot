# Philipp Hilbert. *Product Owner · Technische Produktarbeit in Kundenprojekten.*

hilbert@true-north.berlin · +357 94101644 · www.true-north.berlin · [LinkedIn](https://www.linkedin.com/in/philipp-hilbert-34032275/) · [GitHub](https://github.com/hilbertp)

10+ Jahre Produkterfahrung · APIs, Datenmodelle und Systemintegration · Deutsch Muttersprache, Englisch C2 · Umzug nach Stuttgart möglich · kurzfristig verfügbar

---

## Worin meine technische Leistung als Product Manager besteht

Ich bin kein Entwickler. Programmieren habe ich mir 2014 in meiner Studienarbeit bei Siemens selbst beigebracht, in VBA, weil die Auswertung anders nicht zu machen war. Seitdem habe ich über ein Jahrzehnt auf Product-Owner- und Product-Manager-Ebene die technischen Zusammenhänge der Softwareentwicklung und die technischen Abhängigkeiten hautnah erlebt, von Kleinstorganisationen bis in den Konzern, und die Teamarbeit an genau diesen Abhängigkeiten entlang strukturiert. Meine technische Leistung liegt deshalb hinter der Discovery und neben dem Code: dafür zu sorgen, dass die Kette von der Anforderung bis zum Rollback so organisiert ist, dass ein Team schnell und sicher liefern kann.

- **Die Lieferkette ist die eigentliche Produktentscheidung.** Nach Discovery und Requirements muss eine abgestimmte Entwicklungs- und Testautomatisierung stehen: eine Branching- und Merge-Strategie, die einen Hotfix am selben Tag erlaubt, automatisierte Tests, auf die man sich beim Release wirklich verlässt, und GitOps-Prozesse, die Rollout und Rollback zu einem Nicht-Ereignis machen. Wer das nicht organisiert, diskutiert später über Termine statt über Produkte.
- **Containerisierte Umgebungen als Normalfall.** Kubernetes, OpenShift, GitOps mit ArgoCD. Bei Rohde & Schwarz ist die Deployment-Zeit von mehreren Tagen auf 20 bis 40 Minuten gefallen, und ein Infrastruktur-Blocker, an dem die Entwicklung über ein Jahr hing, wurde aufgelöst. Nicht, weil ich den Fix geschrieben hätte, sondern weil ich ihn als Produktproblem behandelt und die richtigen Leute an einen Tisch geholt habe.
- **Architektur- und Integrationskonzepte.** Bei Scheidt & Bachmann war ich Product Owner genau des Integrationsteams, über Standort- und Zentralsysteme hinweg. Bei der AOK ITSCare lief die Katalog- und API-Integration eines Beschaffungsportals in Bestandssysteme, mit Genehmigungsworkflows je Organisationseinheit. Bei CLINET habe ich die Anbindung an die bestehende Systemlandschaft seinerzeit sogar selbst umgesetzt, was mir bis heute ein realistisches Gefühl dafür gibt, was eine Schnittstelle wirklich kostet.
- **Datenmanagement und Geschäftsprozesse.** Bei der Bundesagentur für Arbeit ein Analyse-Stack auf PostgreSQL, Dagster und dbt mit einer Django-Verwaltungsumgebung, inklusive Datenherkunft und Lineage im wiederkehrenden Audit. Bei Rohde & Schwarz die Überführung multimodaler Quellen in kuratierte Datensätze mit vollständiger Provenienz.
- **Aufwand und Machbarkeit.** Ich schätze nicht allein, und ich lasse auch nicht raten. Aufwände entstehen im Gespräch mit der Entwicklung, und meine Aufgabe ist es, die fachliche Frage so zu stellen, dass eine belastbare technische Antwort überhaupt möglich wird.
- **Zum Stack Ihrer Teams.** Angular, TypeScript, Django und Python sind die Werkzeuge Ihrer Entwicklung, nicht meine. Django kenne ich aus dem produktiven Betrieb bei der Bundesagentur, Python und TypeScript aus meiner eigenen Arbeitsumgebung. Produktionscode schreibe ich darin nicht, und das halte ich für die richtige Arbeitsteilung. Was ich mitbringe, ist Transferwissen entlang der gesamten Wertschöpfungskette, und genau das entscheidet in einer Rolle, die zwischen Fachlichkeit, Architektur und Lieferung vermitteln soll.

---

## Wie ich arbeite / Meine Stärken

**Ich lasse mein Ego zu Hause.**
Stakeholder-Gespräche sind nicht der Ort für eigene Empfindlichkeiten. Ich will die Entscheidung, nicht das letzte Wort, und ich bleibe unaufgeregt, wenn der Raum es nicht ist.

**Ich verliebe mich in das Problem, nicht in die Lösung.**
Kunden werden am ehesten zufrieden, wenn man nicht in die eigene, vermeintlich clevere Lösung verliebt ist. Ein Entwurf, an dem ich hänge, ist ein Entwurf, den ich über sein Verfallsdatum hinaus verteidige. Genau so liefern Organisationen am Ende das Falsche, dafür schön und überzeugend.

**Auf der grünen Wiese kaufe ich Information, bevor ich Software baue.**
Unbekanntes Terrain braucht schnelle, günstige Discovery-Wetten, die die größte Unsicherheit zuerst auflösen. Billige Experimente machen teure Entscheidungen sicherer.

**Ich denke die ganze Wertschöpfungskette mit, nicht nur das Backlog.**
Eine Produktentscheidung ist nicht fertig, wenn die Story verfeinert ist. Die Zeit vom Erkennen eines Fehlers bis zum ausgerollten Fix ist eine Produktkennzahl und kein technisches Detail. Bauen und verantworten können diese Kette Architekten und DevOps-Leute, nicht ich. Was ich mitbringe, ist sie gut genug zu verstehen, um sie in die richtigen Bahnen zu lenken: die richtigen Fragen früh zu stellen und zu merken, wenn Discovery, Anforderungen, Testautomatisierung, Auslieferung und Betrieb auseinanderlaufen.

---

## Die Probleme, für die man mich holt

Niemand weiß, welche Lösung der Markt tatsächlich braucht. Wir nicht, der Kunde nicht, und auch nicht die teuerste Meinung im Raum. Fast jeder teure Produktfehlschlag beginnt damit, dass eine Organisation so tut, als wüsste es jemand.

Die Alternative ist, jede Produktentscheidung als Wette zu behandeln. Kontinuierliche Discovery und schnelles, günstiges Prototyping bringen uns intern in kleinen Schritten näher an die Antwort, und Pilotkunden und Stakeholder bestätigen Prototypen und MVPs dann extern, oder sie kaufen uns die sehr wertvolle Information über einen Fehlschlag so günstig wie irgend möglich. So entstehen Produkte, die Menschen wirklich mögen, statt Produkte, die lediglich existieren (bei null Umsatz).

Die fünf Probleme unten sind das, was passiert, wenn man diesen Weg überspringt. Sie sind nicht branchenspezifisch. Sie beißen am härtesten dort, wo Software als Projekt mit Anfangs- und Enddatum eingekauft statt als Produkt verantwortet wird.

**1. Discovery gilt als Phase, und zwar als kurze.**

Jemand hat eine Idee, sie landet auf einer Roadmap, eine Spezifikation wird geschrieben, das Team fängt an zu bauen. Discovery ist, wenn sie überhaupt stattfindet, eine Handvoll Workshops und ein Foliensatz. Danach wird das Falsche effizient gebaut, und das ist der teuerste Fehlermodus überhaupt, weil es einen vollen Lieferzyklus dauert, bis es jemand merkt.

*So löse ich das:* Discovery ist kontinuierlich, niemals eine Phase. Meine Arbeitsannahme ist, dass die meisten Produktentscheidungen gar keinen Umsatz erzeugen werden, in mindestens der Hälfte der Fälle, vielleicht in dreiviertel. Die einzige rationale Antwort darauf ist, jede Wette so klein und günstig zu halten, dass ein Irrtum überlebbar und schnell erkennbar bleibt. Ich löse die größte Unsicherheit zuerst auf, mit dem billigsten Instrument, das sie klären kann: ein Prototyp, ein paar echte Kundengespräche, ein Klickdummy, manchmal nur eine Tabelle. Ein MVP ist der kleinste Schnitt, der die größte offene Frage beantwortet, nicht das erste Release, auf das sich alle einigen können.

**2. Discovery findet ohne die beiden Menschen statt, die Lösungen gut machen.**

Der Product Owner zieht mit den Stakeholdern los und kommt mit Anforderungen zurück. Die Entwicklung sieht die Idee zum ersten Mal im Refinement, wenn ihre Form längst feststeht. Das Design bekommt einen Flow zum Hübschmachen. Von beiden wird danach Commitment für eine Lösung erwartet, an deren Findung sie nicht beteiligt waren, und die beste technische Option, die nur der Lead Engineer hätte vorschlagen können, taucht nie auf.

*So löse ich das:* Ich halte ein festes Discovery-Kernteam aus mindestens mir, einem Product Designer und der technischen Führung. Kein Ritual, eine Gewohnheit. Entwicklerinnen und Entwickler, die das Kundenproblem früh sehen, bringen Lösungen mit, die niemand spezifiziert hätte, und Designer, die bei der Problemformulierung dabei sind, hören auf, Dekoration zu liefern. Beide nehmen bei mir regelmäßig an Kundenworkshops und Jour Fixes teil.

**3. Arbeit kommt als Dekret statt als Problem.**

Eine Featureliste kommt von der Geschäftsleitung oder von den lautesten Stakeholdern. Dem Team wird gesagt, was es bauen soll, statt was es erreichen soll, das alte Output-statt-Outcome-Dilemma. Und niemand ist eingeladen, mit etwas Besserem zurückzukommen, oder mit der Erkenntnis, dass man es gar nicht bauen sollte.

*So löse ich das:* Ich bringe dem Team das Problem, den Kunden und die Evidenz, und ich verhandle über Outcomes statt über Output. Das setzt voraus, ein unaufgeregtes Gespräch mit einem Stakeholder führen zu können, dessen Lieblingsfeature ich gerade ablehne, und das ist eine Disziplin, kein Charakterzug. Es setzt außerdem Messung voraus, denn ohne Metriken sind Entscheidungen nicht widerlegbar, und dann gewinnt automatisch die lauteste Stimme. Am wichtigsten wird das, wenn die Stakeholder über Abteilungen und Landesgesellschaften verteilt sitzen und jede Seite ihre eigene lokale Wahrheit darüber hat, was der Kunde will.

**4. Das Ergebnis sind Söldner statt Missionare.**

Teams, die Tickets abarbeiten, ohne daran zu glauben. Niemand widerspricht mehr einer schwachen Idee, weil Widerspruch noch nie etwas am Ergebnis geändert hat. Die stärksten Entwickler gehen zuerst, weil sie diejenigen mit Alternativen sind.

*So löse ich das:* Indem ich Teams das Problem und genug Kontext gebe, um es wirklich zu besitzen, und indem ich die Struktur repariere, die sie überhaupt erst zu Söldnern gemacht hat. Bei EMIL habe ich eine 17-köpfige Lieferorganisation übernommen, die stand und ihre erfahrensten Entwickler verlor. Ich habe sie in Teams umgebaut, die etwas von Anfang bis Ende verantworten konnten. Die Geschwindigkeit kam zurück, das Vertrauen der Kunden kam zurück, und aus einer fast vollständigen Abwanderung wurde ein einziger Abgang.

**5. Hinterher kann niemand sagen, ob es funktioniert hat.**

Das Feature ist live, die Release Note ist raus, das Team ist weiter. Ein halbes Jahr später kann niemand sagen, ob sich etwas verändert hat, und dieselbe Diskussion beginnt von vorn, mit denselben Meinungen und ohne neue Evidenz.

*So löse ich das:* Ich definiere vor dem Bauen, was als Erfolg gelten würde, und ich instrumentiere das Produkt so, dass die Antwort beobachtet statt diskutiert werden kann. Auf der Plattform, die ich bei Rohde & Schwarz verantwortet habe, habe ich so lange darauf gedrängt, an den Kundenworkshops teilzunehmen, bis ich endlich eingeladen wurde. Innerhalb einer Sitzung war klar, dass die Entwickler des Kunden völlig anders arbeiteten als von uns angenommen. Wir haben daraufhin einen kleinen, alternativen und deutlich code-lastigeren Workflow neben den geplanten gestellt und gemessen, welcher von beiden benutzt wird. Unser ursprünglich gedachter Workflow bekam exakt null Klicks. Diese Erkenntnis nach einer Woche zu haben ist mir deutlich lieber als nach einem Jahr Bauzeit.

---

## Berufserfahrung

### construct8 · Product Owner, B2B-Marktplatz Bauwirtschaft
*seit 2025 · remote*

Zweiseitiger B2B-Marktplatz, der Bauunternehmen und Bauarbeiter zusammenbringt.

- Von null auf eins: Produktvision, Strategie und Prinzipien, mit laufender Discovery
- Durchgängige Customer Journey über alle drei Seiten: Auftraggeber, Arbeitskräfte und der interne Betrieb
- KI-Unterstützung über den gesamten Funnel, vom Interview über die Auswahl bis zur Prüfung, damit eine Person das Tagesgeschäft führen kann
- Kommunikation in den Kanälen, in denen die Nutzer tatsächlich leben, WhatsApp und Telegram

### Rohde & Schwarz · Product Manager, KI- und Datenplattform
*2024 bis 2025 · München und remote*

Verantwortung für ein Modul einer zentralen KI- und Datenplattform, das multimodale Datenquellen in Datensätze für Training und Evaluation überführt.

- Volle Verantwortung von der Discovery bis in den Betrieb: Anforderungen, Backlog, Release-Definition, Rollout
- Reproduzierbare Pipelines mit vollständiger Provenienz und Audit-Trail
- Führung einer crossfunktionalen Einheit aus Architekten, Data Scientists, Entwicklung und QA über mehrere Länder hinweg
- Deployment-Zeiten von mehreren Tagen auf 20 bis 40 Minuten reduziert; Infrastruktur-Blocker aufgelöst, an dem die Entwicklung über ein Jahr hing

*Kubernetes, OpenShift, GitOps (ArgoCD), Kotlin, Python, PostgreSQL, Kafka*

### Bundesagentur für Arbeit · Product Manager, Daten- und Analyseplattform
*2023 bis 2024 · remote*

Bundesweite Analyseplattform auf einem Data-Warehouse-Stack, genutzt von Politik und Forschung.

- Automatisierte ETL-Orchestrierung und standardisiertes CI/CD eingeführt
- Stellvertretender IT-Sicherheitsbeauftragter: Compliance, Governance und Data Lineage im wiederkehrenden Auditzyklus

*Python, Django, PostgreSQL, Dagster, dbt, Kubernetes*

### EMIL Group · Product Manager, B2B-SaaS-Plattform
*2022 · Berlin*

Mandantenfähige B2B-Plattform für Versicherer, Rückversicherer, Makler und Underwriter.

- Module über Produktkonfiguration, Tarifierung, Underwriting, Policierung und Dokumenten-Workflows geliefert
- Ein Schadenmodul von null aufgebaut, ohne Spezifikation und ohne internen Präzedenzfall, Discovery direkt mit den Schadenspezialisten eines Pilotkunden
- Eine 17-köpfige Lieferorganisation in funktionierende Teams umgebaut, Geschwindigkeit und Kundenvertrauen wiederhergestellt
- Den Prozess so instrumentiert, dass der Abbruch je Prozessschritt zur führenden Priorisierungsmetrik wurde

### CLINET Platforms · Product Owner, Mobile Anwendung (iOS und Android)
*2021 bis 2022 · Berlin*

- Ein natives Produkt auf zwei Plattformen für mehrere unterschiedliche Nutzergruppen ausgeliefert
- Die Schnittstelle in die bestehende Systemlandschaft selbst implementiert
- Eine überambitionierte Roadmap auf die wichtigsten zehn Prozent gekürzt und geliefert

### Bundesdruckerei · Product Owner, nationale Gesundheitsdatenplattform
*2021 · Berlin*

Sichere Datenstrukturen und Identitätsmanagement für nationale Gesundheitsprogramme, unter höchsten Datenschutzanforderungen.

### Scheidt & Bachmann · Product Owner, Integrationsteam
*2020 bis 2021 · Mönchengladbach*

- Product Owner des Integrationsteams, nachgelagert zum Forschungsteam: Forschungsergebnisse in produktive, releasefähige Integration über Standort- und Zentralsysteme überführt
- Backlog-Verantwortung in einer vollständig nach SAFe organisierten Einheit: PI-Planning, Release-Train-Koordination, teamübergreifendes Abhängigkeitsmanagement
- Arbeit in einer Matrixorganisation über geografische und fachliche Bereiche hinweg

### AOK ITSCare · Proxy Product Owner
*2019 bis 2020 · Deutschland*

Migration eines Beschaffungsportals für rund 20.000 Mitarbeitende über drei regionale Krankenkassen, mit Katalog- und API-Integration in Bestandssysteme und Genehmigungsworkflows je Organisationseinheit.

### Enercon · Projektleitung, IT-Modernisierung
*2019 · Deutschland*

Vollständige IT-Modernisierung eines Fertigungsstandorts in der Windenergie.

---

## Gründungen

- **Kvitt Payment Solutions · Gründer und CFO (2013 bis 2018).** Mobile Payments von null aufgebaut: Anbindung des Zahlungsdienstleisters, Settlement, Onboarding, komplette Nutzererfahrung. Übernommen und betrieben von der Sparkasse. Als CFO verantwortlich für Rechnungswesen, Finanzplanung und Investorenreporting.
- **Qcrypt AG · Mitgründer und Product Owner (2016 bis 2018).** Quantensichere Verschlüsselung über eine dreischichtige Hardware- und Softwarearchitektur, ausgeliefert an Unternehmenskunden unter einer Installationsvorgabe von unter zwei Minuten.
- **Smart Soil Technologies · Mitgründer, CDO und CFO (2016 bis 2021).** Nanotechnologieprodukt vom Labor bis in die Investorenrunden; Verantwortung für Finanzen, Personal und die ERP-Einführung.

---

## KI-first als Arbeitsmodus

Mein Ansatz ist KI-first, und er verändert die Ökonomie der Produktarbeit spürbar. Mit KI-Entwicklungswerkzeugen und einem Menschen in der Schleife liefere ich heute in Teilzeit ein Arbeitsvolumen, für das vor einem Jahr ein kleines Team in Vollzeit nötig gewesen wäre: Anforderungen, Oberflächenentwurf, Frontend und Backend, automatisierte Regressions- und End-to-End-Tests, Architektur, Infrastruktur und Betrieb. Den Produktionscode schreibe ich dabei nicht selbst, ich verantworte ihn. Dafür betreibe ich ein Multi-Agenten-Framework, in dem Koordinator-, Implementierungs- und Bewertungsagenten eine gemeinsame Queue unter selbst gesetzten Leitplanken abarbeiten.

Der eigentliche Gewinn daraus ist nicht Geschwindigkeit, sondern Anschauung. Wer so nah an der Entwicklung arbeitet, erlebt am eigenen Leib, wie viel eine saubere Branching- und Merge-Strategie, verlässliche Regressionstests und ein reibungsloser GitOps-Prozess wert sind: Sie entscheiden über die Zeit vom Erkennen eines Fehlers bis zum ausgerollten Fix. Dazu kommt eine These, nach der ich arbeite. Spezialistentiefe verliert an Gewicht, weil die aktuellen Modelle sie zu großen Teilen abdecken. Was an Bedeutung gewinnt, ist Breite und Transferwissen über die gesamte Software-Wertschöpfungskette, also die Fähigkeit, Discovery, Anforderungen, Architektur, Testautomatisierung, Auslieferung und Betrieb als ein System zu sehen und an der richtigen Stelle einzugreifen.

---

## Ausbildung und Sprachen

**Diplom-Wirtschaftsingenieur**, Technische Universität Berlin, Vertiefung Logistik.

Deutsch (Muttersprache) · Englisch (C2).
