# [REQUIREMENTS.md](http://REQUIREMENTS.md)

## 1. Overview

BlackBook is a personal intelligence application for a single investigator conducting structured deep-dive discovery of companies. The investigator gathers information through three channels: interviews with multiple stakeholders, personal obserevations, and documents about the company from employees, press, etc. The work is iterative — the investigator may be building understanding of multiple companies simultaneously and returns to each over time, continuously adding new information and refining their understanding of each organization.

BlackBook accepts raw notes via email or file upload, automatically determining whether the content describes a new company or provides additional information about an existing one. It then uses AI to extract and infer structured information: people, titles, job functions, org structure, functional areas, technology used, process health, technical and non-technical challenges, and action plans. Notes are organized into CGKRA categories — Current State, Going Well, Known Problems, Roadmap, and Art-of-the-possible — based on investigator-supplied tags; investigators may also explicitly tag SWOT signals (Strengths, Weaknesses, Opportunities, Threats) from interviews. Neither CGKRA nor SWOT signals are inferred by the AI — all such categorizations are explicitly entered by the investigator via the prefix language system. This structured information is presented through a navigable visual interface organized by org structure and functional area, with hyperlinks, visuals, and notes that make it easy for the investigator to understand the company being discovered.

Because AI inference is imperfect, no extracted fact is committed to a company profile until the investigator has reviewed and either accepted or corrected it. The investigator retains full authority over what is treated as fact. All information in the system is editable by the investigator.

Beyond individual company profiles, BlackBook provides portfolio-level tools: the investigator can search across all companies by keyword, person, or technology; and view a coverage dashboard that surfaces which standard discovery areas are sparse or missing — making it easy to identify where to focus next. When a company picture is sufficiently complete, the investigator can produce shareable deliverables: a structured briefing document and an AI-authored CGKRA narrative, both grounded in validated, investigator-accepted data.

## 2. Goals

Clear, measurable outcomes the system should achieve.

- Goal 1: The investigator can open any company and immediately understand its people, structure, and CGKRA from structured, validated data — without re-reading raw notes
- Goal 2: Information can be captured quickly via email or file upload without requiring manual categorization at the time of capture — the AI handles extraction and structuring
- Goal 3: AI inferences are never automatically committed — all extracted data is surfaced for investigator review and validation before becoming authoritative
- Goal 4: Each company is navigable visually by org structure and functional area, with people, raw notes, inferred data, action items, and CGKRA accessible from each view
- Goal 5: The investigator can see what they do not yet know about a company — which discovery areas are sparse or empty — so they can plan next steps
- Goal 6: Action items and next steps are tracked and visible in a single consolidated view across all companies under investigation
- Goal 7: The investigator can search across all companies in their portfolio
- Goal 8: The investigator can produce shareable deliverables — both a structured briefing document and an AI-authored CGKRA narrative — from accumulated, validated company data
- Goal 9: The investigator can explicitly tag SWOT signals (Strengths, Weaknesses, Opportunities, Threats) using prefix tags when recording notes from interviews; these are never AI-inferred and are surfaced in reports and CGKRA views where present
- Goal 10: All information in the system — company profiles, inferred facts, people, action items — is editable by the investigator at any time; no data is locked after acceptance
- Goal 11: Access to the application and all its data is protected by authentication; the investigator can securely set and change their credentials

---

## 3. Non-Goals

Explicitly state what this system will NOT do.

- Non-goal 1: Multi-investigator or colaborators. This is a single investigator model
- Non-goal 2: Confidence/source tracking — there is no need to distinguish insider vs. public data, and high vs. low confidence facts
- Non-goal 3: Real-time or automated data collection from external sources (web scraping, third-party APIs) — all input is manually supplied by the investigator

---

## 4. Users / Personas

Who the system is built for.

- Persona 1: Investigator
  - Description: Person doing deep-dive discoveries of companies. They learn about a company through 1: multiple interviews with multiple stakeholder; 2: personal observations; and 3: reading documents provided by the comapany, the press, the public, etc. They need this information to be organzied and come to the applicatoin to refresh, review, and contribute to their understanding of the company being discovered.
  - Needs: The investigator needs to be able to synthesize information about the people, processes, and technology of the company being discovered; review and validate AI-inferred data; understand the CGKRA analysis by functional area and for the company overall; keep track of action items and next steps; and generate reports summarizing the company's current state and opportunities.

---

## 5. Use Cases

Concrete scenarios describing how users interact with the system.

- Use Case 1:
  - Actor : Investigator
  - Description: The Investigator is able to email notes to the application to be ingested by BlackBook to create a new company
  - Success Criteria: Email is digested, the contents are processed, a new company is created using the contents of the email to establish at least the Company name plus additional fields inferable such as: Mission, Vision, people, org structure, processess, technical or process details, and any CGKRA or SWOT signals explicitly tagged by the investigator in the notes.
  - Priority: Ought to  Have
- Use Case 2:
  - Actor : Investigator
  - Description: The Investigator is able to email notes to the application to be ingested by BlackBook to update an existing company
  - Success Criteria: Email is digested, the contents are processed, an existing company is recognized and updated using the contents of the email to establish one or more of: Mission, Vision, people, org structure, processess, technical or process details, and any CGKRA or SWOT signals explicitly tagged by the investigator in the notes.
  - Priority: Ought to  Have
- Use Case 3:
  - Actor : Investigator
  - Description: The Investigator is able to upload notes to the application to be ingested by BlackBook to create a new company
  - Success Criteria: Document is digested, the contents are processed, a new company is created using the contents of the document to establish at least the Company name plus additional fields inferable such as: Mission, Vision, people, org structure, technical or process details, and any CGKRA or SWOT signals explicitly tagged by the investigator in the notes.
  - Priority: Must Have
- Use Case 4:
  - Actor : Investigator
  - Description: The Investigator is able to upload notes to the application to be ingested by BlackBook to update an existing company
  - Success Criteria: Document is digested, the contents are processed, an existing company is recognized and updated using the contents of the documnet to establish one or more of: Mission, Vision, people, org structure, processess, technical or process details, and any CGKRA or SWOT signals explicitly tagged by the investigator in the notes.
  - Priority: Must Have
- Use Case 5:
  - Actor : Investigator
  - Description: Upon accessing a company, the Investigator is presented with the information inferred from documents and emails since the last time the Investigator accessed the company for the Investigator to accept or correct. For each surfaced entity, the system displays a list of existing same-category entities already associated with the company, making it easy to identify duplicates or near-matches and resolve them. For example, if the AI surfaces "J. Smith", the investigator is shown all existing people on the company and can select "Jane Smith" as the correct match rather than creating a duplicate.
  - Success Criteria: New inferences are displayed prominently on access; for each inferred entity, a list of existing same-category entities associated with the company is shown alongside the inference; the investigator can accept the item as a new entity, merge it with an existing entity by selecting from the list, or correct it manually; accepted, merged, corrected, and dismissed items no longer appear as pending on subsequent visits. Exception: accepting a fact with `category = "action-item"` does not merely mark it accepted — it promotes the fact into the `action_items` table as a new ActionItem record (description = inferred value; `person_id` and `functional_area_id` null at creation, assignable later); the InferredFact is then marked `accepted`.
  - Priority: Must Have
- Use Case 6:
  - Actor : Investigator
  - Description: The Investigator is able to see a visual representation of the company's org chart, click on a person and see all notes, action items, etc. about that person.
  - Success Criteria: All known people are represented in the org chart; people with known reporting relationships appear in the hierarchy; people with no known reporting relationship appear in a clearly labelled "Unplaced" section rather than being silently omitted; clicking any person displays their associated notes, action items, and inferred role.
  - Priority: Must Have
- Use Case 7:
  - Actor : Investigator
  - Description: The Investigator is able to see CGKRA (Current State, Going Well, Known Problems, Roadmap, Art-of-the-possible) for every functional area and for the company as a whole. Where the investigator has explicitly tagged SWOT signals, these are also visible alongside CGKRA. All entries are grounded in investigator-tagged notes — none are inferred by the AI.
  - Success Criteria: A CGKRA view is displayed for each functional area and for the company as a whole, populated from investigator-tagged notes; explicitly tagged SWOT signals are displayed alongside CGKRA where present; all entries link back to the originating note.
  - Priority: Must Have
- Use Case 8:
  - Actor: Investigator
  - Description: The investigator exports a structured company briefing document containing CGKRA analysis, technology stack, and open action items. This is a structured data export, distinct from the AI-authored CGKRA narrative in UC-15. Inclusion of the org chart in the export is a nice-to-have due to the complexity of rendering an interactive visualization into a static document format.
  - Success Criteria: A downloadable PDF or doc is generated containing the company's CGKRA analysis, technology stack, and open action items; the export completes without error and the file is well-formatted and readable. Nice-to-have: the export also includes a static representation of the org chart.
  - Priority: Must Have
- Use Case 9:
  - Actor: Investigator
  - Description: The investigator searches across all companies and notes by keyword, person name, or technology, and receives matching results with links to the originating notes and company.
  - Success Criteria: Results are returned matching companies, people, notes, and inferred facts; each result links directly to the originating company and source; queries with no matches return a clear empty state.
  - Priority: Search within a company is a Must Have;  searching accross all companies is a' Nice to Have'
- Use Case 10:
  - Actor: Investigator
  - Description: The investigator views a consolidated list of all open action items across the investigation, can mark them complete, and can assign follow-up notes to each.
  - Success Criteria: All open action items across all companies are shown in a single list; the investigator can mark any item complete; completed items are removed from the open list; investigator notes can be added to any item.
  - Priority: Nice to Have
- Use Case 11:
  - Actor: Investigator
  - Description: BlackBook surfaces a coverage view showing which standard discovery areas (Mission, Org, Tech Stack, Processes, CGKRA) have sparse or no information for a given company, helping the investigator identify where to focus next.
  - Success Criteria: Each discovery area is shown with a clear indicator of data density (populated, sparse, or empty); the investigator can navigate from any gap directly to the relevant section of the company profile.
  - Priority: Nice to Have
- Use Case 12:
  - Actor: Investigator
  - Description: The investigator logs in to BlackBook using their credentials to access the application.
  - Success Criteria: The investigator provides a valid username and password, is authenticated, and is granted access to the application. Invalid credentials are rejected with an appropriate error message.
  - Priority: Must Have
- Use Case 13:
  - Actor: Investigator
  - Description: The investigator sets their password when accessing BlackBook for the first time.
  - Success Criteria: The investigator is prompted to create a password that meets minimum security requirements. Password is saved and the investigator can subsequently log in with it.
  - Priority: Must Have
- Use Case 14:
  - Actor: Investigator
  - Description: The investigator changes their password from within the application.
  - Success Criteria: The investigator provides their current password and a new password meeting minimum security requirements. The new password is saved and old password is invalidated.
  - Priority: Must Have
- Use Case 15:
  - Actor: Investigator
  - Description: The investigator generates an AI-authored narrative CGKRA document for a company. Unlike the structured briefing export in UC-8, this is a prose document written by an LLM synthesizing the company's CGKRA-tagged notes and any explicitly tagged SWOT signals into a coherent narrative. The investigator may optionally upload a markdown file to serve as a template that guides the structure and tone of the generated document. If no template is provided, a default structure is used.
  - Success Criteria: The AI produces a coherent, well-structured CGKRA narrative grounded in the company's investigator-tagged notes and accepted data. If a markdown template is supplied, the output conforms to its structure and section headings. The document is viewable in the UI and downloadable. If the template is malformed or unreadable, the investigator is notified and generation falls back to the default structure.
  - Priority: Must Have
- Use Case 16:
  - Actor: Investigator
  - Description: The investigator optionally prefixes lines in their notes with short tags to guide AI extraction. Tags are normalized by the system to canonical keys before the content is passed to the LLM inference engine, reducing extraction ambiguity. For example, `+:`, `str:`, and `strength:` all resolve to the canonical key `s:` (SWOT strength). Lines without a prefix default to `n:` (plain note). Company routing prefixes (`nc:`, `c:`, `cid:`) are reserved for directing which company record the source belongs to and are stripped before LLM inference — they are not passed to the model. The canonical map is defined in configuration and can be modified by the investigator. The default canonical map is defined in section 6.1.
  - Success Criteria: Prefixed lines are correctly normalized to their canonical keys before LLM processing; untagged lines are treated as `n:` (plain note); company routing prefixes (`nc:`, `c:`, `cid:`) are consumed by the routing step and not forwarded to the LLM; the canonical map is readable and modifiable in configuration without a code change; the LLM receives unambiguous, structured input; unrecognized prefixes are treated as `n:` and flagged in the ingestion log.
  - Priority: Must Have
- Use Case 17:
  - Actor: Investigator
  - Description: The investigator directly edits any previously accepted entity from within the company profile — including company fields (name, mission, vision), person details (name, title, reporting relationship, functional area), and the corrected value of any accepted InferredFact. This is distinct from the initial pending review in UC-5: UC-17 applies after a fact has already been accepted and committed to the profile.
  - Success Criteria: The investigator can edit any accepted entity from the company profile without re-entering the pending review queue; the original inferred value is retained alongside the edit; changes are saved immediately and reflected across all views that display the entity; no accepted data is read-only.
  - Priority: Must Have
- Use Case 18:
  - Actor: Investigator
  - Description: The investigator views the list of all sources ingested for a company — emails and uploaded documents — with their processing status. Failed ingestions are visually distinguished and include the failure reason, fulfilling the reliability requirement that no submitted content is silently dropped. The investigator can view the raw content of any source and re-trigger processing of a failed source.
  - Success Criteria: All sources for a company are listed with type (email | upload), filename or subject line, received date, and processing status (pending | processing | processed | failed); failed sources are visually distinguished and display the failure reason; the investigator can view the full raw content of any source; the investigator can re-trigger processing of a failed source, which re-enters the ingestion queue and its status updates accordingly; a successfully re-triggered source surfaces new pending inferences through the normal review queue.
  - Priority: Must Have
- Use Case 19:
  - Actor: Investigator
  - Description: The investigator creates a new company record directly from the UI by entering the company name and optional top-level fields (mission, vision), without requiring an ingested document or email. This is useful when the investigator wants to establish a company record ahead of any notes arriving, or when the company cannot be reliably inferred from existing content. The resulting company is immediately available in the portfolio and can receive sources through the normal ingestion flow.
  - Success Criteria: A company record is created with the provided name and any supplied optional fields; the company appears immediately in the company list and the investigator is taken to the new company profile; the company starts empty — no sources, no pending inferences, empty coverage; if a company with the exact same name (case-insensitive) already exists, creation fails with a clear error — the investigator must use a distinct name.
  - Priority: Ought to Have

---

## 6. Functional Requirements

What the system must do.

### 6.1 Core Features

- Email ingestion: receive and parse emails sent to a designated address, extract text and attachments for processing
- Document ingestion: accept uploaded files (PDF, Word, text, etc.) and extract their contents for processing
- Source management: list all ingested sources for a company with type, date, and processing status; surface failed ingestions with failure reason; allow the investigator to view raw source content and re-trigger processing of any failed source
- AI inference engine: analyze ingested content to extract and infer people, titles, reporting relationships, org structure, functional areas, technology stack, and processes based on tagged inputs; organize investigator-tagged notes into CGKRA and SWOT categories based on prefix tags — neither CGKRA nor SWOT signals are inferred by the AI. The LLM output contract is:
  - **Output format**: a JSON array of InferredFact objects; each object must contain a `category` field (one of the valid InferredFact categories defined in 6.3) and a `value` field (non-empty string); relationship facts must additionally carry `subordinate` and `manager` fields reflecting the `rel: A > B` syntax. Example:
    ```json
    [
      { "category": "person", "value": "Jane Smith, VP Engineering" },
      { "category": "relationship", "subordinate": "Jane Smith", "manager": "Bob Jones" },
      { "category": "technology", "value": "Kubernetes" },
      { "category": "cgkra-kp", "value": "Deployment pipeline is manual and error-prone" }
    ]
    ```
  - **Malformed response handling**: if the LLM returns invalid JSON, an empty response, or any object with an unrecognized `category` or missing required fields, the entire response is rejected — no partial commits; the Source is marked `failed` with the raw LLM response and error reason stored; the failure is surfaced to the investigator via the source management view (UC 18) for inspection and retry
- Company routing: every ingested source must carry exactly one of three routing prefixes — `nc:` (create new company), `c:` (route to existing by exact name), or `cid:` (route to existing by exact ID); if none is present or the routing fails, ingestion fails with a clear error; no fuzzy matching or automatic inference of company identity is performed (see §9.7)
- Company profile: maintain a structured, editable profile per company encompassing all inferred and accepted data fields; companies can be created manually from the UI or automatically through ingestion
- Manual company creation: the investigator can create a company record directly from the UI by entering a name and optional top-level fields; creation is blocked (not warned) if a company with the exact same name already exists; the created company is immediately available for source ingestion and profile editing
- Pending review queue: surface newly inferred information to the investigator for acceptance or correction before it is committed to the company profile
- Entity disambiguation: during review, for each inferred entity, present a ranked list of existing same-category entities already associated with the company, ordered by similarity to the inferred value (fuzzy name/token matching, not alphabetical); allow the investigator to accept as new, merge with an existing entity, or correct manually; applies to all entity categories (people, technologies, functional areas, etc.) — e.g., "k8s" should surface "Kubernetes", "Eng" should surface "Engineering"
- Org chart visualization: render an interactive visual org chart for a company based on inferred people and reporting relationships; the chart supports multiple root nodes (e.g., when the top of the hierarchy is unknown or there are co-leads); people with no known reporting relationships are shown in a separate "Unplaced" section rather than omitted
- CGKRA synthesis: aggregate investigator-tagged CGKRA notes per functional area and company-wide; display alongside any explicitly tagged SWOT signals; all entries link to their originating source note
- Action item tracker: extract, store, and surface action items and next steps; allow the investigator to mark them complete and add notes
- Coverage analysis: identify and display which standard discovery areas have sparse or missing information for a given company
- Search: full-text search across all companies or within a single company, people, notes, and inferred data
- Export: generate a formatted, downloadable PDF or doc briefing document for a company containing CGKRA analysis, any explicitly tagged SWOT signals, technology stack, and open action items; static org chart inclusion is a nice-to-have
- Authentication: username/password login with first-time password setup and self-service password change
- AI CGKRA document generation: produce a narrative CGKRA document for a company using an LLM, grounded in all investigator-tagged CGKRA notes and any explicitly tagged SWOT signals; support an optional user-supplied markdown template to control output structure; fall back to a default structure when no template is provided
- Prefix language parser: before passing ingested content to the LLM, normalize line prefixes to canonical extraction keys using a configurable alias map; default untagged lines to `n:` (plain note); treat unrecognized prefixes as `n:` and log them; `nc:`, `c:`, and `cid:` are reserved routing prefixes intercepted before the LLM and used to identify which company a source belongs to (see §9.7); the canonical map is defined in configuration and requires no code change to modify. The default canonical map is:
  ```python
  canonical_map = {
      "nc": "nc",                                    # new company — creates a new company with this name; fails if exact name already exists
      "c": "c",                                      # route to existing company by exact name match; fails if no match
      "cid": "cid",                                  # route to existing company by exact ID; fails if no match
      "contact": "who", "from": "who",               # contact / source person
      "d": "date", "when": "date",                   # date
      "source": "src", "via": "src",                 # source
      "person": "p", "pe": "p",                      # person
      "reports": "rel", "under": "rel",              # reporting relationship — syntax: rel: <subordinate> > <manager>  e.g. rel: Jon > Bob (Jon reports to Bob)
      "func": "fn", "area": "fn", "team": "fn",      # functional area
      "tech": "t", "stack": "t",                     # technology
      "process": "proc", "how": "proc",              # process
      # CGKRA categories — investigator-tagged; LLM organizes notes into these buckets
      "cs": "cs", "cur": "cs", "current": "cs",      # current state
      "gw": "gw", "well": "gw",                      # going well
      "kp": "kp", "prob": "kp", "problem": "kp",    # known problems
      "rm": "rm", "road": "rm", "roadmap": "rm",     # roadmap
      "aop": "aop",                                  # art-of-the-possible (investigator assessment only)
      # SWOT tags — investigator-entered explicitly from interviews; not inferred by AI; used in report generation
      "str": "s", "strength": "s", "+": "s",         # strength
      "weak": "w", "weakness": "w", "-": "w",        # weakness
      "opp": "o", "opportunity": "o",                # opportunity
      "threat": "th", "risk": "th",                  # threat
      "action": "a", "todo": "a", "do": "a",         # action item
      "note": "n",                                   # plain note (default) — no structured extraction; stored as-is under category 'other'
  }
  ```
  **Canonical key disposition table** — defines what the system does with each key and whether it produces an `InferredFact` subject to investigator review:

  | Canonical key    | Meaning                      | Disposition                                                                                                          | InferredFact category |
  | ---------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------- | --------------------- |
  | `nc`             | New company routing          | Intercepted before LLM; creates new company with value as name; fails (hard) if exact name already exists in DB      | —                     |
  | `c`              | Existing company by name     | Intercepted before LLM; routes to company with exact name match; fails if no match                                   | —                     |
  | `cid`            | Existing company by ID       | Intercepted before LLM; routes to company with exact ID match; fails if no match                                     | —                     |
  | `who`            | Contact / source attribution | Source metadata only; no InferredFact created                                                                        | —                     |
  | `date`           | Date of interaction          | Source metadata only; no InferredFact created                                                                        | —                     |
  | `src`            | Provenance label             | Source metadata only; no InferredFact created                                                                        | —                     |
  | `p`              | Person                       | InferredFact                                                                                                         | `person`              |
  | `rel`            | Reporting relationship       | InferredFact — syntax: `rel: <subordinate> > <manager>`                                                              | `relationship`        |
  | `fn`             | Functional area              | InferredFact — on acceptance, creates a new FunctionalArea record; use merge to link to an existing area (see §10.4) | `functional-area`     |
  | `t`              | Technology                   | InferredFact                                                                                                         | `technology`          |
  | `proc`           | Process                      | InferredFact                                                                                                         | `process`             |
  | `cs`             | CGKRA: Current state         | InferredFact                                                                                                         | `cgkra-cs`            |
  | `gw`             | CGKRA: Going well            | InferredFact                                                                                                         | `cgkra-gw`            |
  | `kp`             | CGKRA: Known problems        | InferredFact                                                                                                         | `cgkra-kp`            |
  | `rm`             | CGKRA: Roadmap               | InferredFact                                                                                                         | `cgkra-rm`            |
  | `aop`            | CGKRA: Art-of-the-possible   | InferredFact                                                                                                         | `cgkra-aop`           |
  | `s`              | SWOT: Strength               | InferredFact                                                                                                         | `swot-s`              |
  | `w`              | SWOT: Weakness               | InferredFact                                                                                                         | `swot-w`              |
  | `o`              | SWOT: Opportunity            | InferredFact                                                                                                         | `swot-o`              |
  | `th`             | SWOT: Threat                 | InferredFact                                                                                                         | `swot-th`             |
  | `a`              | Action item                  | InferredFact                                                                                                         | `action-item`         |
  | `n`              | Plain note                   | InferredFact — content stored as-is; no structured extraction                                                        | `other`               |
  | *(unrecognized)* | Unrecognized prefix          | Treated as `n`; logged in ingestion log                                                                              | `other`               |

  Notes: `functional-area` facts create a new FunctionalArea record on acceptance; use the merge action to link to an existing area instead. `other` is system-assigned — it is never a valid investigator-supplied prefix.

### 6.2 User Interactions

- Email notes to a designated BlackBook address to trigger ingestion (UCs 1–2)
- Upload documents directly via the web UI to trigger ingestion (UCs 3–4)
- Review pending inferences upon opening a company; for each entity, view existing same-category entities and accept as new, merge with an existing entity, or correct manually (UC 5)
- Navigate a company's org chart visually; click a person to view their details, notes, and action items (UC 6)
- View CGKRA by functional area and for the company as a whole; view alongside any explicitly tagged SWOT signals (UC 7)
- Export a company briefing document as PDF or doc (UC 8)
- Search by keyword, person, or technology across all companies (UC 9)
- View, complete, and add notes to action items from a consolidated action item list (UC 10)
- View the coverage dashboard to see which discovery areas need more information (UC 11)
- Log in with credentials; set password on first access; change password from account settings (UCs 12–14)
- Generate an AI CGKRA narrative document for a company; optionally upload a markdown template file to guide the output structure before generating (UC 15)
- Optionally prefix note lines with canonical tags (e.g., `p:` for person, `fn:` for functional area, `+:` for strength, `a:` for action item) to guide AI extraction; untagged lines are treated as plain notes by default; customize the canonical map in configuration (UC 16)
- Directly edit any previously accepted entity — company fields, person details, or accepted facts — from the company profile (UC 17)
- View the list of ingested sources for a company; inspect raw content of any source; see failure reason for failed ingestions; re-trigger processing of a failed source (UC 18)
- Create a new company record manually from the UI by entering a name and optional fields; creation fails if a company with the exact same name already exists (UC 19)

### 6.3 Data Requirements

**Data inputs:**

Must-have:

- Uploaded documents: plain text (.txt), Word (.docx), Google Docs (exported as plain text or .docx — no HTML)
- Emails: plain-text body with plain text or Word attachments
- CGKRA narrative generation templates: plain text or Word files supplied by the investigator
- Investigator-supplied corrections and action item updates (structured form input)
- Authentication credentials (username, password)

Nice-to-have:

- PDF documents
- Markdown (.md) files
- HTML email bodies and HTML attachments
- Google Docs exported as PDF

**Data outputs:**

- Structured company profiles rendered in the web UI
- Interactive org chart per company
- CGKRA analysis per functional area and company-wide, with any explicitly tagged SWOT signals displayed alongside
- AI-generated CGKRA narrative document (viewable in UI, downloadable as PDF or doc)
- Structured briefing document export (PDF or .docx)
- Search result sets with links to originating company and source document
- Action item list, filterable by company and status
- Coverage dashboard per company

**Key entities and storage requirements:**

- **Company** — one record per discovered company; stores name, mission, and vision; technology and process facts are not direct fields — they are InferredFacts with category `technology` or `process`, linked to the company via the `inferred_facts` table
- **FunctionalArea** — a named area of the business (e.g., Engineering, Product, Sales, Finance, Operations); linked to a Company; inferred from ingested content or manually created; serves as the primary organizational grouping for people, facts, action items, and CGKRA synthesis
- **Person** — name, title, and reporting relationships; linked to a Company and to a primary FunctionalArea; a person may appear under multiple functional areas if their role spans them
- **Source** — represents a single ingested unit (one email or one uploaded file); stores type (email | upload), raw content, filename or subject line, received timestamp, and processing status (pending | processing | processed | failed); linked to a Company
- **InferredFact** — a single piece of information extracted by the AI from a Source; stores category (functional-area | person | relationship | technology | process | cgkra-cs | cgkra-gw | cgkra-kp | cgkra-rm | cgkra-aop | swot-s | swot-w | swot-o | swot-th | action-item | other), the raw inferred value, an optional investigator-supplied corrected value, and status (pending | accepted | corrected | merged | dismissed); linked to its Source, its Company, and optionally a FunctionalArea; every InferredFact must retain its Source link so the investigator can trace any fact back to its origin
- **ActionItem** — description, status (open | complete), and optional investigator notes; linked to a Company, optionally to a Person, and optionally to a FunctionalArea; may be inferred from a Source or manually created by the investigator
- **CGKRATemplate** — name and raw Markdown content; uploaded by the investigator and reusable across companies
- **GeneratedDocument** — type (briefing | cgkra-narrative), file reference or stored content, generation timestamp, and optionally the CGKRATemplate used; linked to a Company

**Entity relationship summary:**

```
Company
  └── FunctionalArea (many)
        ├── Person (many — primary area assignment)
        ├── InferredFact (many — optional area tag)
        ├── ActionItem (many — optional area tag)
        └── CGKRA (aggregated from investigator-tagged InferredFacts; one per FunctionalArea + one company-wide roll-up; SWOT signals displayed alongside where present)
  └── Source (many)
        └── InferredFact (many — derived from this source)
```

**Important storage constraints:**

- Raw Source content must be retained — investigators need to reference original notes
- Corrected InferredFacts must store both the original inferred value and the correction; the original is never silently overwritten
- Merged InferredFacts must link to the selected existing entity rather than creating a new one; the original inferred value is retained alongside the merge decision, consistent with the no-silent-overwrite rule
- Coverage (UC 11) is computed at query time from the presence of accepted InferredFacts per category — no separate storage entity required
- CGKRA per FunctionalArea is aggregated at query time from InferredFacts tagged to that area — no separate CGKRA storage entity required; SWOT signals are similarly aggregated from swot-tagged InferredFacts
- Data volume is expected to be small (1 user, modest number of concurrent investigations); durability and correctness take priority over scale optimizations

---

## 7. Non-Functional Requirements

System qualities and constraints.

### 7.1 Performance

- UI interactions (navigation, org chart, search results): target < 1 second response time
- Ingestion (email and file upload) is asynchronous — the investigator does not wait; new inferences are surfaced on next company access via the pending review queue (UC 5)
- AI inference and CGKRA narrative generation are inherently slow and run asynchronously; the investigator is notified when results are ready rather than waiting
- Document export (PDF/doc) should complete within 30 seconds

### 7.2 Reliability

- The data represents accumulated, irreplaceable research — data loss is the highest-severity failure mode
- Ingestion failures must be logged and surfaced to the investigator; no submitted content should be silently dropped
- All company data, source documents, and inferred facts must be backed up daily
- Uptime: available during normal working hours; brief planned maintenance windows are acceptable given the user base size

### 7.3 Security

- Authentication: username/password with minimum complexity requirements. Credentials (username and bcrypt-hashed password) are stored in the `credentials` table in PostgreSQL (§11.11) — a single-row table written by `POST /auth/password/set` and updated by `POST /auth/password/change`; never stored in config files or environment variables. Session management:
  - **Mechanism**: database-backed server-side sessions stored in PostgreSQL; a `sessions` table holds `(token, created_at, last_active_at)`; token is a cryptographically random 32-byte hex string; no JWT, no Redis, no in-memory store
  - **Transport**: session token delivered to the client as an `HttpOnly`, `Secure`, `SameSite=Strict` cookie named `session`
  - **Expiry**: rolling inactivity timeout — on every authenticated request the server checks `now − last_active_at`; if it exceeds the configured timeout the session is treated as expired and the request is rejected; `last_active_at` is updated on every successful authenticated request
  - **Timeout**: configurable in application config; default 5 minutes of inactivity
  - **Logout**: session record is deleted from the database; the `session` cookie is cleared in the response
  - **Invalid or expired session**: returns 401 with `{ "error": { "code": "unauthenticated", "message": "Session missing or expired" } }`; the client must redirect to the login screen
- Authorization: single-user model — an authenticated user has full access to all data; no role-based access control is needed
- Data protection: all data encrypted at rest; all traffic over HTTPS; source documents may contain confidential insider information and must be treated accordingly

### 7.4 Scalability

- Expected load: 1 user, 1-1000 companies
- Expected data volume: tens to hundreds of source documents per company; hundreds to thousands of inferred facts per company across a modest number of concurrent investigations
- Growth assumptions: modest, if at all
- Correctness and durability take priority over throughput optimization; horizontal scaling is not a design requirement

---

## 8. Technical Constraints

Hard constraints the system must respect.

- Languages: Python (backend), TypeScript/React (frontend)
- Frameworks: FastAPI (backend API), React served directly by the backend — no separate CDN or static hosting required
- APIs: Anthropic Claude API or OpenAI API for AI inference and CGKRA narrative generation; API key stored in a local config file or environment variable; IMAP polling of a dedicated email account for email ingestion — no cloud email routing required
- Infrastructure:
  - Must run on a single Mac (local use) or a low-end AWS EC2 instance (t3.medium or equivalent: 2 vCPU, 4GB RAM)
  - Database: PostgreSQL (native install)
  - File storage: local filesystem for source documents, templates, and generated exports. Conventions:
    - **Root**: a single configurable root directory set via `BLACKBOOK_DATA_DIR` env var; default `~/.blackbook/data` on Mac, `/var/blackbook/data` on EC2; all file I/O is relative to this root so the entire store is portable and backupable with one path
    - **Directory layout**:
      ```
      $BLACKBOOK_DATA_DIR/
        sources/
          {company_id}/
            {source_id}_{sanitized_original_filename}
        templates/
          {template_id}_{sanitized_original_filename}
        exports/
          {company_id}/
            {doc_id}_{type}_{iso_timestamp}.{ext}
      ```
    - **Filename sanitization**: strip all characters outside `[a-zA-Z0-9._-]`; truncate to 100 characters; the entity ID prefix guarantees uniqueness regardless of original filename; export filenames include type and ISO 8601 timestamp for readability (e.g., `a3f9_briefing_2026-03-24T14-05-00.pdf`)
    - **Retention**:
      - Source files: retained indefinitely; deleting a company deletes its `sources/{company_id}/` directory
      - Templates: retained until explicitly deleted by the investigator
      - Generated exports: configurable TTL (default 7 days); the background worker performs a daily cleanup pass deleting exports older than the TTL; exports can always be regenerated on demand
  - Async job processing: in-process background task queue (Python `asyncio` or Celery with a lightweight broker); no Kubernetes, no SQS, no Temporal
  - Deployment: native install; Docker Compose may be adopted later
  - LLM inference via external API only — no self-hosted models
  - No cloud-specific services required (no SES, SQS, EKS, Aurora, S3); S3 may optionally replace local file storage in a future iteration

---

## 9. Architecture (Optional / High-Level)

### 9.1 Architectural Pattern

BlackBook follows a layered SOA pattern within a single deployable process (modular monolith). The four layers are strictly separated: no business logic in the persistence layer, no direct data access in the service layer (services access data exclusively through their own repository — never another service's repository), and no composition logic in the services themselves. Services expose versioned interfaces so that the CGKRA taxonomy, prefix language, and inference pipeline can evolve without breaking the composition or frontend layers.

```
Frontend (React/TypeScript)
    ↕ HTTP/REST
Composition Layer  (FastAPI routes — assembles multi-service responses for the frontend)
    ↕
Service Layer      (Python classes, versioned interfaces — all business logic lives here)
    ├── CompanyService v1
    ├── IngestionService v1
    ├── InferenceService v1
    ├── PrefixParserService v1
    ├── ReviewService v1
    ├── CGKRAService v1
    ├── PersonService v1
    ├── ActionItemService v1
    ├── SearchService v1
    ├── ExportService v1
    └── AuthService v1
    ↕
Repository Layer   (SQLAlchemy — pure data access, zero business logic)
    ↕
PostgreSQL

Background Workers (Python asyncio — same service layer, async entry point;
                    used for LLM inference, email ingestion, export generation)
```

### 9.2 Components

- **Frontend**: React/TypeScript SPA served directly by the FastAPI backend; communicates exclusively with the Composition Layer via REST
- **Composition Layer**: FastAPI route handlers; responsible for assembling responses from multiple services into the shape the frontend needs (e.g., a company profile page composes Company + Person + CGKRA + ActionItem + Coverage); owns no business logic
- **Service Layer**: versioned Python service classes containing all business logic — InferredFact state machine, company routing, CGKRA aggregation, prefix normalization, entity disambiguation, fuzzy matching; each service has a single well-defined responsibility:
  - **IngestionService**: orchestrates the full ingestion pipeline (calls PrefixParserService → applies company routing algorithm §9.7 → calls InferenceService); owns source CRUD (listing, raw content retrieval, status); handles retry logic for failed sources (UC 18); entry point for both the upload REST path and the background IMAP email poller
  - **InferenceService**: LLM extraction — constructs prompt from `ParsedSource.lines`, calls LLM API with retry (§9.5), validates response, returns validated facts as Pydantic models; does not write to the database; called exclusively by IngestionService
  - **ReviewService**: owns the InferredFact lifecycle; `save_facts(facts)` persists InferredFacts returned by InferenceService (called by IngestionService after inference); owns the pending review queue (`GET /companies/{id}/pending`) and all review action endpoints (accept, correct, merge, dismiss); on accept/correct, delegates entity creation to the appropriate domain service (PersonService, ActionItemService, etc.) — never calls another service's repository directly; owns `InferredFactRepository`
  - **PrefixParserService**: normalises raw source text into a `ParsedSource` struct; no LLM calls, no DB access; called exclusively by IngestionService
- **Repository Layer**: SQLAlchemy models and query methods; pure data access with no business logic; the only layer that touches the database directly
- **PostgreSQL**: primary data store for all entities (Company, FunctionalArea, Person, Source, InferredFact, ActionItem, CGKRATemplate, GeneratedDocument, Credentials, Session)
- **Background Workers**: asyncio tasks running within the same process; consume the same service layer as the REST path; handle LLM inference jobs, IMAP email polling, document parsing, and export generation; expose job status via the Repository Layer for the Composition Layer to surface to the frontend

### 9.3 Data Flow

**Ingestion (email or upload):**
Email/file → IngestionService → PrefixParserService (normalize tags) → `ParsedSource` → IngestionService (apply company routing algorithm §9.7; store `who`/`date`/`src` on Source record; fail fast if routing invalid) → InferenceService (receives `ParsedSource.lines`; LLM extraction; returns validated facts as Pydantic models) → IngestionService calls ReviewService.save_facts(facts) → ReviewService writes Source + InferredFacts via InferredFactRepository → pending review queue surfaced on next company access

**Review:**
Investigator accepts/corrects/merges/dismisses → ReviewService (InferredFact state transition, category branching) → domain service for entity creation (PersonService.create_person(), ActionItemService.create_action_item(), etc.) → ReviewService updates InferredFact status via InferredFactRepository

**Read (company profile, CGKRA view, etc.):**
Frontend → Composition Layer → multiple Services → Repository → PostgreSQL → assembled response

**Export / CGKRA narrative generation:**
Frontend triggers → ExportService / CGKRAService → LLM API (for narrative) → GeneratedDocument stored → download link returned

### 9.4 External Dependencies

- **Anthropic Claude API or OpenAI API**: LLM inference (structural extraction) and CGKRA narrative generation
- **IMAP server**: email ingestion via polling of a designated email account
- **Local filesystem**: storage for uploaded source documents, CGKRA templates, and generated export files

### 9.5 InferenceService Contract

The InferenceService is the highest-risk component in the system — if extraction is unreliable, no downstream feature works correctly. This section specifies the LLM integration contract the service must implement.

**Input preparation:**

InferenceService receives a `ParsedSource` object from PrefixParserService (see §9.6). It uses `ParsedSource.lines` — the list of `(canonical_key, text)` pairs that excludes all metadata and routing keys — to construct the LLM user message. The `who`, `date`, `src`, and `nc` fields are never passed to InferenceService; they are consumed by the IngestionService before InferenceService is called.

The LLM user message is constructed by formatting each `(canonical_key, text)` pair as `canonical_key: text`, one per line. The system prompt instructs the LLM to: read each tagged line and extract its content into a typed InferredFact; for `n:` (plain note) lines, extract any identifiable facts of any category, with unextractable remainder stored as `other`; return only a JSON array — no prose, no explanation, no markdown wrapper.

**Extraction strategy:**

Extraction is performed in a **single LLM pass per source**. The entire normalized content is sent in one prompt and all InferredFacts are returned at once. Multi-pass extraction (one pass per category) is not used — it adds latency, cost, and coordination complexity with no correctness benefit given the single-pass output schema.

**Response validation:**

Before any InferredFacts are written to the database, the InferenceService validates the LLM response against the following rules — all must pass; any failure rejects the entire response:

1. Response body is parseable as JSON
2. Top-level value is a non-empty array
3. Every element has a `category` field matching a known InferredFact category (from the enum in 6.3)
4. Every element has a non-empty `value` field
5. Elements with `category: "relationship"` additionally have non-empty `subordinate` and `manager` fields

**Failure path:**

On any validation failure: the Source status is set to `failed`; the raw LLM response and the specific validation error are stored on the Source record for diagnostic purposes; the failure is surfaced to the investigator via UC 18; no retry is attempted automatically — the investigator triggers retry explicitly via `POST /sources/{id}/retry`.

**LLM API failure handling:**

API-level failures (network errors, HTTP error responses from the LLM provider) are distinct from validation failures and are handled with automatic retry before the source is marked failed.

*Retry conditions:*


| Condition                               | Retry? | Reason                                                      |
| --------------------------------------- | ------ | ----------------------------------------------------------- |
| HTTP 429 (rate limit)                   | Yes    | Transient; respect `Retry-After` header if present          |
| HTTP 500 / 502 / 503 / 504              | Yes    | Transient provider error                                    |
| Network timeout                         | Yes    | Transient connectivity issue                                |
| HTTP 400 (bad request)                  | No     | Likely a prompt defect; retrying will not fix it            |
| HTTP 401 (unauthorized)                 | No     | Misconfigured API key; retrying is pointless                |
| Validation failure (malformed response) | No     | Content problem, not infrastructure; see failure path above |


*Retry policy:*

- Maximum 3 attempts total (initial attempt + 2 retries)
- Exponential backoff with jitter: ~1 s before retry 1, ~2–4 s before retry 2
- For HTTP 429: use the `Retry-After` header value if present; otherwise apply exponential backoff
- Retries are transparent to the investigator — the source remains in `processing` status during the retry window

*After retries exhausted:*

The source is marked `failed` and surfaced via UC 18 identically to a validation failure. The `error` field on the Source record must distinguish API-level failure from validation failure — e.g., `"LLM API unavailable after 3 attempts: HTTP 429"` vs `"LLM returned invalid JSON"` — so the investigator knows whether to wait before retrying.

This retry policy applies to the CGKRA narrative LLM call (ExportService) as well — same provider, same failure modes; see §10.12.

**CGKRA and SWOT handling:**

Lines tagged with CGKRA keys (`cs`, `gw`, `kp`, `rm`, `aop`) or SWOT keys (`s`, `w`, `o`, `th`) are passed to the LLM with their canonical keys intact. The LLM's role for these lines is to normalize and clean the text value only — the category is fully determined by the investigator's tag and must not be reclassified or reassigned by the LLM.

**Output JSON schema:**

The LLM must return a JSON array conforming to the following schema. No other top-level structure is permitted — no wrapper object, no markdown code fence, no prose.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12",
  "type": "array",
  "minItems": 1,
  "items": {
    "type": "object",
    "required": ["category", "value"],
    "properties": {
      "category": {
        "type": "string",
        "enum": [
          "functional-area", "person", "relationship",
          "technology", "process", "cgkra-cs", "cgkra-gw", "cgkra-kp",
          "cgkra-rm", "cgkra-aop", "swot-s", "swot-w", "swot-o",
          "swot-th", "action-item", "other"
        ]
      },
      "value": { "type": "string", "minLength": 1 },
      "subordinate": { "type": "string", "minLength": 1 },
      "manager":     { "type": "string", "minLength": 1 }
    },
    "if":   { "properties": { "category": { "const": "relationship" } }, "required": ["category"] },
    "then": { "required": ["category", "value", "subordinate", "manager"] }
  }
}
```

**Sample input (post-normalization):**

The following is a realistic block of text as it would be constructed by the InferenceService after PrefixParserService has stripped metadata and resolved all prefixes. This is the user message sent to the LLM; the system prompt (not shown here) instructs the LLM to return only the JSON array.

```
p: Jane Smith, VP Engineering
fn: Platform Engineering
rel: Jane Smith > Bob Jones
tech: Kubernetes, Terraform
kp: Deployment pipeline is manual and error-prone — every release requires two engineers on a call
gw: Team shipped three major reliability improvements last quarter
n: Jane mentioned they're evaluating Argo Rollouts but haven't decided yet; also noted that the on-call rotation is unsustainable with the current headcount of 8
```

**Worked examples:**

*Example 1 — Clean extraction (one fact per tagged line):*

Input:

```
p: Jane Smith, VP Engineering
fn: Platform Engineering
rel: Jane Smith > Bob Jones
tech: Kubernetes, Terraform
```

Expected output:

```json
[
  { "category": "person",        "value": "Jane Smith, VP Engineering" },
  { "category": "functional-area", "value": "Platform Engineering" },
  { "category": "relationship",  "value": "Jane Smith reports to Bob Jones", "subordinate": "Jane Smith", "manager": "Bob Jones" },
  { "category": "technology",    "value": "Kubernetes" },
  { "category": "technology",    "value": "Terraform" }
]
```

Notes: `tech:` with a comma-separated list produces one fact per technology. `rel:` always produces exactly one fact with both `subordinate` and `manager` populated. `value` for a relationship fact is a human-readable summary of the relationship.

---

*Example 2 — Plain note (`n:`) with multiple extractable facts and unextractable remainder:*

Input:

```
n: Jane mentioned they're evaluating Argo Rollouts but haven't decided yet; also noted that the on-call rotation is unsustainable with the current headcount of 8
```

Expected output:

```json
[
  { "category": "technology",    "value": "Argo Rollouts (under evaluation, not yet adopted)" },
  { "category": "process",       "value": "On-call rotation is unsustainable at current headcount of 8" }
]
```

Notes: The LLM decomposes one `n:` line into as many typed facts as the content supports. There is no `other` fact here because the entire note is extractable. The parenthetical qualification on the technology fact is appropriate — it preserves the investigator's nuance.

---

*Example 3 — CGKRA and SWOT passthrough (category fixed by tag, LLM normalizes text only):*

Input:

```
kp: Deployment pipeline is manual and error-prone — every release requires two engineers on a call
gw: Team shipped three major reliability improvements last quarter
s: Strong institutional knowledge of the legacy system among senior engineers
```

Expected output:

```json
[
  { "category": "cgkra-kp", "value": "Deployment pipeline is manual and error-prone; every release requires two engineers on a call" },
  { "category": "cgkra-gw", "value": "Team shipped three major reliability improvements last quarter" },
  { "category": "swot-s",   "value": "Strong institutional knowledge of the legacy system among senior engineers" }
]
```

Notes: The em dash in the `kp:` line is normalized to a semicolon — minor text cleanup is acceptable. The category (`cgkra-kp`, `cgkra-gw`, `swot-s`) is copied directly from the tag and must not be changed regardless of the content. A `kp:` line that sounds positive must still be emitted as `cgkra-kp`.

---

### 9.6 PrefixParserService Contract

PrefixParserService is responsible for all prefix-language parsing. Its output is a `ParsedSource` object — a typed structure that fully decouples parsing from LLM prompt construction. No other service re-parses the raw source text.

**Input:** raw source text (email body or file contents), as received from the email poller or file upload handler.

**Output — `ParsedSource`:**

```python
@dataclass
class ParsedLine:
    canonical_key: str   # e.g. "p", "fn", "rel", "kp", "n"
    text: str            # content after the colon, stripped of leading/trailing whitespace

@dataclass
class ParsedSource:
    nc: str | None                # value of nc:; new company name; None if absent
    c: str | None                 # value of c:; existing company name (exact match required); None if absent
    cid: str | None               # value of cid:; existing company ID (exact match required); None if absent
    who: str | None               # value of who:; None if absent
    date: str | None              # value of date:; None if absent
    src: str | None               # value of src:; None if absent
    lines: list[ParsedLine]       # all non-metadata, non-routing lines, in document order
```

At most one of `nc`, `c`, `cid` may be non-null. PrefixParserService does not enforce this — the IngestionService validates it (see §9.7).

**Parsing rules:**

- Lines that do not begin with a recognized prefix (or whose prefix is not in the canonical map) are emitted as `ParsedLine(canonical_key="n", text=<full line>)` — treated as plain notes
- `who:`, `date:`, `src:` are extracted into the metadata fields; they do not appear in `lines`
- `nc:`, `c:`, `cid:` are extracted into their respective routing fields; they do not appear in `lines`
- `rel:` lines are parsed syntactically by PrefixParserService to confirm the `>` separator is present; if malformed, the line is emitted as `ParsedLine(canonical_key="n", text=<full line>)` with no error — InferenceService will extract what it can
- Blank lines and comment lines (if any) are discarded
- All other canonical keys (`p`, `fn`, `t`, `proc`, `cs`, `gw`, `kp`, `rm`, `aop`, `s`, `w`, `o`, `th`, `a`, `n`, and any future additions) are emitted verbatim into `lines`; PrefixParserService does not interpret their content

**What PrefixParserService does NOT do:**

- It does not call the LLM
- It does not validate routing fields against the database — that is the IngestionService's responsibility (§9.7)
- It does not enforce that exactly one routing field is set — that is the IngestionService's responsibility
- It does not split comma-separated values (e.g., `tech: Kubernetes, Terraform`) — that is InferenceService's responsibility via the LLM
- It does not infer or reclassify categories

**Downstream consumers of `ParsedSource`:**


| Field                | Consumed by      | Purpose                    |
| -------------------- | ---------------- | -------------------------- |
| `nc`, `c`, `cid`     | IngestionService | Company routing — see §9.7 |
| `who`, `date`, `src` | IngestionService | Store on `sources` record  |
| `lines`              | InferenceService | Construct LLM user message |


---

### 9.7 Company Routing Algorithm

The IngestionService applies the following algorithm synchronously before InferenceService is called. All failures are hard — ingestion does not proceed and the Source is marked `failed` with a descriptive error.

**Validation:**

1. If more than one of `nc`, `c`, `cid` is non-null → fail: `"multiple routing prefixes present; use exactly one of nc:, c:, or cid:"`
2. If all three are null → fail: `"no company routing prefix; add nc: (new company), c: (existing company name), or cid: (existing company id)"`

**Routing:**


| Field set           | Action                                                    | Failure condition                                                                     |
| ------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `nc`                | Query `companies` for exact case-insensitive name match   | Match found → fail: `"company name already exists; use c: to route to it"`            |
| `nc` (no match)     | Create new company record with `name = nc` value; proceed | —                                                                                     |
| `c`                 | Query `companies` for exact case-insensitive name match   | No match → fail: `"no company found with name '{value}'; check spelling or use cid:"` |
| `c` (match found)   | Route source to matched company; proceed                  | —                                                                                     |
| `cid`               | Query `companies` by primary key                          | No match → fail: `"no company found with id '{value}'"`                               |
| `cid` (match found) | Route source to matched company; proceed                  | —                                                                                     |


**Upload endpoint shortcut:**

`POST /sources/upload` accepts an optional `company_id` query parameter. If provided, the IngestionService treats it as equivalent to `cid:` routing — the source is routed directly to that company without requiring a routing prefix in the file content. If `company_id` is provided AND a routing prefix is present in the file, `company_id` takes precedence.

**`POST /companies` (manual create):**

Uses the same exact-match check as `nc:`. If a company with the exact name (case-insensitive) already exists, the request fails with 409 `name_conflict`. No fuzzy warning — the check is binary.

---

## 10. Interfaces / APIs

All endpoints are served by the FastAPI Composition Layer. Base path: `/api/v1`. All requests and responses use JSON unless noted (file uploads use `multipart/form-data`; file downloads return binary with appropriate `Content-Type`). All endpoints except `/auth/login` and `/auth/password/set` require a valid session cookie.

**Error response shape:**

All error responses use a consistent JSON envelope regardless of status code:

```json
{
  "error": {
    "code": "string",     // machine-readable snake_case identifier
    "message": "string",  // human-readable description
    "details": {}         // optional; present for field-level validation errors
  }
}
```

**HTTP status codes:**


| Status | Semantics                                                                                                      |
| ------ | -------------------------------------------------------------------------------------------------------------- |
| 400    | Malformed request body — unparseable JSON, wrong `Content-Type`                                                |
| 401    | Missing or expired session; invalid credentials                                                                |
| 404    | Referenced resource does not exist                                                                             |
| 409    | State conflict — e.g., password already set, retry of a non-failed source                                      |
| 422    | Well-formed but semantically invalid — e.g., unsupported file type, compare endpoint not given exactly two IDs |
| 500    | Unexpected server error; must not include stack traces or internal implementation details                      |


**Validation errors (400 / 422):** when the error is field-level, `details` contains a `fields` array:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": {
      "fields": [
        { "field": "name", "issue": "required" },
        { "field": "format", "issue": "must be one of: pdf, docx" }
      ]
    }
  }
}
```

**Error codes used in this API:**


| Code                       | Status    | Endpoint(s)                                                                                                           |
| -------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------- |
| `unauthenticated`          | 401       | All protected endpoints — session missing or expired                                                                  |
| `invalid_credentials`      | 401       | `POST /auth/login`                                                                                                    |
| `already_set`              | 409       | `POST /auth/password/set`                                                                                             |
| `invalid_current_password` | 401       | `POST /auth/password/change`                                                                                          |
| `not_found`                | 404       | Any endpoint referencing a resource by ID                                                                             |
| `validation_error`         | 400 / 422 | Any endpoint with required fields or constrained inputs                                                               |
| `state_conflict`           | 409       | `POST /sources/{id}/retry` — source is not in `failed` state                                                          |
| `merge_not_applicable`     | 422       | `POST .../merge` — category does not support merge (`relationship`, `action-item`, or non-entity categories)          |
| `invalid_corrected_value`  | 422       | `POST .../correct` — `corrected_value` fails format validation (e.g., missing `>` separator for `relationship` facts) |
| `name_conflict`            | 409       | `POST /companies` — exact company name already exists                                                                 |
| `routing_error`            | 422       | Ingestion — missing, multiple, or unresolvable routing prefix                                                         |
| `internal_error`           | 500       | Any endpoint on unexpected failure                                                                                    |


---

### 10.1 Authentication


| Method | Path                    | Description                                                   |
| ------ | ----------------------- | ------------------------------------------------------------- |
| POST   | `/auth/login`           | Authenticate with username + password; returns session cookie |
| POST   | `/auth/logout`          | Invalidate the current session                                |
| POST   | `/auth/password/set`    | Set password on first access (no existing password required)  |
| POST   | `/auth/password/change` | Change password (requires current password)                   |


**POST `/auth/login`**

- Input: `{ "username": string, "password": string }`
- Output: `{ "ok": true }` + `Set-Cookie: session=...`; or `{ "error": { "code": "invalid_credentials", "message": "Invalid username or password" } }` (401)

**POST `/auth/password/set`**

- Input: `{ "username": string, "password": string }` (called before any session exists)
- Output: `{ "ok": true }` or `{ "error": { "code": "already_set", "message": "Password has already been set" } }` (409)

**POST `/auth/password/change`**

- Input: `{ "current_password": string, "new_password": string }`
- Output: `{ "ok": true }` or `{ "error": { "code": "invalid_current_password", "message": "Current password is incorrect" } }` (401)

---

### 10.2 Companies


| Method | Path              | Description                                                                |
| ------ | ----------------- | -------------------------------------------------------------------------- |
| GET    | `/companies`      | List all companies (name, id, last-updated)                                |
| POST   | `/companies`      | Manually create a company                                                  |
| GET    | `/companies/{id}` | Full company profile (Company + People + CGKRA summary + coverage summary) |
| PUT    | `/companies/{id}` | Update top-level company fields (name, mission, vision)                    |
| DELETE | `/companies/{id}` | Delete company and all associated data                                     |


**GET `/companies`**

- Query params: `limit` (int, default 100, max 1000), `offset` (int, default 0)
- Output: `{ "total": int, "limit": int, "offset": int, "items": [ { "id", "name", "updated_at", "pending_count" } ] }` — ordered by `name` ascending

**POST `/companies`**

- Input: `{ "name": string (required), "mission": string (optional), "vision": string (optional) }`
- Output: `{ "company_id": string, "name": string }` (201)
- Fails with 409 `name_conflict` if a company with the exact name (case-insensitive) already exists — creation is blocked, not warned

**GET `/companies/{id}`**

- Output: `{ "company": {...}, "functional_areas": [...], "people": [...], "cgkra_summary": {...}, "coverage": {...}, "pending_count": int }`

---

### 10.3 Ingestion (Sources)


| Method | Path                      | Description                                                   |
| ------ | ------------------------- | ------------------------------------------------------------- |
| POST   | `/sources/upload`         | Upload a document (triggers async ingestion + LLM extraction) |
| GET    | `/companies/{id}/sources` | List all sources for a company with status                    |
| GET    | `/sources/{id}`           | Get source metadata, raw content, and processing status       |
| GET    | `/sources/{id}/status`    | Lightweight status poll: returns current status (pending \| processing \| processed \| failed) |
| POST   | `/sources/{id}/retry`     | Re-trigger processing of a failed source                      |


**POST `/sources/upload`**

- Input: `multipart/form-data` with fields: `file` (binary), `company_id` (optional — if omitted, company routing is resolved from the routing prefix in the file content via §9.7; if provided, acts as a `cid:` shortcut and takes precedence over any routing prefix in the file)
- Output: `{ "source_id": string, "status": "pending" }`

**GET `/companies/{id}/sources`**

- Query params: `status` (pending | processing | processed | failed | all, default: all), `limit` (int, default 50, max 200), `offset` (int, default 0)
- Output: `{ "total": int, "limit": int, "offset": int, "items": [ { "source_id", "type": "email" | "upload", "subject_or_filename", "received_at", "status", "error": string | null } ] }` — ordered newest-first; `error` is populated only when `status == "failed"`

**POST `/sources/{id}/retry`**

- No input body required
- Output: `{ "source_id": string, "status": "pending" }`; returns 409 if source status is not `failed`

Note: Email ingestion is handled by the background IMAP poller — there is no REST endpoint to submit emails. The poller creates Source records directly via the Service Layer.

---

### 10.4 Pending Review (InferredFacts)


| Method | Path                                        | Description                                                             |
| ------ | ------------------------------------------- | ----------------------------------------------------------------------- |
| GET    | `/companies/{id}/pending`                   | List all pending inferred facts for a company, with disambiguation data |
| POST   | `/companies/{id}/pending/{fact_id}/accept`  | Accept the inferred value as a new entity                               |
| POST   | `/companies/{id}/pending/{fact_id}/merge`   | Merge with an existing entity                                           |
| POST   | `/companies/{id}/pending/{fact_id}/correct` | Accept with an investigator-supplied correction                         |
| POST   | `/companies/{id}/pending/{fact_id}/dismiss` | Dismiss (reject) an inferred fact without accepting it                  |


**GET `/companies/{id}/pending`**

- Query params: `limit` (int, default 50, max 200), `offset` (int, default 0), `category` (optional filter — one of the valid InferredFact categories)
- Output: `{ "total": int, "limit": int, "offset": int, "items": [ { "fact_id", "category", "inferred_value", "source_id", "source_excerpt", "candidates": [ { "entity_id", "value", "similarity_score" } ] } ] }`
- `candidates` meaning varies by category:
  - `person`, `functional-area`, `action-item`: ranked list of existing same-category entities (persons, functional areas, action items) for the company; ordered by fuzzy similarity score against `inferred_value` descending
  - `relationship`: ranked list of existing **persons** for the company, provided twice — once scored against the `subordinate` field, once against the `manager` field; the response shape for relationship facts is `"candidates": { "subordinate": [...], "manager": [...] }` to support per-name disambiguation
  - All other categories: empty array — no entity disambiguation required

**POST `/companies/{id}/pending/{fact_id}/accept`**

Behaviour branches on `category`:

- `**person**`: parse `inferred_value` by splitting on the first comma — left side is `name`, right side (stripped) is `title`; if no comma, full value is `name` and `title` is null. Insert a new row into `persons` with the parsed `name`, `title`, `company_id` from the fact, and `primary_area_id` / `reports_to_person_id` null. Mark the InferredFact `accepted`. If the investigator intends to link to an existing person instead, use `merge`.
- `**relationship**`: the fact carries `subordinate` and `manager` string fields (names). Resolve each name to a `person_id` using the following algorithm: (1) case-insensitive exact match against `persons.name` for the company — if exactly one match, use that ID; (2) no match — create a stub `persons` row with `name = <string>`, `title = null`, `primary_area_id = null`, `reports_to_person_id = null`; (3) multiple matches — use the highest fuzzy-score match. Insert a row into `relationships` with the resolved `subordinate_person_id` and `manager_person_id`. Also set `persons.reports_to_person_id = manager_person_id` on the subordinate record (convenience denormalization). Mark the InferredFact `accepted`. **Side effect**: accepting a relationship fact may implicitly create up to two stub person records if either name is unresolved.
- `**action-item`**: inserts a new row into `action_items` with `description = inferred_value`, `source_id` from the fact's source record, `inferred_fact_id` referencing this fact, `company_id` from the fact, and `person_id` / `functional_area_id` null; then marks the InferredFact `accepted`. The new action item is immediately visible in the action item list and can be updated via `PUT /action-items/{id}`.
- `**functional-area**`: creates a new row in `functional_areas` with `name = inferred_value` and `company_id` from the fact; then marks the InferredFact `accepted`. Disambiguation candidates (from `GET .../pending`) are existing FunctionalArea records for the company — if the investigator intends to link to an existing area rather than create a new one, they should use the `merge` action instead.
- **All other categories**: marks the InferredFact `accepted` in place. No row is inserted into any other table.

**POST `/companies/{id}/pending/{fact_id}/merge`**

- Input: `{ "target_entity_id": string }` — the ID of the existing entity to merge into

Behaviour branches on `category`. Only `person` and `functional-area` support merge — all other categories return 422 `merge_not_applicable`.

- `**person**`: sets `merged_into_entity_type = 'person'` and `merged_into_entity_id = target_entity_id` on the InferredFact; status → `merged`; `reviewed_at` = now(). `target_entity_id` must be the ID of an existing `persons` row for this company — 404 if not found. **No automatic update of the target person's fields** — if the investigator wants to incorporate data from the inferred value (e.g., a title the existing record lacks), they do so explicitly via `PUT /companies/{id}/people/{person_id}`.
- `**functional-area`**: sets `merged_into_entity_type = 'functional_area'` and `merged_into_entity_id = target_entity_id`; status → `merged`; `reviewed_at` = now(). `target_entity_id` must be the ID of an existing `functional_areas` row for this company — 404 if not found. No automatic update of the target area's name.
- `**relationship**`: returns 422 `merge_not_applicable` — there is no relationship entity to merge into; name resolution happens at acceptance time. To force a specific person match, use `correct` to fix the name to exactly match an existing person's name, then `accept`.
- `**action-item**`: returns 422 `merge_not_applicable` — action items are promoted via `accept`, not `merge`.
- **All other categories** (`technology`, `process`, `cgkra-*`, `swot-*`, `other`): returns 422 `merge_not_applicable` — these categories have no corresponding entity table.

**POST `/companies/{id}/pending/{fact_id}/correct`**

- Input: `{ "corrected_value": string }` — investigator override; original inferred value is retained on the InferredFact record and never overwritten

`correct` is semantically equivalent to `accept` with the corrected value substituted for the inferred value. The same entity creation logic fires, using `corrected_value` in place of `inferred_value`. Behaviour branches on `category`:

- `**person**`: parse `corrected_value` (split on first comma → name + title; no comma → full value is name, title null); create new `persons` row from parsed values; status → `corrected`
- `**functional-area**`: create new `functional_areas` row with `name = corrected_value`; status → `corrected`
- `**action-item**`: create new `action_items` row with `description = corrected_value`; status → `corrected`; `inferred_fact_id` set on the new row
- `**relationship**`: parse `corrected_value` as `<subordinate> > <manager>` (same syntax as the `rel:` prefix tag); run the same name-resolution algorithm as `accept` (exact match → stub creation → fuzzy tiebreak); insert `relationships` row and update `persons.reports_to_person_id`; status → `corrected`; returns 422 `invalid_corrected_value` if the `>` separator is absent
- **All other categories** (`technology`, `process`, `cgkra-*`, `swot-*`, `other`): store `corrected_value` on the InferredFact; status → `corrected`; no entity creation — the corrected text is the terminal artifact for these fact types

---

### 10.5 People and Org Chart


| Method | Path                                 | Description                                                  |
| ------ | ------------------------------------ | ------------------------------------------------------------ |
| GET    | `/companies/{id}/people`             | List all people for a company                                |
| POST   | `/companies/{id}/people`             | Manually create a person                                     |
| GET    | `/companies/{id}/people/{person_id}` | Person detail: title, area, notes, action items              |
| PUT    | `/companies/{id}/people/{person_id}` | Update person fields                                         |
| DELETE | `/companies/{id}/people/{person_id}` | Delete person                                                |
| GET    | `/companies/{id}/orgchart`           | Org chart as a hierarchical JSON tree suitable for rendering |


**GET `/companies/{id}/people/{person_id}`**

- Output: `{ "person_id", "name", "title", "primary_area_id", "primary_area_name", "reports_to_person_id", "reports_to_name", "action_items": [ { "item_id", "description", "status", "notes", "created_at" } ], "inferred_facts": [ { "fact_id", "category", "value", "source_id" } ] }` — `inferred_facts` contains accepted and corrected facts linked to this person via `functional_area_id` or directly associated; `action_items` contains all items where `person_id` matches this person

**GET `/companies/{id}/orgchart`**

- Output:
  ```json
  {
    "roots": [
      { "person_id", "name", "title", "reports_to": null, "reports": [ {...} ] }
    ],
    "unplaced": [
      { "person_id", "name", "title" }
    ]
  }
  ```
- `roots`: array of people with no known manager — may be zero, one, or many; each node recurses into `reports`
- `unplaced`: people associated with the company who have no accepted `relationship` InferredFact in either direction (neither a manager nor a subordinate is known); displayed separately in the UI, not silently dropped

---

### 10.6 Functional Areas


| Method | Path                              | Description                                              |
| ------ | --------------------------------- | -------------------------------------------------------- |
| GET    | `/companies/{id}/areas`           | List functional areas for a company                      |
| POST   | `/companies/{id}/areas`           | Manually create a functional area                        |
| GET    | `/companies/{id}/areas/{area_id}` | Area detail: people, CGKRA, action items, facts          |
| PUT    | `/companies/{id}/areas/{area_id}` | Rename or update a functional area                       |
| DELETE | `/companies/{id}/areas/{area_id}` | Delete functional area (does not delete linked entities) |


---

### 10.7 CGKRA


| Method | Path                                    | Description                                                 |
| ------ | --------------------------------------- | ----------------------------------------------------------- |
| GET    | `/companies/{id}/cgkra`                 | Company-wide CGKRA aggregation, with any SWOT signals       |
| GET    | `/companies/{id}/areas/{area_id}/cgkra` | CGKRA for a specific functional area, with any SWOT signals |


**Response shape (both endpoints):**

```json
{
  "current_state":   [ { "fact_id", "value", "source_id" } ],
  "going_well":      [ { "fact_id", "value", "source_id" } ],
  "known_problems":  [ { "fact_id", "value", "source_id" } ],
  "roadmap":         [ { "fact_id", "value", "source_id" } ],
  "art_of_possible": [ { "fact_id", "value", "source_id" } ],
  "swot": {
    "strengths":     [ { "fact_id", "value", "source_id" } ],
    "weaknesses":    [ { "fact_id", "value", "source_id" } ],
    "opportunities": [ { "fact_id", "value", "source_id" } ],
    "threats":       [ { "fact_id", "value", "source_id" } ]
  }
}
```

All entries link to their originating source via `source_id`. CGKRA and SWOT sections are aggregated at query time from InferredFacts — no separate storage entity.

---

### 10.8 Action Items


| Method | Path                           | Description                                              |
| ------ | ------------------------------ | -------------------------------------------------------- |
| GET    | `/action-items`                | All open action items across all companies               |
| GET    | `/companies/{id}/action-items` | Action items for a specific company                      |
| POST   | `/companies/{id}/action-items` | Manually create an action item                           |
| PUT    | `/action-items/{item_id}`      | Update status (open → complete) or add investigator note |
| DELETE | `/action-items/{item_id}`      | Delete an action item                                    |


**GET `/action-items`**

- Query params: `status` (open | complete | all, default: open), `company_id` (optional filter), `person_id` (optional filter), `limit` (int, default 100, max 500), `offset` (int, default 0)
- Output: `{ "total": int, "limit": int, "offset": int, "items": [ { "item_id", "company_id", "company_name", "description", "status", "person_id", "area_id", "notes", "created_at" } ] }`

---

### 10.9 Search


| Method | Path      | Description                                                 |
| ------ | --------- | ----------------------------------------------------------- |
| GET    | `/search` | Full-text search across companies, people, notes, and facts |


**GET `/search`**

- Query params: `q` (required), `type` (companies | people | facts | sources | all, default: all), `company_id` (optional scope), `limit` (int, default 20, max 100), `offset` (int, default 0)
- Output: `{ "total": int, "limit": int, "offset": int, "results": [ { "type", "id", "company_id", "company_name", "excerpt", "score" } ] }`
- Empty results return `{ "total": 0, "results": [] }` (never 404)

**Implementation:**

Full-text search uses PostgreSQL `tsvector`/`tsquery` with GIN indexes. Each searchable table has a stored generated `search_vector tsvector` column (see §11). Queries use `plainto_tsquery('english', q)` — no syntax required from the investigator. Results are ranked by `ts_rank_cd(search_vector, query)`, normalized to a 0–1 float returned as `score`. Results from all applicable tables are unioned and sorted by `score` descending before pagination is applied.

`inferred_facts` are searched only where `status IN ('accepted', 'corrected')` — pending and dismissed facts are excluded from search results.

`excerpt` is generated via `ts_headline('english', source_text, query)` on the primary text column for each result type.

---

### 10.10 Coverage


| Method | Path                       | Description                                                       |
| ------ | -------------------------- | ----------------------------------------------------------------- |
| GET    | `/companies/{id}/coverage` | Coverage dashboard: populated / sparse / empty per discovery area |


**Discovery area definitions:**

Each area is computed from a different source of truth. The mapping is:


| Area         | Counted from                                                                                                                     | `fact_count` meaning                   | Sparse / Populated threshold                                     |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- | ---------------------------------------------------------------- |
| `mission`    | `companies.mission IS NOT NULL`                                                                                                  | 1 if set, 0 if not                     | Binary — no sparse state; status is `populated` or `empty` only  |
| `org`        | Row count in `persons` table for the company                                                                                     | Number of known people                 | Configurable; default sparse < 3, populated ≥ 3                  |
| `tech_stack` | Accepted `inferred_facts` with `category = 'technology'`                                                                         | Number of distinct technology facts    | Configurable; default sparse < 3, populated ≥ 3                  |
| `processes`  | Accepted `inferred_facts` with `category = 'process'`                                                                            | Number of distinct process facts       | Configurable; default sparse < 2, populated ≥ 2                  |
| `cgkra`      | Count of distinct CGKRA sub-categories (`cgkra-cs`, `cgkra-gw`, `cgkra-kp`, `cgkra-rm`, `cgkra-aop`) that have ≥ 1 accepted fact | Number of sub-categories covered (0–5) | Sparse if < 3 sub-categories covered; populated if all 5 covered |


Note: `cgkra` counts sub-categories covered, not total facts — 20 `cgkra-kp` facts with no `cgkra-rm` facts is sparse, not populated.

**Output:**

```json
{
  "areas": {
    "mission":    { "status": "populated" | "empty", "fact_count": int },
    "org":        { "status": "populated" | "sparse" | "empty", "fact_count": int },
    "tech_stack": { "status": "populated" | "sparse" | "empty", "fact_count": int },
    "processes":  { "status": "populated" | "sparse" | "empty", "fact_count": int },
    "cgkra":      { "status": "populated" | "sparse" | "empty", "fact_count": int }
  }
}
```

Sparse/populated thresholds (except `mission`) are configurable. Computed at query time — no stored coverage state.

---

### 10.11 Export (Structured Briefing)


| Method | Path                                  | Description                                                |
| ------ | ------------------------------------- | ---------------------------------------------------------- |
| POST   | `/companies/{id}/export`              | Trigger async generation of a structured briefing document |
| GET    | `/companies/{id}/exports/{export_id}` | Poll status or download the completed file                 |


**POST `/companies/{id}/export`**

- Input: `{ "format": "pdf" | "docx" }` (default: pdf)
- Output: `{ "export_id": string, "status": "pending" }`

**GET `/companies/{id}/exports/{export_id}`**

- Output: if `status == "pending"` or `status == "processing"`: `{ "status": "pending" | "processing" }`; if `status == "ready"`: binary file download with appropriate `Content-Type`; if `status == "failed"`: `{ "status": "failed", "error": string }`

---

### 10.12 CGKRA Narrative Generation


| Method | Path                                       | Description                                     |
| ------ | ------------------------------------------ | ----------------------------------------------- |
| POST   | `/companies/{id}/cgkra-narrative`          | Trigger async AI narrative generation           |
| GET    | `/companies/{id}/cgkra-narrative/{doc_id}` | Poll status or download the completed narrative |


**POST `/companies/{id}/cgkra-narrative`**

- Input: `multipart/form-data` with optional fields:
  - `template_id` (string) — ID of a previously saved template from `cgkra_templates`; 404 if not found
  - `template` (file, Markdown) — inline template upload for one-off use
  - If both are provided, `template_id` takes precedence
  - If neither is provided, default structure is used
- Output: `{ "doc_id": string, "status": "pending" }`
- CGKRA narratives are always generated as Markdown; no format field is accepted or required

**GET `/companies/{id}/cgkra-narrative/{doc_id}`**

- Same status/download pattern as `/exports/{export_id}`; when `status == "ready"`, response is the Markdown file with `Content-Type: text/markdown`
- LLM API failures during generation follow the same retry policy as InferenceService (§9.5 LLM API failure handling); after retries exhausted, `generated_documents.status` is set to `failed` with a descriptive error

---

### 10.13 CGKRA Templates


| Method | Path              | Description                              |
| ------ | ----------------- | ---------------------------------------- |
| GET    | `/templates`      | List all saved CGKRA narrative templates |
| POST   | `/templates`      | Upload and save a reusable template      |
| DELETE | `/templates/{id}` | Delete a template                        |


**POST `/templates`**

- Input: `multipart/form-data` with `file` (Markdown) and `name` (string)
- Output: `{ "template_id": string, "name": string }`

---

## 11. Data Model

All tables use `uuid` primary keys generated by `gen_random_uuid()`. All timestamps are `timestamptz`. Foreign key `ON DELETE` behaviour is noted per column. `merged_into_entity_type` / `merged_into_entity_id` are polymorphic — the application enforces referential integrity since PostgreSQL cannot constrain a polymorphic FK. Coverage, CGKRA, and Timeline views are computed at query time — no tables.

---

### 11.1 `companies`


| Column        | Type        | Null | Default           | Notes                                                                                                                             |
| ------------- | ----------- | ---- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| id            | uuid        | no   | gen_random_uuid() | PK                                                                                                                                |
| name          | text        | no   |                   |                                                                                                                                   |
| mission       | text        | yes  |                   |                                                                                                                                   |
| vision        | text        | yes  |                   |                                                                                                                                   |
| created_at    | timestamptz | no   | now()             |                                                                                                                                   |
| updated_at    | timestamptz | no   | now()             |                                                                                                                                   |
| search_vector | tsvector    | no   | generated         | `to_tsvector('english', coalesce(name,'') || ' ' || coalesce(mission,'') || ' ' || coalesce(vision,''))`; stored generated column |


Indexes: `lower(name)` unique — exact case-insensitive duplicate check; blocks creation on conflict (409 `name_conflict`); GIN `(search_vector)`

---

### 11.2 `functional_areas`


| Column     | Type        | Null | Default           | Notes                                |
| ---------- | ----------- | ---- | ----------------- | ------------------------------------ |
| id         | uuid        | no   | gen_random_uuid() | PK                                   |
| company_id | uuid        | no   |                   | FK → companies(id) ON DELETE CASCADE |
| name       | text        | no   |                   |                                      |
| created_at | timestamptz | no   | now()             |                                      |


Constraints: `UNIQUE(company_id, name)`
Indexes: `(company_id)`

---

### 11.3 `persons`


| Column               | Type        | Null | Default           | Notes                                                                                                                                                              |
| -------------------- | ----------- | ---- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| id                   | uuid        | no   | gen_random_uuid() | PK                                                                                                                                                                 |
| company_id           | uuid        | no   |                   | FK → companies(id) ON DELETE CASCADE                                                                                                                               |
| primary_area_id      | uuid        | yes  |                   | FK → functional_areas(id) ON DELETE SET NULL                                                                                                                       |
| reports_to_person_id | uuid        | yes  |                   | FK → persons(id) ON DELETE SET NULL; self-referential; convenience denormalization updated on relationship acceptance — the `relationships` table is authoritative |
| name                 | text        | no   |                   |                                                                                                                                                                    |
| title                | text        | yes  |                   |                                                                                                                                                                    |
| created_at           | timestamptz | no   | now()             |                                                                                                                                                                    |
| updated_at           | timestamptz | no   | now()             |                                                                                                                                                                    |
| search_vector        | tsvector    | no   | generated         | `to_tsvector('english', coalesce(name,'') || ' ' || coalesce(title,''))`; stored generated column                                                                  |


Indexes: `(company_id)`, `(reports_to_person_id)`, GIN `(search_vector)`

---

### 11.4 `sources`


| Column              | Type        | Null | Default           | Notes                                                                                                                  |
| ------------------- | ----------- | ---- | ----------------- | ---------------------------------------------------------------------------------------------------------------------- |
| id                  | uuid        | no   | gen_random_uuid() | PK                                                                                                                     |
| company_id          | uuid        | no   |                   | FK → companies(id) ON DELETE CASCADE; set synchronously by IngestionService before InferenceService runs (§9.7)        |
| type                | text        | no   |                   | CHECK IN ('email', 'upload')                                                                                           |
| filename_or_subject | text        | yes  |                   |                                                                                                                        |
| raw_content         | text        | no   |                   | extracted text (email body or parsed document text)                                                                    |
| file_path           | text        | yes  |                   | relative path under BLACKBOOK_DATA_DIR/sources/{company_id}/; null for emails with no attachment                       |
| received_at         | timestamptz | no   | now()             | ingestion timestamp — when the source arrived in BlackBook                                                             |
| who                 | text        | yes  |                   | value of `who:` prefix tag — the contact or interviewee who provided the information                                   |
| interaction_date    | text        | yes  |                   | value of `date:` prefix tag — the date of the interaction (free-form string; not parsed); distinct from `received_at`  |
| src                 | text        | yes  |                   | value of `src:` prefix tag — investigator-supplied provenance label (e.g., "Q4 interview", "board deck")               |
| status              | text        | no   | 'pending'         | CHECK IN ('pending', 'processing', 'processed', 'failed')                                                              |
| error               | text        | yes  |                   | failure description; populated when status = 'failed'                                                                  |
| raw_llm_response    | text        | yes  |                   | raw LLM output stored for diagnostics when validation fails (§9.5)                                                     |
| search_vector       | tsvector    | no   | generated         | `to_tsvector('english', coalesce(filename_or_subject,'') || ' ' || coalesce(raw_content,''))`; stored generated column |


Indexes: `(company_id)`, `(status)`, `(received_at DESC)`, GIN `(search_vector)`

---

### 11.5 `inferred_facts`


| Column                  | Type        | Null | Default           | Notes                                                                                                                                                                                                         |
| ----------------------- | ----------- | ---- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| id                      | uuid        | no   | gen_random_uuid() | PK                                                                                                                                                                                                            |
| source_id               | uuid        | no   |                   | FK → sources(id) ON DELETE CASCADE                                                                                                                                                                            |
| company_id              | uuid        | no   |                   | FK → companies(id) ON DELETE CASCADE; denormalized for query efficiency                                                                                                                                       |
| functional_area_id      | uuid        | yes  |                   | FK → functional_areas(id) ON DELETE SET NULL                                                                                                                                                                  |
| category                | text        | no   |                   | CHECK IN ('functional-area', 'person', 'relationship', 'technology', 'process', 'cgkra-cs', 'cgkra-gw', 'cgkra-kp', 'cgkra-rm', 'cgkra-aop', 'swot-s', 'swot-w', 'swot-o', 'swot-th', 'action-item', 'other') |
| inferred_value          | text        | no   |                   | raw value as returned by LLM; never overwritten                                                                                                                                                               |
| corrected_value         | text        | yes  |                   | investigator override; populated when status = 'corrected'                                                                                                                                                    |
| status                  | text        | no   | 'pending'         | CHECK IN ('pending', 'accepted', 'corrected', 'merged', 'dismissed')                                                                                                                                          |
| merged_into_entity_type | text        | yes  |                   | CHECK IN ('person', 'functional_area'); must be non-null when status = 'merged'                                                                                                                               |
| merged_into_entity_id   | uuid        | yes  |                   | references the appropriate table per entity_type; must be non-null when status = 'merged'                                                                                                                     |
| reviewed_at             | timestamptz | yes  |                   | set when investigator accepts, corrects, merges, or dismisses                                                                                                                                                 |
| created_at              | timestamptz | no   | now()             |                                                                                                                                                                                                               |
| search_vector           | tsvector    | no   | generated         | `to_tsvector('english', coalesce(inferred_value,'') || ' ' || coalesce(corrected_value,''))`; stored generated column; queried only where `status IN ('accepted', 'corrected')`                               |


Constraints:

- `CHECK (status != 'merged' OR (merged_into_entity_type IS NOT NULL AND merged_into_entity_id IS NOT NULL))`
- `CHECK (status != 'corrected' OR corrected_value IS NOT NULL)`

Category-specific behaviour by review action (see §10.4 for full specification):


| Category          | `accept`                                                             | `correct`                                                   | `merge`                                      |
| ----------------- | -------------------------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------- |
| `person`          | Parse name+title; create `persons` row                               | Same as accept using corrected_value                        | Link to existing person; no field absorption |
| `functional-area` | Create `functional_areas` row                                        | Same as accept using corrected_value                        | Link to existing area; no name update        |
| `relationship`    | Resolve names → person IDs; create stubs; insert `relationships` row | Re-parse `subordinate > manager`; same resolution           | 422                                          |
| `action-item`     | Promote to `action_items` table                                      | Same as accept using corrected_value                        | 422                                          |
| All others        | Mark `accepted` in place                                             | Store corrected_value; mark `corrected`; no entity creation | 422                                          |


`merged_into_entity_type` valid values: `person`, `functional_area` — only categories that support merge (see §10.4). All other categories return 422 `merge_not_applicable`.

Indexes: `(company_id, status)` — pending review queue, `(source_id)`, `(category)`, `(functional_area_id)`, GIN `(search_vector)`

---

### 11.6 `relationships`

Stores accepted reporting relationships. Authoritative source for org chart construction. Written when a `relationship` InferredFact is accepted; also triggers update of `persons.reports_to_person_id` for the primary line.


| Column                | Type        | Null | Default           | Notes                                                                                                    |
| --------------------- | ----------- | ---- | ----------------- | -------------------------------------------------------------------------------------------------------- |
| id                    | uuid        | no   | gen_random_uuid() | PK                                                                                                       |
| company_id            | uuid        | no   |                   | FK → companies(id) ON DELETE CASCADE                                                                     |
| subordinate_person_id | uuid        | no   |                   | FK → persons(id) ON DELETE CASCADE                                                                       |
| manager_person_id     | uuid        | no   |                   | FK → persons(id) ON DELETE CASCADE                                                                       |
| inferred_fact_id      | uuid        | yes  |                   | FK → inferred_facts(id) ON DELETE SET NULL; the fact that produced this relationship; retained for audit |
| created_at            | timestamptz | no   | now()             |                                                                                                          |


Constraints: `UNIQUE(subordinate_person_id, manager_person_id)`
Indexes: `(company_id)`, `(subordinate_person_id)`, `(manager_person_id)`

Org chart derivation:

- `roots` — persons where no row in `relationships` has `subordinate_person_id = person.id`
- `unplaced` — persons where no row in `relationships` references `person.id` in either column

---

### 11.7 `action_items`


| Column             | Type        | Null | Default           | Notes                                                                                                    |
| ------------------ | ----------- | ---- | ----------------- | -------------------------------------------------------------------------------------------------------- |
| id                 | uuid        | no   | gen_random_uuid() | PK                                                                                                       |
| company_id         | uuid        | no   |                   | FK → companies(id) ON DELETE CASCADE                                                                     |
| person_id          | uuid        | yes  |                   | FK → persons(id) ON DELETE SET NULL                                                                      |
| functional_area_id | uuid        | yes  |                   | FK → functional_areas(id) ON DELETE SET NULL                                                             |
| source_id          | uuid        | yes  |                   | FK → sources(id) ON DELETE SET NULL; null if manually created                                            |
| inferred_fact_id   | uuid        | yes  |                   | FK → inferred_facts(id) ON DELETE SET NULL; the fact that produced this item; null if manually created   |
| description        | text        | no   |                   |                                                                                                          |
| status             | text        | no   | 'open'            | CHECK IN ('open', 'complete')                                                                            |
| notes              | text        | yes  |                   | investigator-added follow-up notes                                                                       |
| created_at         | timestamptz | no   | now()             |                                                                                                          |
| completed_at       | timestamptz | yes  |                   | set when status transitions to 'complete'                                                                |
| search_vector      | tsvector    | no   | generated         | `to_tsvector('english', coalesce(description,'') || ' ' || coalesce(notes,''))`; stored generated column |


Indexes: `(company_id, status)`, `(status)` — cross-company action item list, GIN `(search_vector)`

---

### 11.8 `cgkra_templates`


| Column     | Type        | Null | Default           | Notes                                             |
| ---------- | ----------- | ---- | ----------------- | ------------------------------------------------- |
| id         | uuid        | no   | gen_random_uuid() | PK                                                |
| name       | text        | no   |                   |                                                   |
| file_path  | text        | no   |                   | relative path under BLACKBOOK_DATA_DIR/templates/ |
| created_at | timestamptz | no   | now()             |                                                   |


---

### 11.9 `generated_documents`


| Column       | Type        | Null | Default           | Notes                                                                          |
| ------------ | ----------- | ---- | ----------------- | ------------------------------------------------------------------------------ |
| id           | uuid        | no   | gen_random_uuid() | PK                                                                             |
| company_id   | uuid        | no   |                   | FK → companies(id) ON DELETE CASCADE                                           |
| type         | text        | no   |                   | CHECK IN ('briefing', 'cgkra-narrative')                                       |
| format       | text        | no   |                   | CHECK IN ('pdf', 'docx', 'markdown'); briefing rows use 'pdf' or 'docx'; cgkra-narrative rows always use 'markdown' |
| status       | text        | no   | 'pending'         | CHECK IN ('pending', 'processing', 'ready', 'failed')                          |
| file_path    | text        | yes  |                   | relative path under BLACKBOOK_DATA_DIR/exports/{company_id}/; null until ready |
| template_id  | uuid        | yes  |                   | FK → cgkra_templates(id) ON DELETE SET NULL                                    |
| error        | text        | yes  |                   | populated when status = 'failed'                                               |
| created_at   | timestamptz | no   | now()             |                                                                                |
| completed_at | timestamptz | yes  |                   | set when status reaches 'ready' or 'failed'                                    |


Indexes: `(company_id, type)`, `(status)`

---

### 11.10 `sessions`


| Column         | Type        | Null | Default | Notes                                                                                               |
| -------------- | ----------- | ---- | ------- | --------------------------------------------------------------------------------------------------- |
| token          | text        | no   |         | PK; 32-byte cryptographically random hex string (§7.3)                                              |
| created_at     | timestamptz | no   | now()   |                                                                                                     |
| last_active_at | timestamptz | no   | now()   | updated on every authenticated request; expiry check: `now() − last_active_at > configured_timeout` |


Indexes: `(last_active_at)` — daily cleanup of expired sessions

Note: no `user_id` column — single-user system; the token alone identifies the session.

---

### 11.11 `credentials`

Stores the single investigator's username and hashed password. The application enforces a one-row constraint — `POST /auth/password/set` fails with 409 `already_set` if a row already exists.


| Column        | Type        | Null | Default | Notes                                           |
| ------------- | ----------- | ---- | ------- | ----------------------------------------------- |
| id            | integer     | no   | 1       | PK; fixed value; enforces single-row invariant  |
| username      | text        | no   |         |                                                 |
| password_hash | text        | no   |         | bcrypt hash; plaintext password is never stored |
| updated_at    | timestamptz | no   | now()   | updated on every password change                |


No indexes required — the table always has exactly one row and is always accessed by `id = 1`.

---

### 11.12 Computed Views (no tables)


| View                  | Derived from                                                                                                                        |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Coverage — mission    | `companies.mission IS NOT NULL` for the given `company_id`                                                                          |
| Coverage — org        | Row count in `persons` for the given `company_id`                                                                                   |
| Coverage — tech_stack | Accepted `inferred_facts` with `category = 'technology'` for the given `company_id`                                                 |
| Coverage — processes  | Accepted `inferred_facts` with `category = 'process'` for the given `company_id`                                                    |
| Coverage — cgkra      | Count of distinct CGKRA sub-categories with ≥ 1 accepted fact for the given `company_id` (see §10.10)                               |
| CGKRA (company-wide)  | Accepted `inferred_facts` with `category` IN ('cgkra-cs', 'cgkra-gw', 'cgkra-kp', 'cgkra-rm', 'cgkra-aop') for a given `company_id` |
| CGKRA (per area)      | Same as above filtered by `functional_area_id`                                                                                      |
| SWOT                  | Accepted `inferred_facts` with `category` IN ('swot-s', 'swot-w', 'swot-o', 'swot-th')                                              |
| Timeline              | `sources` ordered by `received_at` for a given `company_id`                                                                         |


---

## 12. Success Metrics

How success will be measured.

- Metric 1:
- Metric 2:

---

## 13. Open Questions

Things that are not yet decided.

- Question 1:
- Question 2:

---

## 14. Assumptions

Things assumed to be true.

- Assumption 1:
- Assumption 2:

---

## 15. Risks

Potential issues or uncertainties.

- Risk 1:
- Risk 2:

---

## 16. Agent Instructions (Important for LLMs)

Guidance specifically for LLM agents working on this project. These rules are mandatory — do not override them with inferred conventions or personal style preferences.

### 16.1 Priorities

**correctness > simplicity > speed**

- **Correctness**: the system must produce the right result. Every acceptance flow, routing decision, and state transition must match the specification in §10.4, §9.5, and §9.7 exactly. Write tests that verify correctness before optimizing anything.
- **Simplicity**: prefer the straightforward implementation. Do not introduce abstractions, caching layers, or indirection unless the requirements explicitly call for them. One obvious way to do something is better than a clever way.
- **Speed**: performance is the lowest priority. The system serves one user at modest data volumes. Do not optimize queries, add indexes beyond those specified in §11, introduce connection pooling, or cache results unless a measured performance problem exists.

When these priorities conflict, correctness wins. When correctness is satisfied and there is a choice between a simple solution and a faster one, choose the simple one.

### 16.2 Coding Guidelines

**Python (backend):**

- Style: PEP 8. Use type hints on all function signatures and return types. Use `snake_case` for functions, variables, and file names. Use `PascalCase` for classes. Use `UPPER_SNAKE_CASE` for constants.
- Formatting: use `black` with default settings. Use `isort` for import ordering.
- Async: use `async def` for route handlers and service methods that perform I/O (database, LLM API, filesystem). Use synchronous functions for pure computation (e.g., PrefixParserService parsing logic).
- Dependencies: use `pydantic` for request/response schemas and configuration. Use `sqlalchemy` (async) for ORM models and repository queries. Use `alembic` for database migrations.

**TypeScript/React (frontend):**

- Style: use `camelCase` for functions and variables. Use `PascalCase` for React components, types, and interfaces. Use `PascalCase.tsx` for component files. Use `camelCase.ts` for non-component modules (API clients, utilities, hooks).
- Formatting: use `prettier` with default settings.
- State management: use React built-ins (`useState`, `useReducer`, `useContext`) unless complexity demands otherwise. Do not introduce Redux, Zustand, or MobX.
- Data fetching: use `fetch` with a thin typed wrapper (see `frontend/src/api/`). Do not introduce Axios, React Query, or SWR unless a specific problem requires it.

**Patterns to follow:**

- **Services accept and return Pydantic models, never raw dicts.** Every service method has a typed input and a typed output. No `dict` or `Any` in service signatures.
- **Repositories return SQLAlchemy model instances.** Services convert between SQLAlchemy models and Pydantic schemas. Route handlers never touch SQLAlchemy models directly.
- **Route handlers use FastAPI `Depends()` for service injection.** Services are instantiated via dependency injection, not imported as module-level singletons.
- **All database access goes through repository classes.** No raw SQL, no direct `session.execute()` calls outside the repository layer. Repositories are the only code that imports from `sqlalchemy`.
- **One repository class per database table.** Repository methods are named for the operation they perform: `get_by_id`, `list_by_company`, `create`, `update_status`, etc.
- **One service class per domain concept**, matching the list in §9.1. Services may call other services (e.g., IngestionService calls PrefixParserService and InferenceService). Services never call repositories belonging to other services — if cross-domain data is needed, call the other service.
- **Domain exceptions for error cases.** Each service defines its own exception classes (e.g., `CompanyNotFoundError`, `SourceNotFailedError`, `RoutingError`). These are plain Python exceptions, not HTTP-aware. They carry a machine-readable `code` attribute matching the error codes in §10.
- **Route handlers catch domain exceptions and map to HTTP responses.** The composition layer is the only place that knows about HTTP status codes. Use a shared exception handler (FastAPI exception handler) to convert domain exceptions to the error envelope defined in §10.
- **Pydantic schemas live in a `schemas/` directory**, organized by domain: `schemas/company.py`, `schemas/source.py`, `schemas/inferred_fact.py`, etc. Request and response models are defined in the same file for each domain.
- **Alembic migrations are the only mechanism for schema changes.** Never use `create_all()` in application code. Every table, index, and constraint defined in §11 must be created via a migration.

**Patterns to avoid:**

- **No business logic in route handlers.** Route handlers call services and return responses. They do not contain conditional logic, database queries, or data transformations beyond schema conversion.
- **No ORM imports outside the repository layer.** If you find yourself importing `sqlalchemy` in a service or route handler, refactor.
- **No mutable global state.** No module-level variables that accumulate state across requests. Configuration is read once at startup and passed via dependency injection.
- **No `from x import *`.** All imports are explicit.
- **No inline SQL strings.** Use SQLAlchemy's expression language or ORM query API in repositories.
- **No premature abstraction.** Do not create base classes, mixins, generic repositories, or factory patterns unless three or more concrete implementations exist and share significant logic. Start concrete; refactor to abstract only when duplication is proven.
- **No print statements for logging.** Use Python's `logging` module with structured log messages.

### 16.3 Decision-Making Rules

- **When ambiguous**: re-read the relevant section of this document. If the answer is still unclear, choose the simplest interpretation that preserves correctness. Do not invent features or behaviors not described in this document. If a decision has non-trivial downstream consequences, add a `# DECISION:` comment in the code explaining the choice and the section of the requirements that informed it.
- **When requirements conflict**: correctness wins. If two sections of this document contradict each other, follow the more specific section (e.g., §10.4 overrides §6.1 on acceptance behavior; §9.7 overrides §6.1 on routing). Flag the conflict with a `# CONFLICT:` comment citing both sections.
- **When the requirements are silent**: do the minimum. If a behavior is not specified, do not implement it. For example: if no sorting order is specified for a list endpoint, return results in database natural order (typically insertion order). Do not add sorting, filtering, or pagination beyond what is explicitly specified in this document.
- **When choosing between libraries**: prefer the standard library or the libraries already listed in §8 (FastAPI, SQLAlchemy, Pydantic, Alembic, React). Do not introduce new dependencies without a clear, stated reason tied to a specific requirement.

### 16.4 Output Expectations

**Project directory layout:**

```
blackbook/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI application factory
│   │   ├── config.py                  # Pydantic Settings — all configuration
│   │   ├── dependencies.py            # FastAPI dependency providers
│   │   ├── exceptions.py              # Base domain exception classes
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py          # Top-level router aggregating all sub-routers
│   │   │       ├── auth.py            # /auth/* route handlers
│   │   │       ├── companies.py       # /companies/* route handlers
│   │   │       ├── sources.py         # /sources/* route handlers
│   │   │       ├── pending.py         # /companies/{id}/pending/* route handlers
│   │   │       ├── people.py          # /companies/{id}/people/* and orgchart
│   │   │       ├── areas.py           # /companies/{id}/areas/*
│   │   │       ├── cgkra.py           # /companies/{id}/cgkra/*
│   │   │       ├── action_items.py    # /action-items/* and /companies/{id}/action-items/*
│   │   │       ├── search.py          # /search
│   │   │       ├── coverage.py        # /companies/{id}/coverage
│   │   │       ├── exports.py         # /companies/{id}/export/* and /companies/{id}/exports/*
│   │   │       ├── narratives.py      # /companies/{id}/cgkra-narrative/*
│   │   │       └── templates.py       # /templates/*
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── company_service.py
│   │   │   ├── ingestion_service.py
│   │   │   ├── inference_service.py
│   │   │   ├── prefix_parser_service.py
│   │   │   ├── review_service.py
│   │   │   ├── person_service.py
│   │   │   ├── cgkra_service.py
│   │   │   ├── action_item_service.py
│   │   │   ├── search_service.py
│   │   │   ├── export_service.py
│   │   │   └── auth_service.py
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── company_repository.py
│   │   │   ├── functional_area_repository.py
│   │   │   ├── person_repository.py
│   │   │   ├── source_repository.py
│   │   │   ├── inferred_fact_repository.py
│   │   │   ├── relationship_repository.py
│   │   │   ├── action_item_repository.py
│   │   │   ├── template_repository.py
│   │   │   ├── generated_document_repository.py
│   │   │   ├── session_repository.py
│   │   │   └── credential_repository.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── base.py                # SQLAlchemy declarative base + all ORM model classes
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── company.py
│   │   │   ├── source.py
│   │   │   ├── inferred_fact.py
│   │   │   ├── person.py
│   │   │   ├── functional_area.py
│   │   │   ├── relationship.py
│   │   │   ├── action_item.py
│   │   │   ├── cgkra.py
│   │   │   ├── search.py
│   │   │   ├── coverage.py
│   │   │   ├── export.py
│   │   │   └── template.py
│   │   └── workers/
│   │       ├── __init__.py
│   │       ├── ingestion_worker.py    # Background ingestion task (file + email)
│   │       ├── export_worker.py       # Background export/narrative generation
│   │       ├── email_poller.py        # IMAP polling loop
│   │       └── cleanup_worker.py      # TTL-based export cleanup + expired session cleanup
│   ├── alembic/
│   │   ├── alembic.ini
│   │   ├── env.py
│   │   └── versions/                  # Migration files
│   ├── tests/
│   │   ├── conftest.py                # Fixtures: test DB, test client, service mocks
│   │   ├── test_services/
│   │   │   ├── test_company_service.py
│   │   │   ├── test_ingestion_service.py
│   │   │   ├── test_inference_service.py
│   │   │   ├── test_prefix_parser_service.py
│   │   │   ├── test_review_service.py
│   │   │   ├── test_person_service.py
│   │   │   ├── test_auth_service.py
│   │   │   └── ...
│   │   ├── test_repositories/
│   │   │   └── ...
│   │   └── test_api/
│   │       ├── test_auth.py
│   │       ├── test_companies.py
│   │       ├── test_sources.py
│   │       ├── test_pending.py
│   │       └── ...
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts              # Typed fetch wrapper; handles session cookie, error envelope
│   │   │   ├── companies.ts           # Company API functions
│   │   │   ├── sources.ts
│   │   │   ├── pending.ts
│   │   │   ├── people.ts
│   │   │   ├── cgkra.ts
│   │   │   ├── actionItems.ts
│   │   │   ├── search.ts
│   │   │   ├── coverage.ts
│   │   │   ├── exports.ts
│   │   │   ├── auth.ts
│   │   │   └── templates.ts
│   │   ├── components/
│   │   │   ├── OrgChart.tsx
│   │   │   ├── PendingReviewQueue.tsx
│   │   │   ├── CGKRAView.tsx
│   │   │   ├── CoverageDashboard.tsx
│   │   │   ├── ActionItemList.tsx
│   │   │   ├── SourceList.tsx
│   │   │   ├── SearchResults.tsx
│   │   │   └── ...                    # Shared UI components
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── CompanyListPage.tsx
│   │   │   ├── CompanyProfilePage.tsx
│   │   │   ├── OrgChartPage.tsx
│   │   │   ├── CGKRAPage.tsx
│   │   │   ├── ActionItemsPage.tsx
│   │   │   ├── SearchPage.tsx
│   │   │   ├── SourcesPage.tsx
│   │   │   └── SettingsPage.tsx       # Password change
│   │   ├── hooks/                     # Custom React hooks
│   │   ├── types/                     # Shared TypeScript type definitions
│   │   ├── App.tsx
│   │   └── index.tsx
│   ├── package.json
│   └── tsconfig.json
└── REQUIREMENTS.md
```

This layout is canonical. Do not reorganize, rename, or add directories without a requirement-driven reason. When adding a new file, place it in the appropriate existing directory.

**Naming conventions:**

| Context | Convention | Example |
|---------|-----------|---------|
| Python files | `snake_case.py` | `company_service.py` |
| Python classes | `PascalCase` | `CompanyService`, `CompanyNotFoundError` |
| Python functions/variables | `snake_case` | `get_by_id`, `company_id` |
| Python constants | `UPPER_SNAKE_CASE` | `MAX_RETRY_ATTEMPTS` |
| Database tables | `snake_case` plural | `companies`, `inferred_facts` |
| Database columns | `snake_case` | `company_id`, `inferred_value` |
| Alembic migrations | auto-generated with descriptive `message` | `create_companies_table` |
| TypeScript component files | `PascalCase.tsx` | `OrgChart.tsx` |
| TypeScript non-component files | `camelCase.ts` | `client.ts`, `companies.ts` |
| TypeScript components | `PascalCase` | `OrgChart`, `PendingReviewQueue` |
| TypeScript functions/variables | `camelCase` | `fetchCompany`, `companyId` |
| TypeScript types/interfaces | `PascalCase` | `Company`, `InferredFact` |
| API route paths | `kebab-case` | `/action-items`, `/cgkra-narrative` |
| Error codes | `snake_case` | `name_conflict`, `merge_not_applicable` |

**Testing expectations:**

- **Framework**: `pytest` with `pytest-asyncio` for async tests.
- **Database**: tests run against a real PostgreSQL database (not SQLite). Use a dedicated test database created and torn down per test session. Use transaction rollback per test for isolation.
- **What to test**:
  - **Service layer**: test every public method of every service. These are the most important tests — they verify business logic, state transitions, and cross-service interactions. Mock the repository layer using dependency injection, or use the real repository against the test database.
  - **Repository layer**: test queries that involve non-trivial logic (joins, filters, aggregations, fuzzy matching). Simple CRUD methods do not need dedicated tests if they are exercised by service tests.
  - **API layer**: test each endpoint via FastAPI's `TestClient`. Verify request validation, response shapes, status codes, and error codes from the error code table in §10. These are integration tests — they exercise the full stack from route handler through service to repository.
  - **PrefixParserService**: test thoroughly with unit tests — this is pure computation with no I/O. Cover every canonical key, every alias, unrecognized prefixes, malformed `rel:` lines, missing routing prefixes, and edge cases (blank lines, multiple routing prefixes).
  - **InferenceService validation**: test the LLM response validation logic (§9.5) with unit tests using canned JSON responses — valid, malformed, missing fields, wrong categories, empty arrays.
- **What NOT to test**: do not write tests for Pydantic schema definitions, configuration loading, or ORM model declarations. These are declarative and tested implicitly by the service and API tests.
- **LLM in tests**: **never call a real LLM API in tests.** Mock InferenceService at the service boundary. For InferenceService's own tests, mock the HTTP client that calls the LLM provider and return canned responses.
- **Test file naming**: mirror the source file — `test_company_service.py` tests `company_service.py`.

**Documentation expectations:**

- **Docstrings**: every public service method gets a one-line docstring describing what it does. Repository methods and route handlers do not need docstrings — their names and type signatures are sufficient.
- **Inline comments**: use sparingly. Prefer clear code over explanatory comments. Use `# DECISION:` and `# CONFLICT:` comments as described in §16.3.
- **No README or markdown files** beyond this `REQUIREMENTS.md` unless explicitly requested.

---

## 17. Milestones / Phases

Each phase produces a deployable, testable system. At the end of each phase, the application can be started and the implemented features exercised through the UI. Do not begin a subsequent phase until all tests for the current phase pass.

### Phase 1 — Foundation: Data Model + Auth + Company CRUD + Frontend Scaffold

**Detailed decomposition**: see [`PHASE1.md`](PHASE1.md) for the step-by-step checklist of 5 sequential units of work.

**Goal**: a running application with login, company list, manual company create/edit/delete, and an empty company profile page.

**Backend:**
- Alembic migrations for all tables in §11 (create the entire schema upfront — this prevents migration conflicts in later phases)
- AuthService: `POST /auth/password/set`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/password/change`; session middleware that validates the `session` cookie on every protected request
- CompanyService: `GET /companies`, `POST /companies`, `GET /companies/{id}`, `PUT /companies/{id}`, `DELETE /companies/{id}`
- Error envelope and exception handler per §10
- Configuration via Pydantic Settings (`config.py`)

**Frontend:**
- React scaffold with routing
- Login page (UC 12), first-time password set page (UC 13)
- Company list page showing all companies with `pending_count`
- Company create form (UC 19)
- Company profile page — renders company fields (name, mission, vision); edit form (UC 17 for company fields); all other sections (people, CGKRA, coverage, sources) are placeholder/empty
- Settings page for password change (UC 14)

**Tests:**
- AuthService: login, logout, session expiry, password set idempotency (409), password change with wrong current password (401)
- CompanyService: create, duplicate name (409), list, get, update, delete cascade
- API tests for all auth and company endpoints

**Exit criteria**: investigator can log in, create companies, view the company list, open a company profile, edit company fields, and change their password.

---

### Phase 2 — Ingestion Pipeline: Upload + Prefix Parser + LLM Extraction + Pending Review (Accept Only)

**Goal**: the investigator can upload a file, the system extracts inferred facts via LLM, and the investigator can accept simple facts (person, functional-area, technology, process, CGKRA, SWOT, action-item, other).

**Backend:**
- PrefixParserService (§9.6): full implementation with all canonical keys; unit tests covering every alias and edge case
- Company routing algorithm (§9.7): implemented within IngestionService
- InferenceService (§9.5): LLM prompt construction, response validation, retry policy; mock LLM in tests
- IngestionService: `POST /sources/upload`, `GET /companies/{id}/sources`, `GET /sources/{id}`, `GET /sources/{id}/status`, `POST /sources/{id}/retry`
- Background worker for async ingestion (ingestion_worker.py)
- Pending review endpoints: `GET /companies/{id}/pending`, `POST .../accept`, `POST .../dismiss`
- Accept flow for all categories per §10.4 — person (parse name+title, create persons row), functional-area (create functional_areas row), action-item (promote to action_items), relationship (name resolution + stub creation + relationships row), all others (mark accepted in place)
- Dismiss flow: mark InferredFact `dismissed`

**Frontend:**
- File upload component on the company profile page
- Source list on the company profile (UC 18) — status, error display, retry button
- Pending review queue component (UC 5) — list pending facts, accept button, dismiss button
- Company profile page now shows accepted people, functional areas, technologies, processes

**Tests:**
- PrefixParserService: exhaustive unit tests for all canonical keys, aliases, routing fields, metadata extraction, malformed rel: lines, unrecognized prefixes
- InferenceService: validation logic with canned LLM responses (valid, malformed JSON, missing fields, empty array, wrong category, relationship without subordinate/manager)
- IngestionService: routing algorithm (nc/c/cid), upload with company_id shortcut, retry of non-failed source (409)
- Accept flow: one test per category verifying the correct entity creation behavior
- API tests for all source and pending endpoints

**Exit criteria**: investigator can upload a document with prefix tags, the system extracts facts, the investigator can review and accept/dismiss them, and accepted facts appear in the company profile.

---

### Phase 3 — Full Review Flow + Org Chart + Person Management

**Goal**: the investigator can merge and correct facts, navigate the org chart, and manage people.

**Backend:**
- Merge flow per §10.4: person merge, functional-area merge, 422 for all other categories
- Correct flow per §10.4: person correct (parse corrected value), functional-area correct, action-item correct, relationship correct (parse subordinate > manager, name resolution), all others (store corrected_value)
- Disambiguation candidates: fuzzy matching for `GET .../pending` — ranked candidates per category
- People endpoints: `GET /companies/{id}/people`, `POST /companies/{id}/people`, `GET/PUT/DELETE /companies/{id}/people/{person_id}`
- Org chart endpoint: `GET /companies/{id}/orgchart` — roots, unplaced, recursive tree
- Functional area endpoints: `GET/POST/PUT/DELETE /companies/{id}/areas/*`
- In-place editing of accepted entities (UC 17): PUT endpoints for people, functional areas, accepted inferred facts

**Frontend:**
- Pending review queue with merge (select from candidates) and correct (text input) actions
- Org chart visualization (UC 6) — interactive tree with multiple roots; unplaced section; click-to-detail
- Person detail view: title, area, notes, action items
- Functional area list and detail view
- Edit forms for people and functional areas (UC 17)

**Tests:**
- Merge flow: person merge to existing person, functional-area merge, 422 for unsupported categories, 404 for invalid target_entity_id
- Correct flow: person correct with comma (name+title), relationship correct with > separator, relationship correct without > (422), action-item correct
- Disambiguation: verify candidate list is returned and ordered by similarity (person candidates) or name (functional-area candidates); verify empty list when no entities exist for the company
- Org chart: verify roots, unplaced, and recursive tree construction for various relationship configurations (single root, multiple roots, no roots, cycles if any)
- People CRUD: create, update, delete with CASCADE behavior on relationships

**Exit criteria**: investigator can merge, correct, and dismiss facts; navigate the org chart; click into person details; manage people and functional areas directly.

---

### Phase 4 — CGKRA + SWOT + Coverage + Search

**Goal**: the investigator can view CGKRA analysis, coverage dashboard, and search across companies.

**Backend:**
- CGKRA endpoints: `GET /companies/{id}/cgkra`, `GET /companies/{id}/areas/{area_id}/cgkra` — aggregate from accepted inferred facts; include SWOT signals
- Coverage endpoint: `GET /companies/{id}/coverage` — computed from §10.10 definitions with configurable thresholds
- Search endpoint: `GET /search` — PostgreSQL `tsvector`/`tsquery` full-text search; union across companies, persons, sources, inferred_facts; score and excerpt; respect `company_id` scope filter
- Within-company search (Must Have) and cross-company search (Nice to Have) both implemented via the same endpoint with optional `company_id`

**Frontend:**
- CGKRA view per functional area and company-wide (UC 7) — five CGKRA sections plus SWOT panel; each entry links to source
- Coverage dashboard (UC 11) — five areas with populated/sparse/empty indicators; click to navigate to relevant section
- Search page (UC 9) — search bar, type filter, results with excerpts and links to originating company/source
- Company profile page now integrates CGKRA summary and coverage summary

**Tests:**
- CGKRA aggregation: verify facts are grouped by sub-category and filtered by functional_area_id; verify SWOT signals appear alongside CGKRA
- Coverage: verify threshold logic for each area (mission binary, org/tech/process count-based, cgkra sub-category-based); verify configurable thresholds
- Search: verify tsvector ranking, excerpt generation, type filtering, company scoping, exclusion of pending/dismissed facts
- API tests for all CGKRA, coverage, and search endpoints

**Exit criteria**: investigator can view CGKRA by area and company-wide, see SWOT signals, check coverage gaps, and search across all data.

---

### Phase 5 — Export + CGKRA Narrative Generation + Templates

**Goal**: the investigator can generate downloadable briefing documents and AI-authored CGKRA narratives.

**Backend:**
- ExportService: `POST /companies/{id}/export`, `GET /companies/{id}/exports/{export_id}` — async PDF/DOCX generation with CGKRA, SWOT, technology stack, action items
- CGKRA narrative generation: `POST /companies/{id}/cgkra-narrative`, `GET /companies/{id}/cgkra-narrative/{doc_id}` — LLM-generated prose with optional template; same retry policy as InferenceService
- Template CRUD: `GET /templates`, `POST /templates`, `DELETE /templates/{id}`
- Background worker for async export and narrative generation (export_worker.py)
- Export file cleanup worker (cleanup_worker.py) — TTL-based deletion per §8

**Frontend:**
- Export button on company profile — format selector (PDF/DOCX), status polling, download link
- CGKRA narrative generation — template selector (from saved templates or upload new), generation trigger, status polling, view in UI and download
- Template management — list, upload, delete

**Tests:**
- ExportService: verify document generation produces valid PDF/DOCX with expected sections; verify file storage path conventions per §8
- Narrative generation: mock LLM; verify template is included in prompt when provided; verify fallback to default structure; verify retry on LLM API failure
- Template CRUD: upload, list, delete; verify file stored at correct path
- Cleanup worker: verify exports older than TTL are deleted; verify source files and templates are not affected

**Exit criteria**: investigator can generate and download briefing documents and CGKRA narratives; templates are reusable; old exports are cleaned up automatically.

---

### Phase 6 — Email Ingestion + Action Items + Polish

**Goal**: the investigator can send emails to BlackBook for ingestion; action items are fully manageable; the system is complete.

**Backend:**
- Email poller (email_poller.py): IMAP polling of configured mailbox; extract plain-text body and attachments; create Source records; route through the same IngestionService pipeline as uploads
- Action item endpoints: `GET /action-items` (cross-company), `GET /companies/{id}/action-items`, `POST /companies/{id}/action-items`, `PUT /action-items/{id}`, `DELETE /action-items/{id}`
- Session cleanup worker: delete expired sessions from the database daily

**Frontend:**
- Action item list page (UC 10) — consolidated cross-company view; filter by company, status; mark complete; add notes
- Action items on company profile and person detail views
- Polish: loading states, error handling, empty states, responsive layout

**Tests:**
- Email poller: mock IMAP connection; verify emails are parsed into Source records; verify routing through IngestionService; verify attachments are stored at correct file paths
- Action items: CRUD, status transitions (open → complete), cross-company listing with filters, pagination
- Session cleanup: verify expired sessions are deleted; active sessions are retained
- End-to-end: upload a file with prefix tags → verify ingestion → accept facts → verify company profile → export briefing → verify download

**Exit criteria**: all use cases (UCs 1–19) are implemented and testable. The system is complete.

