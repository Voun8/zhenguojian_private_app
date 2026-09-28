import argparse
import hashlib
import re
import shutil
from pathlib import Path


def prepare(downloads, output, project):
    match = re.search(r'^version:\s*(\S+)\s*$', (project / 'pubspec.yaml').read_text(encoding='utf-8'), re.MULTILINE)
    if not match:
        raise ValueError('pubspec.yaml 缺少版本号')
    version = match.group(1)
    if output.exists() and any(output.iterdir()):
        raise ValueError('发布目录必须为空')
    output.mkdir(parents=True, exist_ok=True)
    checksums = []
    for edition in ('hongguojian', 'zhenguojian'):
        packages = {
            'android': [f'{edition}-{version}-{abi}.apk' for abi in ('arm64-v8a', 'armeabi-v7a', 'x86_64')],
            'windows': [f'{edition}-{version}-windows-x64.zip'],
            'ios-altstore': [f'{edition}-{version}-ios-altstore.ipa'],
        }
        for platform, names in packages.items():
            folder = downloads / f'{edition}-{platform}'
            if not folder.is_dir():
                raise ValueError(f'缺少构建产物目录：{folder}')
            actual = {file.name for file in folder.iterdir() if file.is_file()}
            expected = set(names) | {'SHA256SUMS.txt'}
            if actual != expected:
                raise ValueError(f'{folder} 文件不符：缺少 {sorted(expected - actual)}，多余 {sorted(actual - expected)}')
            listed = {}
            for line in (folder / 'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
                digest, separator, name = line.partition('  ')
                if not separator or not re.fullmatch(r'[0-9a-f]{64}', digest) or name in listed:
                    raise ValueError(f'{folder} 校验清单无效')
                listed[name] = digest
            if set(listed) != set(names):
                raise ValueError(f'{folder} 校验清单与产物不一致')
            for name in names:
                source = folder / name
                with source.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if digest != listed[name]:
                    raise ValueError(f'校验失败：{source}')
                shutil.copy2(source, output / name)
                checksums.append(f'{digest}  {name}')
    (output / 'SHA256SUMS.txt').write_text('\n'.join(sorted(checksums)) + '\n', encoding='ascii')
    (output / 'RELEASE_NOTES.md').write_text(
        f'开发快照 {version}。Android、Windows 和 iOS 两种编译版本的构建产物及 SHA256 校验值见附件。\n\n'
        'iOS 附件为 AltStore 兼容 IPA，使用 AltStore 以自己的 Apple ID 重签名后安装。各平台真实设备和站源播放仍待集中验收。\n',
        encoding='utf-8',
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('downloads', type=Path)
    parser.add_argument('output', type=Path)
    options = parser.parse_args()
    prepare(options.downloads, options.output, Path(__file__).resolve().parents[1])
