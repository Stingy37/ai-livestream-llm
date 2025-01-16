"""
This module provides functions that were previously used to troubleshoot/debug issues

Functions:
    troubleshoot_chromedriver()
    get_version()
    check_versions()
"""


# Standard Library Imports
import subprocess


def troubleshoot_chromedriver():
    try:
        # List the chromedriver path
        subprocess.run(["ls", "/root/.wdm/drivers/chromedriver/linux64/127.0.6533.72/chromedriver-linux64"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error listing chromedriver: {e}")

    # Uncomment the following line to remove the chromedriver directory
    # subprocess.run(["rm", "-rf", "/root/.wdm"], check=True)


# Get version of a certain package
def get_version(cmd, flag):
    result = subprocess.run([cmd, flag], capture_output=True, text=True)
    return result.stdout.split()[1] if result.returncode == 0 else "Error"

# print all installed package versions
def check_versions():
    import importlib.metadata
    import subprocess

    versions = {}
    packages = {
        'beautifulsoup4': 'beautifulsoup4',
        'langchain-community': 'langchain_community',
        'langchain-openai': 'langchain_openai',
        'langchain_text_splitters': 'langchain_text_splitters',
        'markdownify': 'markdownify',
        'openai': 'openai',
        'faiss-cpu': 'faiss_cpu',
        'selenium': 'selenium',
        'pydub': 'pydub',
        'PyPDF2': 'PyPDF2',
        'webdriver-manager': 'webdriver_manager',
        'rsync': 'rsync --version',
        'google-chrome-stable': 'google-chrome-stable --version',
        'chromedriver': 'chromedriver --version',
        'ffmpeg': 'ffmpeg -version'
    }


    for package, command in packages.items():
        try:
            if ' ' in command:
                # Split the command and the version flag
                cmd, flag = command.split()
                versions[package] = get_version(cmd, flag)
            else:
                # For Python packages, use importlib.metadata to get version
                versions[package] = importlib.metadata.version(command)
        except Exception as e:
            versions[package] = str(e)

    for package, version in versions.items():
        print(f"{package}: {version}")
