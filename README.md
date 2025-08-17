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

# AI Co-Scientist - Hypothesis Evolution System (Gradio Version)

This project implements an AI-powered system for generating, reviewing, ranking, and evolving research hypotheses using a multi-agent architecture and Large Language Models (LLMs). The user interface is built with Gradio for rapid prototyping and interactive research.

## Quick Start

1. **Set up a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

2. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3. **Set up your OpenRouter API key:**
    - Sign up at [https://openrouter.ai/](https://openrouter.ai/) and obtain an API key.
    - Add at least $5 to your OpenRouter account balance (or use a free model if available).
    - Set the environment variable:
      ```bash
      export OPENROUTER_API_KEY=your_api_key
      ```

4. **Run the Gradio app:**
    ```bash
    python app.py
    ```
    Or, using the Makefile:
    ```bash
    make run
    ```

5. **Access the web interface:**
    - Open your browser and go to [http://localhost:7860](http://localhost:7860)

## Features

- **Multi-Agent System:** Iteratively generates, reviews, ranks, and evolves research hypotheses.
- **LLM Integration:** Uses OpenRouter API to access a variety of LLMs (model selection in UI).
- **Interactive Gradio UI:** Easy-to-use interface for research goal input, advanced settings, and results visualization.
- **References & Literature:** Integrated arXiv search for related papers.
- **Logging:** Each run is logged to a timestamped file in the `results/` directory.

## Usage

1. **Enter a research goal** in the provided textbox.
2. **(Optional) Adjust advanced settings** such as LLM model, number of hypotheses, temperatures, etc.
3. **Click "Run Cycle"** to generate, review, and evolve hypotheses.
4. **View results, meta-review, and related literature** in the web interface.
5. **Iterate** by running additional cycles to refine hypotheses.

## Example Research Goals

- Develop new methods for increasing the efficiency of solar panels.
- Create novel approaches to treat Alzheimer's disease.
- Design sustainable materials for construction.
- Improve machine learning model interpretability.
- Develop new quantum computing algorithms.

## Configuration

- Default settings can be adjusted in `config.yaml`.
- Many settings can be overridden in the Gradio UI under "Advanced Settings".

## Troubleshooting

- **Authentication errors:** Ensure your `OPENROUTER_API_KEY` is set and has sufficient balance.
- **No hypotheses generated:** May be due to rate limits or insufficient API balance.
- **Port conflicts:** The Gradio app runs on port 7860 by default.

## License

MIT

## Acknowledgements

- Based on the open-source implementation of Google's AI Co-Scientist system.
- Uses [Gradio](https://gradio.app/) for the user interface.
- LLM access via [OpenRouter](https://openrouter.ai/).
