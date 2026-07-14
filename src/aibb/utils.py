from typing import Sequence

def listed(items: Sequence):

    length = len(items)
    if not length:
        return ""
    if length == 1:
        return str(items[0])
    if length == 2:
        return f"{str(items[0])} and {str(items[1])}"
    else:
        start, tail = items[:-2], items[-2:]
        start_str = ", ".join(str(i) for i in start)
        tail_str = " and ".join(str(i) for i in tail)
        return f"{start_str} {tail_str}"