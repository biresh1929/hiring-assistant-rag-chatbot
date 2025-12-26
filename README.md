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

# Challenges & solutions (development notes)

This section lists important real problems we encountered and how they were resolved — useful to include in your README or to talk about in interviews.

### 1. **Encryption key handling**

* **Problem:** Initially, the app generated a new key silently if AWS Secrets Manager retrieval failed — which could make old data undecryptable.
* **Solution:** Implemented `APP_ENV` gating:

  * `development` → allow key generation (dev convenience).
  * `production` → fail loudly and abort startup to avoid silent key rotation and irreversible data loss.

### 2. **Datetime serialization for export**

* **Problem:** `json.dumps()` failed with `datetime` objects when exporting candidate data.
* **Solution:** Convert DB datetimes to ISO-8601 strings (`.isoformat()`) before return, or use `json.dumps(..., default=str)` as a fallback.

### 3. **Encrypted-field indexing**

* **Problem:** Attempting to index encrypted `email` produced a useless index because ciphertext is non-deterministic.
* **Solution:** Remove index on encrypted email. If email lookups are required, store an indexed deterministic hash (SHA-256 of normalized email) in a separate field.

### 4. **Pinecone / Vector DB GDPR risk**

* **Problem:** Storing raw conversation text (PII) in a vector DB makes deletion & compliance complex.
* **Solution:** Removed Pinecone writes by default. If re-enabled in V2, store only sanitized summaries or enable per-candidate deletion and redaction pipelines.

### 5. **Duplicate candidate inserts**

* **Problem:** `insert_one` could raise `DuplicateKeyError` if candidate_id is reused.
* **Solution:** Either ensure candidate_id uniqueness per session or use `update_one(..., upsert=True)` when resaving/resuming.

### 6. **Off-topic / rubbish input handling**

* **Problem:** Users sometimes type irrelevant text (jokes, queries) that derail stage flow.
* **Solution:** Add lightweight stage-aware redirection: detect off-topic patterns and politely prompt the candidate to continue the current step.

### 7. **Auditability**

* **Problem:** Need a reliable audit trail for GDPR actions (access, export, deletion).
* **Solution:** Implemented `audit_log` collection and log every action originating from the MongoDB handler.

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

# Resume / presentation bullets (copy-paste)

* Designed and implemented `TalentScout` — an LLM-powered hiring assistant with Streamlit UI.
* Implemented GDPR-compliant encrypted storage (Fernet), key management (ENV + AWS Secrets), and audit logging in MongoDB.
* Engineered adaptive question generation (difficulty buckets based on years of experience) using prompt templates and LLMs.
* Built secure data operations: data access, export, permanent deletion, and automated retention cleanup.

---

# License & credits

This project is open-source. Choose a license (MIT / Apache-2.0) and add `LICENSE` file if you plan to publish.

---

## Final notes

You have a strong project: it combines practical LLM usage with real-world operational and compliance concerns. The README above is designed to be both a user-facing document (how to run & use) and a technical one (why choices were made, how to extend). If you want, I can:

* Generate a final `README.md` file ready to paste into your repo (I can produce exactly formatted Markdown now).
* Produce a short demo script / Loom outline for your video.
* Create a one-page slide (bullet points) for recruiters.

Which one would you like next?
