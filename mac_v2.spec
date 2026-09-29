from pathlib import Path

root = Path(SPECPATH)
a = Analysis([str(root / 'todo_app_v2_16.py')], pathex=[], binaries=[], datas=[],
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='MyHomework_v2_0', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, disable_windowed_traceback=False,
          argv_emulation=False, target_arch=None, codesign_identity=None,
          entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='MyHomework_v2_0')
app = BUNDLE(coll, name='MyHomework_v2_0.app', icon=str(root / 'todo.icns'),
             bundle_identifier='com.moongchy.myhomework',
             info_plist={'CFBundleDisplayName': '나만의 숙제 v2.0',
                         'CFBundleShortVersionString': '2.0.0',
                         'CFBundleVersion': '2.0.0',
                         'NSHighResolutionCapable': True})
