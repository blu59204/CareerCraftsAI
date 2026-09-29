/**
 * Fictional resume used for template thumbnails. All contact details are
 * placeholders (example.com domain, 555-01xx phone range).
 */
export const SAMPLE_RESUME_MARKDOWN = `# Jane Doe
jane.doe@example.com | +1 555 010 0199 | Austin, TX, USA | linkedin.com/in/janedoe-example | github.com/janedoe-example

## SUMMARY
Backend engineer with 6 years of experience building **Python** and **Go** services for high-traffic payments and logistics platforms. Known for turning slow, fragile pipelines into observable, well-tested systems.

## EXPERIENCE
### Senior Software Engineer | Northwind Payments | Austin, TX | Jun 2022 - Present
- Led the migration of the settlement pipeline to event-driven **Kafka** consumers, cutting end-of-day reconciliation from 4 hours to 25 minutes.
- Designed an idempotent refunds API handling 1.2M requests/day at 99.98% availability.
- Mentored 4 engineers and introduced contract testing that reduced integration incidents by 40%.

### Software Engineer | Contoso Logistics | Remote | Aug 2019 - May 2022
- Built route-optimization microservices in **Go** that lowered average delivery cost by 11%.
- Added *OpenTelemetry* tracing across 30+ services, reducing mean time to resolution from 3 hours to 45 minutes.
- Automated PostgreSQL schema migrations in CI, eliminating manual release steps.

## PROJECTS
### Ledger Lint | Open source | 2023
- CLI that validates double-entry accounting exports; 1.4k GitHub stars and 20 contributors.

## EDUCATION
### B.S. Computer Science | University of Texas at Austin | Austin, TX | Aug 2015 - May 2019
- GPA 3.8/4.0 · Teaching assistant for Data Structures

## SKILLS
**Languages:** Python, Go, TypeScript, SQL
**Infrastructure:** AWS, Kubernetes, Terraform, Docker
**Data:** PostgreSQL, Kafka, Redis, dbt
`;
