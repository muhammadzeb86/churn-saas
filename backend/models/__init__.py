# Models package - import from models.py in parent directory
import sys
import os

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import from the models.py file in the backend directory
import importlib.util
spec = importlib.util.spec_from_file_location("models_module", os.path.join(backend_dir, "models.py"))
models_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(models_module)

# Export the models
User = models_module.User
Upload = models_module.Upload
Lead = models_module.Lead
Prediction = models_module.Prediction
PredictionStatus = models_module.PredictionStatus

__all__ = ["User", "Upload", "Lead", "Prediction", "PredictionStatus"]
