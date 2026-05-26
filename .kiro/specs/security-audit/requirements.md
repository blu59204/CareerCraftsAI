# Requirements Document

## Introduction

This document defines the security requirements for the JobAgent AI platform security audit framework. The platform handles sensitive user data including API keys (BYOK model), personal resumes, email content, and LinkedIn credentials through a multi-agent architecture spanning Next.js frontend, FastAPI backend, LangGraph agent layer, and infrastructure services (Supabase, Redis, Docker, Nginx). These requirements ensure that all security vulnerabilities identified in the design audit are addressed through verifiable, testable criteria.

## Glossary

- **Platform**: The JobAgent AI system comprising frontend, backend, agent layer, and infrastructure
- **JWT_Verifier**: The component responsible for verifying JSON Web Tokens issued by Supabase Auth
- **RLS_Engine**: PostgreSQL Row-Level Security policies enforcing data isolation between users
- **Encryption_Service**: The AES-256-GCM encryption/decryption module in `backend/app/core/security.py`
- **Agent_Harness**: The LangGraph orchestration entry point that executes AI agent tasks on behalf of users
- **Approval_Gate**: The server-side mechanism requiring explicit user approval before executing sensitive actions (email send, application submit)
- **Rate_Limiter**: The slowapi-based request throttling component
- **Sanitizer**: Components responsible for cleaning untrusted content before rendering or storage
- **Infrastructure_Layer**: Docker containers, Nginx reverse proxy, and Redis cache/queue services
- **Finding**: A security vulnerability or misconfiguration identified during audit, classified by severity

## Requirements

### Requirement 1: JWT Authentication Security

**User Story:** As a platform operator, I want JWT verification to use a pinned algorithm, so that algorithm confusion attacks are prevented.

#### Acceptance Criteria

1. WHEN a JWT token is received for verification, THE JWT_Verifier SHALL accept only the ES256 algorithm and reject tokens specifying any other algorithm in the header
2. WHEN a token specifies `alg: none` or `alg: HS256`, THE JWT_Verifier SHALL reject the token with HTTP 401 without attempting verification
3. WHEN a valid ES256 token is received, THE JWT_Verifier SHALL verify the `aud` claim equals "authenticated" before accepting
4. WHEN a token has expired based on the `exp` claim, THE JWT_Verifier SHALL reject the token with HTTP 401
5. IF the Supabase signing key is rotated, THEN THE JWT_Verifier SHALL support multiple `kid` values during the rotation window

### Requirement 2: Row-Level Security Data Isolation

**User Story:** As a platform user, I want my data isolated from other users via RLS policies, so that no cross-user data access is possible.

#### Acceptance Criteria

1. THE RLS_Engine SHALL enforce that all table policies reference the `supabase_uid` column matched against `auth.jwt() ->> 'sub'`
2. WHEN a user queries any protected table, THE RLS_Engine SHALL return only rows where `supabase_uid` matches the authenticated user identity
3. THE RLS_Engine SHALL NOT reference the deprecated `clerk_id` column in any policy definition
4. WHEN a user attempts to access a resource owned by another user via direct API call, THE Platform SHALL return HTTP 403

### Requirement 3: API Key Encryption

**User Story:** As a platform user, I want my API keys encrypted at rest with unique cryptographic parameters, so that a database breach does not expose plaintext keys.

#### Acceptance Criteria

1. WHEN an API key is stored, THE Encryption_Service SHALL encrypt it using AES-256-GCM with a fresh random 16-byte salt and 12-byte nonce per encryption operation
2. WHEN an API key is decrypted and re-encrypted, THE Encryption_Service SHALL produce a different ciphertext than the original due to fresh salt and nonce
3. THE Encryption_Service SHALL derive the encryption key using PBKDF2 with a minimum of 100,000 iterations and SHA-256
4. WHEN decryption is performed with an incorrect secret, THE Encryption_Service SHALL raise a ValueError without leaking information about the plaintext
5. WHEN an API key is decrypted for use, THE Encryption_Service SHALL ensure the plaintext is not written to logs or cached beyond the immediate operation

### Requirement 4: Agent Prompt Injection Defense

**User Story:** As a platform operator, I want agent inputs sanitized with prompt/data separation, so that malicious content in resumes or job descriptions cannot hijack agent behavior.

#### Acceptance Criteria

1. WHEN user-controlled data is passed to an LLM, THE Agent_Harness SHALL separate prompt instructions from user data using explicit delimiters
2. WHEN an LLM response is received, THE Agent_Harness SHALL validate the response structure against a Pydantic schema before persisting to agent_learnings
3. WHEN a reflection output fails schema validation, THE Agent_Harness SHALL discard the output and log the validation failure
4. WHEN user-controlled content contains known prompt injection patterns, THE Agent_Harness SHALL sanitize or escape the content before inclusion in the prompt context

### Requirement 5: Human-in-the-Loop Approval Enforcement

**User Story:** As a platform user, I want sensitive actions to require my explicit approval stored server-side, so that no email is sent or application submitted without my consent.

#### Acceptance Criteria

1. WHEN an agent requests to send an email or submit a job application, THE Approval_Gate SHALL block execution until a matching approval record exists in the database
2. WHEN an approval request is submitted, THE Approval_Gate SHALL verify that the authenticated user owns the corresponding agent run
3. WHEN an action is executed, THE Platform SHALL verify that the approval record was created before the action execution timestamp
4. IF an approval record does not exist for a sensitive action, THEN THE Agent_Harness SHALL halt execution and emit an SSE event requesting user approval

### Requirement 6: Infrastructure Hardening

**User Story:** As a platform operator, I want infrastructure services hardened against unauthorized access, so that compromised containers cannot pivot to sensitive data.

#### Acceptance Criteria

1. THE Infrastructure_Layer SHALL configure Redis with `requirepass` authentication
2. THE Infrastructure_Layer SHALL NOT expose the PinchTab service port (9867) to the host network
3. WHEN a request targets any `/internal/*` endpoint from outside the Docker network, THE Infrastructure_Layer SHALL return HTTP 404
4. THE Infrastructure_Layer SHALL run all Docker containers as non-root users with explicit resource limits (CPU and memory)
5. THE Infrastructure_Layer SHALL configure Nginx with TLS 1.2 minimum, HSTS header, and X-Frame-Options DENY

### Requirement 7: Frontend Content Security

**User Story:** As a platform user, I want LLM-generated content sanitized before rendering, so that crafted agent outputs cannot execute scripts in my browser.

#### Acceptance Criteria

1. WHEN LLM-generated content is rendered in the frontend, THE Sanitizer SHALL process it through DOMPurify before insertion into the DOM
2. THE Platform SHALL NOT use `dangerouslySetInnerHTML` with any LLM-generated or user-generated content
3. THE Infrastructure_Layer SHALL configure Content-Security-Policy headers that reference only active authentication domains (Supabase project URL) and remove stale domains (Clerk.com)
4. WHEN rendering markdown from LLM output, THE Sanitizer SHALL strip script tags, event handlers, and javascript: URIs

### Requirement 8: Rate Limiting and API Protection

**User Story:** As a platform operator, I want rate limiting applied per-user on sensitive endpoints, so that brute-force and abuse attacks are mitigated.

#### Acceptance Criteria

1. WHEN authentication endpoints receive more than 10 requests per minute from a single source, THE Rate_Limiter SHALL return HTTP 429
2. WHEN API key submission endpoints receive more than 5 requests per minute from a single user, THE Rate_Limiter SHALL return HTTP 429
3. THE Platform SHALL NOT expose the OpenAPI documentation endpoint (`/openapi.json`, `/docs`, `/redoc`) in production deployments
4. THE Platform SHALL validate all request bodies against Pydantic models and reject requests with unexpected fields

### Requirement 9: Audit Logging and Findings Management

**User Story:** As a security engineer, I want all audit findings tracked with severity, evidence, and remediation guidance, so that vulnerabilities are systematically resolved.

#### Acceptance Criteria

1. WHEN a security finding is created, THE Platform SHALL assign it an ID following the pattern `{CATEGORY_PREFIX}-{NNN}` and classify severity as CRITICAL, HIGH, MEDIUM, LOW, or INFO
2. WHEN a finding is recorded, THE Platform SHALL include affected file paths, evidence (code snippet or configuration), impact description, and concrete remediation steps
3. THE Platform SHALL map each finding to a CWE identifier where applicable
4. WHEN remediation is applied for a finding, THE Platform SHALL verify the fix through automated testing before marking the finding as resolved

### Requirement 10: SQL Injection Prevention

**User Story:** As a platform operator, I want all database queries to use parameterized statements, so that SQL injection attacks are structurally prevented.

#### Acceptance Criteria

1. THE Platform SHALL use SQLAlchemy ORM or parameterized queries for all database interactions
2. THE Platform SHALL NOT construct SQL queries using string concatenation or f-string interpolation with user-provided values
3. WHEN input validation is applied, THE Platform SHALL reject inputs containing SQL metacharacters in fields where they are not expected
