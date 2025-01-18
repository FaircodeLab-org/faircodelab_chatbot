from setuptools import setup, find_packages

# Read the requirements from requirements.txt
with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="faircodelab_chatbot",
    version="0.0.1",
    description="faircodelab_chatbot",
    author="vinay",
    author_email="reddysrivinayofficial@gmail.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)