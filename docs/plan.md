# Plan to Implement Open AI Co-Scientist Core Algorithms

## 1. Introduction

**Goal:** Extend the existing Python codebase to implement the core algorithms and architecture of the AI Co-Scientist system as described in the paper "Towards an AI Co-Scientist" (Gottweis et al., 2025).

**Current State:** The codebase provides a FastAPI web server with basic, sequential agent implementations (`Generation`, `Reflection`, `Ranking`, `Evolution`, `Proximity`, `MetaReview`) orchestrated by a `SupervisorAgent`. It includes data models (`Hypothesis`, `ResearchGoal`, `ContextMemory`) and API endpoints for setting goals and running cycles. LLM interaction is basic, relying on simple prompts for generation and review.

**Key Gaps:**
*   **Asynchronous Framework:** Missing the asynchronous, scalable task execution framework.
*   **Agent Sophistication:** Current agent logic is rudimentary compared to the paper's descriptions (e.g., no literature search, scientific debate, deep verification, diverse evolution strategies, effective meta-review feedback).
*   **Tool Integration:** Lacks mechanisms for agents to use external tools like web search or specialized models.
*   **Scientist-in-the-Loop:** Interaction is limited to setting initial goals and running cycles; lacks features for feedback, hypothesis contribution, or directed exploration.
*   **Context Management:** Current in-memory context is insufficient for a robust, potentially long-running asynchronous system.
*   **Safety Mechanisms:** No explicit safety checks are implemented.

## 2. Core Architectural Changes

### 2.1. Asynchronous Task Execution Framework
*   **Objective:** Replace the sequential `SupervisorAgent.run_cycle` with an asynchronous task queue system.
*   **Tasks:**
    *   Choose an appropriate framework (e.g., Python's `asyncio` with `aiohttp` for external calls, or a dedicated task queue like Celery with Redis/RabbitMQ).
    *   Refactor `SupervisorAgent` to dispatch agent actions (generate, review, rank, evolve) as independent tasks.
    *   Implement mechanisms for task dependency management (e.g., a review task depends on a generation task).
    *   Modify agent methods (`generate_new_hypotheses`, `review_hypotheses`, etc.) to be asynchronous (`async def`).
    *   Ensure the FastAPI endpoints (`/run_cycle`) can trigger the asynchronous workflow without blocking.

### 2.2. Enhanced Context Memory
*   **Objective:** Improve state management for robustness and asynchronous access.
*   **Tasks:**
    *   Replace the simple in-memory `ContextMemory` dictionary.
    *   Consider using a database (e.g., SQLite for simplicity, PostgreSQL for scalability) or a persistent key-value store (like Redis) to store hypotheses, tournament results, and system state.
    *   Implement locking or transaction mechanisms to handle concurrent access from asynchronous tasks safely.
    *   Store more detailed state information, including task statuses, detailed tournament history, and comprehensive meta-review feedback.

### 2.3. Configuration Refinement
*   **Objective:** Increase flexibility and control over the system's behavior.
*   **Tasks:**
    *   Expand `config.yaml` and the `ResearchGoal` model to include parameters for:
        *   Specific agent strategies to enable/disable (e.g., which evolution methods to use).
        *   Tool configurations (API keys, endpoints).
        *   Asynchronous worker settings (number of workers, queue settings).
        *   Detailed prompt templates for different agent actions.
    *   Ensure the Supervisor and individual agents correctly read and utilize these configurations.

## 3. Agent Implementation Plan

*(Implementations should leverage the asynchronous framework and enhanced context memory)*

### 3.1. Generation Agent
*   **Objective:** Implement advanced hypothesis generation techniques from the paper.
*   **Tasks:**
    *   **Literature Exploration:** Integrate web search tool use. Implement logic to parse search results, read relevant articles (potentially using LLM summarization), and use findings to ground hypothesis generation.
    *   **Simulated Scientific Debates:** Implement multi-turn LLM conversations where the agent simulates experts debating a topic to refine or generate hypotheses.
    *   **Iterative Assumption Identification:** Develop logic (likely LLM-driven) to break down goals into testable assumptions and build hypotheses from them.
    *   **Research Expansion:** Use feedback from the Meta-Review agent to guide exploration into under-explored areas of the hypothesis space.

### 3.2. Reflection Agent
*   **Objective:** Implement diverse and deep review methodologies.
*   **Tasks:**
    *   **Multiple Review Types:** Develop distinct LLM prompts and logic for:
        *   `Initial Review`: Quick check for flaws/novelty (similar to current, but maybe refined).
        *   `Full Review`: Integrate web search to find supporting/contradicting literature for deeper novelty/correctness assessment.
        *   `Deep Verification`: Implement logic to decompose hypotheses into assumptions and use LLM calls (potentially with web search) to verify each fundamental sub-assumption.
        *   `Observation Review`: Use LLM to assess if a hypothesis can explain known (potentially obscure) observations from literature (requires literature search integration).
        *   `Simulation Review`: Use LLM prompting to simulate the proposed mechanism or experiment step-by-step to identify failure points.
        *   `Tournament Review`: Adapt review logic based on patterns identified by the Meta-Review agent.
    *   Store different review types distinctly within the `Hypothesis` object in the context memory.

### 3.3. Ranking Agent
*   **Objective:** Implement Elo ranking based on simulated scientific debates.
*   **Tasks:**
    *   Replace `run_pairwise_debate` score comparison with an LLM call simulating a multi-turn debate between two hypotheses, concluding with a winner determination.
    *   Refine tournament scheduling logic:
        *   Prioritize matches between newer hypotheses or those with high Elo ratings.
        *   Potentially use the Proximity Agent's graph to prioritize debates between similar or dissimilar ideas based on configuration.
    *   Ensure debate results (winner/loser, potentially key arguments) are stored in the context memory.

### 3.4. Evolution Agent
*   **Objective:** Implement multiple strategies for hypothesis refinement and generation.
*   **Tasks:**
    *   Implement distinct evolution methods, selectable via configuration:
        *   `Enhancement through Grounding`: Use web search to find supporting details or address weaknesses identified in reviews.
        *   `Coherence/Practicality Improvement`: Use LLM prompts to refine wording, address logical gaps, or improve experimental feasibility based on reviews.
        *   `Inspiration`: Generate new hypotheses inspired by analogies or themes from multiple existing top hypotheses.
        *   `Combination`: More sophisticated combination than simple text concatenation (e.g., LLM synthesizes a new hypothesis incorporating core ideas).
        *   `Simplification`: Use LLM prompts to simplify complex hypotheses.
        *   `Out-of-Box Thinking`: Use LLM prompts designed to generate divergent ideas based on, but distinct from, existing ones.
    *   Ensure evolved hypotheses correctly link to their parents in the context memory.

### 3.5. Meta-Review Agent
*   **Objective:** Implement a meaningful feedback loop and research overview generation.
*   **Tasks:**
    *   **Pattern Synthesis:** Analyze stored reviews and debate outcomes to identify recurring critiques, common flaws, or successful patterns using LLM analysis or rule-based methods.
    *   **Feedback Generation:** Generate specific feedback based on synthesized patterns.
    *   **Feedback Application:** Implement a mechanism for this feedback to *modify* the behavior of other agents in subsequent cycles (e.g., dynamically appending feedback to prompts used by Generation, Reflection, or Evolution agents).
    *   **Research Overview Generation:** Implement logic to synthesize top-ranked hypotheses and meta-review insights into a structured research overview (as shown in paper Appendix Fig A.12-A.13).
    *   **(Optional) Contact Identification:** Implement logic to suggest potential expert contacts based on literature review (requires parsing author information).

### 3.6. Proximity Agent
*   **Objective:** Ensure integration with the asynchronous framework.
*   **Tasks:**
    *   Refactor `build_proximity_graph` to run asynchronously if needed.
    *   Ensure similarity calculations (`similarity_score`) are efficient or run asynchronously to avoid blocking.

## 4. Tool Integration Strategy

*   **Objective:** Enable agents to utilize external tools, starting with web search.
*   **Tasks:**
    *   Define a generic `Tool` interface or base class.
    *   Implement a `WebSearchTool` class using a library/API (e.g., `requests` with SerpAPI, Google Search API, Tavily API). Requires API key management (via config/env variables).
    *   Integrate `WebSearchTool` usage into `GenerationAgent` (literature exploration) and `ReflectionAgent` (full review, observation review, deep verification).
    *   Design the system to allow adding other tools (e.g., database query tools, specialized model APIs like AlphaFold) by implementing the `Tool` interface.

## 5. Scientist-in-the-Loop Enhancements

*   **Objective:** Allow richer interaction between the scientist and the system.
*   **Tasks:**
    *   **API Enhancements:**
        *   Add endpoints for submitting manual reviews for specific hypotheses.
        *   Add an endpoint for submitting a scientist's own hypothesis.
        *   Add endpoints to provide feedback or refine the current research goal mid-process.
        *   Add endpoints to potentially prioritize specific hypotheses or exploration directions.
    *   **Frontend Enhancements (Optional):** Update the basic HTML frontend or create a more interactive UI to utilize the new API endpoints.

## 6. Safety Mechanisms

*   **Objective:** Implement basic safety checks as described in the paper.
*   **Tasks:**
    *   Implement an initial safety check for the `ResearchGoal` upon submission (e.g., using an LLM classifier with a safety prompt or keyword filtering). Reject unsafe goals.
    *   Implement safety checks within the `ReflectionAgent` or as a separate step after `GenerationAgent` to evaluate generated hypotheses. Flag or deactivate unsafe hypotheses.
    *   Integrate safety considerations into the `MetaReviewAgent`'s overview.
    *   Ensure clear logging of safety evaluations and actions.

## 7. Testing and Evaluation Strategy

*   **Objective:** Ensure the correctness and robustness of the enhanced system.
*   **Tasks:**
    *   Develop unit tests for individual agent methods and tool integrations.
    *   Develop integration tests for the asynchronous task workflow and context management.
    *   Implement automated evaluations using benchmarks like GPQA (as done in the paper) if feasible, tracking accuracy against Elo scores.
    *   Refine the Elo calculation or explore alternative auto-evaluation metrics if Elo proves insufficient or biased.
    *   Plan for manual evaluation with domain experts on curated research goals.

## 8. Phased Rollout / Milestones (Suggested)

1.  **Phase 1: Foundation:** Implement asynchronous framework, enhanced context memory, and configuration updates.
2.  **Phase 2: Core Agent Logic:** Enhance Generation (literature search), Reflection (full review), Ranking (debate), Evolution (basic combination/inspiration), Meta-Review (basic pattern summary). Integrate web search tool.
3.  **Phase 3: Advanced Agent Features:** Implement remaining Generation/Reflection/Evolution strategies. Implement effective Meta-Review feedback loop.
4.  **Phase 4: Scientist-in-the-Loop & Safety:** Implement enhanced interaction APIs and safety mechanisms.
5.  **Phase 5: Refinement & Evaluation:** Comprehensive testing, evaluation, and performance tuning.

## 9. Dependencies & Technologies

*   **Potential New Dependencies:**
    *   Asynchronous framework: `asyncio`, `aiohttp`, `celery`, `redis`/`rabbitmq`
    *   Database/Persistence: `SQLAlchemy`, `psycopg2-binary` (for Postgres), `redis-py`, `sqlite3`
    *   Web Search: Library for chosen search API (e.g., `google-api-python-client`, `serpapi-python`, `tavily-python`)
    *   Enhanced testing: `pytest-asyncio`
*   **Existing Dependencies (likely):** `fastapi`, `uvicorn`, `pydantic`, `requests`, `python-dotenv`, `PyYAML`, `numpy` (for similarity), `scikit-learn` (for similarity), `vis-network` (frontend). (Verify against `requirements.txt`).
