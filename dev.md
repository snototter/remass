```bash
# Set up virtualenv
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -e .

python -m remass

### File selection widget
# With dummy file hierarchy
python -m remass.fileselect
# With backed up tablet files
python -m remass.fileselect --bp path/to/backup/xochitl/

### File hierarchy parsing
python -m remass.filesystem path/to/backup/xochitl/
```

