# Freelance Project Portals by Region (freelancermap equivalents)

Research 2026-07-17. Goal: find the same quality of freelance/contract PROJECT marketplace
as freelancermap (DACH) for other regions, for a senior PM / PO / Fractional-CPO profile,
EN + DE, remote / Limassol-based.

**Two types** (matters for the bot):
- **OPEN BOARD** = public, browsable/searchable project feed, apply per mission. Like
  freelancermap. **Scrapeable / integrable into jobbot.**
- **VETTED** = application-gated; you join once, they match/push you. No open feed to scrape.
  Action = create a profile, not scrape.

## DACH (baseline, for reference)
- **freelancermap** (have it), freelance.de (scraper disabled, robots), GULP, SOLCOM, Etengo,
  Hays, 12punkt5, Questax, Ferchau. All OPEN boards.

## UK / Ireland
- **YunoJuno** — OPEN-ish. Closest quality equivalent. Mid-senior, day-rate transparent
  (avg £379/day, strategy ~£520). IR35/contracts/payments handled. Tech + strategy + product.
- **Worksome** — VETTED. UK + Denmark + US; 4% fee; on-site + remote.
- **JobServe** — OPEN. Long-running UK/IE IT-contract board.
- **Technojobs** — OPEN. UK IT permanent + contract.
- CW Jobs (contract filter), Outsourcery — OPEN, lower signal.

## France
- **Free-Work** (ex Freelance-Info / freelance-info.fr) — OPEN board, **the closest
  freelancermap clone in FR**: IT contract missions, browsable, TJM (day rate) shown.
- **Malt** — semi-open (public freelancer profiles + client-initiated + some mission feed).
  Europe's largest; dominant FR/DE/ES. Generalist incl. product.
- **Comet** — VETTED. Tech & data, high rates, long missions, big-group clients.
- **Crème de la Crème** — VETTED, selective, digital/tech.
- LeHibou, 404Works, Cherrypick — FR IT freelance.

## Benelux / Netherlands
- **Striive** (ex Nétive/Brainnet) — marketplace via brokers; NL/BE public-sector + corporate
  contract tenders. Semi-open.
- **Malt** — active in BE/NL.
- Hoofdkraan, Jellow, Freep.nl — NL freelance boards (OPEN, mostly Dutch-language).

## Nordics (SE/DK/NO/FI)
- **Brainville** — OPEN board, **largest independent Nordic project marketplace** (18k+
  freelancers/consultancies); browsable open assignments, some in English. Closest
  freelancermap-equivalent for the Nordics.
- **Onsiter / Right People Group** — semi-open; IT + business consultants across Europe.
- **Verama** (Ework Group's platform) — VETTED-ish; large enterprise/public frameworks.
- Cinode, A-Society — SE consultant networks.

## Iberia / Southern EU
- **Malt** — dominant in Spain.
- **Shakers** — ES, tech/product squads.
- **Outvise** — VETTED; consulting/telco/digital, ES + MENA + global.

## US
- **Braintrust** — OPEN-ish, user-owned network; browsable jobs, no talent-side fee.
- **Contra** — OPEN, commission-free; product/design/marketing.
- **Toptal** — VETTED (top 3%); enterprise clients, 2-5x rates; strong PM/management-consultant
  verticals.
- **A.Team** — VETTED; senior product + eng squads, AI-first framing.
- **Catalant** — VETTED; high-end business/strategy consulting (ex-McKinsey tier), enterprises + PE.
- **Business Talent Group (BTG)** — VETTED; high-end management consulting, corporates + PE.
- Gigster, Graphite — VETTED tech/product.

## Global consulting-tier (for the Fractional CPO / interim-exec angle)
- **Malt Strategy** (ex COMATCH) — VETTED; independent management consultants, EU-wide.
- **Movemeon** — VETTED; ex-consultants / commercial leaders.
- **Consultport** — VETTED; digital transformation / interim.
- **Expert360** — VETTED; APAC/AU strategy + transformation.
- **Talmix, Outvise, Graphite** — VETTED expert networks.

## Recommendation for Philipp
**Sign up (VETTED, push you high-value remote mandates, worth the one-time profile):**
Toptal (product-manager vertical), Malt (pan-EU incl. DE, one profile covers FR/ES/BENELUX),
Malt Strategy + Catalant + BTG + Movemeon (all for the Fractional-CPO track), Braintrust, A.Team.

**Integrate into jobbot (OPEN boards, scrapeable, same pattern as Remotive/RemoteOK/Himalayas):**
Malt (search/mission feed), Free-Work (FR IT, has EN + remote filter), Brainville (Nordics,
EN assignments), YunoJuno, JobServe, Braintrust, Contra.
Priority order by remote-senior-PM yield: **Malt > Free-Work > Brainville > Braintrust > Contra > YunoJuno.**

**Caveats:** many VETTED platforms gate by residence/tax entity — Cyprus/EU base is fine for
Malt/Free-Work/Brainville; US platforms (Braintrust/Contra/Toptal) accept international but
some client contracts prefer US-timezone. Verify per-platform on signup.


## Endpoint-Discovery-Ergebnis (2026-07-17, verifiziert per curl)

**INTEGRIERT in jobbot (live):**
- **Free-Work** — JSON-API `/api/job_postings?contracts=contractor&searchKeywords=...` (hydra); Tagessaetze, remoteMode-Feld; 335 PO-Contractor-Missionen zum Testzeitpunkt.
- **Braintrust** — JSON-API `app.usebraintrust.com/api/jobs/?search=...` (DRF); Budget-Felder in USD (gut fuer die 150k-US-Schwelle), Detail-Endpoint fuer Beschreibungen.
- **Brainville** — HTML `/HittaKonsultuppdrag?Text=...&lang=en`; anonym max 5 Karten/Query + Gesamtzahl, Abdeckung ueber mehrere Keywords; Detailseiten oeffentlich.

**GATED (bestaetigt, NICHT scrapebar -> VETTED-Route):**
- **Malt** — Cloudflare-Challenge auf allem; Partner-API nur Invoices/SCIM. Malt ist client-initiated: Missionen erscheinen nur im eingeloggten Dashboard. Aktion: Profil anlegen; optional spaeter Brave-CDP-Automation des eigenen Dashboards.
- **Contra** — Job-Feed login-gated (persistierte GraphQL-Queries); anonyme Daten sind eingefrorene SEO-Listen (13 Monate alt).
- **YunoJuno** — Briefs login-gated.
