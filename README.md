---
title: Ai Co Scientist
emoji: 📊
colorFrom: gray
colorTo: gray
sdk: gradio
sdk_version: 5.38.2
app_file: app.py
pinned: false
license: mit
short_description: open-source implementation of Google's AI co-scientist syste
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference

# AI Co-Scientist - Hypothesis Evolution System (v1)

This project implements an AI-powered system for generating, reviewing, ranking, and evolving research hypotheses. It leverages Large Language Models (LLMs) for various tasks, including hypothesis generation, reflection, and comparison. The system is designed to assist researchers in exploring a research space and identifying promising hypotheses.

https://storage.googleapis.com/coscientist_paper/ai_coscientist.pdf

Documentation, Diagrams and Question-Answering of this project using DeepWiki
* https://deepwiki.com/chunhualiao/ai-co-scientist 

## Overview

This project implements a multi-agent system within the `app` package that iteratively generates and refines research hypotheses. The code is organized into modules:
*   `app/models.py`: Defines data structures (`Hypothesis`, `ResearchGoal`, `ContextMemory`) and API request/response schemas.
*   `app/utils.py`: Contains utility functions for LLM calls, logging, similarity scoring, etc.
*   `app/agents.py`: Implements the core agent logic (`GenerationAgent`, `ReflectionAgent`, `RankingAgent`, `EvolutionAgent`, `ProximityAgent`, `MetaReviewAgent`, `SupervisorAgent`).
*   `app/api.py`: Defines the FastAPI application, API endpoints, startup events (like fetching models), and serves the HTML frontend.
*   `app/config.py`: Handles loading the `config.yaml` file.
*   `app/main.py`: The main entry point for running the Uvicorn server.

**Core Components:**

*   **LLM Integration:** Uses the OpenRouter API to interact with LLMs. The default model is specified in `config.yaml` (currently `google/gemini-2.0-flash-001`), but can be overridden via the UI. Fetches available models from OpenRouter on startup to populate a dropdown list. Requires an `OPENROUTER_API_KEY` environment variable.
*   **Hypothesis Representation:** (`app/models.py`) A `Hypothesis` class stores the hypothesis details (ID, title, text, reviews, score, etc.).
*   **Research Goal Representation:** (`app/models.py`) A `ResearchGoal` class stores the description and runtime settings (LLM model, temperatures, counts) provided via the UI or defaulted from `config.yaml`.
*   **Context Memory:** (`app/models.py`) The `ContextMemory` class stores the state (hypotheses, results) during a research run.
*   **Agents:** (`app/agents.py`) Different agents perform specific tasks:
    *   `GenerationAgent`: Generates new hypotheses.
    *   `ReflectionAgent`: Reviews hypotheses.
    *   `RankingAgent`: Ranks hypotheses using Elo.
    *   `EvolutionAgent`: Combines top hypotheses.
    *   `ProximityAgent`: Calculates similarity using `sentence-transformers` and generates graph data.
    *   `MetaReviewAgent`: Summarizes progress.
    *   `SupervisorAgent`: Orchestrates the cycle.
*   **FastAPI Application:** (`app/api.py`) Provides API endpoints and a web interface with basic controls and an "Advanced Settings" section.

## How it Works

1.  **Startup:** The FastAPI application starts, fetching available LLM models from OpenRouter.
2.  **Set Research Goal:** The user provides a research goal description and optionally adjusts parameters in the "Advanced Settings" section of the web UI. Clicking "Submit Research Goal" sends this information to the `/research_goal` endpoint.
3.  **Initialization:** The backend creates a `ResearchGoal` object containing the description and runtime settings (using UI values or `config.yaml` defaults). It resets the `ContextMemory` and configures a timestamped log file in the `results/` directory.
4.  **Run Cycle (Trigger):** The first cycle is triggered automatically after submitting the goal. Subsequent cycles are triggered manually by clicking "Run Next Cycle". This calls the `/run_cycle` endpoint.
5.  **Cycle Execution (`SupervisorAgent`):**
    *   **Generation:** Generates new hypotheses based on the `ResearchGoal` settings (model, temperature, count).
    *   **Reflection:** Reviews active hypotheses using the specified reflection temperature.
    *   **Ranking:** Ranks hypotheses using Elo, applying the specified K-factor.
    *   **Evolution:** Combines the top K hypotheses (specified by `top_k_hypotheses`).
    *   **Reflection (Evolved):** Reviews any newly evolved hypotheses.
    *   **Ranking:** Ranks all active hypotheses again.
    *   **Proximity Analysis:** Calculates similarity scores between active hypotheses using `sentence-transformers` (`all-MiniLM-L6-v2` by default, configurable via `sentence_transformer_model` in `config.yaml` - *Note: This config key needs to be added if not present*) and prepares data for the Vis.js graph.
    *   **Meta-Review:** Summarizes the cycle's results.
6.  **Display Results:** The results, including hypotheses, meta-review, and the similarity graph, are displayed on the web page.
7.  **Iteration:** The user can click "Run Next Cycle" to repeat step 5 onwards.

## User Instructions

1.  **Set up a virtual environment (recommended):**
    It is recommended to create and activate a Python virtual environment before installing dependencies to avoid conflicts with other packages on your system. For example:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    (This includes `fastapi`, `uvicorn`, `openai`, `requests`, `sentence-transformers`, `scikit-learn`, `torch`, `numpy`, `PyYAML`).
3.  **Set Up OpenRouter API Key:**
    **Important:** You need an OpenRouter API key with sufficient balance to use this system.
    
    a. **Get API Key:** Sign up at [https://openrouter.ai/](https://openrouter.ai/) and obtain an API key
    
    b. **Add Initial Balance:** **CRITICAL** - Add at least $5 to your OpenRouter account balance. Without sufficient funds, the system will fail to generate hypotheses and you'll see "insufficient funds" errors in the terminal.
    
    c. **Set Environment Variable:**
    ```bash
    export OPENROUTER_API_KEY=your_api_key
    ```
    
    **Note:** The system uses LLM API calls for hypothesis generation, review, and ranking. Each research cycle typically costs $0.10-$0.50 depending on the model and number of hypotheses generated.

    There are free models available too from openrouter. 
4.  **Run the Application:**
    ```bash
    # Use the Makefile (default target runs uvicorn)
    make run
    ```
    (Alternatively, for development with auto-reload: `make run-reload`)
    
    (This uses the command `uvicorn app.api:app --host 0.0.0.0 --port 8000` internally.)
5.  **Access the Web Interface:**
    Open a web browser and go to `http://localhost:8000`. (Note: The server log may show `http://0.0.0.0:8000`, which means the server is listening on all network interfaces. However, you should use `localhost` in your browser to access the server from your local machine. You cannot directly type `0.0.0.0` into your browser's address bar.)
6.  **Enter Research Goal:**
    Enter your research goal in the text area provided. Optionally, expand "Advanced Settings" to customize the LLM model, temperatures, and other parameters.
7.  **Submit and Run:**
    Click the "Submit Research Goal" button. This sets the goal and parameters, resets the context, configures logging for the run, and automatically triggers the first cycle.
8.  **Iterate:**
    Click the "Run Next Cycle" button to perform subsequent refinement cycles on the current set of hypotheses using the same settings. Results are updated on the page after each cycle.

## Expected Results

The system will generate a list of hypotheses related to the research goal. Each hypothesis will have:

*   A unique ID. The ID starts with a prefix indicating its origin: 'G' for generated by the `GenerationAgent`, 'E' for evolved by the `EvolutionAgent`, and 'H' as the default.
*   A title
*   A description (text)
*   Novelty and feasibility assessments (HIGH, MEDIUM, LOW)
*   An Elo score (representing its relative strength)
*   Comments from the LLM review
*   References (if found by the LLM). These include arXiv IDs, DOIs, paper titles, and PubMed identifiers (PMIDs) when appropriate for biomedical topics.

The web interface will display the top-ranked hypotheses after each cycle, along with a meta-review critique, suggested next steps, a hypothesis similarity graph, and a **References section** showing related arXiv papers and literature citations. The results are iterative, meaning that the hypotheses should improve over multiple cycles. Log files for each run (initiated by "Submit Research Goal") are created in the `results/` directory with a timestamp.

## References Section

The AI Co-Scientist system includes an integrated literature discovery feature that automatically finds and displays relevant research papers related to your research goal and generated hypotheses.

### Features

**Automatic arXiv Integration:**
- Searches arXiv.org for papers related to your research goal
- Displays up to 5 most relevant papers with full metadata
- Shows paper titles, authors, abstracts, publication dates, and categories
- Provides direct links to arXiv papers and PDF downloads

**Smart Reference Detection:**
- Automatically detects different types of references from hypothesis reviews
- **arXiv IDs**: Links to arXiv papers (e.g., `2301.12345`, `arxiv:1706.03762`)
- **DOIs**: Links to journal articles (e.g., `10.1145/3394486.3403087`)
- **PubMed IDs**: Links to biomedical literature with domain-appropriate warnings
- **Paper titles**: Displays general citations and conference papers

**Domain-Appropriate References:**
- For computer science topics: Prioritizes arXiv papers and CS conferences
- For biomedical topics: Supports PubMed integration
- Provides warnings when PubMed references appear in non-biomedical contexts

### How It Works

1. **After each cycle**, the system:
   - Extracts reference IDs from LLM-generated hypothesis reviews
   - Searches arXiv for papers matching your research goal keywords
   - Processes and formats all references for display

2. **The References section displays**:
   - **Related arXiv Papers**: Automatically discovered papers with full details
   - **Additional References**: Citations mentioned in hypothesis reviews

3. **Error handling and logging**:
   - Comprehensive frontend-to-backend logging for debugging
   - Graceful fallbacks if arXiv search fails
   - Detailed error reporting in log files

### API Endpoints

The references feature uses several API endpoints:
- `POST /arxiv/search` - Search arXiv for papers
- `GET /arxiv/paper/{id}` - Get specific paper details  
- `GET /arxiv/categories` - List available arXiv categories
- `GET /arxiv/test` - Testing interface for arXiv integration
- `POST /log_frontend_error` - Frontend error logging

## Configuration (config.yaml)

The `config.yaml` file provides default settings for the system. Many of these can be overridden at runtime via the "Advanced Settings" section in the web UI when submitting a new research goal.

*   **`openrouter_base_url`**: Base URL for the OpenRouter API. Default: `"https://openrouter.ai/api/v1"`.
*   **`llm_model`**: Default LLM model identifier used if not specified in the UI. Default: `"google/gemini-2.0-flash-001"`.
*   **`num_hypotheses`**: Default number of hypotheses generated per cycle. Default: `6`.
*   **`elo_k_factor`**: Default K-factor for Elo rating updates (ranking sensitivity). Default: `32`.
*   **`top_k_hypotheses`**: Default number of top hypotheses used for evolution. Default: `2`.
*   **`logging_level`**: Controls logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). Default: `"INFO"`.
*   **`log_file_name`**: Base name for timestamped log files created in the `results/` directory. Default: `"app"`.
*   **`fastapi_host`**: Network interface for the server. Default: `"0.0.0.0"`.
*   **`fastapi_port`**: Port for the server. Default: `8000`.
*   **`step_temperatures`**: Contains temperature settings for different LLM calls:
    *   **`generation`**: Controls creativity during hypothesis generation. Default: `0.7`.
    *   **`reflection`**: Controls analytical focus during hypothesis review. Default: `0.5`.
*   **(Optional) `sentence_transformer_model`**: Specifies the model used for similarity scoring. If not present, defaults to `'all-MiniLM-L6-v2'` in `app/utils.py`. Example: `sentence_transformer_model: 'all-MiniLM-L6-v2'`

## Known Limitations

*   **LLM Dependency:** The quality of the results heavily depends on the capabilities of the underlying LLM and the prompts used.
*   **Parsing LLM Output:** Relies on the LLM consistently returning the requested JSON format. Errors in parsing can occur.
*   **Basic Evolution:** The `EvolutionAgent` uses a simple combination strategy.
*   **In-Memory Storage:** Hypothesis context is lost when the server restarts. A database would be needed for persistence.
*   **Error Handling:** While improved, error handling for edge cases (e.g., API failures, parsing issues) could be more robust.
*   **Prompt Engineering:** Prompts are functional but could be further optimized.
*   **OpenAI Dependency:** The `openai` library is used as the client for OpenRouter.

## Diagram

```mermaid
flowchart TD
    A[Start] --> B[Set Research Goal]
    B --> C[Initialize Context Memory]
    C --> D[Run Cycle]
    
    subgraph CycleProcess["Supervisor Agent Run Cycle"]
        D1[Generation: Create New Hypotheses] --> D2[Add to Context Memory]
        D2 --> D3[Reflection: Review Hypotheses]
        D3 --> D4[Ranking: Run Tournament]
        D4 --> D5[Evolution: Improve Top Ideas]
        D5 --> D6[Add Evolved Hypotheses to Context]
        D6 --> D7[Review Evolved Hypotheses]
        D7 --> D8[Ranking: Run Tournament Again]
        D8 --> D9[Proximity Analysis]
        D9 --> D10[Meta-Review]
        D10 --> D11[Increment Iteration Number]
    end
    
    D --> CycleProcess
    CycleProcess --> E[Return Overview Results]
    
    subgraph APIEndpoints["API Endpoints"]
        F1[POST /research_goal]
        F2[POST /run_cycle]
        F3[GET /hypotheses]
        F4[GET /]
    end
    
    F1 --> B
    F2 --> D
    F3 -.-> G[List Active Hypotheses]
    
    subgraph LLMCalls["LLM API Calls"]
        L1[call_llm_for_generation]
        L2[call_llm_for_reflection]
    end
    
    D1 --> L1
    D3 --> L2
```

## Example Input and Output

This section provides an example of the input you might provide to the system and the corresponding output you might receive.

**Input (Research Goal):**

```
Develop new methods for increasing the efficiency of solar panels.
```

**Output (Example - Simplified):**

```
Iteration: 1

Meta-Review Critique:
    - Some ideas are not very novel.

Top Hypotheses:

    - Hypothesis: (ID: G1234, Elo: 1250.50)
      Title: Use of Nanomaterials for Enhanced Light Absorption
      Text: Explore the use of novel nanomaterials, such as quantum dots and perovskites, to enhance light absorption in solar panels.
      Novelty: MEDIUM
      Feasibility: HIGH

    - Hypothesis: (ID: G5678, Elo: 1220.25)
      Title: Bio-Inspired Surface Texturing
      Text: Investigate bio-inspired surface texturing techniques, mimicking natural structures like moth eyes, to reduce reflection and increase light trapping in solar cells.
      Novelty: HIGH
      Feasibility: MEDIUM

    - Hypothesis: (ID: G9012, Elo: 1195.75)
      Title: Improved Cooling Systems for Solar Panels
      Text: Develop more efficient cooling systems to mitigate the negative impact of high temperatures on solar panel performance.
      Novelty: LOW
      Feasibility: HIGH
      
Combined Hypotheses:
    - Hypothesis: (ID: E4321, Elo: 1235.10)
      Title: Combined: Use of Nanomaterials for Enhanced Light Absorption & Bio-Inspired Surface Texturing
      Text: Explore the use of novel nanomaterials, such as quantum dots and perovskites, to enhance light absorption in solar panels.

      Additionally, Investigate bio-inspired surface texturing techniques, mimicking natural structures like moth eyes, to reduce reflection and increase light trapping in solar cells.
      Novelty: HIGH
      Feasibility: MEDIUM

Suggested Next Steps:
    - Conduct further in vitro experiments on top hypotheses.
    - Collect domain expert feedback and refine constraints.
```

**Explanation of Output:**

*   **Iteration:** The cycle number of the hypothesis generation process.
*   **Meta-Review Critique:**  Provides a high-level summary of any issues identified with the current set of hypotheses (e.g., lack of novelty).
*   **Top Hypotheses:** Displays the hypotheses with the highest Elo scores. Each hypothesis includes:
    *   **ID:** A unique identifier (G for generated, E for evolved).
    *   **Elo:**  A numerical score representing the hypothesis's relative strength.
    *   **Title:**  A concise title for the hypothesis.
    *   **Text:** A more detailed description of the hypothesis.
    *   **Novelty:**  An assessment of the hypothesis's originality (HIGH, MEDIUM, LOW).
    *   **Feasibility:** An assessment of the hypothesis's practicality (HIGH, MEDIUM, LOW).
*   **Combined Hypotheses:** Displays hypotheses that have been created by combining top-ranked hypotheses from previous cycles.
*   **Suggested Next Steps:**  Recommendations for future research directions.