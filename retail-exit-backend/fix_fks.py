import glob
import re

for filepath in glob.glob("src/db/models/*.py"):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace foreign_keys=[Model.column] with string references if needed
    # Better yet, since we have __init__.py importing all models, we can just replace ExitEvent.invoice_id with 'ExitEvent.invoice_id' etc.
    content = re.sub(r'foreign_keys=\[([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\]', r'foreign_keys="[\1.\2]"', content)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
