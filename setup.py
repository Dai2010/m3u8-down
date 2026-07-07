from setuptools import find_packages, setup


setup(
    name="m3u8-downloader",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["requests>=2.31.0"],
    entry_points={"console_scripts": ["m3u8-downloader=m3u8_downloader.main:main"]},
)
