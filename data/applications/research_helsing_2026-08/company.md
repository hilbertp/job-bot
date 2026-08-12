# Helsing Deep-Dive (Stand: August 2026) — Rohmaterial für PM-Interview-Prep

## 1. Firmen-Snapshot

- **Helsing SE**, gegründet März 2021 in München von Torsten Reil, Gundbert Scherf und Niklas Köhler. Selbstbeschreibung: KI-/Software-first Verteidigungsunternehmen, verkauft nur an demokratische Regierungen ([Wikipedia](https://en.wikipedia.org/wiki/Helsing_(company))).
- Bewertung **$18 Mrd.** nach Series E ($1,8 Mrd., Juli 2026) — größte Defense-Tech-Finanzierungsrunde in der europäischen Geschichte ([Helsing Newsroom](https://helsing.ai/newsroom/helsing-raises-1-8bn-in-series-e), [CNBC](https://www.cnbc.com/2026/07/13/helsing-fund-raise-defense-18-billion.html)).
- Kumuliert über **€3 Mrd.** Kapital seit 2021; Chairman ist Spotify-Gründer Daniel Ek (via Prima Materia), im Board u.a. Ex-Airbus-CEO Tom Enders (laut Berichten Co-Chair) ([Forbes](https://www.forbes.com/sites/madhulika-pathak/2026/07/14/helsing-cofounders-fortunes-get-big-boost-from-new-18-billion-valuation/)).
- Positionierung: „Europas Anduril", souveräne europäische Alternative zu US-Anbietern; Wandel von reinem Software-Anbieter zu **Full-Stack** (Software + eigene Drohnen, Flugzeuge, UUVs, Satelliten).

## 2. Produkte und Produktlinien

### Software-Plattformen (das ursprüngliche Kerngeschäft)

- **Altra** — Recce-Strike-Softwareplattform (C4ISR): fusioniert ISR-Drohnendaten für Lagebild und Targeting; Operator koordiniert über die Altra-Groundstation Drohnenschwärme und indirektes Feuer in Echtzeit (Time-on-Target-/Sättigungsangriffe); On-Edge-AI plus störresilienter Networking-Stack; ein Operator kann HX-2-Schwärme steuern („less operators, more drones"). Seit Sept. 2025 Integration mit Systematics SitaWare-C4ISR-System (DSEI-Partnerschaft) ([Janes](https://www.janes.com/osint-insights/defence-news/security/dsei-2025-helsing-and-systematic-partner-on-swarming-recce-strike-c2-system), [Breaking Defense](https://breakingdefense.com/2025/09/helsing-systematic-partner-on-ai-enabled-swarm-capabilities-for-european-recon-strikes/)).
- **Cirra** — KI-Elektronische-Kampfführung (EW): Deep-Learning-Modul zur Echtzeit-Erkennung/Klassifikation feindlicher Emitter, adaptives Jamming. Kern des deutschen **Eurofighter EK**-Programms (Ersatz Tornado-ECR): 2023 wurden Saab Deutschland + Helsing ausgewählt, 15 Eurofighter auszurüsten; Dez. 2025 Vertrag unterschrieben — Cirra wird über 3 Jahre in Saabs Arexis-EW-Sensorik integriert, Volumen „dreistelliger Millionenbetrag"; EK-Umrüstung bis 2028, operationell Anfang der 2030er ([Overt Defense](https://www.overtdefense.com/2025/12/04/helsing-and-saab-germany-sign-contract-for-ai-powered-electronic-warfare-upgrade-on-eurofighter/), [Aviationist](https://theaviationist.com/2025/11/16/airbus-orders-saabs-arexis-eurofighter-ek/)).
- **Centaur** — KI-Luftkampf-Agent (Reinforcement Learning, trainiert in Helsings „RL-Factory"; „Jahrzehnte virtueller Luftkampferfahrung in 24 Stunden"). Meilenstein: 28. Mai und 3. Juni 2025 flog Centaur einen **Saab Gripen E** real über der Ostsee, führte BVR-Manöver gegen einen bemannten Gripen aus und gab Feuerkommandos (Sicherheitspilot an Bord); von Konzept bis Flug unter 6 Monate ([Helsing](https://helsing.ai/newsroom/helsing-ai-agent-successfully-completes-saab-gripen-e-test-flight), [Defense News](https://www.defensenews.com/global/europe/2025/06/11/saab-helsing-let-gripen-fighter-fly-with-ai-in-charge/)). Centaur ist auch der native „Pilot" des CA-1 Europa.
- **Lura** — „Large Acoustic Model" (analog zu LLMs) für Unterwasser-Überwachung: klassifiziert/lokalisiert akustische Signaturen, erkennt laut Helsing bis zu 10x leisere Signaturen als klassische Modelle, arbeitet 40x schneller als menschliche Operatoren; läuft on-edge auf SG-1 Fathom ([Helsing](https://helsing.ai/newsroom/helsing-unveils-lura-and-sg-1-fathom-autonomous-mass-to-surveil-and-defend-the-depths)).
- **FCAS AI-Backbone / CFSN**: Aug. 2023 gewann das HIS-Konsortium (Helsing + Schönhofer/Rohde & Schwarz + IBM) den Auftrag für das KI-Backbone des FCAS; Mai 2024 „operational" erklärt ([Helsing](https://helsing.ai/newsroom/helsing-commissioned-for-ai-backbone-in-fcas), [ESD](https://euro-sd.com/2024/05/major-news/38421/fcas-ai-backbone-operational/)). Nach dem FCAS-Kollaps: Deutschland vergibt **€580 Mio.** an Helsing als Prime für den **Combat Fighter System Nucleus (CFSN)** — nationale Combat-Cloud-/Referenzarchitektur, die Jets, Drohnen, Satelliten, Sensoren vernetzt; Lieferumfang: 2 experimentelle unbemannte Kampfflugzeuge, 2 Bodenkontrollstationen, Betriebssystem-/Autonomie-Software, staatseigene Referenzarchitektur; Subunternehmer MBDA Deutschland, Grob Aircraft, Hensoldt, Rohde & Schwarz; geplant 2026/27 ([TNW](https://thenextweb.com/news/helsing-germany-cfsn-combat-cloud-contract)).

### Luft (Hardware)

- **HF-1** — günstigere Loitering Munition (Sperrholzrumpf), GPS-freie KI-Navigation, gemeinsam mit ukrainischem Hersteller Terminal Autonomy gebaut; Auftrag über 4.000 Stück für die Ukraine, ~1.950 geliefert (Stand der Berichte), im Fronteinsatz bei mehreren ukrainischen Einheiten ([Defense Express](https://en.defence-ua.com/weapon_and_tech/smart_plywood_drone_helsing_hf_1_makes_difference_in_ukraine_quantities_and_operational_details_revealed-14090.html), [Odessa Journal](https://odessa-journal.com/helsing-boosts-ukraines-defense-with-delivery-of-1950-ai-loitering-munitions)).
- **HX-2** — X-Wing-Präzisionsmunition, elektrisch, ~12 kg, bis 220 km/h, bis 100 km Reichweite, Multi-Purpose-Gefechtskopf; Onboard-KI für Zielsuche/-wiedererkennung auch ohne Datenlink (EW-resistent beworben); schwarmfähig via Altra. Vorgestellt Dez. 2024. Produktion in „**Resilience Factory RF-1**" (Süddeutschland), Kapazität >1.000/Monat ([Helsing](https://helsing.ai/newsroom/helsing-to-produce-6000-additional-strike-drones-for-ukraine), [The Defense Post](https://thedefensepost.com/2024/12/03/helsing-unveils-hx-2-strike-drone/)). Feb. 2025: Zusage von 6.000 HX-2 für die Ukraine. **Aber:** Jan. 2026 Berichte über Auftragspause wegen technischer Mängel (Details unten). Positiv-Datenpunkt: US-Army-Test „Project Flytrap 5.0" (Pabradė, Litauen, Mai 2026): 15 Kills + 2 Near-Misses bei 17 Engagements (~88%) unter simulierten EW-Bedingungen, durch 2nd Cavalry Regiment ([Army Recognition](https://www.armyrecognition.com/news/army-news/2026/u-s-soldiers-test-helsing-hx-2-ai-strike-drone-achieving-15-kills-in-nato-eastern-flank-exercise), [Calibre Defence](https://www.calibredefence.co.uk/us-army-tests-helsings-hx-2-strike-drone-during-flytrap-5-0/)). Ukraine testete HX-2-Starts von Schnellbooten ([RBC Ukraine](https://newsukraine.rbc.ua/news/ukraine-tests-german-hx-2-strike-drones-launched-1778478182.html)).
- **CA-1 Europa** — autonomes unbemanntes Kampfflugzeug (UCAV), enthüllt 25. Sept. 2025; hoch-subsonisch, ~4 t, ~11 m Länge, ~500 kg Payload, 1.400-1.800 km Reichweite (Angaben lt. Wikipedia/Fact Sheet); massenproduzierbare Zelle (Entwicklung/Test bei Grob Aircraft), einzeln oder im Schwarm, nativ von Centaur geflogen; Erstflug Ziel 2027, Indienststellung ~2029 ([Helsing](https://helsing.ai/newsroom/helsing-unveils-ca-1-europa-an-autonomous-fighter-jet), [Breaking Defense](https://breakingdefense.com/2025/09/germanys-helsing-unveils-ai-enabled-ca-1-europa-ucav-targets-2029-entry-to-service/)). Auf der ILA Juni 2026: **CA-1EA** (Electronic Attack) als zweite Variante vorgestellt; Ursprungsversion heißt jetzt **CA-1KA** (Kinetic Attack); Hensoldt liefert CAIRAS-Raketenwarntechnik ([Army Recognition](https://www.armyrecognition.com/news/aerospace-news/2026/helsing-ca-1ea-electronic-attack-drone-ila-2026-berlin)).

### See (Unterwasser)

- **SG-1 Fathom** — autonomer Unterwasser-Gleiter: 1,95 m lang, 28 cm Durchmesser, ~60 kg, ohne Propeller (Auftriebs-/Flügelgleiten, 1-2 kn), bis ~1.000 m Tiefe, bis zu 3 Monate Patrouille; „Autonomous Mass": hunderte Gleiter pro Mission, ein Operator überwacht sie aus einem Maritime HQ; laut Helsing ~10% der Kosten bemannter ASW-Patrouillen. Vorgestellt Mai 2025 ([Helsing](https://helsing.ai/newsroom/helsing-unveils-lura-and-sg-1-fathom-autonomous-mass-to-surveil-and-defend-the-depths), [Naval News](https://www.navalnews.com/naval-news/2025/05/helsing-unveils-lura-and-sg-1-fathom-autonomous-mass-to-surveil-and-defend-the-depths/)).
- Reifegrad: See-Erprobungen 2025 kulminierend am BUTEC-Range (Schottland) ([Naval News](https://www.navalnews.com/event-news/dsei-uk-2025/2025/09/helsing-completes-at-sea-trials-of-integrated-fathom-lura-uuv-capability/)); UK-„Resilience Factory" in **Plymouth** mit Serienproduktion ab Nov. 2025 ([Janes](https://www.janes.com/defence-intelligence-insights/defence-news/c4isr/helsing-to-produce-sg-1-fathom-underwater-glider-at-uk-resilience-factory)); Royal Navy erprobt SG-1 im Rahmen von **Atlantic Bastion** (Nordatlantik-Unterwasser-Überwachungsnetz, formal gestartet 8. Dez. 2025), Tech-Demo Dez. 2025 ([UK Defence Journal](https://ukdefencejournal.org.uk/royal-navy-will-trial-sg-1-drone-subs-under-atlantic-bastion/)). Ursprung: Royal-Navy-Auftrag zu KI-Akustik; Hardware-Basis vom australischen Partner Blue Ocean (inzwischen übernommen).

### Weltraum

- **Loft Orbital-Partnerschaft** (Feb. 2025, Paris AI Summit): Europas erste KI-Multi-Sensor-Konstellation (optisch + RF) in LEO mit Helsing-KI on-board — autonome Erkennung/Klassifikation militärischer Fahrzeuge im Orbit statt Post-Processing am Boden; Start der Satelliten ab 2026, teils mit eigenem Kapital finanziert ([Loft Orbital](https://loftorbital.com/helsing-and-loft-orbital-join-forces-to-deploy-europes-first-ai-powered-multi-sensor-satellite-constellation-for-governmental-defense-and-security-applications/), [Calibre Defence](https://www.calibredefence.co.uk/loft-orbital-and-helsing-partner-for-ai-enabled-isr-satellites/)).
- **Kongsberg + Hensoldt** (Dez. 2025): geplante souveräne europäische ISR/T-Konstellation („großer zweistelliger" Satellitenanzahl) bis 2029 ([Janes](https://www.janes.com/osint-insights/defence-news/air/helsing-and-kongsberg-working-on-large-two-digit-number-of-satellites-for-isrt-constellation), [SatNews](https://news.satnews.com/2025/12/13/kongsberg-helsing-target-2029-for-sovereign-european-ist-constellation/)). Beide Space-Initiativen sind früh; materieller Umsatz Jahre entfernt ([Sacra](https://sacra.com/c/helsing/)).

### Land

- Kein eigenes Landsystem-Produkt, aber: Partnerschaft mit **ARX Robotics** (Sept. 2025) für ein KI-Recce-Strike-Netzwerk (Boden-Drohnen + Helsing-Software) ([Tectonic](https://www.tectonicdefense.com/helsing-and-arx-robotics-team-up/)); Übernahme von **Keybotic** (Barcelona, vierbeinige UGVs, Jan. 2026) ([Tracxn](https://tracxn.com/d/acquisitions/acquisitions-by-helsing/__yaQheqV6gU9etck87uLAlIXjcfsje_L3URRpcI9dcqM)). Historisch: Bundeswehr-Projekte zu KI-Upgrades gepanzerter Fahrzeuge ([Wikipedia](https://en.wikipedia.org/wiki/Helsing_(company))).

## 3. Finanzierung, Bewertung, Umsatzsignale

| Runde | Betrag | Datum | Lead/Investoren | Bewertung |
|---|---|---|---|---|
| Series A | ~€100 Mio. (102,5) | Nov. 2021 | Prima Materia (Daniel Ek) | n/a |
| Series B | €209 Mio. | Sept. 2023 | General Catalyst; Saab strategisch ~€75 Mio. | ~$1,7 Mrd. |
| Series C | €450 Mio. | Juli 2024 | General Catalyst, Saab, Accel, Lightspeed | ~€5 Mrd. |
| Series D | €600 Mio. | Juni 2025 | Prima Materia; + Lightspeed, Accel, Plural, GC, Saab, BDT & MSD | ~€12 Mrd. |
| Series E | $1,8 Mrd. | Juli 2026 | Dragoneer; + Lightspeed, Disruptive, Iconiq, Goldman Sachs Growth Equity, JPMorganChase, CPP Investments, GC, Plural, StepStone, Prima Materia, Accel, Greenoaks | $18 Mrd. |

Quellen: [Wikipedia](https://en.wikipedia.org/wiki/Helsing_(company)), [Helsing Series D](https://helsing.ai/newsroom/helsing-raises-eur600m-to-invest-in-european-technological-sovereignty), [Helsing Series E](https://helsing.ai/newsroom/helsing-raises-1-8bn-in-series-e), [TechCrunch](https://techcrunch.com/2026/05/11/daniel-ek-backed-defense-tech-helsing-to-raise-1-2b-at-18b-valuation/) (Mai 2026: zunächst $1,2 Mrd. geplant, Runde wurde wegen Überzeichnung auf $1,8 Mrd. vergrößert), [CNBC](https://www.cnbc.com/2026/07/13/helsing-fund-raise-defense-18-billion.html), [Bloomberg](https://www.bloomberg.com/news/articles/2026-07-13/drone-startup-helsing-raises-at-18-billion-with-goldman-backing).

**Umsatzsignale** (keine offiziellen Zahlen): Sacra schätzt 2023-Umsatz ~€9,6 Mio. (+721% YoY, v.a. Softwarelizenzen/Integrationsprojekte DE/UK/FR). Umsatzqualität ist der wunde Punkt: Bloomberg kritisierte im April 2025, Helsing verkünde Verträge verfrüht und sei bei Bewertung vs. real gebuchtem Umsatz weit gespreizt ([Militarnyi/Bloomberg-Zusammenfassung](https://militarnyi.com/en/news/bloomberg-summarizes-the-criticism-of-helsing-drones-overpriced-and-announce-contracts-prematurely/)). Substanzielle Auftragsbasis inzwischen: Eurofighter-EK/Cirra (dreistelliger Mio.-Betrag, Dez. 2025), CFSN €580 Mio. (2026), Bundeswehr-Rahmenvertrag Loitering Munitions (bis ~€1 Mrd. Helsing-Anteil), Ukraine-Aufträge (HF-1/HX-2), UK-SG-1-Programm ([Sacra](https://sacra.com/c/helsing/)). Geschäftsmodell-These: Fixpreis-Produkte mit 40-50% Zielmarge statt klassischer Cost-plus-5-10% ([Sacra](https://sacra.com/c/helsing/)).

## 4. Partnerschaften und Übernahmen

**Partnerschaften:**
- **Saab** (seit Sept. 2023, plus Investment): Gripen-E-Radar-KI, Centaur-Testflüge, Arexis/Cirra Eurofighter EK ([Saab](https://www.saab.com/newsroom/press-releases/2025/saab-achieves-ai-milestone-with-gripen-e)).
- **Airbus Defence & Space** (Juni 2024, ILA): Rahmenvertrag KI für Manned-Unmanned-Teaming des **Wingman**-Systems (unbemannter Begleiter für Eurofighter; Zielaufklärung, Jamming, Hochrisiko-Aufgaben) ([Airbus](https://www.airbus.com/en/newsroom/press-releases/2024-06-airbus-and-helsing-to-collaborate-on-artificial-intelligence-for)).
- **Mistral AI** (Feb. 2025): gemeinsame Vision-Language-Action-Modelle für Verteidigungsplattformen (natürlichsprachliche Interaktion, Umgebungsverständnis) ([Helsing](https://helsing.ai/newsroom/helsing-and-mistral-announce-strategic-partnership-in-defence-ai), [Sifted](https://sifted.eu/articles/helsing-mistral-ai-models-defence-news)).
- **Loft Orbital** (Feb. 2025) und **Kongsberg/Hensoldt** (Dez. 2025): Satelliten-ISR (siehe oben).
- **Systematic** (Sept. 2025): Altra-SitaWare-Integration. **ARX Robotics** (Sept. 2025): Boden-Recce-Strike-Netz.
- Historisch: **Rheinmetall**-Partnerschaft (2022) scheiterte 2024; 2026 schlugen Helsing/Stark Rheinmetall im Bundeswehr-Loitering-Munition-Wettbewerb ([DroneXL](https://dronexl.co/2026/01/27/helsing-stark-rheinmetall-loitering-munition/)).

**Übernahmen:**
- **Grob Aircraft** (Juni 2025, Tussenhausen bei München): Trainingsflugzeughersteller, Composite-Leichtbau; Basis für CA-1 Europa ([Helsing](https://helsing.ai/newsroom/helsing-acquires-grob-aircraft-to-accelerate-innovation-in-aerospace-and-defence), [Bloomberg](https://news.bloombergtax.com/artificial-intelligence/defense-startup-helsing-buys-grob-aircraft-to-bring-ai-to-planes)).
- **Blue Ocean MTS** (Okt. 2025, Australien): UUV-Entwickler hinter der SG-1-Fathom-Hardware ([Calibre Defence](https://www.calibredefence.co.uk/helsing-to-acquire-blue-ocean-in-drive-for-maritime-autonomy/)).
- **Keybotic** (Jan. 2026, Barcelona): vierbeinige UGVs ([Tracxn](https://tracxn.com/d/acquisitions/acquisitions-by-helsing/__yaQheqV6gU9etck87uLAlIXjcfsje_L3URRpcI9dcqM)).
- Früh: Hellsicht (Köhlers KI-Firma, eingegliedert), Design AI (2022, RL-Spezialist) ([Wikipedia](https://en.wikipedia.org/wiki/Helsing_(company))).

## 5. Strategie und Positionierung

- **Software-first → Full-Stack:** Start als „KI-Layer für bestehende Plattformen" (Sensorfusion, EW). Ab 2024 Pivot zu eigener Hardware: HF-1/HX-2 (2024), SG-1 Fathom (2025), Grob-Kauf und CA-1 Europa (2025), Satelliten (2025/26). Begründung: KI entfaltet Wert nur mit kontrollierter, massenproduzierbarer „autonomous mass"; „Resilience Factories" (RF-1 Süddeutschland, Plymouth UK, Martinsburg USA) als dezentrales, skalierbares Produktionsmodell ([TechCrunch](https://techcrunch.com/2025/02/13/germanys-helsing-doubles-down-on-drones-for-ukraine-scales-up-manufacturing), [Contrary Research](https://research.contrary.com/company/helsing)).
- **FCAS-Dynamik:** Helsing lieferte ab Aug. 2023 das KI-Backbone (HIS-Konsortium). Das deutsch-französische NGF/FCAS zerbrach am Dassault-Airbus-Streit (Workshare/Führungsrolle); Merz sprach Anfang 2026 von fundamentaler Inkompatibilität; am 8. Juni 2026 wurde das gemeinsame Kampfjet-Programm laut Berichten beendet ([Aviationist](https://theaviationist.com/2026/06/08/france-germany-end-fcas/), [DGAP](https://dgap.org/en/research/publications/restructuring-fcas)). Deutschland baut national weiter: CFSN (€580 Mio., Helsing Prime, via Politico-Enthüllung interner BMVg-Dokumente) — Helsing ist damit vom Zulieferer zum Architekt des deutschen „Combat Cloud"-Nachfolgers aufgestiegen; CA-1 Europa positioniert sich als europäische CCA-/UCAV-Antwort außerhalb klassischer Primes ([TNW](https://thenextweb.com/news/helsing-germany-cfsn-combat-cloud-contract)).
- **Wettbewerber:** **Anduril** (USA; 2025-Umsatz ~$2,1 Mrd. — mehr als das gesamte europäische Defense-VC-Funding 2025 von ~$1,5 Mrd.; Fury/Lattice als direkte Analogien zu CA-1/Altra) ([Newfund](https://blog.newfundcap.com/defense-tech-europes-next-arsenal/)); **Palantir** (Daten-/C2-Software, NATO-Verträge); **Quantum Systems** (München, Aufklärungsdrohnen Vector, Unicorn); **STARK** (Berlin, Thiel-backed, Loitering Munition „Virtus" — gewann parallel zum HX-2 den Bundeswehr-Rahmenvertrag; direktester deutscher Rivale); **ARX Robotics** (Boden-UGVs; Partner und potenzieller Rivale); **Tekever** (Portugal, UAS-Unicorn); **Rheinmetall** (klassischer Prime, verlor Loitering-Munition-Ausschreibung, eigenes FV-014-Programm). Helsings Differenzierung: europäische Souveränität, KI-Kernkompetenz (RL, Large Acoustic Models, VLA mit Mistral), Kriegserprobtheit in der Ukraine, Fixpreis + Massenproduktion.

## 6. Gründer, Leadership, Kultur, Wachstum

- **Torsten Reil (Co-CEO):** Computational Biologist (Oxford, PhD abgebrochen), gründete 2001 NaturalMotion (Spiele-/Animations-KI), 2014 für $527 Mio. an Zynga verkauft. Motivation u.a. Krim-Annexion 2014 ([Spark Daily](https://sparkdaily.co.uk/torsten-reil/), [Wikipedia](https://en.wikipedia.org/wiki/Helsing_(company))).
- **Dr. Gundbert Scherf (Co-CEO):** Ex-McKinsey-Partner, 2 Jahre Sonderberater im BMVg (Rüstungs-Digitalisierung, Aufbau CIR-nahe Strukturen); Cambridge/FU Berlin/Sciences Po ([Contrary](https://research.contrary.com/company/helsing)).
- **Niklas Köhler (President & CPO):** ML-Ingenieur, gründete 2017 Hellsicht (ging in Helsing auf). Alle drei laut Forbes nach Series E je ~$2,3 Mrd. schwer ([Forbes](https://www.forbes.com/sites/madhulika-pathak/2026/07/14/helsing-cofounders-fortunes-get-big-boost-from-new-18-billion-valuation/)).
- **Weitere:** Daniel Ek (Chairman), Tom Enders (Board, Berichten zufolge Co-Chair), Antoine Bordes (VP AI, Ex-Meta-FAIR).
- **Wachstum/Standorte:** Offiziell „900+ Mitarbeiter" (Fact Sheet Sept. 2025); LinkedIn-basierte Schätzungen niedriger (~700-760 Mitte 2026) — Vorsicht bei Zahlen. HQ München; Büros Berlin, London, Paris, Barcelona (Keybotic), Stockholm (April 2026), Tochtergesellschaften u.a. Estland; Ukraine-Präsenz seit Nov. 2022 (Memorandum mit der Ukraine Feb. 2024); Fabriken: RF-1 (Süddeutschland, geheim gehaltene Standorte wegen Sabotagegefahr), Plymouth (UK), Martinsburg/West Virginia (USA, $50 Mio., >2.000 HX-2/Monat geplant, angekündigt 14. Juli 2026) ([Helsing](https://helsing.ai/newsroom/helsing-expands-us-market-selecting-west-virginia-for-its-first-u-s-resilience-factory), [Breaking Defense](https://breakingdefense.com/2026/07/german-uav-firm-helsing-picks-west-virginia-for-first-us-manufacturing/), [JobsByCulture](https://jobsbyculture.com/blog/working-at-helsing-2026)).
- **Kultur:** Mission-getrieben („Schutz von Demokratien"), Verkauf nur an demokratische Regierungen; hohe Geheimhaltung; Talent-Mix aus Gaming (NaturalMotion-Netzwerk), ML-Forschung und Defense-Establishment. Reibung: Ethikdebatten in der europäischen Tech-Szene, Spotify-Künstlerboykotte gegen Ek (Dez. 2021 und Juli 2025 nach der Series D) ([Wikipedia](https://en.wikipedia.org/wiki/Helsing_(company))).

## 7. News-Chronik 2025/2026 (Aufträge + Kontroversen)

**Aufträge/Meilensteine:**
- Feb. 2025: 6.000 HX-2 für die Ukraine zugesagt (nach 4.000 HF-1); Mistral- und Loft-Orbital-Partnerschaften.
- Mai/Juni 2025: SG-1 Fathom/Lura-Launch; Centaur-Gripen-Flüge; Grob-Kauf; Series D €12 Mrd.
- Sept. 2025: CA-1 Europa; ARX- und Systematic-Partnerschaften; BUTEC-Trials.
- Okt.-Dez. 2025: Blue-Ocean-Kauf; Plymouth-Fabrik produziert; Atlantic Bastion (UK); Saab-Cirra-Vertrag (dreistelliger Mio.-Betrag); Kongsberg-Konstellation.
- Jan. 2026: Keybotic-Kauf; Helsing/Stark schlagen Rheinmetall.
- 25. Feb. 2026: Bundestag genehmigt **Rahmenverträge ~€4,3 Mrd.** (gedeckelt ~€1 Mrd. pro Hersteller) für Loitering Munitions; erster Festabruf ~€270 Mio.: 4.300 HX-2 (Helsing) + 2.200 Virtus (Stark), ab 2027 u.a. für die Panzerbrigade 45 in Litauen ([Janes](https://www.janes.com/osint-insights/defence-news/air/bundeswehr-is-procuring-hx-2-loitering-munition-helsing-confirms), [Army Recognition](https://www.armyrecognition.com/news/aerospace-news/2026/germany-approves-540m-medium-range-loitering-munition-procurement-from-helsing-and-stark-defence-firms), [JPost](https://www.jpost.com/defense-and-tech/article-886330)).
- 2026: CFSN-€580-Mio.-Vertrag; Japan unterzeichnet Erstvereinbarung zu HX-2 ([The Defense News](https://www.thedefensenews.com/Japan-Signs-Initial-Agreement-with-Germanys-Helsing-for-HX-2-Loitering-Munition-System/)); Juni 2026: US-Army-Flytrap-Ergebnisse + CA-1EA-Enthüllung (ILA); Juli 2026: Series E $1,8 Mrd. + US-Fabrik West Virginia.

**Kontroversen/Kritik (Interview-relevant, ehrlich einordnen):**
- **Preisgestaltung:** Ukrainischer Offizier Karpiuk: HF-1 koste €16.700 — „zu viel für eine Sperrholzdrohne", Vergleichbares ab ~€2.200 ([Militarnyi](https://militarnyi.com/en/news/bloomberg-summarizes-the-criticism-of-helsing-drones-overpriced-and-announce-contracts-prematurely/)).
- **Bloomberg-Recherche (April 2025):** Vorwürfe überteuerter Drohnen, „glitchy" Software, verfrühter Vertragskommunikation; Quellen: Ex-Mitarbeiter, Investoren, Militärs ([Wikipedia](https://en.wikipedia.org/wiki/Helsing_(company))).
- **HX-2-Wirksamkeitskrise (Jan. 2026):** Bloomberg/WELT: Ukraine und Deutschland pausierten weitere HX-2-Bestellungen nach Feldproblemen — Verbindungsabrisse unter russischem Jamming, teils fehlende beworbene KI-Komponenten (Terminal Guidance, Midcourse-Nav, visuelle Zielerfassung), Startversagen bei Trials; ukrainisches Dokument ans BMVg: nur 5 von 14 Treffern (~35,7%) ([The Defense Post](https://thedefensepost.com/2026/01/20/ukraine-pause-helsing-hx2/), [Militarnyi/WELT](https://militarnyi.com/en/news/welt-german-hx-2-drones-in-ukraine-prove-only-35-accurate/), [Kyiv Post](https://www.kyivpost.com/post/68341)).
- **Helsings Rebuttal:** Bloomberg-Bericht sei irreführend; aktive Nachfrage von sechs ukrainischen Einheiten, eine forderte 1.000 weitere Stück ([The Defense Post](https://thedefensepost.com/2026/01/23/helsing-disputes-ukraine-paused-orders/), [Helsing Statement](https://helsing.ai/newsroom/statement-from-helsing)). Gegen-Datenpunkt: 88% Erfolgsquote im US-Army-Test Mai 2026. Bundeswehr bestellte im Feb. 2026 trotzdem — aber „unter strengen Bedingungen" (Bundestag-Deckelung, Nachweispflichten) ([The Defense News](https://www.thedefensenews.com/news-details/Germany-Approves-43-Billion-For-HX-2-and-Virtus-Strike-Drone-Procurement-Under-Strict-Conditions/)).
- **Ethik:** Spotify-Boykottwellen gegen Ek (2021, 2025); generelle Debatte um autonome Waffen und „nur Demokratien"-Pledge als selbstauferlegte, nicht extern verifizierte Grenze ([Wikipedia](https://en.wikipedia.org/wiki/Helsing_(company))).

## 8. Schnelle PM-Einordnung (Talking Points)

- Produktportfolio ist eine klassische Plattform-Strategie: gemeinsamer KI-Stack (Perception, RL-Agenten, EW, Akustik) über vier Domänen ausgerollt; Hardware ist „Delivery Vehicle" für Software — Grob/Blue Ocean/Keybotic sind Distributions-Käufe für den Stack.
- Kern-Spannungsfeld fürs Interview: **Skalierungs-Narrativ vs. Feld-Evidenz** (HX-2: 35% Ukraine-Bericht vs. 88% NATO-Übung — Umgebung, Jamming-Intensität und Messmethodik unterscheiden sich massiv; sauberes Beispiel für „Metriken brauchen Kontext").
- Zweites Spannungsfeld: **Fixpreis-Massenprodukt vs. Government-Procurement-Zyklen** (verfrühte Vertragskommunikation als Symptom des Drucks, Bewertung mit Backlog zu unterlegen).
- Drittes: **Software-first-Identität vs. Capex-schwere Hardware-Realität** (Fabriken auf 3 Kontinenten, Flugzeugbau bis 2029 — Execution-Risiko, das eher Airbus- als SaaS-Muskeln braucht).

## KEY FACTS
- Helsing wurde März 2021 in München von Torsten Reil, Gundbert Scherf und Niklas Köhler gegründet und ist mit $18 Mrd. Bewertung (Series E, Juli 2026, $1,8 Mrd., Lead Dragoneer) Europas wertvollstes Defense-Tech-Startup.
- Funding-Historie: Series A ~€100 Mio. (Prima Materia, 2021), B €209 Mio. (2023), C €450 Mio. bei €5 Mrd. (2024), D €600 Mio. bei €12 Mrd. (Juni 2025), E $1,8 Mrd. bei $18 Mrd. (Juli 2026); kumuliert über €3 Mrd.; Daniel Ek ist Chairman.
- Produktlinien: Software (Altra Recce-Strike/C4ISR, Cirra EW, Centaur KI-Pilot, Lura Large Acoustic Model, CFSN Combat Cloud), Luft (HF-1, HX-2, CA-1 Europa UCAV), See (SG-1 Fathom Gleiter), Space (Loft-Orbital- und Kongsberg-Konstellationen).
- HX-2: 12 kg X-Wing-Loitering-Munition, 100 km Reichweite, 220 km/h, schwarmfähig via Altra, produziert in 'Resilience Factory' RF-1 (>1.000/Monat); 6.000 Stück für die Ukraine zugesagt (Feb. 2025) nach 4.000 HF-1 (mit Terminal Autonomy gebaut).
- Jan. 2026: Bloomberg/WELT berichteten, Ukraine und Deutschland pausierten HX-2-Nachbestellungen wegen Jamming-Anfälligkeit, fehlender KI-Komponenten und nur 5/14 Treffern (~35,7%); Helsing bestritt dies (Nachfrage von 6 ukrainischen Einheiten).
- Gegenläufig: Beim US-Army-Test 'Project Flytrap 5.0' in Litauen (Mai 2026) erzielte die HX-2 15 Kills bei 17 Engagements (~88%) unter simulierten EW-Bedingungen; Juli 2026 kündigte Helsing seine erste US-Fabrik in Martinsburg, West Virginia an ($50 Mio., >2.000 HX-2/Monat).
- Feb. 2026: Bundestag genehmigte Rahmenverträge über ~€4,3 Mrd. für Loitering Munitions an Helsing (HX-2) und STARK (Virtus), gedeckelt ~€1 Mrd. pro Hersteller; erster Abruf ~€270 Mio. für 4.300 HX-2 + 2.200 Virtus, ab 2027 u.a. für Panzerbrigade 45 in Litauen; Rheinmetall verlor die Ausschreibung.
- Centaur flog Ende Mai/Anfang Juni 2025 real einen Saab Gripen E über der Ostsee (BVR-Manöver gegen bemannten Gripen, Feuerkommandos) — von Konzept bis Flug unter 6 Monate; Saab ist auch strategischer Investor (~€75 Mio. seit 2023).
- Cirra wird als KI-EW-Modul in Saabs Arexis-Suite für das deutsche Eurofighter-EK-Programm integriert (15 Jets, Tornado-ECR-Ersatz); Vertrag Dez. 2025 im dreistelligen Millionenbereich, EK-Fähigkeit bis 2028, operationell Anfang 2030er.
- SG-1 Fathom: 1,95 m / ~60 kg Unterwasser-Gleiter, bis 3 Monate Patrouille, mit Lura (Large Acoustic Model, laut Helsing 10x leisere Signaturerkennung, 40x schneller als Menschen); Royal Navy erprobt es im Atlantic-Bastion-Programm, Serienproduktion in Plymouth seit Nov. 2025.
- CA-1 Europa: eigenes autonomes Kampfflugzeug (UCAV, ~4 t, hoch-subsonisch), enthüllt Sept. 2025, entwickelt bei der übernommenen Grob Aircraft; Erstflug 2027, Zieldatum Indienststellung 2029; ILA Juni 2026 zweite Variante CA-1EA (Electronic Attack) vorgestellt.
- Übernahmen: Grob Aircraft (Juni 2025), Blue Ocean MTS (Okt. 2025, UUV-Hardware), Keybotic (Jan. 2026, vierbeinige UGVs); früh Hellsicht und Design AI.
- Partnerschaften: Airbus (Wingman-MUT, Juni 2024), Mistral AI (Vision-Language-Action-Modelle, Feb. 2025), Loft Orbital (KI-ISR-Satelliten ab 2026), Kongsberg/Hensoldt (europäische ISR/T-Konstellation bis 2029), Systematic (Altra+SitaWare), ARX Robotics; Rheinmetall-Partnerschaft von 2022 scheiterte 2024.
- FCAS: Helsing lieferte ab Aug. 2023 das KI-Backbone (HIS-Konsortium mit Rohde&Schwarz-Tochter SSE und IBM); nach dem Dassault-Airbus-Zerwürfnis und dem berichteten Ende des gemeinsamen NGF (Juni 2026) wurde Helsing Prime des deutschen €580-Mio.-CFSN-Combat-Cloud-Programms (2 experimentelle UCAVs, Autonomie-OS, staatliche Referenzarchitektur; Subs: MBDA DE, Grob, Hensoldt, Rohde&Schwarz).
- Umsatz intransparent: Sacra schätzt 2023 nur ~€9,6 Mio. Umsatz; Bloomberg kritisierte im April 2025 überteuerte Drohnen (HF-1 €16.700 vs. ~€2.200 Vergleichspreis) und verfrüht kommunizierte Verträge; Geschäftsmodell zielt auf Fixpreis mit 40-50% Marge statt Cost-plus.
- Wettbewerber: Anduril (2025-Umsatz ~$2,1 Mrd., mehr als das gesamte europäische Defense-VC-Funding), Palantir, Quantum Systems, STARK (Thiel-backed, direktester deutscher Rivale), ARX Robotics, Tekever, Rheinmetall; Helsing positioniert sich als souveräne europäische Full-Stack-Alternative.
- Gründerprofile: Reil (Oxford-Biologe, NaturalMotion für $527 Mio. an Zynga verkauft), Scherf (Ex-McKinsey-Partner, Ex-BMVg-Sonderberater), Köhler (ML-Ingenieur, Hellsicht-Gründer); laut Forbes nach Series E je ~$2,3 Mrd. Vermögen.
- Organisation: offiziell 900+ Mitarbeiter (Sept. 2025; LinkedIn-Schätzungen ~700-760 Mitte 2026); Standorte München (HQ), Berlin, London, Paris, Barcelona, Stockholm (April 2026), Estland; Ukraine-Präsenz seit Nov. 2022; Fabriken in Süddeutschland, Plymouth und West Virginia; Produktionsstandorte teils geheim wegen Sabotagegefahr.
- Ethik/Kontroversen: Verkaufs-Pledge nur an Demokratien; Spotify-Künstlerboykotte gegen Daniel Ek (2021 und Juli 2025); laufende Debatte um autonome Waffen; Japan unterzeichnete 2026 eine Erstvereinbarung zur HX-2.

## SOURCES
- https://en.wikipedia.org/wiki/Helsing_(company)
- https://helsing.ai/newsroom/helsing-to-produce-6000-additional-strike-drones-for-ukraine
- https://helsing.ai/newsroom/helsing-raises-1-8bn-in-series-e
- https://helsing.ai/newsroom/helsing-raises-eur600m-to-invest-in-european-technological-sovereignty
- https://helsing.ai/newsroom/helsing-unveils-lura-and-sg-1-fathom-autonomous-mass-to-surveil-and-defend-the-depths
- https://helsing.ai/newsroom/helsing-ai-agent-successfully-completes-saab-gripen-e-test-flight
- https://helsing.ai/newsroom/helsing-unveils-ca-1-europa-an-autonomous-fighter-jet
- https://helsing.ai/newsroom/helsing-acquires-grob-aircraft-to-accelerate-innovation-in-aerospace-and-defence
- https://helsing.ai/newsroom/helsing-and-mistral-announce-strategic-partnership-in-defence-ai
- https://helsing.ai/newsroom/helsing-commissioned-for-ai-backbone-in-fcas
- https://helsing.ai/newsroom/helsing-expands-us-market-selecting-west-virginia-for-its-first-u-s-resilience-factory
- https://helsing.ai/newsroom/statement-from-helsing
- https://thedefensepost.com/2026/01/20/ukraine-pause-helsing-hx2/
- https://thedefensepost.com/2026/01/23/helsing-disputes-ukraine-paused-orders/
- https://militarnyi.com/en/news/welt-german-hx-2-drones-in-ukraine-prove-only-35-accurate/
- https://militarnyi.com/en/news/bloomberg-summarizes-the-criticism-of-helsing-drones-overpriced-and-announce-contracts-prematurely/
- https://www.kyivpost.com/post/68341
- https://www.armyrecognition.com/news/army-news/2026/u-s-soldiers-test-helsing-hx-2-ai-strike-drone-achieving-15-kills-in-nato-eastern-flank-exercise
- https://www.calibredefence.co.uk/us-army-tests-helsings-hx-2-strike-drone-during-flytrap-5-0/
- https://www.cnbc.com/2026/07/13/helsing-fund-raise-defense-18-billion.html
- https://techcrunch.com/2026/05/11/daniel-ek-backed-defense-tech-helsing-to-raise-1-2b-at-18b-valuation/
- https://www.bloomberg.com/news/articles/2026-07-13/drone-startup-helsing-raises-at-18-billion-with-goldman-backing
- https://sacra.com/c/helsing/
- https://www.navalnews.com/event-news/dsei-uk-2025/2025/09/helsing-completes-at-sea-trials-of-integrated-fathom-lura-uuv-capability/
- https://www.janes.com/defence-intelligence-insights/defence-news/c4isr/helsing-to-produce-sg-1-fathom-underwater-glider-at-uk-resilience-factory
- https://ukdefencejournal.org.uk/royal-navy-will-trial-sg-1-drone-subs-under-atlantic-bastion/
- https://www.defensenews.com/global/europe/2025/06/11/saab-helsing-let-gripen-fighter-fly-with-ai-in-charge/
- https://www.saab.com/newsroom/press-releases/2025/saab-achieves-ai-milestone-with-gripen-e
- https://www.airbus.com/en/newsroom/press-releases/2024-06-airbus-and-helsing-to-collaborate-on-artificial-intelligence-for
- https://loftorbital.com/helsing-and-loft-orbital-join-forces-to-deploy-europes-first-ai-powered-multi-sensor-satellite-constellation-for-governmental-defense-and-security-applications/
- https://www.janes.com/osint-insights/defence-news/air/helsing-and-kongsberg-working-on-large-two-digit-number-of-satellites-for-isrt-constellation
- https://www.calibredefence.co.uk/helsing-to-acquire-blue-ocean-in-drive-for-maritime-autonomy/
- https://tracxn.com/d/acquisitions/acquisitions-by-helsing/__yaQheqV6gU9etck87uLAlIXjcfsje_L3URRpcI9dcqM
- https://breakingdefense.com/2025/09/germanys-helsing-unveils-ai-enabled-ca-1-europa-ucav-targets-2029-entry-to-service/
- https://www.armyrecognition.com/news/aerospace-news/2026/helsing-ca-1ea-electronic-attack-drone-ila-2026-berlin
- https://thenextweb.com/news/helsing-germany-cfsn-combat-cloud-contract
- https://euro-sd.com/2024/05/major-news/38421/fcas-ai-backbone-operational/
- https://theaviationist.com/2026/06/08/france-germany-end-fcas/
- https://dgap.org/en/research/publications/restructuring-fcas
- https://www.janes.com/osint-insights/defence-news/air/bundeswehr-is-procuring-hx-2-loitering-munition-helsing-confirms
- https://www.armyrecognition.com/news/aerospace-news/2026/germany-approves-540m-medium-range-loitering-munition-procurement-from-helsing-and-stark-defence-firms
- https://www.thedefensenews.com/news-details/Germany-Approves-43-Billion-For-HX-2-and-Virtus-Strike-Drone-Procurement-Under-Strict-Conditions/
- https://dronexl.co/2026/01/27/helsing-stark-rheinmetall-loitering-munition/
- https://www.jpost.com/defense-and-tech/article-886330
- https://breakingdefense.com/2026/07/german-uav-firm-helsing-picks-west-virginia-for-first-us-manufacturing/
- https://www.overtdefense.com/2025/12/04/helsing-and-saab-germany-sign-contract-for-ai-powered-electronic-warfare-upgrade-on-eurofighter/
- https://theaviationist.com/2025/11/16/airbus-orders-saabs-arexis-eurofighter-ek/
- https://www.janes.com/osint-insights/defence-news/security/dsei-2025-helsing-and-systematic-partner-on-swarming-recce-strike-c2-system
- https://breakingdefense.com/2025/09/helsing-systematic-partner-on-ai-enabled-swarm-capabilities-for-european-recon-strikes/
- https://www.forbes.com/sites/madhulika-pathak/2026/07/14/helsing-cofounders-fortunes-get-big-boost-from-new-18-billion-valuation/
- https://research.contrary.com/company/helsing
- https://en.defence-ua.com/weapon_and_tech/smart_plywood_drone_helsing_hf_1_makes_difference_in_ukraine_quantities_and_operational_details_revealed-14090.html
- https://odessa-journal.com/helsing-boosts-ukraines-defense-with-delivery-of-1950-ai-loitering-munitions
- https://www.thedefensenews.com/Japan-Signs-Initial-Agreement-with-Germanys-Helsing-for-HX-2-Loitering-Munition-System/
- https://newsukraine.rbc.ua/news/ukraine-tests-german-hx-2-strike-drones-launched-1778478182.html
- https://www.tectonicdefense.com/helsing-and-arx-robotics-team-up/
- https://jobsbyculture.com/blog/working-at-helsing-2026
- https://blog.newfundcap.com/defense-tech-europes-next-arsenal/
- https://techcrunch.com/2025/02/13/germanys-helsing-doubles-down-on-drones-for-ukraine-scales-up-manufacturing
