from django import template
from django.utils.safestring import mark_safe

from songs import chordpro

register = template.Library()


@register.filter
def render_chordpro(body: str):
    # chordpro.render_html escapes all user content.
    return mark_safe(chordpro.render_html(body))  # noqa: S308
