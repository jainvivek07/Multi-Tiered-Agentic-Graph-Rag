# RAG Studio (Intelligence Studio)

RAG Studio is a full-stack, enterprise-grade Retrieval-Augmented Generation application designed to securely ingest, analyze, and query documents.

## 🚀 Key Features

* **Real-Time Intelligence Chat:** Sub-second latency streaming via Server-Sent Events (SSE) and optimized hybrid retrieval.
* **3D Knowledge Graph Visualization:** Explore entity relationships and document chunks interactively via our `d3-force-3d` canvas.
* **Hybrid Routing Engine:** Intelligently routes queries to Vector search, Neo4j Graph search, or executes Hybrid queries based on conversational context.
* **Enterprise AI Guardrails:** Powered by NeMo Guardrails to strictly enforce topical boundaries and prevent jailbreak attempts.
* **Asynchronous Ingestion:** Robust background document processing using Celery and Redis.
* **Secure Authentication:** OAuth2 flow utilizing strictly HttpOnly cookies for session management.

## 🛠 Tech Stack

* **Frontend:** React, TypeScript, Vite, Zustand, CSS Modules, d3-force-3d.
* **Backend:** Python, FastAPI, SQLAlchemy, Alembic, Celery, NeMo Guardrails.
* **Databases:** PostgreSQL (Relational), Neo4j (Knowledge Graph), Redis (Broker/Cache).
