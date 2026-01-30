import string
from typing import Dict, Optional
from datetime import datetime

try:
    from jinja2 import Template
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

def render_eisenscript_template(script: str, context: Dict[str, str], use_jinja2: Optional[bool] = None) -> str:
    """
    Render an EisenScript template with variables from context.
    Supports both $var (string.Template) and {{ var }} (Jinja2) syntax.
    
    Args:
        script: The EisenScript string with variables.
        context: Dictionary of variables to substitute.
        use_jinja2: If True, use Jinja2 ({{ var }}), if False use string.Template ($var),
                    if None, auto-detect by presence of '{{' in script and Jinja2 availability.
    Returns:
        Rendered script with variables replaced.
    """
    if not script:
        return script
    if use_jinja2 is None:
        use_jinja2 = ('{{' in script and JINJA2_AVAILABLE)
    if use_jinja2 and JINJA2_AVAILABLE:
        template = Template(script)
        return template.render(**context)
    else:
        # Fallback to string.Template ($var style)
        template = string.Template(script)
        return template.safe_substitute(context)

# Example usage:
if __name__ == "__main__":
    eisenscript = '''
    text "$username"
    serial "$serial"
    bio "$bio"
    '''
    context = {
        'username': 'Alice',
        'serial': 'SN-1234',
        'bio': 'Adventurer and artist',
        'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    print(render_eisenscript_template(eisenscript, context))
    # For Jinja2 style:
    eisenscript_jinja = '''
    text "{{ username }}"
    serial "{{ serial }}"
    bio "{{ bio }}"
    '''
    if JINJA2_AVAILABLE:
        print(render_eisenscript_template(eisenscript_jinja, context, use_jinja2=True))
