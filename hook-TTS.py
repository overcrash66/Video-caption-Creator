# hook-TTS.py
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
import typeguard._decorators
typeguard._decorators.instrument = lambda func, **kwargs: func
from TTS.api import TTS

datas, binaries, hiddenimports = collect_all('TTS')
datas += collect_data_files('TTS')
hiddenimports += collect_submodules('TTS')