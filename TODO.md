# AI Co-Scientist - Prioritized Feature Roadmap

This list outlines the top 10 priority features identified to make this system an indispensable tool for scientists and entrepreneurs.

1.  **Persistent Storage:**
    *   Implement database storage (e.g., SQLite, PostgreSQL) for research goals, context memory (hypotheses, results), run history, and user feedback.
    *   *Why:* Essential for any non-trivial use; allows resuming runs, comparing results across sessions, and managing generated data effectively.

2.  **Enhanced Novelty/Feasibility Validation:**
    *   Integrate external data sources for validation. Examples:
        *   PubMed API search for novelty checks against existing literature.
        *   Patent database search (e.g., Google Patents API) for IP checks.
        *   Use specialized LLMs or structured data for deeper technical feasibility analysis.
    *   *Why:* Grounds LLM assessments in real-world data, crucial for scientific rigor and entrepreneurial due diligence.

3.  **Market/Impact Assessment Agent:**
    *   Add a dedicated agent or enhance the Reflection agent to evaluate hypotheses based on potential market size, societal impact, commercial viability, or alignment with business goals.
    *   *Why:* Directly addresses entrepreneurial needs, adding a crucial dimension beyond purely technical assessment.

4.  **User Feedback Integration & Weighted Ranking:**
    *   Allow users to rate, tag, or comment on hypotheses within the UI during/after cycles.
    *   Modify the ranking system (e.g., Elo or a new multi-objective approach) to incorporate user feedback as a weighted factor alongside novelty, feasibility, etc.
    *   *Why:* Makes the user an active participant, tailoring results to their domain expertise and specific priorities.

5.  **Experimental Design / Next Step Suggestion Agent:**
    *   Add an agent that analyzes top-ranked hypotheses and suggests concrete next steps.
    *   Examples: Propose specific experiments, identify necessary resources/expertise, suggest validation methods.
    *   *Why:* Increases the actionability of the generated hypotheses, bridging the gap between idea and practical execution for scientists.

6.  **Literature Corpus Integration (RAG):**
    *   Allow users to upload relevant documents (PDFs) or specify research areas/keywords.
    *   Implement Retrieval-Augmented Generation (RAG) to provide this specific corpus as context to the LLM during generation and reflection steps.
    *   *Why:* Massively improves the quality, relevance, and grounding of hypotheses within a specific domain.

7.  **Advanced Visualization & Interaction:**
    *   Enhance the similarity graph (e.g., node clustering, filtering by score/tags, sizing nodes by Elo).
    *   Add plots showing score/metric trends over iterations.
    *   Allow direct interaction with visualizations (e.g., selecting nodes to prune/evolve).
    *   *Why:* Improves usability, facilitates pattern recognition, and allows for more intuitive exploration of the hypothesis space.

8.  **Structured Input & Constraints:**
    *   Develop a more structured way for users to define the research goal, including key variables, target outcomes, specific technical/budgetary constraints, target user/market segments.
    *   Use this structured input to generate more targeted prompts for agents.
    *   *Why:* Provides finer-grained control over the process, leading to more relevant and constrained results.

9.  **Advanced Evolution Strategies:**
    *   Implement more sophisticated methods for evolving hypotheses beyond simple combination.
    *   Examples: LLM-driven mutation based on critiques, varied crossover techniques, targeted refinement prompts.
    *   *Why:* Improves the core refinement capability of the system, potentially leading to more creative and robust hypotheses.

10. **Run Comparison & Trend Analysis:**
    *   Store results from multiple runs (potentially with different settings).
    *   Add UI features to compare results across runs (e.g., which settings produced higher-ranked hypotheses?).
    *   Visualize trends over time (e.g., average Elo score per cycle).
    *   *Why:* Enables meta-analysis of the system's performance and helps users understand how different parameters influence the outcomes.
