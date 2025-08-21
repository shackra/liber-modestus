import re
from typing import List, Tuple

Token = Tuple[str, str]  # (kind, value)


class Tokenizer:
    def __init__(self, text: str):
        self.text = text
        self.tokens: List[Token] = []
        if self.text == "":
            raise ValueError("text cannot be empty")

        self._tokenize()

    def _tokenize(self):
        token_specification = [
            ("LPAREN", r"\("),
            ("RPAREN", r"\)"),
            ("LBRACK", r"\["),
            ("RBRACK", r"\]"),
            ("SEMICOLON", r";"),
            ("COLON", r":"),
            ("DOLLAR", r"\$"),
            ("BANG", r"!"),
            ("AMP", r"&"),
            ("EQUAL", r"="),
            ("SLASH", r"/"),
            ("DASH", r"-"),
            ("NUMBER", r"\d+(\.\d+)?"),
            ("WORD", r"[^\s;\[\]()$!&=:/-]+"),
            ("SKIP", r"[ \t]+"),
            ("NEWLINE", r"\n"),
        ]
        tok_regex = "|".join(
            f"(?P<{name}>{pattern})" for name, pattern in token_specification
        )

        raw_tokens = []
        for mo in re.finditer(tok_regex, self.text):
            kind = mo.lastgroup
            value = mo.group()
            if kind == "SKIP" or kind is None:
                continue

            raw_tokens.append((kind, value))

        i = 0
        header = False
        header_text = []
        bang = False
        newline = True
        while i < len(raw_tokens):
            match raw_tokens[i][0]:
                case "SEMICOLON":
                    if i + 1 < len(raw_tokens) and raw_tokens[i + 1][0] == "SEMICOLON":
                        self.tokens.append(("SEP", ";;"))
                        i += 1
                    elif bang:
                        self.tokens.append(("SEP", ";"))
                    else:
                        self.tokens.append(raw_tokens[i])
                    newline = False
                case "LBRACK":
                    header = True
                    newline = False
                case "RBRACK":
                    header = False
                    self.tokens.append(("HEADER", f"[{" ".join(header_text)}]"))
                    header_text = []
                    newline = False
                case "BANG" | "EQUAL":
                    bang = True
                    self.tokens.append(raw_tokens[i])
                    newline = False
                case "NEWLINE":
                    bang = False
                    if newline is False:
                        newline = True
                        self.tokens.append(raw_tokens[i])
                case _:
                    if header:
                        header_text.append(raw_tokens[i][1])
                    else:
                        self.tokens.append(raw_tokens[i])

                    newline = False
            i += 1

    def __iter__(self):
        return iter(self.tokens)

    def __len__(self):
        return len(self.tokens)

    def __repr__(self):
        return " ".join([f"{name} {value}" for name, value in self.tokens])
