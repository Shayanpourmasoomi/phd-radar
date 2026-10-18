@echo off
rem Daily run (Windows). Task Scheduler: Create Basic Task -> Daily -> Start a program -> this file.
cd /d "%~dp0"
python -m agent run >> data\run.log 2>&1
