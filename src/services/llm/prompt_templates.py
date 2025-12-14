"""
Email prompt templates for different use cases.
"""
from typing import Optional


def get_default_template() -> str:
    """Get default email template."""
    return """Hi {name},

I hope this email finds you well. I came across {company} and was impressed by your work in the industry.

I'd love to explore how we might be able to help {company} achieve [specific goal]. We specialize in [value proposition] and have helped similar companies [results/benefits].

Would you be open to a brief conversation to see if there's a fit?

Best regards,
[Your Name]"""


def get_custom_template(template: Optional[str]) -> str:
    """Get custom template or default."""
    return template if template else get_default_template()

