# Peer Review Report

> **Instructions:** Complete this form **individually and independently**.
> Do not discuss your ratings with teammates before submitting.
> Submit via EEClass as a **separate, confidential submission** — not in the shared team repo.
> Your teammates will not see this report.
>
> Reference the team's `WORK_ALLOCATION_TEMPLATE.md` when completing this form.

---

## Your Details

| Field | Your answer |
|-------|------------|
| Full Name | 賴柔羽 |
| Student ID | 113403503 |
| Team ID | 13 |
| Date submitted | 6/11 |

---

## Rating Scale

| Rating | Meaning |
|--------|---------|
| **5** | Exceeded expectations — delivered more than agreed; helped teammates; consistently high quality |
| **4** | Met expectations fully — delivered exactly what was agreed; on time; good quality |
| **3** | Mostly met expectations — minor shortfalls; one or two items completed late or with help |
| **2** | Partially met expectations — noticeable gaps; teammates had to cover some tasks |
| **1** | Did not meet expectations — significant tasks left incomplete; very limited contribution |

---

## Section A — Self-Assessment

### A1. What did you personally implement?

> 
I led the PostgreSQL schema design, including relational table design, JSONB modelling, ER diagram design, and PostgreSQL seeding implementation. I was responsible for transforming the provided mock JSON datasets into a normalized relational schema, implementing the PostgreSQL seeding workflow (seed_postgres.py), validating seeded data, and documenting the database design. I also contributed to seat layout modelling, database testing, and project documentation.


---

### A2. What challenges did you face?

> 
One of the main challenges was designing a database schema that could support both metro and national rail systems while remaining normalized and easy to query. Another challenge was understanding how to represent seat layout data stored in JSON format and deciding how much information should be stored in relational tables versus JSON structures.

During integration testing, we also encountered issues related to Docker configuration, PostgreSQL seeding, Neo4j routing queries, and Ollama model setup. We resolved these issues through incremental testing, reviewing query outputs in pgAdmin, and validating system behavior using the provided TransitFlow interface.

---

### A3. Self-rating

| Criterion | Rating (1–5) | Justification (1–2 sentences) |
|-----------|-------------|-------------------------------|
| I delivered the tasks assigned to me in the work allocation | 5 | I completed all database design and documentation tasks assigned to me. |
| The quality of my work was satisfactory | 4 | The schema, ER diagram, and database-related documentation were completed and tested successfully. |
| I communicated well and kept the team informed | 4 | I regularly discussed design decisions and progress with teammates. |
| I met deadlines agreed within the team | 5 | All assigned tasks were completed on schedule. |
| **Overall self-rating** | 4 | I fulfilled my responsibilities and contributed to both implementation and documentation. |

---

### A4. Estimated contribution percentage

What percentage of the total team effort do you estimate you personally contributed?

> My estimated contribution: **__34__%**

---

## Section B — Peer Assessments

Complete one subsection per teammate. Add or remove subsections to match your team size.
If your team has 2 members, complete B1 only. If 3 members, complete B1 and B2.

---

### B1. Assessment of Teammate 1

| Field | Your answer |
|-------|------------|
| Teammate's full name | 黃妍瑄 |
| Teammate's student ID | 113403038 |

#### What did this teammate deliver?

List the tasks, functions, files, or document sections that this teammate was the primary author of,
based on what you observed during the project (compare against the work allocation).

> 
This teammate was primarily responsible for the Neo4j graph database component. They designed the graph schema, implemented graph seeding, developed route-finding queries, and integrated the graph database with the TransitFlow system. They also contributed to graph-related documentation and testing.

---

#### Did their actual contribution match the agreed work allocation?

> 
Yes. The teammate completed the graph database tasks that were assigned in the work allocation and actively participated in integration testing.

---

#### Peer rating for this teammate

| Criterion | Rating (1–5) | Justification (1–2 sentences) |
|-----------|-------------|-------------------------------|
| Delivered the tasks assigned in the work allocation | 5 | Successfully completed the assigned Neo4j and graph database tasks. |
| Quality of their work was satisfactory | 4 | The graph database functions operated correctly during testing. |
| Communicated well and kept the team informed | 4 | Regularly shared progress and discussed technical issues with the team. |
| Met deadlines agreed within the team | 5 | Completed assigned tasks on time. |
| **Overall rating for this teammate** | 4 | Consistently delivered the assigned work with good quality. |

#### Estimated contribution percentage for this teammate

> My estimate of their contribution: **__33__%**

---

### B2. Assessment of Teammate 2

| Field | Your answer |
|-------|------------|
| Teammate's full name | 胡亞嫙|
| Teammate's student ID | 113403008|

#### What did this teammate deliver?

> 
his teammate was primarily responsible for implementing relational database query functions, booking operations, authentication functionality, and application-level integration. Their work included availability queries, fare queries, booking logic, user-related functions, and AI workflow integration.

---

#### Did their actual contribution match the agreed work allocation?

> 
Yes. The teammate completed the assigned implementation tasks and contributed to testing and debugging during integration.

---

#### Peer rating for this teammate

| Criterion | Rating (1–5) | Justification (1–2 sentences) |
|-----------|-------------|-------------------------------|
| Delivered the tasks assigned in the work allocation | 5 | Completed the assigned query functions and integration tasks. |
| Quality of their work was satisfactory | 4 | The implemented functionality worked correctly during testing. |
| Communicated well and kept the team informed | 4 | Participated in team discussions and provided progress updates. |
| Met deadlines agreed within the team | 5 | Completed tasks according to the agreed timeline. |
| **Overall rating for this teammate** | 4 | Successfully completed the assigned responsibilities and supported integration efforts. |

#### Estimated contribution percentage for this teammate

> My estimate of their contribution: **__33__%**

---

## Section C — Contribution Percentage Summary

All members (including yourself) must sum to 100%.

| Member | Your estimated % | Notes |
|--------|----------------|-------|
| Yourself | 34% | |
| Teammate 1 | 33% | |
| Teammate 2 | 33% |  |
| **Total** | **100%** | |

---

## Section D — Overall Team Reflection

### D1. What went well in the team's collaboration?

> 
Our team divided the project into relational database, graph database, and application/query development tasks. This allowed each member to focus on a specific area while maintaining clear responsibilities. Throughout the project, team members regularly shared progress updates and assisted each other during integration and testing, which helped us identify and resolve issues efficiently.

---

### D2. What would you do differently if you did this project again?

> 
If we were to do this project again, we would begin system integration and end-to-end testing earlier in the development process. While individual components worked well independently, several issues only became visible when integrating PostgreSQL, Neo4j, vector search, and the user interface. Earlier integration testing would help reduce debugging time and improve overall development efficiency.

---

### D3. Is there anything else the markers should know about team dynamics or individual contributions?

This is optional. Use it only if there is important context that the ratings above do not capture
(e.g., a member had a documented personal emergency, or a member was unresponsive for a significant period).

> 

Nothing to add.

---

## Declaration

I confirm that this peer review reflects my honest and independent assessment.
I understand it will be kept confidential from my teammates.

**Signed:** ______賴柔羽___________________________ **Date:** ______6/11_________
