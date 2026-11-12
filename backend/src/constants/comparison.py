# 跨批次主题对比的规则版本。
# 口径（对齐方式、相似度定义、匹配算法、门槛语义）任何一项变化都必须升级版本，
# 已保存的旧结论会在读取时被标记为 stale，并在再次请求时失效重算。
RULE_VERSION='term-aligned-cosine-hungarian-v1'

# 默认与允许的匹配门槛；低于门槛的 Hungarian 配对不硬配，双方主题都进入未匹配。
DEFAULT_THRESHOLD=0.35
MIN_THRESHOLD=0.0
MAX_THRESHOLD=0.95

# 差异词与匹配依据展示的词数上限。
EVIDENCE_TERMS=12
DIFF_TERMS=8
