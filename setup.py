import setuptools

# Load description
with open('README.md', 'r') as fr:
    long_description = fr.read()

# Load version string
loaded_vars = dict()
with open('remass/version.py') as fv:
    exec(fv.read(), loaded_vars)

setuptools.setup(
    name="remass",
    version=loaded_vars['__version__'],
    author="snototter",
    author_email="snototter@users.noreply.github.com",
    description="A curses-based TUI to interact with reMarkable e-ink tablets.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/snototter/remass",
    packages=setuptools.find_packages(),
    install_requires=[
        'wheel',
        'appdirs',
        'npyscreen',
        'paramiko',
        'toml'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)