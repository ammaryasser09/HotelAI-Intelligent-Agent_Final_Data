@echo off
rem Opens the ngrok link to the API on port 8000, skipping the certificate check some networks block.
rem Run from the project folder:  scripts\tunnel
ngrok http 8000 --config "%LOCALAPPDATA%\ngrok\ngrok.yml" --config "%~dp0ngrok.yml"
