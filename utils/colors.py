from typing import Any

import colorful as _colorful

# colorful replaces its own sys.modules entry with a proxy object at import
# time, so its colour attributes (cf.red, cf.grey, ...) are invisible to static
# analysis. Re-export it as Any here so type checkers stay useful everywhere
# else instead of being blanket-disabled per file.
cf: Any = _colorful
cf.use_true_colors()
