"""Shared RAG source classification constants."""

SENSITIVE_FILE_NAMES = {
    '.env', '.env.local', '.env.production', 'credentials.json', 'credential.json',
    'private.key', 'id_rsa', 'id_ed25519', 'secrets.json', 'secret.json',
}
SENSITIVE_PARTS = {'node_modules', 'dist', 'build', '.git', '__pycache__', '.venv', 'venv'}
SOURCE_CODE_EXTENSIONS = {
    '.py', '.pyw', '.ts', '.tsx', '.js', '.jsx', '.java', '.cs', '.go', '.rs', '.cpp', '.c',
    '.h', '.hpp', '.sql', '.ps1', '.sh', '.yaml', '.yml', '.json', '.xml', '.toml', '.ini', '.md',
}
