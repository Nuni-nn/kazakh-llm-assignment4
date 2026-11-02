import re

TOKEN_RE = re.compile(r"\S+", re.UNICODE)
HAS_ALNUM = re.compile(r"[^\W_]", re.UNICODE)

def count_words(text: str) -> int:
    """
    Frozen Assignment 4 word-count rule:
    - split on whitespace;
    - exclude punctuation-only tokens;
    - hyphenated forms without spaces count as one token.
    """
    if not text:
        return 0
    return sum(1 for tok in TOKEN_RE.findall(text.strip()) if HAS_ALNUM.search(tok))

if __name__ == "__main__":
    import sys
    print(count_words(" ".join(sys.argv[1:])))
