"""Explicit isolated provider configuration for paid comparison harnesses."""
import os
from dotenv import dotenv_values

def add_provider_options(parser):
    parser.add_argument('--api-style', choices=['responses', 'chat_completions'])
    parser.add_argument('--tool-choice', choices=['auto', 'required', 'forced'])
    parser.add_argument('--no-strict-tools', action='store_true')

def load_provider(args):
    # Never combine one provider's key with another provider's leftover settings.
    for key in list(os.environ):
        if key.startswith(('LLM_', 'POE_')):
            del os.environ[key]
    values = dotenv_values(args.env_file)
    for key, value in values.items():
        if key.startswith(('LLM_', 'POE_')) and value is not None:
            os.environ[key] = value
    defaults = {'LLM_API_STYLE': 'chat_completions', 'LLM_TOOL_CHOICE': 'forced',
                'LLM_STRICT_TOOLS': 'true', 'LLM_TIMEOUT_SECONDS': '90'}
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    if args.api_style:
        os.environ['LLM_API_STYLE'] = args.api_style
    if args.tool_choice:
        os.environ['LLM_TOOL_CHOICE'] = args.tool_choice
    if args.no_strict_tools:
        os.environ['LLM_STRICT_TOOLS'] = 'false'
