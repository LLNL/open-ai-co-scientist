---
title: Open AI Co-Scientist
emoji: 🔬
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
short_description: Generate, review, rank, and evolve research hypotheses using AI agents
---

# 🔬 Open AI Co-Scientist - Hypothesis Evolution System

An AI-powered system for generating, reviewing, ranking, and evolving research hypotheses using multiple AI agents. This system helps researchers explore research spaces and identify promising hypotheses through iterative refinement.

## 🚀 Features

- **Multi-Agent System**: Uses specialized AI agents for generation, reflection, ranking, evolution, and meta-review
- **Hypothesis Evolution**: Combines top-performing hypotheses to create improved versions
- **Literature Integration**: Automatically finds related arXiv papers for your research topic
- **Cost Control**: Automatically filters to cost-effective models in production deployment
- **Interactive Interface**: Easy-to-use Gradio interface with advanced settings

## 🎯 How to Use

1. **Enter Research Goal**: Describe what you want to research in the text area
2. **Adjust Settings** (optional): Expand "Advanced Settings" to customize:
   - LLM model selection
   - Number of hypotheses per cycle
   - Temperature settings for creativity vs. analysis
   - Ranking and evolution parameters
3. **Set Goal**: Click "Set Research Goal" to initialize the system
4. **Run Cycles**: Click "Run Cycle" to generate and evolve hypotheses iteratively

## 🧠 How It Works

The system uses a multi-agent approach:

1. **Generation Agent**: Creates new research hypotheses
2. **Reflection Agent**: Reviews and assesses hypotheses for novelty and feasibility
3. **Ranking Agent**: Uses Elo rating system to rank hypotheses
4. **Evolution Agent**: Combines top hypotheses to create improved versions
5. **Proximity Agent**: Analyzes similarity between hypotheses
6. **Meta-Review Agent**: Provides overall critique and suggests next steps

## 📚 Literature Integration

- Automatically searches arXiv for papers related to your research goal
- Displays relevant papers with full metadata, abstracts, and links
- Helps contextualize generated hypotheses within existing research

## 💡 Example Research Goals

- "Develop new methods for increasing the efficiency of solar panels"
- "Create novel approaches to treat Alzheimer's disease"
- "Design sustainable materials for construction"
- "Improve machine learning model interpretability"
- "Develop new quantum computing algorithms"

## ⚙️ Technical Details

- **Models**: Uses OpenRouter API with cost-effective models in production
- **Environment Detection**: Automatically detects Hugging Face Spaces deployment
- **Cost Control**: Filters to budget-friendly models (Gemini Flash, GPT-3.5-turbo, Claude Haiku, etc.)
- **Iterative Process**: Each cycle builds on previous results for continuous improvement

## 🔧 Configuration

The system automatically configures itself based on the deployment environment:

- **Production (HF Spaces)**: Limited to cost-effective models for budget control
- **Development**: Full access to all available models

## 📖 Research Paper

Based on the AI Co-Scientist research: https://storage.googleapis.com/coscientist_paper/ai_coscientist.pdf

## 🤝 Contributing

This is an open-source project. Feel free to contribute improvements, bug fixes, or new features.

## ⚠️ Note

This system requires an OpenRouter API key to function. The public demo uses a limited budget, so please use it responsibly. For extensive research, consider running your own instance with your API key.
