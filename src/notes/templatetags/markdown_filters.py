from django import template
from django.utils.safestring import mark_safe
import markdown

register = template.Library()

@register.filter(name='render_markdown')
def render_markdown(text):
    if not text:
        return ""
    # Use fenced_code for code blocks, nl2br to preserve newlines as breaks if needed,
    # tables for table support.
    rendered_html = markdown.markdown(
        text, 
        extensions=['fenced_code', 'nl2br', 'tables', 'sane_lists']
    )
    return mark_safe(rendered_html)
