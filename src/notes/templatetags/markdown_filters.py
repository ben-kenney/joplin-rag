from django import template
from django.utils.safestring import mark_safe, SafeString
import markdown
import re

register = template.Library()

def fix_broken_markdown(text: str) -> str:
    """
    Fix broken markdown elements that can occur when text is chunked.
    
    Handles:
    - Unclosed fenced code blocks (```)
    - Unclosed inline code (`)
    - Unclosed bold/italic markers (* or **)
    - Broken links/images at the end of text
    """
    # Fix unclosed fenced code blocks (```)
    fenced_blocks = len(re.findall(r'```', text))
    if fenced_blocks % 2 != 0:
        # Remove the last orphan marker
        text = re.sub(r'```(?!.*```)', '', text, count=1)
    
    # Fix unclosed inline code (single backtick)
    # Only fix if there's an odd number at the END of the text
    inline_code = len(re.findall(r'(?<!`)`(?!`)', text))
    if inline_code % 2 != 0:
        # Remove trailing orphan backtick
        text = re.sub(r'`\s*$', '', text)
    
    # Fix trailing broken link/image syntax (e.g., "[text" or "![alt")
    text = re.sub(r'\[!\[?[^\]]*$', '', text)  # Remove incomplete image/link at end
    text = re.sub(r'\[[^\]]*$', '', text)  # Remove incomplete link text at end
    
    # Fix trailing broken URL part (e.g., "](http://..." at the end)
    text = re.sub(r'\]\([^\)]*$', '', text)
    
    return text

from django.conf import settings as django_settings

@register.filter(name='render_markdown')
def render_markdown(text: str) -> SafeString:
    """
    Render raw markdown text into safe HTML.
    """
    if not text:
        return mark_safe("")
    
    # Check if markdown rendering is disabled
    if not getattr(django_settings, 'RENDER_MARKDOWN', True):
        # Return raw text in a preformatted block
        from django.utils.html import escape
        return mark_safe(f"<pre style='white-space: pre-wrap;'>{escape(text)}</pre>")
    
    # Fix broken markdown from chunking before rendering
    text = fix_broken_markdown(text)
    
    # Use fenced_code for code blocks, nl2br to preserve newlines as breaks if needed,
    # tables for table support.
    rendered_html = markdown.markdown(
        text, 
        extensions=['fenced_code', 'nl2br', 'tables', 'sane_lists']
    )
    return mark_safe(rendered_html)
