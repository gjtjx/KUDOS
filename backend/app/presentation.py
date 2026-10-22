"""Normalize generated display text, never source records or transcript evidence."""
import re
from opencc import OpenCC

TRADITIONAL = OpenCC('s2t')


def display_text(text, doctors=()):
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    text = text.replace('\\r\\n', '\n').replace('\\n', '\n')
    # Protect contextual phrases from one-character homograph conversion.
    protected = {'只有': '只有', '只是': '只是', '系統': '系統', '系统': '系統'}
    for i, phrase in enumerate(protected):
        text = text.replace(phrase, f'__PHRASE_{i}__')
    text = TRADITIONAL.convert(text)
    for i, phrase in enumerate(protected):
        text = text.replace(f'__PHRASE_{i}__', protected[phrase])
    text = re.sub(r'(?<![一二三四五六七八九十幾兩多])隻有', '只有', text)
    for wrong, right in (('此係統', '此系統'), ('本係統', '本系統'), ('該係統', '該系統'), ('這個係統', '這個系統')):
        text = text.replace(wrong, right)
    for doctor in doctors:
        name = doctor['full_name']
        # Remove an invented Chinese name attached to a real catalog name.
        text = re.sub(r'[\u4e00-\u9fff]{1,4}(?:醫師|醫生)\s*[（(]\s*' + re.escape(name) + r'\s*[）)]', name, text)
    return text.strip()
