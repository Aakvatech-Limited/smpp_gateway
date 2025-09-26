from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in smpp_gateway/__init__.py
from smpp_gateway import __version__ as version

setup(
	name="smpp_gateway",
	version=version,
	description="Message transcever app",
	author="aakvatech",
	author_email="info@aakvatech.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
