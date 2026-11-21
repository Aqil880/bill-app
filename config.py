import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'billing-pro-secret-key-2026-secure-random')
    INSTANCE_DIR = BASE_DIR / 'instance'
    DATABASE_PATH = INSTANCE_DIR / 'billing.db'
    PDF_DIR = BASE_DIR / 'invoices' / 'generated_pdfs'
    
    # Ensure necessary folders exist
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
