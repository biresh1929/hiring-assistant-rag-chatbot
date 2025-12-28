# TalentScout — Hiring Assistant Chatbot

**An intelligent, GDPR-aware hiring assistant** built with Streamlit + LLMs that performs initial candidate screening, asks technical questions tailored to each candidate’s declared tech stack and experience, and stores results securely in MongoDB with encryption and auditable GDPR operations.

---

## Table of contents

* [Project Overview](#project-overview)
* [Features](#features)
* [Architecture & Dataflow](#architecture--dataflow)
* [Installation](#installation)
* [Environment / Secrets](#environment--secrets)
* [Running Locally](#running-locally)
* [Usage Guide (UI walkthrough)](#usage-guide-ui-walkthrough)
* [Technical Details](#technical-details)
* [Prompt Design & Examples](#prompt-design--examples)
* [GDPR, Security & Data Handling](#gdpr-security--data-handling)
* [Challenges & Solutions — Development Notes](#challenges--solutions---development-notes)
* [Troubleshooting](#troubleshooting)
* [Project Structure](#project-structure)
* [Contributing / Extending](#contributing--extending)
* [License & Credits](#license--credits)

---

# Project overview

TalentScout is a small, production-minded hiring-assistant chatbot that guides candidates through a short interview:

* Collects basic PII and profile data (name, email, phone, experience, desired position, location).
* Asks 3–5 technical questions automatically generated from the candidate’s declared tech stack.
* Adapts question difficulty to the candidate’s years of experience (beginner / intermediate / advanced).
* Stores all official records (encrypted) in MongoDB.
* Provides GDPR features in the UI: View, Export (JSON/CSV), and Delete data per candidate, with audit logging.
* Built with Streamlit for UI and an LLM backend (model is configurable).

This repository demonstrates clean prompt design, secure data handling, and a pragmatic tradeoff between AI-driven behaviour and compliance.

---

# Features

* Streamlit UI with a stepwise interview flow
* Dynamic question generation conditioned on tech stack + experience
* Short-term in-session context awareness
* Encryption of PII using Fernet (symmetric authenticated encryption)
* Secrets management (ENV → AWS Secrets Manager fallback)
* MongoDB as authoritative storage + audit log collection
* GDPR rights: access, export, delete, retention cleanup
* Simple fallback / off-topic gentle redirects for better UX
* Optional vector DB (Pinecone) support discussed — removed by default for GDPR safety

---

# Architecture & dataflow

```
User (Streamlit UI)
    ↓ (form inputs / chat)
Streamlit frontend (session_state)
    • conversation_context (last 5 turns)
    • candidate_id (session-scoped)
    ↓ calls
MongoDBHandler (backend)
    • encrypts PII with Fernet, stores candidate doc in `candidates` collection
    • logs audit events to `audit_log`
LLM (initialize_llm)
    • receives prompts (tech_stack + experience_level + num_questions)
    • returns question text
Optional (advanced) → Vector DB (Pinecone): semantic memory (ONLY if sanitized)
```

Important: **MongoDB is the source of truth**. Vector DB usage is optional and only makes sense when semantic search/use-cases are implemented and PII is sanitized or removed.

---

# Installation

## Prerequisites

* Python 3.10+ (recommended)
* MongoDB (local or Atlas)
* (Optional) AWS account + Secrets Manager if you want production key management
* (Optional) A large language model provider / API key (OpenAI, HuggingFace Inference, etc.)

## Clone

```bash
git clone https://github.com/<your-repo>/talentscout.git
cd talentscout
```

## Create virtualenv & install

```bash
python -m venv .venv
source .venv/bin/activate            # mac/linux
# .venv\Scripts\Activate             # Windows
pip install -r requirements.txt
```

`requirements.txt` should include:

```
streamlit
pymongo
cryptography
python-dotenv
boto3
botocore
# LLM client(s) you use, e.g. openai, transformers, smolagents, langchain
# optional: pinecone-client (if you enable vector DB)
```

---

# Environment / Secrets

Create a `.env` file in project root with at least:

```ini
# MongoDB
MONGODB_URI=mongodb+srv://<user>:<pass>@cluster0.mongodb.net/?retryWrites=true&w=majority

# Local Fernet key for dev (optional; recommended to store in AWS Secrets for prod)
ENCRYPTION_KEY=BASE64_URLSAFE_FERNET_KEY_HERE

# App environment
APP_ENV=development   # or production

# AWS region (if using Secrets Manager)
AWS_REGION=eu-north-1

# (If you integrate an LLM provider)
OPENAI_API_KEY=sk-...
# or other provider keys...
```

### AWS Secrets Manager expected secret

If using AWS Secrets Manager, it expects a JSON secret string:

```json
{
  "FERNET_KEY": "b64-urlsafe-fernet-key"
}
```

Production note: In `APP_ENV=production`, if encryption key retrieval fails, the application is designed to **fail loudly** rather than generate a new key — this prevents silent data corruption.

---

# Running locally

From project root:

```bash
# activate venv first
streamlit run app.py
# or if your main Streamlit file is e.g. src/app.py:
streamlit run src/streamlit_app.py
```

Open the provided `http://localhost:8501` URL.

---

# Usage guide (UI walkthrough)

1. **Consent screen** — user must accept privacy policy to proceed.
2. **Interview flow** — the bot greets and collects:

   * Full name
   * Email (validated)
   * Phone (validated)
   * Years of experience
   * Desired position
   * Location
   * Tech stack (comma-separated)
3. **Question generation** — after tech stack is provided, the bot generates 3–5 questions tailored to the stack and experience.
4. **Answer questions** — candidate answers sequentially. Answers are appended to candidate record.
5. **Completion** — the app saves encrypted data to MongoDB and shows a Candidate ID.
6. **Post-interview GDPR actions** — after completion you will see:

   * **View My Data** — shows decrypted JSON in UI (session scoped)
   * **Download My Data (JSON)** — exports decrypted JSON (serialized properly)
   * **Delete My Data (Permanent)** — deletes candidate record and logs audit event

---

# Technical details

## Core components

* **Frontend**: Streamlit — single-page conversational interface and buttons for GDPR actions.
* **Backend**: `src/mongodb_handler.py` — a class that encapsulates DB access, encryption, and audit logging.
* **Context manager**: `src/context_manager.py` — handles in-session memory; optional integration with Pinecone (disabled by default for GDPR reasons).
* **Prompting**: `src/helper.py` (or similar) contains `generate_technical_questions`, `generate_greeting`, `generate_goodbye`, fallback logic, and minor prompt utilities.
* **LLM**: `initialize_llm()` (abstracted) — you can plug OpenAI (GPT), a HuggingFace endpoint, or a local model as needed.

## Data model (MongoDB `candidates` document)

```json
{
  "candidate_id": "candidate_...",
  "created_at": ISODate(...),
  "retention_until": ISODate(...),
  "full_name": "<encrypted>",
  "email": "<encrypted>",
  "phone": "<encrypted>",
  "years_experience": "3",
  "desired_position": "...",
  "current_location": "...",
  "tech_stack": ["Python","Django"],
  "technical_questions": ["q1","q2"],
  "answers": [{ "question":"...", "answer":"..." }],
  "consent_given": true,
  "consent_timestamp": ISODate(...)
}
```

## Indexes

* `candidate_id` — unique index (lookup primary key)
* `audit_log.candidate_id` — index for audit queries
  **Note:** Encrypted fields (like `email`) are not indexed. If you need search by email, store a separate deterministic hash (SHA-256 of normalized email) and index that instead.

## Encryption & Key Management

* **Fernet** (from `cryptography`) for authenticated symmetric encryption.
* Keys sourced from:

  1. `ENCRYPTION_KEY` environment variable (dev/test)
  2. AWS Secrets Manager (`talentscout/encryption_key`) in production
* **Behavior**: Dev may generate a key if missing. Production fails fast if key absent (preventing silent loss).

---

# Prompt design — how questions are generated

Prompt design is the heart of adaptive question generation. The project separates **control** and **language** responsibilities:

1. **Control (code side)**

   * Convert `years_experience` to discrete bucket:

     * beginner (0–2 years)
     * intermediate (3–5 years)
     * advanced (6+ years)
   * Format `tech_stack` as a comma-separated list.
   * Provide `num_questions`.

2. **Prompt (LLM side)**
   The prompt template (stored as `TECH_QUESTION_GENERATION_PROMPT`) instructs the model:

   * Use `tech_stack` for topical scope.
   * Use `experience_years` bucket to set difficulty: if beginner → conceptual/basic questions; if advanced → scenario/problem-solving/system-level questions.
   * Generate exactly `num_questions` clear, unambiguous interview questions.
   * Avoid asking for personally identifying data; stick to technical topics.

### Example prompt snippet (conceptual)

```
You are an experienced technical interviewer. Generate {num_questions} concise technical questions for a candidate whose tech stack is: {tech_stack}. The candidate's experience level is: {experience_years}. 
- For "beginner", ask conceptual/basic questions that test fundamental understanding.
- For "intermediate", ask practical questions and small design/troubleshooting scenarios.
- For "advanced", ask scenario-based, architecture, performance, and optimization questions.
Return each question on a new line with a question mark. Do not include answers.
```

This pattern is general and LLM-agnostic.

---

## Challenges & Design Decisions

* **Failure-resilient candidate identity:**
  Timestamp-based IDs risked collisions and data loss under concurrent usage and network failures. Replaced with UUID-based candidate IDs generated immediately after user consent and used as the single source of truth across the system.

* **Secure encryption key lifecycle (GDPR-safe):**
  Sensitive candidate data is encrypted using Fernet. Encryption keys are centrally managed via AWS Secrets Manager and injected at runtime. The application fails fast in production if the key is unavailable, preventing silent data corruption.

* **GDPR compliance by design:**
  Implemented candidate-level data access, JSON export, immediate deletion (“right to erasure”), retention controls, and audit logging to support GDPR Articles 5, 15, 17, 20, and 32.

* **Vector DB risk assessment:**
  Initially evaluated Pinecone for semantic retrieval, but removed it in the current version to avoid storing PII in vector databases and simplify GDPR compliance. MongoDB remains the single source of truth.

* **Prompt orchestration:**
  Replaced a monolithic prompt with a multi-stage prompt pipeline (consent, info collection, question generation, evaluation, fallback, termination) to enforce deterministic interview flow.

* **Encrypted field indexing:**
  Avoided indexing encrypted fields. Where lookup is required, deterministic hashes are stored in separate indexed fields.

---

# Troubleshooting

### `TypeError: argument should be bytes-like or ASCII string, not 'NoneType'`

* Cause: `get_encryption_key()` returned `None`.
* Fix: Ensure `ENCRYPTION_KEY` is set in `.env` for local dev or that Secrets Manager holds `FERNET_KEY`. For production, set `APP_ENV=production` and make sure AWS Secrets Manager has the key.

### `Object of type datetime is not JSON serializable`

* Cause: `export_candidate_data()` tried to `json.dumps()` Python `datetime` objects.
* Fix: Convert datetimes to ISO strings in `get_candidate_data()` before export.

### Export JSON button not responding

* Cause: File serialization failure due to non-serializable fields (datetime).
* Fix: Use ISO strings; test `handler.export_candidate_data(candidate_id, "json")` in Python REPL.

### MongoDB connectivity issues

* Check `MONGODB_URI`, network access/firewall, and that the database user has appropriate permissions.

---

# Project structure (example)

```
.
├── app.py                      # Streamlit entrypoint (or src/streamlit_app.py)
├── requirements.txt
├── README.md
├── .env.example
├── src/
│   ├── mongodb_handler.py      # MongoDBHandler (encryption + audit + GDPR ops)
│   ├── context_manager.py      # in-session context + optional vector DB interface
│   ├── helper.py               # prompts, generate_technical_questions, utilities
│   └── llm.py                  # initialize_llm wrapper (provider-agnostic)
└── tests/                      # unit/integration tests (optional)
```

---

# Contributing / Extending

If you want to extend this project:

* **Add model backends:** add a `llm` provider (OpenAI, HF endpoint, local model).
* **Add sentiment/multilingual features:** use a lightweight classifier only if privacy-aware.
* **Reintroduce Vector DB:** do so only if you implement redaction and deletion hooks.
* **Unit tests:** add tests for `MongoDBHandler` (mock Mongo), `export_candidate_data`, and prompt parsing.
---

# License & credits

This project is open-source. Choose a license (MIT / Apache-2.0) and add `LICENSE` file if you plan to publish.

---
