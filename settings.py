import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv("SOPHNET_API_KEY", ""))
    preferred_llm_model: str = field(
        default_factory=lambda: os.getenv("PREFERRED_LLM_MODEL", "DeepSeek-V4-Flash-Vision-Exp")
    )
    preferred_video_model: str = field(
        default_factory=lambda: os.getenv("PREFERRED_VIDEO_MODEL", "happyhorse-1.1-i2v")
    )

    # SophNet endpoints
    llm_base_url: str = "https://www.sophnet.com/api/open-apis/v1/chat/completions"
    video_gen_url: str = "https://www.sophnet.com/api/open-apis/projects/easyllms/videogenerator/generate"
    video_query_url: str = "https://www.sophnet.com/api/open-apis/projects/easyllms/videogenerator/task/{task_id}"

    # SophNet image generation endpoints
    image_gen_url: str = "https://www.sophnet.com/api/open-apis/projects/easyllms/imagegenerator/generate"
    image_query_url: str = "https://www.sophnet.com/api/open-apis/projects/easyllms/imagegenerator/task/{task_id}"
    image_edit_url: str = "https://www.sophnet.com/api/open-apis/projects/easyllms/imageeditor/edit"
    image_edit_query_url: str = "https://www.sophnet.com/api/open-apis/projects/easyllms/imageeditor/task/{task_id}"

    # Polling
    image_poll_interval_sec: int = 3
    image_timeout_sec: int = 300

    # File storage
    upload_dir: str = "uploads"
    output_dir: str = "outputs"
    database_url: str = "sqlite+aiosqlite:///data.db"

    # Limits
    max_image_size_mb: int = 20
    video_poll_interval_sec: int = 5
    video_timeout_sec: int = 600
    llm_retry_count: int = 2
    llm_retry_delay_sec: int = 3
    llm_timeout_sec: int = 120
    max_concurrent_tasks: int = 1


SETTINGS = Settings()

# Ensure storage dirs exist
os.makedirs(SETTINGS.upload_dir, exist_ok=True)
os.makedirs(SETTINGS.output_dir, exist_ok=True)
