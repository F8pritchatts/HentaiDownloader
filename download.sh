#! /bin/bash
rm -f failures.txt 
echo "Change environment to virtualenv"
source venv/bin/activate
python Hentai.py -u $1
zip -r $2 HDownload
rm -r HDownload
deactivate
