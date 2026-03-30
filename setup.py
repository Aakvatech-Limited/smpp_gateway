from setuptools import find_packages, setup

install_requires = ["smpplib==2.2.1"]

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
