import bleach
import jinja2
from django_jinja import library


# based on bleach.sanitizer.ALLOWED_TAGS
ALLOWED_TAGS = [
    'a',
    'abbr',
    'acronym',
    'b',
    'blockquote',
    'code',
    'em',
    'i',
    'li',
    'ol',
    'p',
    'small',
    'strike',
    'strong',
    'ul',
]


@library.filter
def external_html(content):
    """Clean and mark "safe" HTML content from external data"""
    return jinja2.Markup(bleach.clean(content, tags=ALLOWED_TAGS))
