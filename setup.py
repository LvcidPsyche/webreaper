from setuptools import setup, find_packages

# Core deps (mirrors requirements.txt — keep in sync)
INSTALL_REQUIRES = [
    "aiohttp>=3.9.0",
    "aiofiles>=23.0.0",
    "httpx>=0.27.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=4.9.0",
    "playwright>=1.40.0",
    "tldextract>=5.0.0",
    "fake-useragent>=1.4.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0.0",
    "sqlalchemy>=2.0.0",
    "aiosqlite>=0.19.0",
    "alembic>=1.13.0",
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "sse-starlette>=1.6.0",
    "websockets>=12.0",
    "supabase>=2.0.0",
    "stripe>=8.0.0",
    "anthropic>=0.28.0",
    "dnspython>=2.5.0",
    "python-whois>=0.9.0",
    "openpyxl>=3.1.0",
    "structlog>=24.0.0",
    "slowapi>=0.1.9",
]

# Optional extras — install with: pip install webreaper[postgres]
EXTRAS_REQUIRE = {
    "postgres": [
        "asyncpg>=0.29.0",
        "psycopg2-binary>=2.9.0",
    ],
    "dev": [
        "pytest>=8.0.0",
        "pytest-asyncio>=0.23.0",
        "pytest-httpx>=0.30.0",
        "pytest-cov>=5.0.0",
        "respx>=0.21.0",
        "autoflake>=2.0.0",
        "black>=24.0.0",
        "isort>=5.13.0",
    ],
}

setup(
    name="webreaper",
    version="2.3.0",
    description="WebReaper — smart async web scraper with AI digest and change monitoring",
    packages=find_packages(exclude=["tests*", "docs*"]),
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    entry_points={
        "console_scripts": [
            "webreaper=webreaper:main",
        ],
    },
    python_requires=">=3.11",
    classifiers=[
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
