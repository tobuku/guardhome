"""Three-tier content classifier.

Usage:
    from core.classifier import classify

    category = await classify("some-unknown-site.com")
"""
from typing import Optional


async def classify(domain: str) -> Optional[str]:
    """Run domain through all three classifier tiers, return first match."""
    from core.classifier.domain_lookup import lookup as tier1
    from core.classifier.url_reputation  import lookup as tier2
    from core.classifier.ai_classifier   import classify as tier3

    result = await tier1(domain)
    if result:
        return result

    result = await tier2(domain)
    if result:
        return result

    return await tier3(domain)
