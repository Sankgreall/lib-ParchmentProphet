from setuptools import setup, find_packages

setup(
    name='PapyrusProphet',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'python-dotenv',
        'lxml',
        'pandoc',
        'pdfminer.six',
        'openai',
        'tiktoken',
        'nltk',
        'bayoo-docx',
        'git+https://github.com/JSv4/Python-Redlines',
        'bs4',
        'Elasticsearch',
    ],
)