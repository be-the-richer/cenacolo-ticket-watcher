import sys
from pathlib import Path

# Add the root directory to the path so tests can import modules from the root
sys.path.insert(0, str(Path(__file__).parent.parent))
