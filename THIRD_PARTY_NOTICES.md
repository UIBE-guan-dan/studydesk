# Third-party components

StudyDesk's own source is MIT licensed. This does not replace licenses of bundled dependencies.
The Windows package includes `third-party-licenses/` with dependency versions, metadata and available license notices, as well as notices supplied by PyInstaller's package hooks under `_internal/`.

Python: https://www.python.org/downloads/release/python-3135/
PyInstaller bootloader and exception: https://pyinstaller.org/en/stable/license.html

Audio decoding uses unmodified PyAV 18.1.0 (BSD-3-Clause) and dynamically linked FFmpeg 8.1.2 libraries. The bundled FFmpeg library reports LGPL version 3 or later. Their licenses and any other bundled component licenses continue to apply. This project imposes no restriction on replacing those libraries or reverse engineering for debugging modifications to them.

- PyAV source: https://github.com/PyAV-Org/PyAV/tree/v18.1.0
- FFmpeg source: https://ffmpeg.org/releases/ffmpeg-8.1.2.tar.xz
- Upstream build scripts and dependency source locations: https://github.com/PyAV-Org/pyav-ffmpeg
- PyAV's version-specific build configuration: https://github.com/PyAV-Org/PyAV/blob/v18.1.0/scripts/ffmpeg-8.1.json
- LGPL v3 text: https://www.gnu.org/licenses/lgpl-3.0.html

Speech recognition models are not included in this distribution. Downloading a model obtains it from its upstream repository, with its own model license. No textbooks, recordings, user databases or API credentials are distributed.
