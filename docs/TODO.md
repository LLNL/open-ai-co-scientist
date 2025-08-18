# Open AI Co-Scientist - Prioritized Feature Roadmap

This list outlines the top 10 priority features identified to make this system an indispensable tool for scientists and entrepreneurs.

1.  **Persistent Storage:**
    *   Implement database storage (e.g., SQLite, PostgreSQL) for research goals, context memory (hypotheses, results), run history, and user feedback.
    *   *Why:* Essential for any non-trivial use; allows resuming runs, comparing results across sessions, and managing generated data effectively.

2.  **Leverage Model Context Protocol (MCP):**
    *   Implement MCP servers to provide tools for external interactions (web search, database lookups, API calls).
    *   Refactor agents to use `use_mcp_tool` for accessing external data/functionality needed for validation, RAG, market analysis, etc.
    *   *Why:* Provides a standardized, robust, and extensible way to connect the AI to real-time external information and capabilities, enabling many other features on this list.

3.  **Enhanced Novelty/Feasibility Validation (via MCP):**
    *   Build MCP tools that wrap external APIs/services for validation:
        *   PubMed API search tool for novelty checks.
        *   Patent database search (e.g., Google Patents API) for IP checks.
        *   Use specialized LLMs or structured data for deeper technical feasibility analysis.
    *   *Why:* Grounds LLM assessments in real-world data, crucial for scientific rigor and entrepreneurial due diligence. (Enabled by MCP).

4.  **Market/Impact Assessment Agent (via MCP):**
    *   Add an agent or enhance Reflection agent to use MCP tools (e.g., web search, financial data APIs) to assess market size, impact, viability.
    *   *Why:* Directly addresses entrepreneurial needs, adding a crucial dimension beyond purely technical assessment. (Enabled by MCP).

5.  **User Feedback Integration & Weighted Ranking:**
    *   Allow users to rate, tag, or comment on hypotheses within the UI during/after cycles.
    *   Modify the ranking system (e.g., Elo or a new multi-objective approach) to incorporate user feedback as a weighted factor alongside novelty, feasibility, etc.
    *   *Why:* Makes the user an active participant, tailoring results to their domain expertise and specific priorities.

6.  **Experimental Design / Next Step Suggestion Agent (via MCP):**
    *   Add an agent using MCP tools (e.g., querying protocol databases, chemical suppliers) to suggest concrete next steps, experiments, resources.
    *   *Why:* Increases the actionability of the generated hypotheses, bridging the gap between idea and practical execution for scientists. (Potentially enabled by MCP).

7.  **Literature Corpus Integration (RAG via MCP):**
    *   Allow users to upload relevant documents (PDFs) or specify research areas/keywords.
    *   Implement RAG, potentially using an MCP server/tool to interface with a vector database or document retrieval system containing the user-provided corpus.
    *   *Why:* Massively improves the quality, relevance, and grounding of hypotheses within a specific domain. (Enabled by MCP).

8.  **Advanced Visualization & Interaction:**
    *   Enhance the similarity graph (e.g., node clustering, filtering by score/tags, sizing nodes by Elo).
    *   Add plots showing score/metric trends over iterations.
    *   Allow direct interaction with visualizations (e.g., selecting nodes to prune/evolve).
    *   *Why:* Improves usability, facilitates pattern recognition, and allows for more intuitive exploration of the hypothesis space.

9.  **Structured Input & Constraints:**
    *   Develop a more structured way for users to define the research goal, including key variables, target outcomes, specific technical/budgetary constraints, target user/market segments.
    *   Use this structured input to generate more targeted prompts for agents.
    *   *Why:* Provides finer-grained control over the process, leading to more relevant and constrained results.

10. **Advanced Evolution Strategies:**
    *   Implement more sophisticated methods for evolving hypotheses beyond simple combination.
    *   Examples: LLM-driven mutation based on critiques, varied crossover techniques, targeted refinement prompts.
    *   *Why:* Improves the core refinement capability of the system, potentially leading to more creative and robust hypotheses.

11. **Run Comparison & Trend Analysis:**
    *   Requires persistent storage (#1). Store results from multiple runs.
    *   Add UI features to compare results across runs.
    *   Visualize trends over time.
    *   *Why:* Enables meta-analysis and understanding of how settings impact outcomes.
