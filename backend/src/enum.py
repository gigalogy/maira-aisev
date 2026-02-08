import enum


class TargetModel(enum.Enum):
    maira = "maira"


class EvalModel(enum.Enum):
    openai = "openai"


class AIModelType(enum.Enum):
    target = "target"
    eval = "eval"
    both = "both"
