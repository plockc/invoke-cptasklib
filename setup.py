from setuptools import setup
from setuptools import find_packages

setup(name='invoke-cptasklib',
      version="0.1.2",
      description='Task modules for invoke',
      url='https://github.com/plockc/invoke-cptasklib',
      author='Chris Plock',
      license='Unlicense',
      packages=find_packages(),
      install_requires=[
          'invoke>=1.0.0',
          'requests',
      ],
      entry_points={
          'console_scripts': ['cptasks = invoke_cptasklib.main:program.run']
      },
      zip_safe=False)

