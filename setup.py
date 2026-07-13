from setuptools import find_packages, setup


setup(
    name="m3u8-downloader",
    version="4.1.1",
    packages=find_packages(),
    install_requires=["requests>=2.31.0", "aiohttp>=3.9.0", "textual>=0.80.0"],
    extras_require={"desktop": ["PyQt6>=6.6.0"]},
    entry_points={
        "console_scripts": [
            "m3u8-downloader=m3u8_downloader.main:main",
            "m3u8-downloader-gui=m3u8_downloader.gui.app:main",
            "m3u8-downloader-tui=m3u8_downloader.tui.app:main",
        ]
    },
)
