from django import template
from django.utils.safestring import mark_safe, SafeString
import markdown
import re

register = template.Library()

def fix_unclosed_code_blocks(text: str) -> str:
    """
    Fix unclosed markdown code blocks by removing orphan ``` markers.
    
    This handles the case where text chunking splits a fenced code block,
    leaving one chunk with an opening ``` but no closing one.
    """
    # Count occurrences of code block markers (```)
    # We use regex to find all ``` that are at the start of a line or preceded by whitespace
    pattern = r'```'
    matches = list(re.finditer(pattern, text))
    
    if len(matches) % 2 != 0:
        # Odd number of markers means there's an unclosed block
        # Remove the last (orphan) marker
        last_match = matches[-1]
        text = text[:last_match.start()] + text[last_match.end():]
    
    return text

@register.filter(name='render_markdown')
def render_markdown(text: str) -> SafeString:
    """
    Render raw markdown text into safe HTML.
    """
    if not text:
        return mark_safe("")
    
    # Fix unclosed code blocks before rendering
    text = fix_unclosed_code_blocks(text)
    
    # Use fenced_code for code blocks, nl2br to preserve newlines as breaks if needed,
    # tables for table support.
    rendered_html = markdown.markdown(
        text, 
        extensions=['fenced_code', 'nl2br', 'tables', 'sane_lists']
    )
    return mark_safe(rendered_html)
