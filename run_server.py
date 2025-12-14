"""
Script to run the FastAPI server with better Windows compatibility.
This script reduces reloader warnings on Windows.
"""
import uvicorn
import sys
import os

# Suppress multiprocessing warnings on Windows
if sys.platform == "win32":
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="multiprocessing")
    os.environ["PYTHONUNBUFFERED"] = "1"

# Add backend to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

if __name__ == "__main__":
    # Use absolute path for reload_dirs to ensure only src directory is watched
    src_dir = os.path.join(backend_dir, "src")
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[src_dir],
        reload_includes=["*.py"],
        reload_excludes=[
            "*.pyc",
            "__pycache__",
            "**/__pycache__/**",
            ".venv/**",
            ".venv",
            "**/.venv/**",
            ".git/**",
            "*.pyo",
            "*.pyd",
            "**/site-packages/**",
            "**/*.pyc",
        ],
        log_level="info",
        access_log=True,
    )

