from dataclasses import dataclass, field


@dataclass
class Job:
    company: str
    id: str
    title: str = ""
    location: str = ""
    url: str = ""
    description: str = ""
    required_text: str = ""
    preferred_text: str = ""
    posted: str = ""
    raw: dict = field(default_factory=dict)
    enriched: bool = False

    @property
    def key(self):
        return f"job#{self.company}#{self.id}"
