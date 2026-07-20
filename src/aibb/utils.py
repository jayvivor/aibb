from typing import Sequence, Iterable, Union, Optional
from openrouter import OpenRouter
from dotenv import load_dotenv
import os



_client_cache: Optional[OpenRouter] = None


def listed(items: Sequence, attr: Optional[str]=None):
    '''
    Prints the items as a list of strings
    '''
    if attr is not None:
        getter = lambda item: str(getattr(item, attr))
    else:
        getter = lambda item: str(item)

    length = len(items)
    if not length:
        return ""
    if length == 1:
        return getter(items[0])
    if length == 2:
        return f"{getter(items[0])} and {getter(items[1])}"
    else:
        start, tail = items[:-2], items[-2:]
        start_str = ", ".join(getter(i) for i in start)
        tail_str = " and ".join(getter(i) for i in tail)
        return f"{start_str}, {tail_str}"
    

def get_client(use_cache: bool=False):
    global _client_cache
    if _client_cache and use_cache:
        return _client_cache
    load_dotenv()
    client = OpenRouter(api_key=os.environ["OPENROUTER_API_KEY"])
    _client_cache = client
    return client
    

def as_union(iterable: Iterable):
    return Union[*iterable]