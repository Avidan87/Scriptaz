"""
Scriptaz Configuration & Environment Settings
Handles explicit AWS credentials, Bedrock models, S3 bucket settings,
and local macOS/Windows application paths.
"""

import os
import sys
import boto3
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment from multiple candidate locations
candidate_env_paths = [
    Path.home() / "Library" / "Application Support" / "Scriptaz" / ".env",
    Path(__file__).resolve().parent.parent / ".env",
    Path.cwd() / ".env",
    Path(sys.executable).parent / ".env",
]
if hasattr(sys, "_MEIPASS"):
    candidate_env_paths.insert(0, Path(sys._MEIPASS) / ".env")

for env_path in candidate_env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)

# Clean up AWS_PROFILE if no ~/.aws profile file exists on the machine
if "AWS_PROFILE" in os.environ and not (Path.home() / ".aws" / "credentials").exists() and not (Path.home() / ".aws" / "config").exists():
    del os.environ["AWS_PROFILE"]


@dataclass
class AppConfig:
    # Explicit AWS Credentials & Region
    aws_region: str = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    aws_access_key_id: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token: Optional[str] = os.getenv("AWS_SESSION_TOKEN")
    aws_profile: Optional[str] = os.getenv("AWS_PROFILE")

    # Amazon Bedrock Settings
    bedrock_model_id: str = os.getenv("BEDROCK_MODEL_ID", "us.deepseek.r1-v1:0")
    bedrock_fallback_model_id: str = os.getenv("BEDROCK_FALLBACK_MODEL_ID", "amazon.nova-lite-v1:0")
    bedrock_embedding_model_id: str = os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
    
    # S3 Settings
    s3_bucket_name: Optional[str] = os.getenv("S3_BUCKET_NAME")

    # Local Paths
    app_name: str = "Scriptaz"
    data_dir: Path = Path.home() / "Library" / "Application Support" / "Scriptaz" if os.name != "nt" else Path.home() / "AppData" / "Local" / "Scriptaz"
    
    # Defaults
    default_interval_minutes: int = int(os.getenv("DEFAULT_INTERVAL_MINUTES", "60"))
    default_daily_limit: int = int(os.getenv("DEFAULT_DAILY_LIMIT", "5"))
    default_bible_version: str = os.getenv("DEFAULT_BIBLE_VERSION", "NKJV")
    default_theme: str = os.getenv("DEFAULT_THEME", "Peace")

    # FastAPI Server
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8765"))

    def __post_init__(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.aws_access_key_id:
            self.aws_access_key_id = self.aws_access_key_id.strip().strip("'\"")
        if self.aws_secret_access_key:
            self.aws_secret_access_key = self.aws_secret_access_key.strip().strip("'\"")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "scriptaz.sqlite"

    def get_boto3_session(self) -> boto3.Session:
        """Returns an authenticated boto3 Session with graceful fallbacks."""
        if self.aws_access_key_id and self.aws_secret_access_key and "your_" not in self.aws_access_key_id:
            return boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_session_token=self.aws_session_token,
                region_name=self.aws_region
            )
        
        return boto3.Session(region_name=self.aws_region)


# Global singleton instance
config = AppConfig()
