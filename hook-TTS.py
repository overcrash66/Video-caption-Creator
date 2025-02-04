# hook-TTS.py
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
from PyInstaller.utils.hooks import get_package_paths

def hook(hook_api):
    package_path = get_package_paths('inflect')[0]
    hook_api.add_datas([(package_path, 'inflect')])
    hiddenimports = ['inflect.engine', 'inflect.__init__']
    hook_api.add_imports(*hiddenimports)
    package_path = get_package_paths('TTS')[0]
    hook_api.add_datas([(package_path, 'TTS')])
    hiddenimports = ['TTS.engine', 'TTS.__init__']
    hook_api.add_imports(*hiddenimports)
    package_path = get_package_paths('typeguard')[0]
    hook_api.add_datas([(package_path, 'typeguard')])
    hiddenimports = ['typeguard._decorators', 'typeguard._importhook']
    hook_api.add_imports(*hiddenimports)
    return hook_api

infl_datas, infl_binaries, infl_hiddenimports = collect_all('inflect')
tts_datas, tts_binaries, tts_hiddenimports = collect_all('TTS')
typeguard_datas = collect_data_files('typeguard')

datas = infl_datas + tts_datas + typeguard_datas
binaries = infl_binaries + tts_binaries
hiddenimports = infl_hiddenimports + tts_hiddenimports + collect_submodules('TTS') + ['typeguard._decorators', 'typeguard._importhook']