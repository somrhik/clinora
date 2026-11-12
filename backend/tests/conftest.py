import os
os.environ["DATABASE_URL"] = "sqlite:///./test_clinora.db"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough"
