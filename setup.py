import re
from setuptools import find_namespace_packages, setup

with open('langolier/__init__.py', 'r') as fh:
    version = re.search(r"__version__ = '(.*?)'", fh.read()).group(1)

with open('README.md', 'r') as fh:
    readme = fh.read()

setup(
    name='langolier',
    version=version,
    author='Scott Smitelli',
    author_email='scott@smitelli.com',
    description='Nothing good ever came from a ten-year-old tweet.',
    long_description=readme,
    packages=find_namespace_packages(),
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.6",
    install_requires=[
        'PyYAML==5.3.1',
        'tweepy==3.9.0'
    ],
    entry_points={
        'console_scripts': [
            'langolier = langolier:main'
        ]
    },
)
