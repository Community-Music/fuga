from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="fuga",  # Package name
    version="1.1.1",  # Version of the package
    author="LANKS",
    author_email="will.cuming@unifiedmusicgroup.com",
    description="A Python client for interacting with the FUGA API.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/will-unified/fuga",  # Repository URL
    packages=find_packages(exclude=["scripts", "scripts.*"]),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.32.3",
        "google-cloud-storage>=2.17.0",
        "python-dotenv>=1.0.1",
    ],
)
