import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    vk_group_token: str
    hf_api_token: str
    hf_model: str


def load_settings() -> Settings:
    vk_group_token = os.getenv('VK_GROUP_TOKEN', '').strip()
    hf_api_token = (os.getenv('HF_API_TOKEN') or os.getenv('HF_TOKEN', '')).strip()
    hf_model = os.getenv('HF_MODEL', 'Qwen/Qwen2.5-1.5B-Instruct').strip()

    if not vk_group_token:
        raise ValueError('VK_GROUP_TOKEN is required in .env')

    return Settings(
        vk_group_token=vk_group_token,
        hf_api_token=hf_api_token,
        hf_model=hf_model,
    )
