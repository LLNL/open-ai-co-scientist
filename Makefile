# Makefile for AI Co-Scientist Application

# Default host and port (can be overridden)
HOST ?= 0.0.0.0
PORT ?= 8000

# Default target: run the application without reload
run:
	@echo "Starting AI Co-Scientist server on $(HOST):$(PORT)..."
	uvicorn app.api:app --host $(HOST) --port $(PORT)

# Target to run with auto-reload for development
run-reload:
	@echo "Starting AI Co-Scientist server on $(HOST):$(PORT) with reload..."
	uvicorn app.api:app --host $(HOST) --port $(PORT) --reload

# Phony targets to avoid conflicts with filenames
.PHONY: run run-reload
