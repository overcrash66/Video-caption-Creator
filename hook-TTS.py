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
torch_datas = collect_data_files('torch')
#add numpy
numpy_datas = collect_data_files('numpy')
gruut_datas = collect_data_files('gruut')

tensorflow_datas = collect_data_files('tensorflow')
datas = infl_datas + tts_datas + typeguard_datas + torch_datas + numpy_datas + tensorflow_datas + gruut_datas
binaries = infl_binaries + tts_binaries
hiddenimports = infl_hiddenimports + tts_hiddenimports + collect_submodules('TTS') + collect_submodules('tensorflow') + ['typeguard._decorators', 'typeguard._importhook']