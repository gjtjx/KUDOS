"""Normalize generated display text, never source records or transcript evidence."""
import re
from opencc import OpenCC

TRADITIONAL = OpenCC('s2t')


def display_text(text, doctors=()):
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    text = text.replace('\\r\\n', '\n').replace('\\n', '\n')
    text = TRADITIONAL.convert(text)
    for doctor in doctors:
        name = doctor['full_name']
        # Remove an invented Chinese name attached to a real catalog name.
        text = re.sub(r'[\u4e00-\u9fff]{1,4}(?:醫師|醫生)\s*[（(]\s*' + re.escape(name) + r'\s*[）)]', name, text)
    return text.strip()
