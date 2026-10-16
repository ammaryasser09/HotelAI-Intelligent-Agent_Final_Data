# -*- coding: utf-8 -*-
"""
A small voice-agent prototype on top of app/rag.

    agent = Agent(llm=QwenLLM('Qwen/Qwen2.5-7B-Instruct'))      # free, runs on a Colab T4
    agent = Agent(llm=OpenAICompatibleLLM(base_url, api_key, model))   # any OpenAI-style API
    reply = agent.ask('الفطار بكام؟')
    reply['answer'], reply['tools'], reply['docs']
    agent.login(997)            # the logged-in guest (user_accounts.account_id); agent.logout() = visitor

The session decides who is calling, never the conversation: tools that take an account_id always get the
logged-in account, whatever the model writes, so it cannot read another guest's bookings.
"""
import inspect, json, re, time
from importlib import import_module

R = import_module('app.rag.retriever')
P = import_module('app.rag.prompt')
T = import_module('app.rag.tools')
RT = import_module('app.rag.router')
TOOLS = [{'type': 'function', 'function': s} for s in T.TOOL_SCHEMAS]

class QwenLLM:
    """Local chat model through transformers (4-bit). Qwen2.5 speaks Arabic and supports tool calls."""
    def __init__(self, name='Qwen/Qwen2.5-7B-Instruct', max_new_tokens=300):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        self.tok = AutoTokenizer.from_pretrained(name)
        self.model = AutoModelForCausalLM.from_pretrained(
            name, device_map='auto',
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16))
        self.max_new_tokens = max_new_tokens

    def __call__(self, messages, tools):
        text = self.tok.apply_chat_template(messages, tools=tools, add_generation_prompt=True, tokenize=False)
        ids = self.tok(text, return_tensors='pt').to(self.model.device)
        out = self.model.generate(**ids, max_new_tokens=self.max_new_tokens, do_sample=False)
        raw = self.tok.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=False)
        raw = raw.replace('<|im_end|>', '').replace('<|endoftext|>', '').strip()
        calls = [json.loads(m) for m in re.findall(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', raw, re.S)]
        text = re.sub(r'<tool_call>.*?</tool_call>', '', raw, flags=re.S).strip()
        return text, [(c['name'], c.get('arguments', {})) for c in calls]

class OpenAICompatibleLLM:
    """Any OpenAI-style /chat/completions endpoint (OpenAI, Groq, Together, a local vLLM, ...)."""
    def __init__(self, base_url, api_key, model):
        self.url, self.key, self.model = base_url.rstrip('/') + '/chat/completions', api_key, model

    def __call__(self, messages, tools):
        import requests
        msgs = []
        for m in messages:                                   # OpenAI wants string arguments + ids
            m = dict(m)
            if m.get('tool_calls'):
                m['tool_calls'] = [{'id': f'call_{i}', 'type': 'function',
                                    'function': {'name': t['function']['name'], 'arguments': json.dumps(t['function']['arguments'], ensure_ascii=False)}}
                                   for i, t in enumerate(m['tool_calls'])]
            if m['role'] == 'tool': m['tool_call_id'] = m.pop('call_id', 'call_0')
            msgs.append(m)
        r = requests.post(self.url, headers={'Authorization': f'Bearer {self.key}'}, timeout=120,
                          json={'model': self.model, 'messages': msgs, 'tools': tools, 'temperature': 0}).json()
        msg = r['choices'][0]['message']
        calls = [(c['function']['name'], json.loads(c['function']['arguments'] or '{}')) for c in (msg.get('tool_calls') or [])]
        return (msg.get('content') or '').strip(), calls

class Agent:
    def __init__(self, llm, retriever=None, mode='hybrid', max_tool_rounds=3):
        self.llm = llm
        self.retriever = retriever or R.HybridRetriever(mode=mode)
        self.max_tool_rounds = max_tool_rounds
        self.history = []                                   # earlier turns of this call
        self.call_lang = 'Arabic-Egyptian'                  # language of the call so far
        self.account_id = None                              # logged-in guest; None = visitor

    def reset(self): self.history = []
    def login(self, account_id): self.account_id = str(account_id) if account_id not in (None, '') else None
    def logout(self): self.account_id = None

    def session_note(self):
        if self.account_id is None:
            return 'SESSION: visitor, not logged in.'
        a = T._account(self.account_id)
        return f"SESSION: logged in as {a['full_name'] if a else 'unknown'} (account {self.account_id})."

    def run_tool(self, name, args):
        """Run a tool the model asked for; account_id always comes from the session."""
        if name not in T.TOOLS: return {'ok': False, 'reason': 'UNKNOWN_TOOL'}
        fn = T.TOOLS[name]; args = dict(args)
        if 'account_id' in inspect.signature(fn).parameters:
            if self.account_id is None and name in ('my_bookings', 'link_booking'):
                return {'ok': False, 'reason': 'NOT_LOGGED_IN'}
            args['account_id'] = self.account_id
        try: return fn(**args)
        except TypeError as e: return {'ok': False, 'reason': f'BAD_ARGUMENTS: {e}'}

    def greet(self, language='Arabic-Egyptian'):
        """Start a call: the fixed hotel greeting becomes the first turn of the history."""
        self.reset(); self.call_lang = language; text = P.greeting(language)
        self.history.append({'role': 'assistant', 'content': text})
        return text

    def ask(self, question):
        t0 = time.time()
        lang = P.detect_language(question)
        if lang == 'Arabic' and self.call_lang == 'Arabic-Egyptian' and len(question.split()) <= 5:
            lang = 'Arabic-Egyptian'                             # short replies keep the call's dialect
        self.call_lang = lang
        if P.is_goodbye(question):                               # "شكراً" / "مع السلامة": close politely, no LLM
            text = P.closing(lang)
            self.history += [{'role': 'user', 'content': question}, {'role': 'assistant', 'content': text}]
            return {'question': question, 'answer': text, 'tools': [], 'docs': [], 'out_of_scope': False,
                    'language': lang, 'seconds': round(time.time() - t0, 1), 'needs_lookup': False}
        found = self.retriever.search(question)
        pre, notes = RT.route(question, account_id=self.account_id)   # tools the code runs itself
        notes = [self.session_note()] + notes
        used = [{'tool': n, 'args': 'router', 'result': r} for n, r in pre]
        messages = P.build_messages(question, found, history=self.history,
                                    tool_results=[f'{n}: {r}' for n, r in pre], notes=notes)
        for i, _ in enumerate(range(self.max_tool_rounds + 1)):
            text, calls = self.llm(messages, TOOLS)
            if not calls: break
            messages.append({'role': 'assistant', 'content': text,
                             'tool_calls': [{'type': 'function', 'function': {'name': n, 'arguments': a}} for n, a in calls]})
            for k, (name, args) in enumerate(calls):
                result = self.run_tool(name, args)
                used.append({'tool': name, 'args': args, 'result': result})
                messages.append({'role': 'tool', 'call_id': f'call_{k}', 'content': json.dumps(result, ensure_ascii=False, default=str)})
        self.history += [{'role': 'user', 'content': question}, {'role': 'assistant', 'content': text}]
        return {'question': question, 'answer': text, 'tools': used, 'docs': found['docs'],
                'out_of_scope': found['out_of_scope'], 'language': lang, 'needs_lookup': bool(pre),
                'seconds': round(time.time() - t0, 1)}


def needs_lookup(question, account_id=None):
    """True when the agent will look something up: play the hold phrase before thinking."""
    return bool(RT.route(question, account_id=account_id)[0])
