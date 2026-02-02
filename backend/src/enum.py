import enum


class AIModelName(enum.Enum):
    maira = "maira"
    openai = "openai"


class AIModelType(enum.Enum):
    target = "target"
    eval = "eval"
    both = "both"
