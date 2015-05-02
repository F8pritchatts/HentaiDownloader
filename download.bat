@echo off
echo "Change environment to virtualenv"
venv-hentai\scripts\activate & python Hentai.py -u %1
deactivate
