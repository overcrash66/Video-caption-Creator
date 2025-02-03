# hook-TTS.py
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('inflect')

datas, binaries, hiddenimports = collect_all('TTS')

datas += collect_data_files('TTS')
hiddenimports += collect_submodules('TTS')

datas = collect_data_files('typeguard')
hiddenimports = ['typeguard._decorators', 'typeguard._importhook']