class Adapter:
    """A strategy for reading one company's job listings."""

    def list_jobs(self, cfg):
        raise NotImplementedError

    def enrich(self, cfg, job):
        """Fetch/prepare the full description for a job that passed listing filters."""
        job.enriched = True
