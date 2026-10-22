"""Real provider transport. No local answer or model substitution on failure."""
import os
import time
import copy
from urllib.parse import urlsplit
import httpx


class ProviderError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def configuration():
    style = os.getenv('LLM_API_STYLE', 'chat_completions')
    if style not in ('responses', 'chat_completions'):
        raise ValueError('LLM_API_STYLE must be responses or chat_completions')
    base = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
    url = urlsplit(base)
    if url.scheme not in ('https', 'http') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Invalid LLM_BASE_URL')
    if url.scheme == 'http' and url.hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('Remote model providers require HTTPS')
    timeout = float(os.getenv('LLM_TIMEOUT_SECONDS', '90'))
    if not 1 <= timeout <= 180:
        raise ValueError('LLM_TIMEOUT_SECONDS must be between 1 and 180')
    choice = os.getenv('LLM_TOOL_CHOICE', 'forced')
    if choice not in ('auto','required','forced'):
        raise ValueError('Invalid LLM_TOOL_CHOICE')
    return {'style':style, 'base':base, 'model':os.getenv('LLM_MODEL','').strip(),
            'tool_choice':choice, 'strict':os.getenv('LLM_STRICT_TOOLS','true').lower()=='true',
            'key':os.getenv('LLM_API_KEY','').strip() or os.getenv('POE_API_KEY','').strip(), 'timeout':timeout}


async def complete(messages, tools=None):
    config = configuration()
    if not config['key'] or not config['model']:
        raise ProviderError('configuration_missing')
    payload = {'model':config['model']}
    if tools:
        tools = copy.deepcopy(tools)
        if not config['strict']:
            for tool in tools:
                tool['function'].pop('strict',None)
    if config['style']=='responses':
        path = '/responses'
        payload.update(input=messages, store=False)
        if tools:
            payload.update(tools=[{'type':'function', **t['function']} for t in tools],
                           tool_choice={'type':'function','name':tools[0]['function']['name']} if config['tool_choice']=='forced' else config['tool_choice'])
    else:
        path = '/chat/completions'
        payload['messages'] = messages
        if tools:
            payload.update(tools=tools, tool_choice={'type':'function','function':{'name':tools[0]['function']['name']}} if config['tool_choice']=='forced' else config['tool_choice'])
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=config['timeout']) as client:
        r = await client.post(config['base']+path, headers={'Authorization':'Bearer '+config['key']}, json=payload)
    if r.is_error:
        codes = {400:'invalid_request',401:'authentication_failed',402:'insufficient_credits',403:'access_denied',404:'model_or_endpoint_not_found',429:'rate_limited'}
        raise ProviderError(codes.get(r.status_code,'provider_unavailable'))
    data = r.json()
    if config['style']=='responses':
        if data.get('status') not in (None,'completed'):
            raise ProviderError('incomplete_response')
        calls, texts = [], []
        for item in data.get('output',[]):
            if item.get('type')=='function_call':
                calls.append({'id':item.get('call_id'),'type':'function','function':{'name':item['name'],'arguments':item['arguments']}})
            elif item.get('type')=='message':
                texts.extend(b['text'] for b in item.get('content',[]) if b.get('type')=='output_text')
        message = {'content':'\n'.join(texts)}
        if calls:
            message['tool_calls'] = calls
    else:
        choice = data['choices'][0]
        if choice.get('finish_reason') in ('length','content_filter'):
            raise ProviderError('incomplete_response')
        message = choice['message']
    if tools and len(message.get('tool_calls',[]))!=1:
        raise ProviderError('invalid_tool_response')
    if not tools and (not isinstance(message.get('content'),str) or not message['content'].strip()):
        raise ProviderError('empty_response')
    usage = data.get('usage') or {}
    metadata = {'tool':'LLM '+(tools[0]['function']['name'] if tools else 'answer'), 'status':'ok',
                'api_style':config['style'], 'model':data.get('model',config['model']),
                'response_id':data.get('id'), 'latency_ms':round((time.monotonic()-started)*1000),
                'input_tokens':usage.get('input_tokens',usage.get('prompt_tokens')),
                'output_tokens':usage.get('output_tokens',usage.get('completion_tokens'))}
    return message, metadata
