@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "PYTHON_EXE="

if not defined PYTHON_EXE if exist "%PROJECT_ROOT%..\.venv\Scripts\python.exe" set "PYTHON_EXE=%PROJECT_ROOT%..\.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%PROJECT_ROOT%.venv\Scripts\python.exe" set "PYTHON_EXE=%PROJECT_ROOT%.venv\Scripts\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

pushd "%PROJECT_ROOT%"
"%PYTHON_EXE%" -c "from dotenv import load_dotenv; load_dotenv(); from utils.model_utils import ModelUtils; ModelUtils.list_all_available_models()"
set "EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %EXIT_CODE%
