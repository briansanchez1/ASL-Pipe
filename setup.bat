::Update pip
.venv\Scripts\python.exe -m pip install --upgrade pip

::.venv\Scripts\python.exe -m pip freeze > pip.txt
::.venv\Scripts\python.exe -m pip uninstall -r pip.txt -y
::del pip.txt
::.venv\Scripts\python.exe -m pip uninstall -r requirements_windows.txt -y
.venv\Scripts\python.exe -m pip install -r requirements_windows.txt

::Install ipykernel for Jupiter notebook files
.venv\Scripts\python.exe -m pip install ipykernel

::Add missing builder.py file to Protobuf by copying it from the Protobuf GitHub repository
if not exist ".venv\Lib\site-packages\google\protobuf\internal\builder.py" (
    powershell -Command "Invoke-WebRequest https://raw.githubusercontent.com/protocolbuffers/protobuf/refs/heads/main/python/google/protobuf/internal/builder.py -OutFile .venv\Lib\site-packages\google\protobuf\internal\builder.py"
)

::Create backup of MediaPipe's writer_utils.py, or overwrite the file with the backup if the backup exists
if exist ".venv\Lib\site-packages\mediapipe\tasks\python\metadata\metadata_writers\writer_utils.py.bak" (
    type ".venv\Lib\site-packages\mediapipe\tasks\python\metadata\metadata_writers\writer_utils.py.bak">>".venv\Lib\site-packages\mediapipe\tasks\python\metadata\metadata_writers\writer_utils.py"
) else (
    type ".venv\Lib\site-packages\mediapipe\tasks\python\metadata\metadata_writers\writer_utils.py">>".venv\Lib\site-packages\mediapipe\tasks\python\metadata\metadata_writers\writer_utils.py.bak"
)
::Append the "create_model_asset_bundle" function to writer_utils.py
type writer_utils.py>>".venv\Lib\site-packages\mediapipe\tasks\python\metadata\metadata_writers\writer_utils.py"
