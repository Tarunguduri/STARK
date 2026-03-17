"""
Extended setup script for STARK with GUI support
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the contents of README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

# Core requirements
core_requirements = [
    "requests>=2.31.0",
    "psutil>=5.9.0",
    "urllib3>=2.0.0",
    "PyYAML>=6.0",
    "python-dateutil>=2.8.0"
]

# GUI requirements
gui_requirements = [
    "Pillow>=9.0.0",
    "pystray>=0.19.0"
]

# Platform-specific requirements
platform_requirements = {
    "win32": ["win10toast>=0.9"],
    "darwin": [],
    "linux": []
}

# Optional requirements
optional_requirements = {
    "voice": ["pyttsx3>=2.90", "SpeechRecognition>=3.10.0"],
    "pdf": ["reportlab>=4.0.0"],
    "notifications": ["playsound>=1.3.0"],
    "hotkeys": ["keyboard>=1.13.0"],
    "dev": ["pytest>=7.0.0", "black>=23.0.0", "flake8>=6.0.0"]
}

setup(
    name="stark-desktop-assistant",
    version="1.0.0",
    author="STARK Development Team",
    author_email="your-email@example.com",
    description="A hybrid LLM-powered smart desktop assistant with GUI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/STARK-Desktop-Assistant",
    py_modules=["stark", "stark_gui"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Desktop Environment",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities",
        "Environment :: X11 Applications",
        "Environment :: Win32 (MS Windows)",
        "Environment :: MacOS X"
    ],
    python_requires=">=3.8",
    install_requires=core_requirements + gui_requirements,
    extras_require={
        **optional_requirements,
        "all": sum(optional_requirements.values(), [])
    },
    entry_points={
        "console_scripts": [
            "stark=stark_launcher:main",
            "stark-cli=stark:main",
            "stark-gui=stark_gui:main",
        ],
    },
    keywords="ai assistant desktop automation llm privacy offline gui",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/STARK-Desktop-Assistant/issues",
        "Source": "https://github.com/yourusername/STARK-Desktop-Assistant",
        "Documentation": "https://github.com/yourusername/STARK-Desktop-Assistant/docs",
    },
    include_package_data=True,
    package_data={
        "": ["*.ico", "*.png", "*.json", "*.yaml"]
    }
)