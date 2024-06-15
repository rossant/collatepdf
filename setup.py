from setuptools import setup


def parse_requirements(filename):
    """ Load requirements from a pip requirements file """
    with open(filename, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]


setup(
    name='collatepdf',
    version='0.1.0',
    py_modules=['collatepdf'],
    install_requires=parse_requirements('requirements.txt'),
    entry_points={
        'console_scripts': [
            'collatepdf=collatepdf:main',
        ],
    },
)
