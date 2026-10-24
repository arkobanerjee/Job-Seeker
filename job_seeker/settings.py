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

class AdaptiveSettings(Strict):
    enabled: bool = False
    max_rounds: int = Field(default=4, ge=1, le=8)
    queries_per_round: int = Field(default=3, ge=1, le=5)
    pages_per_round: int = Field(default=6, ge=1, le=10)
    max_minutes: int = Field(default=20, ge=1, le=20)
    max_stalled_rounds: int = Field(default=2, ge=1, le=4)
    planning_effort: Literal['medium', 'high'] = 'medium'
    assessment_effort: Literal['medium', 'high'] = 'medium'
    max_high_escalations: int = Field(default=2, ge=0, le=4)
    max_output_tokens: int = Field(default=8000,ge=1000,le=8000)


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
    run_usd: float = Field(default=0.50, gt=0, le=2, allow_inf_nan=False)
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

class VacancySettings(Strict):
    role_families: dict[Literal['ai','data'],list[str]] = Field(default_factory=lambda:{
        'ai':['AI engineer','applied AI engineer','machine learning engineer','LLM engineer'],
        'data':['data scientist','data analyst','analytics engineer','BI analyst']})
    regions: list[str] = Field(default_factory=lambda:['Germany','Europe','UAE','remote'],max_length=12)
    navigation_links: int = Field(default=2,ge=0,le=3)

    @model_validator(mode='after')
    def bounded_terms(self):
        if any(not terms or len(terms)>12 or any(not t.strip() or len(t)>100 for t in terms) for terms in self.role_families.values()):
            raise ValueError('Use 1–12 role terms per track, each 1–100 characters')
        if any(not t.strip() or len(t)>100 for t in self.regions):
            raise ValueError('Use region terms of 1–100 characters')
        return self

class Search(Strict):
    queries: list[Query] = Field(min_length=1, max_length=30)

class CompanyDiscoverySettings(Strict):
    run_usd: float = Field(default=0.50,gt=0,le=2,allow_inf_nan=False)
    max_searches: int = Field(default=10,ge=1,le=20)
    max_pages: int = Field(default=24,ge=1,le=40)
    max_model_calls: int = Field(default=32,ge=1,le=50)
    lookback_months: int = Field(default=6,ge=1,le=24)
    include_older: bool = False
    focus: str = Field(default='Germany Europe AI RAG data engineering',min_length=1,max_length=150)
    themes: list[Literal['funding','expansion','product','deployment','team']] = Field(default_factory=lambda:['funding','expansion','product','deployment','team'],min_length=1,max_length=5)

class Notifications(Strict):
    telegram: bool = False

class Monitoring(Strict):
    schedule_enabled: bool = False
    daily_run_usd: float = Field(default=0.25, gt=0, le=2, allow_inf_nan=False)
    enabled: bool = False
    max_sources: int = Field(default=12, ge=1, le=40)
    board_observations: bool = True
    max_boards: int = Field(default=4,ge=1,le=10)
    board_urls: list[str] = Field(default_factory=list,max_length=20)

    @model_validator(mode='after')
    def public_boards(self):
        from .ats import endpoint
        from .sources import normalized
        for url in self.board_urls:
            info=endpoint(normalized(url))
            if not info or info[2] is not None:raise ValueError('Board seeds must be public Greenhouse or Lever board URLs')
        return self

class SignalQuery(Query):
    route: Literal["company","hiring","technology","product","organization"] = "company"

class Signals(Strict):
    enabled: bool = False
    max_queries: int = Field(default=2,ge=1,le=5)
    queries: list[SignalQuery] = Field(default_factory=list,max_length=20)

class ReviewSettings(Strict):
    enabled: bool = False
    max_jobs: int = Field(default=3,ge=1,le=10)

class Competitors(Strict):
    enabled: bool = False
    max_queries: int = Field(default=1,ge=1,le=2)

class CompanyProfile(Strict):
    name: str = Field(min_length=1,max_length=200)
    aliases: list[str] = Field(default_factory=list,max_length=30)
    official_domains: list[str] = Field(default_factory=list,max_length=10)

    @model_validator(mode="after")
    def validate_domains(self):
        import re,ipaddress
        from .registry import ATS
        for domain in self.official_domains:
            if domain!=domain.lower() or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?",domain) or '..' in domain or '.' not in domain:raise ValueError('Use lowercase domain names without URLs or wildcards')
            if domain in ATS or any(domain.endswith('.'+d) for d in ATS):raise ValueError('Shared ATS domains cannot identify a company official domain')
            if domain.endswith(('.local','.internal','.localhost')):raise ValueError('Private domains are unsupported')
            try:ipaddress.ip_address(domain)
            except ValueError:continue
            raise ValueError('Official domains must be hostnames')
        return self

class Companies(Strict):
    profiles: list[CompanyProfile] = Field(default_factory=list,max_length=200)

    @model_validator(mode="after")
    def unique_aliases(self):
        seen={}
        for profile in self.profiles:
            for name in [profile.name,*profile.aliases]:
                key=' '.join(name.split()).casefold()
                if not key:raise ValueError('Company aliases cannot be empty')
                if key in seen and seen[key]!=profile.name:raise ValueError('Company alias assigned to multiple profiles')
                seen[key]=profile.name
        return self

class CorroborationSettings(Strict):
    enabled: bool = False
    max_pairs: int = Field(default=2,ge=1,le=5)
    publishers: dict[str,list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def publisher_domains(self):
        seen={}
        for name,domains in self.publishers.items():
            CompanyProfile(name=name,official_domains=domains)
            for domain in domains:
                if domain in seen and seen[domain]!=name:raise ValueError('Publisher domain assigned to multiple owners')
                seen[domain]=name
        return self


class Settings(Strict):
    company_discovery: CompanyDiscoverySettings = Field(default_factory=CompanyDiscoverySettings)
    vacancy: VacancySettings = Field(default_factory=VacancySettings)
    adaptive: AdaptiveSettings = Field(default_factory=AdaptiveSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    limits: Limits = Field(default_factory=Limits)
    prompts: Prompts = Field(default_factory=Prompts)
    search: Search
    notifications: Notifications = Field(default_factory=Notifications)
    monitoring: Monitoring = Field(default_factory=Monitoring)
    signals: Signals = Field(default_factory=Signals)
    review: ReviewSettings = Field(default_factory=ReviewSettings)
    competitors: Competitors = Field(default_factory=Competitors)
    companies: Companies = Field(default_factory=Companies)
    corroboration: CorroborationSettings = Field(default_factory=CorroborationSettings)

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
