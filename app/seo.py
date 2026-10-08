"""SEO helpers: structured data (JSON-LD) that search engines read."""


def faq_schema(faqs):
    """FAQPage structured data for a list of FAQ(question, answer), in the current language."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": str(faq.question),
                "acceptedAnswer": {"@type": "Answer", "text": str(faq.answer)},
            }
            for faq in faqs
        ],
    }
