import torch
try:
    torch._C._jit_set_profiling_executor(False)
    torch._C._jit_set_profiling_mode(False)
except Exception as e:
    print("Warning: unable to disable torch JIT profiling:", e)

import main  # This should point to your actual main script.