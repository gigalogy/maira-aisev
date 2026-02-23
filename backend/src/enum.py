import enum


class TargetModel(enum.Enum):
    maira = "maira"


class EvalModel(enum.Enum):
    openai = "openai"
    maira = "maira"


class AIModelType(enum.Enum):
    target = "target"
    eval = "eval"
    both = "both"


class TargetLanguage(enum.Enum):
    japanese = "ja"
    english = "en"
