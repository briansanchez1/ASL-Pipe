
from typing import Dict
import zipfile

def create_model_asset_bundle(input_models: Dict[str, bytes],
                              output_path: str) -> None:
  """Creates the model asset bundle.

  Args:
    input_models: A dict of input models with key as the model file name and
      value as the model content.
    output_path: The output file path to save the model asset bundle.
  """
  if not input_models or len(input_models) < 2:
    raise ValueError("Needs at least two input models for model asset bundle.")

  with zipfile.ZipFile(output_path, mode="w") as zf:
    for file_name, file_buffer in input_models.items():
      zf.writestr(file_name, file_buffer)
