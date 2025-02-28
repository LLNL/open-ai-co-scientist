# AI Co-Scientist System - Proposal Generator (v1)

This project implements an AI-powered system for generating, reviewing, ranking, and evolving research hypotheses. It leverages Large Language Models (LLMs) for various tasks, including hypothesis generation, reflection, and comparison. The system is designed to assist researchers in exploring a research space and identifying promising hypotheses.

## Overview

The `proposal-gen-v1.py` script implements a multi-agent system that iteratively generates and refines research hypotheses. The core components include:

*   **LLM Integration:** Uses the OpenRouter API to interact with LLMs (currently configured for `google/gemini-2.0-flash-thinking-exp:free`).  You will need an OpenRouter API key.
*   **Hypothesis Representation:**  A `Hypothesis` class stores the hypothesis title, text, novelty/feasibility reviews, Elo score, comments, and references.
*   **Context Memory:** The `ContextMemory` class stores hypotheses, tournament results, and meta-review feedback.
*   **Agents:**
    *   `GenerationAgent`: Generates new hypotheses based on a research goal.
    *   `ReflectionAgent`: Reviews hypotheses for novelty and feasibility.
    *   `RankingAgent`: Conducts a tournament to rank hypotheses using an Elo rating system.
    *   `EvolutionAgent`: Combines top-ranked hypotheses to create new, evolved hypotheses.
    *   `ProximityAgent`: Builds a graph representing the similarity between hypotheses (currently a placeholder).
    *   `MetaReviewAgent`: Summarizes the research progress and provides feedback.
    *   `SupervisorAgent`: Orchestrates the entire process.
*   **FastAPI Application:** Provides a web interface for setting research goals and running cycles of the system.

## How it Works

1.  **Set Research Goal:** The user provides a research goal description and optional constraints via the web interface.
2.  **Hypothesis Generation:** The `GenerationAgent` uses the research goal to prompt an LLM to generate initial hypotheses.
3.  **Hypothesis Reflection:** The `ReflectionAgent` prompts an LLM to review each hypothesis, assessing its novelty and feasibility (HIGH, MEDIUM, LOW), providing comments, and suggesting references.
4.  **Hypothesis Ranking:** The `RankingAgent` runs a tournament, comparing hypotheses pairwise and updating their Elo scores based on the outcomes.
5.  **Hypothesis Evolution:** The `EvolutionAgent` combines the top-ranked hypotheses to create new, potentially improved hypotheses.
6.  **Proximity Analysis:** The `ProximityAgent` calculates the similarity between hypotheses (currently a placeholder using random values).
7.  **Meta-Review:** The `MetaReviewAgent` summarizes the current state, including top hypotheses and feedback, and suggests next steps.
8.  **Iteration:** Steps 2-7 are repeated in cycles, iteratively refining the hypotheses.

## User Instructions

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Set Environment Variable:**
    Obtain an API key from OpenRouter ([https://openrouter.ai/](https://openrouter.ai/)) and set it as an environment variable:
    ```bash
    export OPENROUTER_API_KEY=your_api_key
    ```
3.  **Run the Application:**
    ```bash
    uvicorn proposal-gen-v1:app --host 0.0.0.0 --port 8000
    ```
4.  **Access the Web Interface:**
    Open a web browser and go to `http://localhost:8000`.
5.  **Enter Research Goal:**
    Enter your research goal in the text area provided.
6.  **Submit and Run:**
    Click the "Submit Research Goal" button. This will automatically set the research goal and run the first cycle.  Subsequent cycles will run automatically.  Results will be displayed on the page.

## Expected Results

The system will generate a list of hypotheses related to the research goal. Each hypothesis will have:

*   A unique ID
*   A title
*   A description (text)
*   Novelty and feasibility assessments (HIGH, MEDIUM, LOW)
*   An Elo score (representing its relative strength)
*   Comments from the LLM review
*   References (if found by the LLM)

The web interface will display the top-ranked hypotheses after each cycle, along with a meta-review critique and suggested next steps. The results are iterative, meaning that the hypotheses should improve over multiple cycles. Log files are created in the `results/` directory for each run.

## Known Limitations

*   **LLM Dependency:** The quality of the results heavily depends on the capabilities of the underlying LLM.
*   **Parsing LLM Output:** The current implementation uses simple string parsing to extract information from the LLM responses. This may be brittle and require adjustments depending on the LLM's output format.
*   **Similarity Score Placeholder:** The `similarity_score` function currently returns a random number. A robust implementation would use a more sophisticated similarity measure.
*   **Limited Evolution:** The `EvolutionAgent` only combines the top two hypotheses. More advanced evolutionary strategies could be implemented.
*   **In-Memory Storage:** The current implementation uses in-memory storage. For production use, a persistent storage solution (e.g., a database) would be necessary.
*   **Error Handling:** While basic error handling is included, more comprehensive error handling and logging should be implemented for a production-ready system.
*   **Prompt Engineering:** The prompts used for LLM calls are relatively simple. More sophisticated prompt engineering could improve the quality of the results.
*   **Single Cycle Execution:** The `/run_cycle` endpoint only executes one cycle at a time.  A mechanism for running multiple cycles automatically would be beneficial.
*   **OpenAI Dependency:** Although OpenRouter is used, the code still imports and uses the `OpenAI` class from the `openai` library. It should be updated to use a more generic client if other LLM providers are to be supported.
* **Logging:** The logging configuration is set up for each new research goal, which could lead to multiple loggers being created if the research goal is set multiple times without restarting the application.
