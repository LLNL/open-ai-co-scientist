import uvicorn
import os

# Import the FastAPI app instance from the api module
from .api import app
# Import the config dictionary from the config module
from .config import config
# Import the logger from utils (optional, if main needs logging)
from .utils import logger

# Ensure OPENROUTER_API_KEY is set before starting (optional check)
if not os.getenv("OPENROUTER_API_KEY"):
    logger.warning("OPENROUTER_API_KEY environment variable is not set.")
    # Depending on requirements, you might exit here or let the app handle it.
    # print("Error: OPENROUTER_API_KEY environment variable must be set.")
    # exit(1)

if __name__ == "__main__":
    host = config.get("fastapi_host", "0.0.0.0")
    port = config.get("fastapi_port", 8000)
    reload_flag = config.get("uvicorn_reload", False) # Add a config option for reload

    logger.info(f"Starting Uvicorn server on {host}:{port} (Reload: {reload_flag})")

    # Note: When running this script directly (python app/main.py),
    # Uvicorn needs the app location string relative to the execution directory.
    # If run from project root: "app.api:app"
    # If run from inside 'app': "api:app"
    # The string "app.api:app" assumes you run `python -m app.main` from the project root,
    # or configure the run environment correctly.
    # A simpler approach for direct execution `python app/main.py` might be needed
    # if relative imports cause issues depending on how it's run.

    # Let's assume running from project root for now.
    # If issues arise, might need to adjust how uvicorn is called or the project structure.
    uvicorn.run(app, host=host, port=port, reload=reload_flag)

    # Alternative if running `python app/main.py` directly causes import issues:
    # uvicorn.run("app.api:app", host=host, port=port, reload=reload_flag)
    # This tells uvicorn where to find the app object.
