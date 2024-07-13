from setuptools import setup, find_packages

setup(
    name='ParchmentProphet',
    version='0.1.2',
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
        'Python-Redlines @ git+https://github.com/JSv4/Python-Redlines.git',
        'bs4',
        'Elasticsearch',
        'openpyxl',
        'xlrd',
        'numpy',
        'pandas',
        'scikit-learn',
        'syllapy',
        'textstat',
        'matplotlib',
        'scipy',
        'spacy',
        'networkx',
        'transformers',
        'torch',
        'cryptography==41.0.7',
        'pdf2image',
        'tenacity'
    ],
    entry_points={
        'console_scripts': [
            'spacy_en_download = spacy.cli:download',
        ],
    },
)

