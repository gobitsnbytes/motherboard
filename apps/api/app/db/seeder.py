"""Retired: configuration must be changed explicitly through IAM."""


async def run_seeds(session):
    raise RuntimeError("Seeding is disabled. Use audited configuration management.")
