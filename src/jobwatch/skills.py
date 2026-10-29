import re

# canonical name -> aliases. Alias prefixes: "=" case-sensitive, "re:" raw regex.
TAXONOMY = {
    "Java": ["java"],
    "Python": ["python"],
    "C++": ["c++", "cpp"],
    "C#": ["c#"],
    "Go": ["golang", "=Go programming", "=Go developer", "=Go services", "=Go microservices",
           r"re:(?-i:\b(?:Java|Python|Rust|Scala|Kotlin|Ruby|C\+\+|Node\.js)\s*(?:,|/|and|or)\s*Go\b)",
           r"re:(?-i:\bGo\s*(?:,|/)\s*(?:Java|Python|Rust|Scala|Kotlin|Ruby|C\+\+))"],
    "Rust": ["=Rust"],
    "Scala": ["scala"],
    "Kotlin": ["kotlin"],
    "JavaScript": ["javascript"],
    "TypeScript": ["typescript"],
    "Node.js": ["node.js", "nodejs", "node js"],
    "Ruby": ["=Ruby", "ruby on rails"],
    "PHP": ["=PHP"],
    "Spring Boot": ["spring boot", "spring framework", "spring mvc", "spring cloud"],
    "React": ["=React", "reactjs", "react.js"],
    "Angular": ["=Angular", "angularjs"],
    "Vue": ["vue.js", "vuejs", "=Vue"],
    "Django": ["django"],
    "Flask": ["=Flask"],
    "FastAPI": ["fastapi"],
    ".NET": [".net", "dotnet", "asp.net"],
    "HTML": ["html"],
    "CSS": ["css"],
    "Bootstrap": ["bootstrap"],
    "gRPC": ["grpc"],
    "GraphQL": ["graphql"],
    "REST APIs": ["rest api", "rest apis", "restful", "rest services"],
    "Microservices": ["microservice", "microservices"],
    "SQL": ["sql"],
    "NoSQL": ["nosql"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb"],
    "Cassandra": ["cassandra"],
    "DynamoDB": ["dynamodb"],
    "Redis": ["redis"],
    "Elasticsearch": ["elasticsearch", "elastic search"],
    "Full-text search": ["full text search", "fts", "lucene", "solr"],
    "Vector search": ["vector search", "vector database", "vector databases", "vector db",
                      "vector similarity", "embeddings", "semantic search"],
    "Pinecone": ["pinecone"],
    "Kafka": ["kafka"],
    "RabbitMQ": ["rabbitmq"],
    "Pulsar": ["=Pulsar", "apache pulsar"],
    "Spark": ["apache spark", "pyspark", "=Spark"],
    "Flink": ["flink"],
    "Hadoop": ["hadoop"],
    "Airflow": ["airflow"],
    "Snowflake": ["=Snowflake"],
    "BigQuery": ["bigquery"],
    "ClickHouse": ["clickhouse"],
    "Presto/Trino": ["presto", "trino"],
    "YugabyteDB": ["yugabytedb", "yugabyte"],
    "CockroachDB": ["cockroachdb"],
    "Debezium": ["debezium"],
    "Change data capture": ["change data capture", "cdc"],
    "Apache Paimon": ["paimon"],
    "Apache Iceberg": ["iceberg"],
    "Delta Lake": ["delta lake"],
    "Data lake": ["data lake", "datalake", "lakehouse"],
    "Liquibase": ["liquibase"],
    "AWS": ["aws", "amazon web services"],
    "GCP": ["gcp", "google cloud"],
    "Azure": ["azure"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Docker": ["docker"],
    "Terraform": ["terraform"],
    "Infrastructure as code": ["infrastructure as code", "iac"],
    "Helm": ["=Helm", "helm charts"],
    "ArgoCD": ["argocd", "argo cd"],
    "Jenkins": ["jenkins"],
    "CI/CD": ["ci/cd", "cicd", "continuous integration", "continuous delivery", "continuous deployment"],
    "Ansible": ["ansible"],
    "Cloud Composer": ["cloud composer"],
    "Prometheus": ["prometheus"],
    "Grafana": ["grafana"],
    "OpenTelemetry": ["opentelemetry", "otel"],
    "Observability": ["observability", "telemetry"],
    "Linux": ["linux", "unix"],
    "Service mesh": ["service mesh", "istio", "envoy"],
    "Site reliability": ["site reliability", "sre"],
    "Distributed systems": ["distributed system", "distributed systems", "distributed computing",
                            "distributed database", "distributed databases"],
    "System design": ["system design", "systems design"],
    "Concurrency": ["multithreading", "multi-threading", "concurrency", "concurrent programming"],
    "High availability": ["high availability", "fault tolerance", "fault-tolerant", "highly available"],
    "Machine learning": ["machine learning"],
    "LLMs": ["llm", "llms", "large language model", "large language models", "generative ai", "genai"],
    "OAuth": ["oauth", "oauth2", "openid connect", "oidc"],
}


def _compile(alias):
    if alias.startswith("re:"):
        return re.compile(alias[3:], re.I)
    cs = alias.startswith("=")
    if cs:
        alias = alias[1:]
    parts = [p for p in re.split(r"[\s\-]+", alias) if p]
    body = r"[\s\-]+".join(re.escape(p) for p in parts)
    return re.compile(r"(?<![\w+#])%s(?![\w+#])" % body, 0 if cs else re.I)


_PATTERNS = {c: [_compile(a) for a in aliases] for c, aliases in TAXONOMY.items()}
_LOWER = {k.lower(): k for k in TAXONOMY}


def canonical(name):
    return _LOWER.get((name or "").strip().lower())


def find_skills(text):
    """Skills mentioned in text, in order of first appearance."""
    hits = []
    for canon, pats in _PATTERNS.items():
        pos = [m.start() for p in pats for m in [p.search(text or "")] if m]
        if pos:
            hits.append((min(pos), canon))
    return [c for _, c in sorted(hits)]


PREF_HEAD = re.compile(
    r"^(?:preferred|nice[\s-]*to[\s-]*have|bonus|good[\s-]*to[\s-]*have|desired|desirable|extra credit|"
    r"a plus|pluses|what would make you stand out|even better|great to have)\b", re.I)
REQ_HEAD = re.compile(
    r"^(?:(?:basic|minimum|required|key|core)\s+)?(?:requirements?|qualifications?|skills)\b"
    r"|^(?:what you(?:'|\u2019)?ll need|what you(?:'|\u2019)?ll bring|what we(?:'|\u2019)?re looking for|"
    r"who you are|you have|you will have|you(?:'|\u2019)?ll have|must[\s-]*have|about you|what you bring|"
    r"minimum|basic|required)\b", re.I)
OTHER_HEAD = re.compile(
    r"^(?:responsibilities|what you(?:'|\u2019)?ll do|what you will do|the role|about the (?:role|team|job|position)|"
    r"about (?:us|the company)|who we are|benefits|perks|what we offer|compensation|why join|the team|"
    r"overview|job description|in this role|your role|day[\s-]*to[\s-]*day|how you(?:'|\u2019)?ll)\b", re.I)
INLINE_PREF = re.compile(
    r"\b(?:plus|preferred|bonus|nice[\s-]*to[\s-]*have|good[\s-]*to[\s-]*have|desirable|advantage)\b", re.I)
_BULLET = re.compile(r"^\s*[\u2022\-\*\u2013]\s")


def _heading_kind(line):
    if _BULLET.match(line):
        return None
    s = line.strip().lstrip("#*:").strip()
    if not s or len(s) > 90:
        return None
    if PREF_HEAD.match(s):
        return "preferred"
    if REQ_HEAD.match(s):
        return "required"
    if OTHER_HEAD.match(s):
        return "other"
    return None


def classify_text(text):
    """Split skills found in a job description into (required, preferred) lists."""
    state, has_req, hits = "unknown", False, []
    for line in (text or "").split("\n"):
        kind = _heading_kind(line)
        if kind:
            state = kind
            has_req = has_req or kind == "required"
        inline = bool(INLINE_PREF.search(line))
        for s in find_skills(line):
            hits.append((s, state, inline))
    req, pref = [], []
    for s, state, inline in hits:
        if state == "preferred" or inline:
            bucket = pref
        elif state == "required" or not has_req:
            bucket = req
        else:
            continue
        if s not in bucket:
            bucket.append(s)
    pref = [s for s in pref if s not in req]
    return req, pref


class Profile:
    def __init__(self, data):
        self.have, self.unknown = set(), []
        for n in data.get("have", []):
            c = canonical(n)
            if c:
                self.have.add(c)
            else:
                self.unknown.append(n)
        for src, targets in data.get("implies", {}).items():
            if canonical(src) in self.have:
                for t in targets:
                    c = canonical(t)
                    if c:
                        self.have.add(c)


def analyze(job, profile):
    if job.required_text or job.preferred_text:
        req = find_skills(job.required_text)
        pref = [s for s in find_skills(job.preferred_text) if s not in req]
    else:
        req, pref = classify_text(job.description)
    return {
        "required_have": [s for s in req if s in profile.have],
        "required_missing": [s for s in req if s not in profile.have],
        "preferred_have": [s for s in pref if s in profile.have],
        "preferred_missing": [s for s in pref if s not in profile.have],
    }
