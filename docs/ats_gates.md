# ATS Automatic Gates, and How to Tailor CVs to Them

Research date: 2026-08-13. Market scope: Germany, EU-remote, Cyprus. Both
permanent roles via company career sites and freelance mandates via agencies.

Method: eight parallel research agents against vendor documentation (Workday,
Oracle, SAP, Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Personio,
Textkernel, Bullhorn, LinkedIn), the EU legal texts, recruiter practitioner
sources, and the Harvard Business School "Hidden Workers" study. Plus direct
measurement against our own rendered PDFs, which is where the sharpest findings
came from.

---

## The Headline, Because It Inverts The Common Advice

**No mainstream applicant tracking system automatically rejects anyone based on
the content of their CV.** Not on keywords, not on formatting, not on employment
gaps. Every documented automatic rejection path in every system we examined runs
on **structured answers to application-form questions**, never on free CV text.

The "75% of CVs are auto-rejected by keyword scanners" figure has no source. It
traces to marketing by Preptel, a resume-tool vendor that shut down in August
2013 without ever publishing a study, dataset, or method. The number circulates
as 70%, 75% and 88%, which is itself the tell: a real statistic has one value and
one method.

This does not mean the CV is unimportant. It means the CV's job is different from
what folklore says. The CV must:

1. **Parse cleanly**, so the structured record behind you is complete.
2. **Contain literal keyword tokens**, so a recruiter's boolean search finds you.
3. **Mirror the requisition's own wording**, so AI ranking sorts you into the
   pile a human actually opens.
4. **Read well in seven seconds**, because in the DACH market a human very
   probably is reading it.

What actually rejects you automatically is the answer you give to a dropdown.

---

## 1. The Five Layers of Gating

Think of it as five layers. Only one of them rejects. The others decide whether
you are ever seen.

| Layer | Mechanism | Rejects? | Runs on |
|---|---|---|---|
| 0 | Submission-time required fields | Blocks submission | Form completeness |
| 1 | **Knockout / screening questions** | **Yes, terminal** | Structured answers |
| 2 | CV parsing into structured fields | No, but silently empties your record | The PDF text layer |
| 3 | AI ranking and match grading | No, buries you | Parsed profile vs requisition |
| 4 | Recruiter database search | No, you are simply never retrieved | Literal string index |

Layer 1 is the only true auto-reject. Layers 2 to 4 are where a well-built CV
actually earns its keep, and where most candidates lose without ever knowing.

---

## 2. Layer 1: Knockout Questions, The Only Real Auto-Reject

Universal properties across every system examined:

- **Always opt-in.** Never default-on. An admin configures a rule per job.
- **Only on closed-format questions.** Yes/No, single-select, multi-select.
  Free-text and file uploads cannot trigger a knockout, because there is no rule
  to match them against.
- **The candidate is usually not told.** Greenhouse does not even notify the
  hiring team of auto-rejected applicants.

### What The Questions Actually Are

From five live Product Manager / Product Owner application forms pulled from
Greenhouse's public board API (GetYourGuide, N26, Celonis, SumUp, GitLab), the
required machine-readable fields, in observed frequency:

| Field | Frequency | Auto-reject eligible |
|---|---|---|
| Current location / country of residence | 5/5 | Yes if select |
| Salary expectation | 4/5 | Yes when bracketed select |
| Work authorisation / visa sponsorship | 3/5 | Yes |
| Non-compete / prior-employment restrictions | 2/5 | Yes |
| Notice period | 1/5 | Text, usually not |
| Onsite / hybrid willingness | 1/5 | Yes |
| Language proficiency level | 1/5 | Yes |
| Most recent employer and job title | 1/5 | Structured, sorted on directly |

**Notably absent: not one of the five asked for years of product management
experience.** The "6+ years in product management" line lives in the job
description prose and is enforced by a human eye, not by a rule. The exception is
JOIN (Berlin, common in European SMBs), which uniquely supports **numeric and
date** knockouts, so a years-of-experience field genuinely can auto-reject there.

### Per-Platform Auto-Reject Matrix

| System | Auto-rejects on CV content | Knockout auto-reject | Notes |
|---|---|---|---|
| Workday | No | Yes, customer-built via calculated fields and condition rules | #1 Fortune 500 ATS |
| Oracle Taleo | No | Yes, disqualification questions exit you mid-application | ACE model tiers, does not reject |
| SAP SuccessFactors | No | Yes, disqualifier questions plus a Required Score threshold | Dominant in DACH enterprise |
| iCIMS | No | Yes, auto-assigns "Initial DNQ" status | Role Fit AI ranks only |
| Greenhouse | No | Yes, Yes/No + single/multi-select only, Plus/Pro tiers | Exact-match search |
| Lever | No | Yes, but only with the Advanced Automation add-on | |
| Ashby | No | Yes, evaluated only at submission | AI explicitly never ranks or rejects |
| SmartRecruiters | No | Yes, knockout screening questions | Match score contractually cannot auto-reject |
| Workable | No | Yes, Yes/No questions only | **See exception below** |
| Teamtailor | No dedicated reject action | "Smart move" can route on resume keywords | Only resume-keyword automation found |
| Recruitee | No | Yes | |
| JOIN | No | Yes, incl. **numeric and date** | Berlin, European SMBs |
| Personio | No | **Disputed, see caveat** | Dominant German SMB ATS |
| LinkedIn | No | Yes, "Must-have qualification" + opt-in auto-archive | 12 templated question types |
| Indeed | No | Yes, on its own pre-made screeners only | |

**The one genuine exception:** Workable's "Workable Agent" (paid add-on) scores
every candidate 0-100 against an ideal-candidate profile across 14 categories and
**auto-disqualifies poor fits with a reason attached**. This is the only product
found that autonomously acts on a resume-derived judgement. Workable-hosted
applications therefore deserve the most aggressive mirroring of the job
description's requirement language.

> **Unresolved contradiction, flagged rather than smoothed over.** Two of our
> researchers disagreed on Personio: one found its own community docs saying
> automatic rejection is impossible and every rejection is a manual action; the
> other found documentation of an "automated screening" feature that
> auto-disqualifies on structured attributes and delays the rejection email to
> 12:00 the next working day. The likeliest explanation is that the feature
> shipped between the two sources' dates. The adversarial verification pass that
> would have settled this **did not run** because the session hit its usage
> limit. Treat Personio as "may auto-reject on form answers, verify before
> relying on it". This matters because Personio covers a large slice of German
> Mittelstand postings.

---

## 3. Layer 2: Parsing, Where You Become Invisible Rather Than Rejected

Parsing failure does not reject you. It empties the structured record that every
filter, score and recruiter search actually runs on. Greenhouse still creates the
candidate record when a resume fails to parse; the recruiter just gets blank
fields.

**The one genuinely fatal surface is contact information.** Daxtra's parser
*fails outright* without a name plus at least one of phone or email. Textkernel
uses missing contact details as its canonical example of a quality finding. Name,
email and phone as ordinary body text in the first lines of page 1 is the single
non-negotiable rule.

What the evidence actually supports, separated from folklore:

| Rule | Verdict |
|---|---|
| Single column | **Real.** Textkernel's own engineering data puts well-rendered column CVs at 90% accuracy after a major ML investment, up from 62%. A 10% chance of scrambled work history is not worth it. |
| Text-layer PDF is fine | **True.** The "PDF is dangerous" rule is a 2010s artefact. All modern parsers list PDF and DOCX as first-class. Scanned/image PDFs still fail outright. |
| No tables, text boxes, graphics, skill bars | **Real.** Skill bars encode the level only visually; the parser takes the label and loses the level. |
| Contact info never in a header/footer | **Real for DOCX** (separate XML part, routinely skipped). Lower risk in PDF. |
| Standard section headings | **Real.** Parsers map to a `sectionType` enum: SUMMARY, SKILLS, WORK_HISTORY, EDUCATION, CERTIFICATIONS, LANGUAGES. Invented headings cause misclassification cascades. |
| Headings alone on their line, bold, uppercase | **Real.** OpenResume's published heuristic is literally "the only text item in the line, bolded, and uppercase". |
| Title first, then company, on one line | **Real.** Title-vs-company disambiguation is probabilistic; Textkernel exposes a `CompanyNameProbabilityInterpretation` from VeryUnlikely to Confident. |
| Consistent MM/YYYY or Month YYYY dates | **Real.** `DocumentCulture` detection drives date parsing; mixed formats destabilise it. `2020-23` is a documented cause of five years computing as one or zero. |
| Filename must be "ATS-compliant" | **Folklore.** No vendor documentation supports it. But the filename *is* an indexed searchable field in Bullhorn, so `Lastname_Firstname_Role_CV_EN.pdf` is still worth doing. |
| Jobscan / Teal "ATS scores" | **Folklore.** Keyword-overlap metrics those vendors invented. No real ATS exposes a numeric resume score and no recruiter ever sees one. |
| Keyword stuffing / white text | **Counterproductive.** Daxtra states parsers "easily see through" it, including background-coloured text. Skills are evaluated in context, with the section they were found in recorded. |

### The Insight Most PM CVs Get Wrong

Textkernel attributes every skill a `@totalMonths` and `@lastUsed`, derived from
*where in the document it was found*. A term that appears only in a Skills block
exists in the index with **zero months and no recency**, so it drops out of every
"5+ years of X" and "used in the last 2 years" recruiter filter.

PM CVs conventionally park all methodology and tool vocabulary in a skills
header. That is exactly wrong. **Every tool and method that matters must also
appear inside a dated role's bullets** so it inherits duration and recency. Keep
the skills block as a retrieval aid, but mirror the load-bearing terms down into
the roles.

Related: **overlapping date ranges do not stack.** Textkernel explicitly does not
double-count overlaps in `MonthsOfWorkExperience`. Parallel freelance mandates
plus a founder role will not add up to a bigger number, and to a human reading
the parsed timeline it looks like padding.

---

## 4. Layer 3: AI Ranking, Which Buries Rather Than Rejects

| Product | Output | Rejects? |
|---|---|---|
| Workday HiredScore | A/B/C/D grade vs requisition requirements | No. Ranks. Over 40% of Fortune 100. |
| Workday Candidate Skills Match | Four match tiers in the recruiter grid | No |
| iCIMS Role Fit | Relative tiering, heavy exact-keyword matching | No |
| SmartRecruiters SmartAssistant | 1-5 stars | No, contractually barred from automating dispositions |
| Ashby AI review | Criteria met / not met, no score | No, and explicitly never ranks |
| Workable Agent | 0-100 across 14 categories | **Yes, auto-disqualifies** |

The failure mode here is different and worse than rejection: **your application
exists but is never opened.** A C or D grade in a high-volume requisition means
nobody ever reads it.

Because HiredScore grades "reported qualifications against the specific job
requirements", the counter-play is literal overlap with the requisition's own
wording for the requirements you genuinely meet. A true qualification that is
absent from your text counts as missing.

Legal context worth knowing: *Mobley v. Workday* (N.D. Cal.) had an age-
discrimination collective preliminarily certified in May 2025 covering applicants
"scored, sorted, ranked, or screened" by Workday/HiredScore AI since September
2020. Workday represented that 1.1 billion applications were rejected through its
tools in the period. A court ordered Workday to name every employer that enabled
HiredScore.

---

## 5. Layer 4: Recruiter Search, The Gate Nobody Optimises For

This is where headhunters and agency recruiters actually work, and where keyword
absence means you are never seen at all rather than rejected.

**The dominant engines are literal-string exact-match.** Bullhorn's own knowledge
base: "Only candidates that are an exact match for the boolean statement will be
returned." Loxo: boolean searches "do not show profiles that match synonyms,
similar job titles, or skill sets." Greenhouse full-text search is documented
exact-match with no stemming.

| System | Wildcards | Synonym expansion | Notes |
|---|---|---|---|
| Bullhorn (agency standard, est. 40-50% share) | Yes, `manag*` | No | Searches 7 fields incl. **full resume text** and file attachments |
| Bullhorn + Textkernel Search & Match | Yes, plus proximity, weighting, `experience:5..10` | Taxonomy normalisation | Years of experience is a filterable numeric field |
| LinkedIn Recruiter | **No wildcards at all** | **No auto-expansion on title filter** | Stop words silently dropped from Keywords |
| Greenhouse | No | No | Smart quotes from Word break the query |
| Malt (freelance) | n/a | Yes, embedding retrieval | Genuine semantic exception |

### The Two Findings That Matter Most For This Profile

**1. "Product Manager" and "Product Owner" are different strings and do not
cross-match.** LinkedIn Recruiter's title filter does not expand to synonyms; a
search for "Product Manager" will not return "PM", "Product Lead" or "Product
Owner". Recruiters must OR them manually, and many do not. Carry both strings
verbatim.

**2. Published PM boolean strings almost always end with a NOT clause excluding
"project manager" and "program manager".** A representative library string:

```
('Product Manager' OR 'Senior Product Manager' OR 'Group Product Manager'
 OR 'Director of Product' OR 'VP Product' OR 'Head of Product')
AND ('SaaS' OR 'B2B' OR 'platform' OR 'marketplace' OR 'API')
NOT ('project manager' OR 'program manager' OR 'intern' OR 'coordinator')
```

This means project-management framing does not merely under-rank you, it
**actively removes you** from Product Manager searches. Describe project delivery
in a bullet if you must, never in a role title.

Two more retrieval mechanics with direct consequences:

- Bullhorn/Textkernel exposes **"Last Position"** and **"Recent Titles (past 4
  years)"** as separate facets. The most recent role's title is the single
  highest-leverage string on the CV. An idiosyncratic current title ("Proxy PO",
  "Delivery Lead") does not land in the Product Owner facet even if the phrase
  appears elsewhere in the document.
- LinkedIn's "Open to Work (recruiters only)" is a free lever into a bucket
  recruiters filter on first.

---

## 6. Step 2: How These Gates Are Set Up For PM and PO Roles Specifically

### The Gates PM/PO Requisitions Actually Carry

1. **Not years of experience.** Zero of five live PM forms gated on it. It sits
   in prose. Exception: JOIN-hosted postings, where numeric knockouts exist.
2. **Salary expectation**, often a bracketed select (GetYourGuide used 17 EUR
   brackets from "less than 25,000" to "more than 150,000"). A bracketed select
   is auto-reject eligible in Greenhouse. This is a live risk against a 125k-170k
   target band.
3. **Work authorisation and visa sponsorship.** The most common genuine knockout.
4. **Location / onsite willingness.** SmartRecruiters' own documented example of
   a knockout is answering "no" to "Do you want to work in an office location?"
5. **German language level.** In DACH permanent postings this is phrased as a
   CEFR level or "verhandlungssicher" (legal advice discourages requiring
   "Muttersprachler" as presumptively discriminatory under the AGG). Freelance
   briefs are less careful: a live freelancermap PO/PM mandate stated "Deutsch
   auf Muttersprachenniveau (zwingend erforderlich)".
6. **Certifications.** Mostly "preferred" tokens, and DACH product practitioners
   openly discount them. **Except on LinkedIn**, where Certifications is a
   first-class screening-question type that can be flagged must-have with
   auto-archive.

### The Token Set Recruiters String Together For PM/PO

- **Titles:** Product Manager, Senior / Group / Principal / Staff / Technical
  Product Manager, Product Owner, Head of Product, Director of Product, VP
  Product, Product Lead
- **Methodology:** Agile, Scrum, Kanban, SAFe, discovery, OKRs
- **Artifacts:** roadmap, backlog, PRD, user stories, stakeholder management,
  go-to-market
- **Tools:** Jira, Confluence, Figma, SQL, product analytics, A/B testing, API
- **Certifications:** CSPO, PSPO, SAFe POPM, Pragmatic Institute

A typical working search is title AND one or two skill tokens: `"product
manager" AND (roadmap OR backlog) AND SaaS NOT junior`.

### Where Seniority Inference Breaks

Three distinct failure points for a profile with a finance-to-product history and
interim/proxy titles:

1. **The structured "Most Recent Job Title" field** on some forms (Celonis
   requires it). No CV wording overrides it.
2. **LinkedIn's computed "Years of experience"**, derived from all dated
   positions, which over-reads total career length while saying nothing about
   product tenure.
3. **Title-string seniority parsing**, which cannot map "Proxy PO", "interim" or
   "fractional" onto a recognised product seniority band.

Mitigation: an explicit product-tenure sentence for the human, plus
product-shaped titles with the modifier **appended, not prepended**: "Product
Owner (interim)", never "Interim PO" alone.

Also: `MonthsOfWorkExperience` is computed from dates, never from a summary
sentence claiming "10+ years". The sentence is purely for the human reader.

---

## 7. The EU and DACH Legal Overlay

This is why the German market is meaningfully less automated than the US one.

- **GDPR Article 22** prohibits decisions based solely on automated processing
  with legal or similarly significant effect. Rejection from a hiring process
  qualifies.
- **The CJEU SCHUFA ruling (C-634/21, 7 Dec 2023)** extended this to *scoring
  itself* when the score plays a determining role, even with nominal human
  sign-off downstream.
- **AGG §22** reverses the burden of proof: once a rejected applicant shows
  indications of discrimination, the employer must prove none occurred. German
  employment-law commentary is uniform that this is near-impossible with an
  unexplainable AI ranking, which pushes employers toward documented human
  decisions.
- **Works councils** co-determine question scoring in German enterprises;
  SuccessFactors "Qualifizierungsfragen" scoring is a Betriebsvereinbarung
  matter.
- **Adoption is low anyway.** Bitkom's 2025 New Work survey puts AI use in German
  recruiting at roughly 11% of companies, GDPR concerns being the top barrier,
  with automated CV screening used by about a third of that minority. German
  practitioners call parser-based auto-rejection "eine Urban Legende".
- **Data deletion.** Rejected applicants' data must generally be deleted within
  3 to 6 months of the rejection letter. Being "in the database" is time-boxed
  unless you consent to a talent pool. Re-applying after 6+ months is a fresh
  record, so it is safe and should be scheduled rather than avoided.

> **Unverified, flagged.** One researcher reported that the EU AI Act's Annex III
> high-risk obligations (which cover recruitment AI) were postponed from 2 August
> 2026 to 2 December 2027 by a "Digital Omnibus" approved by the Council on 29
> June 2026, with Article 50 transparency duties still starting 2 August 2026.
> This is a post-cutoff legislative claim and the verification pass did not run.
> **Confirm against EUR-Lex before relying on it.** The direction (recruitment AI
> is Annex III high-risk) is not in doubt; the dates are.

---

## 8. Measured Against Our Own Pipeline

This section is direct measurement, not research. It produced the sharpest
findings in the whole exercise.

### Finding 1: Our Renderer Was Destroying The Contact Block

Rendering `data/base_cv.md` through the real `_render_html` + WeasyPrint path and
extracting the text layer as a parser would:

```
H I L B E R T @ T R U E - N O R T H . B E R L I N · + 3 5 7 9 4 1 0 1 6 4 4
§ W H AT I C A N D O
§ E D U C AT I O N A N D L A N G U A G E S
```

- **Email regex hits: 0.** Phone regex hits: **0.**
- `EDUCATION` heading: undetectable.

Given that Daxtra's parser *fails outright* without a name plus phone or email,
this is the worst possible place for the defect.

**Cause, isolated by controlled test:** CSS `letter-spacing`. Nothing else. The
`§` marker and `text-transform: uppercase` are harmless.

**Threshold, found by sweep:**

| letter-spacing | poppler/pdftotext | pdfminer.six | pypdf |
|---|---|---|---|
| 0 to 0.08em | parses | parses | parses |
| 0.10em | **breaks** | parses | parses |
| 0.12em and above | **breaks** | **breaks** | parses |

Our CSS used **0.12em** on the contact line and **0.16em** on section headings.
Two of three extraction engines break at those values. Capping at **0.08em**
restores email, phone and the Education heading, keeps the document at two pages,
and is visually near-indistinguishable.

Note this is a *renderer* defect, not a content defect. No amount of CV rewriting
would have fixed it.

### Finding 2: Zero Of 51 Tailored CVs Had A Parseable Skills Section

Across the real corpus in `data/applications/`, counting German and English
canonical headings as equivalent:

| Section | CVs carrying a parser-recognised heading |
|---|---|
| Experience | 48/51 (94%) |
| Education | 34/51 (66%) |
| Languages | 34/51 (66%) |
| **Skills** | **0/51 (0%)** |

75 distinct H2 headings appear across the corpus. Skills vocabulary lived under
"Kernkompetenzen", "What I can do" and similar, none of which map to the
`SKILLS` section type. This is the field that feeds recruiter skill filters and
AI skills-match.

### Finding 3: No Month Precision Anywhere

Across all 51 tailored CVs: **0 occurrences** of `MM/YYYY` or `Mon YYYY` date
ranges. 270 occurrences of "YYYY to YYYY" and 87 of "YYYY - YYYY". Year-only
dates degrade every computed field: tenure, years of experience, gap detection.

### Finding 4: The Two-Column Warning Does Not Apply To Our Renderer

Tested directly: the `column-count: 2` CSS rule extracts in correct reading
order. Worth knowing so we do not "fix" a non-problem.

---

## 9. Audit Of The New General CV

`CV general .pdf`, 2 pages, macOS Quartz text layer. Structurally this is a
large improvement and it is well-built for ATS.

**What it gets right:**

- Canonical headings: `WORK EXPERIENCE`, `SKILLS`, `EDUCATION`, `LANGUAGES`
- Both title tokens in the header line: `PRODUCT MANAGER | PRODUCT OWNER`
- Title-first role lines: `Product Manager, Rohde & Schwarz, Munich / Remote`
- 13 role ranges in `MM/YYYY - MM/YYYY`
- Email, phone, LinkedIn and GitHub all extract cleanly in both engines
- Single column, no tables, no graphics, no skill bars
- No em-dashes, no Lovable URL

**What needs fixing, in priority order:**

| # | Issue | Evidence | Fix |
|---|---|---|---|
| 1 | **Section headings are letter-spaced.** pdfminer shreds *all* of them (`W O R K   E X P E R I E N C E`, `S K I L L S`, `L A N G U A G E S`); poppler shreds `E D U C AT I O N`. | Measured, both engines | Cap letter-spacing at 0.08em in whatever generated it |
| 2 | **Degree is unclassifiable.** Only "Diplom" appears. No Master, M.Sc., or Dipl.-Ing. token. | Measured | Add "(equivalent to Master's degree)". Feeds HiredScore's "Highest degree" facet and degree knockouts |
| 3 | **Work authorisation not stated.** | Measured | Add "EU citizen, no visa sponsorship required". The most common genuine knockout |
| 4 | **`OKR` absent** (0 occurrences) | Measured | Add to a dated role bullet, not just Skills |
| 5 | **Tools live only in the Skills block** | Textkernel `@totalMonths` | Mirror Jira, Confluence, Scrum, SAFe, SQL, A/B testing into dated role bullets so they inherit duration and recency |
| 6 | **29 overlapping role-pairs.** Naive duration sum = 39.8 years; union = 20.6; CV claims 13. | Measured | Not fixable and not fatal (overlaps are not double-counted), but do not lean on stacked parallel engagements |
| 7 | Freelance umbrella uses year-only `2017 - Present` while all else is MM/YYYY | Measured | Make it `01/2017 - Present` for format consistency |
| 8 | No `Senior Product Manager` token anywhere | Measured | Consider it in the header for the 125k-170k band |
| 9 | No CEFR code for German | Measured | "German (native speaker, C2)" matches LinkedIn's Language screening shape |

---

## 10. What To Change In The Pipeline

1. **Cap `letter-spacing` at 0.08em** in `src/jobbot/generators/pipeline.py`
   (currently 0.12em and 0.16em). Free fix, no design cost, verified.
2. **Add a parse-fidelity gate** to the render step. On every generated PDF,
   extract the text layer and assert: name in first 3 lines; email and phone
   match a regex; expected section headings present verbatim; symbol-character
   ratio under 5%; no `U+FB00-FB04` ligatures. Cheap, deterministic, catches
   every documented failure mode.
3. **Lock the section headings** in `prompts/cv_tailor.md` to the canonical set.
   The prompt currently says "preserve the section order: Summary, Experience,
   Skills, Education, Languages" while the base CV has none of those headings
   except Experience. That instruction is incoherent and the corpus shows the
   model ignoring it.
4. **Mirror tools into dated bullets**, not just the Skills block.
5. **Capture screening answers as first-class artifacts.** The gates are the
   form, not the CV. Salary bracket, work authorisation, notice period, onsite
   willingness, language level. Log every answer given.
6. **Do not chase keyword density** beyond one honest mention of each relevant
   token. Parsers detect stuffing; DACH SMEs read the CV with human eyes.

---

## Caveats On This Research

- The **adversarial verification pass did not run** (session usage limit). Six
  load-bearing claims were queued for refutation and were not tested: the
  Personio contradiction, the EU AI Act timing, Greenhouse exact-match, Workday's
  Skills field behaviour, the two-column and DOCX parse-failure numbers, and the
  central no-keyword-auto-reject claim.
- The **completeness critic did not run** for the same reason.
- Two numbers reported by researchers from single secondary sources are quoted
  here only where corroborated, and are **not** relied on: "93% vs 86% parse
  accuracy for single vs two-column" and "4% DOCX vs 18% PDF parse failure".
- Where a claim rests on resume-tool vendors (Jobscan, Teal, Enhancv), that
  commercial bias is noted inline. Vendor documentation and legal texts were
  preferred throughout.
- Everything in section 8 is direct measurement and can be re-run.
