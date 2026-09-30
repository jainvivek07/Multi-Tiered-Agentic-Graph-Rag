
# High-Level Design (HLD): RAG Studio

## 1. System Overview

RAG Studio is an enterprise-grade Retrieval-Augmented Generation application. It enables users to query secure, internal documents while utilizing a hybrid routing mechanism (Vector, Graph, Cache) and enforcing strict conversational boundaries via NeMo Guardrails.

## 2. Core Subsystems

### 2.1 Client Tier (Frontend)

* **Framework:** React + TypeScript + Vite.
* **State Management:** Zustand (decoupled stores for Auth, Chat, and Theme).
* **Visualization:** 3D Knowledge Graph rendering using `d3-force-3d`.
* **Communication:** REST for standard operations; Server-Sent Events (SSE) for low-latency, real-time AI token streaming.

### 2.2 Application Tier (Backend)

* **Framework:** FastAPI (Python).
* **API Gateway:** Routes requests based on domain (`routes_admin.py`, `routes_auth.py`, `routes_sse.py`).
* **Security Layer:** NeMo Guardrails intercept all incoming prompts to prevent jailbreaks and off-topic queries before they reach the LLM.
* **RAG Router:** Analyzes the prompt and dynamically routes to the Vector index, Neo4j Graph index, or Redis Cache.

### 2.3 Asynchronous Processing Tier

* **Task Queue:** Celery with Redis as the message broker.
* **Workers:** Dedicated worker nodes execute `ingestion_tasks.py` for chunking, embedding generation, and entity extraction (Knowledge Graph population).

### 2.4 Data Tier

* **Relational DB:** PostgreSQL tracks application state, user metadata, and telemetry.
* **Graph DB:** Neo4j stores entity-relationship data for complex, multi-hop queries.
* **Vector/Cache DB:** Redis (or dedicated vector store) handles high-speed semantic similarity searches and query caching.

## 3. Primary Data Flows

1. **Document Ingestion:** Admin uploads PDF -> FastAPI validates -> Saved to storage -> Celery Task triggered -> PDF parsed -> Chunks embedded & Entities extracted -> Stored in Vector DB & Neo4j.
2. **Query Execution:** User sends prompt -> NeMo Guardrails validate -> RAG Router selects strategy -> Context retrieved (Graph + Vector) -> Prompt constructed -> LLM generates response -> Check for hallucination with lettuce detect -> Streamed via SSE to Client.
