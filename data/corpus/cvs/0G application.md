# Philipp Hilbert

## Senior Product Manager | AI Infrastructure & Web3 Ecosystems | Platform Products

### Motivational Letter

0g describes a problem that I faced in my last product at Rohde & Schwarz: a clear and auditable provenance trail leading to an auditable AI model. This sentence seems clear and straightforward but it requires a lot more systems design and complexity than is apparent at first glance.

In the AI era, it is more relevant than ever to understand the full chain from birth to existence of a model. Neural networks are like human minds: they are only predictable to a certain degree. Just like in human minds, artificial neural networks have a certain degree of entropy and small differences can sometimes lead to largely different outcomes. Especially when systems and reasoning are chained together, uncertainty compounds a lot. As a consequence, the determinism we have grown accustomed to after decades of traditional web2-style software is not realistically attainable with them.

All the more, the risks that come with it need to be understood, traced back to their cause and controlled to the extent it is possible under these new constraints. Without control, we would inevitably cause unsuitable, sometimes heavily garbled results that will be argued and defended by the LLMs with a high degree of confidence. That confidence is not well earned because in the course of arguing its decisions, LLMs today have unavoidable gap filling mechanisms (hallucinations). And they do not make those gaps transparent; they go to great lengths to cover them up and to appear as if the decisions were completely rational. When interviewed, they will sometimes use post-hoc style justification like some human personalities tend to do when put to the test. So the phenomenon is not new and we have learned to be careful with those human personalities, so we need to be just as careful with the AI fallacies. To bring AI into a controllable ecosystem, you need to think the entire information and causality chain from the ground up. This requires public, transparent training data, not only the raw data but also the transformed dataset as well (filtered, normalized, augmented). Herein lies the first change to the information already. Deterministically described data transformation pipelines, and which version of them was used, need to be tracked automatically. After making the entire training data transparent, you also need to expose the modeling and training stack: which architecture was chosen? (single dense model vs mixture/tree of experts) Which optimization algorithm or reinforcement learning alignment layer was used? (human or automated reward models) Are there safety/control layers in place? (measuring the outcomes in different scenarios, audit technologies like safeAI or explainableAI)

All those decisions lead to different biases and weights. And knowing this is essential for risk assessment. Even small details like which version of a pipeline, database or algorithm was used, are important to know.

So, while the last product I shaped was in a highly regulated and sensitively secretive defense environment where even our own customers had problems talking openly to us and every business partnership needed to be documented with painful accuracy and lawyer-signed-off, the 0g product would have an entirely different approach. And therefore it requires an entirely different vision. Where before it was about legal safety and being able to prove “it was your fault”, now it’s about a maximum of transparency to enable a maximum of network effect and learning of the swarm. Yet, outcomes still need to be well understood, controlled, used to change and adapt systems. It’s still a circular learning mechanism involving different roles and actors: developers, auditors, business users, private users, governments and institutions and our own system thinkers. All of them only loosely intertwined in philosophy and goals but much more closely connected through a platform that suits the needs and goals of all of them in different and not yet fully explored use cases. Still large scale cloud storage, high performance training and inference hardware, high throughput interfaces and high availability systems are required. Still the full provenance chain must be available to auditors and still a wide range of technical tools need to be supported within only a limited amount of time to implement them. So synthesizing and distilling the way forward with high probability bets, a simple and reliable measurement system to validate or invalidate our bets with the outcomes and an ego-free pivot mentality without losing trust or motivation from the implementation teams needs to be built. The team also needs to be involved closely in the discovery process. We need to accept certain tradeoffs over others and the decisions must be transparent and reversible. The more obscure our decision-making is, the more dissatisfaction and rumor we set ourselves up for downstream of time and hierarchy. 
The top 10 % of companies innovated and develop their products completely differently from the others. This is how the likes of Adobe, Apple, Amazon etc  can continue having outstanding success while the others are mediocre at best: they discovery with the entire product team and take many, many small bets, assess, pivot and rinse and repeat. It is a good assumption that 75 % of the product decisions turn into absolutely zero revenues, so all the more it is absolutely critical, to make these decisions at a minimum of implementation cost and reduce risk ahead of time as much as possible to fail fast and cheap. Failure also has the highest information and learning density, so if we do it in an ego-free and pragmatic way, we will learn much faster than the competition.

This is the sort of thing that I excel at and that I love doing. It’s a challenge with unknown outcomes but a fulfilling and satisfying journey along a stony and foggy path. It requires a fresh yet experienced mind. It’s where visionaries, geniuses and builders come together to try and shape a vision of the future that can make or break an organization. A high achieving team effort with maximum pain and learning opportunities.

### Location

Berlin, Germany  
Limassol, Cyprus  
philipp@projuncta.com  
+357 94101644

Sample of my English language skills: https://www.youtube.com/watch?v=nt06f71lgfE  
(Quantum encryption technology featured in this video)


### Profile

More than ten years of product leadership with a strong technical foundation in AI and Web3 infrastructure, DevOps, requirements engineering and test environments. Proven ability to build stable, demoable MVPs and evolve them into scalable, production-ready platform systems. Skilled at guiding teams through uncertainty toward measurable outcomes across multiple connected product surfaces. Comfortable in regulated, high stakes environments with strong requirements around auditability, provenance and security. Pragmatic communicator fluent in English and German.

### Core strengths

* Turning uncertainty and incomplete information into clearly prioritized, achievable goals  
* Surfacing solution tradeoffs, measuring impact and pivoting based on better evidence  
* Translating complex technical and economic stakeholder priorities into clear product definitions  
* Strong stakeholder alignment without politics or drama: pure pragmatism  
* Delivery discipline across the full chain: discovery, execution, rollout, operations and support

### Web3 and DeFi expertise

* Centralized venues (CEX)
  * custody model, deposits and withdrawals, compliance and risk controls  
  * order book trading, market structure concepts and matching engine fundamentals  
  * margin and liquidation concepts as implemented in centralized risk engines  

* On-chain spot DEX mechanics
  * AMMs and concentrated liquidity: fee tiers, ticks, range positions, rebalancing incentives, v2 vs v3  
  * execution quality: routing and aggregation, multi-hop paths, exact-in vs exact-out swaps and slippage controls  
  * LP economics and risk: divergence loss, fee revenue vs volatility and arbitrage flow and its impact on LP returns  
  * MEV awareness and mitigation: sandwich risk, private transaction submission and MEV-protected RPCs, RFQ and intent-based execution where applicable  

* On-chain perpetual DEX mechanics and risk
  * margin models: isolated vs cross, leverage constraints, collateral and haircuts  
  * funding: mark price vs index price, premium index, funding rate mechanics and manipulation risk  
  * liquidation and backstops: partial liquidation, liquidation penalties, insurance fund and backstop liquidity  
  * deleveraging mechanics: ADL versus alternatives (insurance fund, backstop market makers, socialized loss)  
  * oracle dependency and pricing safety: mark price design, oracle fallbacks and circuit breakers under volatility  
  * execution models: on-chain order books, hybrid order books, vAMM-style designs and off-chain matching with on-chain settlement  

* Bridges and cross-chain risk
  * messaging vs lock-and-mint vs liquidity networks  
  * risk framing around trust assumptions and failure domains  

* Oracles and pricing safety
  * fallback pricing, predictability via bounds and danger signaling  

* Hands-on user experience as a retail crypto user for 8+ years
  * wallet ops across hot and cold storage, DEX and aggregator usage and LP exposure  
  * product quality radar from real usage, not theory  
  * first-hand UX experience across CEX and DEX flows, including custodial vs non-custodial and varying AML/KYC regimes  

### AI expertise



### Professional experience

#### Product Manager, AI Data Transformation | Rohde and Schwarz | 2024 to 2025

* Built a central AI and data management platform for multimodal datasets (image, audio, tabular)  
* Improved data quality via filtering, tagging, reproducible data transformation pipelines, audit trails with	 full data provenance  
* Enabled ML training and evaluation on curated datasets with transparent evaluation concepts (SafeAI, ExplainableAI)  
* Delivered autonomous feature sets end to end, including user stories, acceptance criteria, implementation support, testing and GitOps-based rollout  
* Unblocked infrastructure-level issues in OpenShift when needed  
* Led a cross-functional team including architect, data scientists, backend and frontend engineers and QA  

Tech: Kotlin (Spring Boot), Python, PostgreSQL, MongoDB, Redpanda, Kubernetes, Argo Workflows, Argo CD, OpenShift  

#### Product Manager, Public Data Analytics | Federal Employment Agency | 2023 to 2024

* Advanced an analytics platform for regional labor and demographic data and trends  
* Delivered new features including labor shortage analytics, regional trends and modernized admin tooling  
* Introduced Dagster for automated ETL and indicator generation  
* Designed interactive dashboards, tables and community features (groups, networks, events)  
* Migrated legacy systems to Kubernetes and handled major system upgrades  
* Served as Deputy IT Security Officer with a focus on compliance, governance and data lineage  

Tech: Python, Django, JavaScript, PostgreSQL, dbt, Dagster, DuckDB, MicroStrategy, Kubernetes, Jenkins, Bitbucket, Git  

#### Product Manager, InsurTech SaaS Platform | Emil Group | 2022

* Developed a modular insurance platform for primary insurers (Erstversicherer), reinsurers (Rückversicherer), Assekuradeure (MGAs), brokers and underwriters  
* Delivered modules across product configuration, pricing, underwriting, policy issuance, document management and workflow automation  
* Designed and delivered a Claims Center module from concept to production rollout  
* Re-established sprint discipline and delivery stability, split a bloated 17-person team into smaller units and introduced ownership and deputy concepts  
* Regained client trust in a prototype-stage environment through structured communication and weekly product workshops  

Tech: Low-code platform, Java, HTML/CSS, Kubernetes, REST APIs  

#### Product Owner, Mobile Healthcare App | CLINET Platforms | 2021 to 2022

* Built a mobile-first pilot app for hospitals across iOS and Android  
* Delivered core flows for digital anamnesis, meal and therapy plans, transport, chat and patient document storage  
* Integrated CGM interface into hospital information system workflows  
* Led a small team under tight deadlines with strict focus on the highest-leverage features  

Tech: AngularJS, Ionic, Python, Kubernetes, CGM API integration  

### Earlier experience, selected

* Co-founder, CDO and Head of HR: Smart Soil Technologies  
* Product Owner, COVID-19 data platform, Bundesdruckerei (RKI projects DIM and DESH)  
* Proxy Product Owner, AOK Insurance ITSCare, webshop migration to Shopware  
* Project Lead, Enercon, IT modernization (end devices, software migration, Office 365, SSO, infrastructure)  
* Product Owner, Qcrypt AG, quantum-resistant encryption product  
* Founder and CFO, Kvitt Payment Solutions, FinTech startup later acquired by Sparkasse  

### Education

Diplom Wirtschaftsingenieur (Industrial Engineering), Technische Universität Berlin  

### Languages

* German (native)  
* English (C2)
