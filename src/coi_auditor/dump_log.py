import os

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logs_dir = os.path.join(project_root, 'logs')
os.makedirs(logs_dir, exist_ok=True)
LOG_PATH = os.path.join(logs_dir, 'coi_audit.log')
DUMP_PATH = os.path.join(logs_dir, 'coi_audit_dump.txt')

with open(LOG_PATH, 'r', encoding='utf-8', errors='replace') as f:
    log_content = f.read()

with open(DUMP_PATH, 'w', encoding='utf-8') as f:
    f.write(log_content)

print(f"Full log dumped to {DUMP_PATH}")
