"""Validated configuration; secrets never enter configuration snapshots."""
from pathlib import Path
import hashlib
import json
import math
import tomllib
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parent.parent

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class ModelSettings(Strict):
    provider: Literal["openai", "anthropic"] = "openai"
    name: str = "gpt-5.6-luna"
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "low"
    max_output_tokens: int = Field(default=4000, ge=1000, le=8000)
    input_usd_per_million: float = Field(default=0.20, gt=0, le=100)
    output_usd_per_million: float = Field(default=1.20, gt=0, le=500)

    @model_validator(mode="after")
    def rates(self):
        if not all(math.isfinite(x) for x in (self.input_usd_per_million,self.output_usd_per_million)):
            raise ValueError("Model rates must be finite")
        known = {"gpt-5.6-luna":(0.20,1.20), "gpt-5-mini":(0.25,2.0)}
        if self.provider == "openai" and self.name in known:
            a,b=known[self.name]
            if self.input_usd_per_million<a or self.output_usd_per_million<b:
                raise ValueError("Configured rates are below verified model prices")
        return self

class Limits(Strict):
    run_usd: float = Field(default=2, gt=0, le=2, allow_inf_nan=False)
    max_searches: int = Field(default=6, ge=1, le=20)
    max_pages: int = Field(default=12, ge=1, le=40)
    max_model_calls: int = Field(default=16, ge=1, le=50)
    context_bytes: int = Field(default=60000, ge=10000, le=80000)

class Prompts(Strict):
    master_file: str = "prompts/master.md"
    profile_file: str = "private/profile.md"
    resume_file: str = "private/resume.md"
    instructions: str = ""

class Query(Strict):
    track: Literal["ai", "data"]
    query: str = Field(min_length=1, max_length=350)

class Search(Strict):
    queries: list[Query] = Field(min_length=1, max_length=30)

class Notifications(Strict):
    telegram: bool = False

class Monitoring(Strict):
    schedule_enabled: bool = False
    daily_run_usd: float = Field(default=0.25, gt=0, le=2, allow_inf_nan=False)
    enabled: bool = False
    max_sources: int = Field(default=12, ge=1, le=40)

class Settings(Strict):
    model: ModelSettings = Field(default_factory=ModelSettings)
    limits: Limits = Field(default_factory=Limits)
    prompts: Prompts = Field(default_factory=Prompts)
    search: Search
    notifications: Notifications = Field(default_factory=Notifications)
    monitoring: Monitoring = Field(default_factory=Monitoring)

def load_settings(path=None):
    path=Path(path or ROOT/"config.toml").resolve()
    return Settings.model_validate(tomllib.loads(path.read_text(encoding="utf-8-sig"))), path.parent

def local_file(root, name):
    path=(root/name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Prompt and background paths must stay inside the configuration directory")
    if path.suffix.lower()!=".md": raise ValueError("Prompt and background files must be Markdown")
    return path

def render_prompt(settings, root):
    p=settings.prompts
    master=local_file(root,p.master_file).read_text(encoding="utf-8-sig")
    profile=local_file(root,p.profile_file).read_text(encoding="utf-8-sig")
    resume_path=local_file(root,p.resume_file)
    resume=resume_path.read_text(encoding="utf-8-sig") if resume_path.exists() else "No resume supplied. Use the profile only."
    if not profile.strip(): raise ValueError("The candidate profile is empty")
    if "{{profile}}" not in master or "{{resume}}" not in master:
        raise ValueError("Master prompt must contain {{profile}} and {{resume}}")
    # Single pass: placeholders in background data are never interpreted.
    import re
    text=re.sub(r"\{\{(profile|resume)\}\}",lambda m: {"profile":profile,"resume":resume}[m[1]],master)
    text += "\nUSER SEARCH PREFERENCES:\n"+p.instructions
    if len(text.encode("utf-8"))>25000:
        raise ValueError("Combined master prompt/profile/resume exceeds 25 KB; shorten background text")
    return text

def fingerprint(settings,prompt):
    return hashlib.sha256((json.dumps(settings.model_dump(),sort_keys=True)+prompt).encode()).hexdigest()
