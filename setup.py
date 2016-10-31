from setuptools import setup, find_packages


setup(
    name='tervis',
    version='0.1.0.dev0',
    url='http://github.com/getsentry/tervis',
    license='BSD',
    author='Sentry',
    author_email='hello@getsentry.com',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'click~=6.6',
        'PyYAML~=3.12',
        'confluent-kafka~=0.9',
        'redis~=2.10',
        'aiohttp~=1.0.3',
        'SQLAlchemy~=1.1.3',
        'aiopg~=0.12.0',
    ],
    entry_points={
        'console_scripts': [
            'tervis = tervis.cli:cli',
        ],
    },
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
)
