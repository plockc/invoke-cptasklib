from setuptools import setup

setup(name='invoke-cptasklib',
      version=.1,
      description='Task modules for invoke',
      url='https://github.com/plockc/invoke-cptasklib',
      author='Chris Plock',
      license='Unlicense',
      packages=['invoke_cptasklib'],
      install_requires=[
          'invoke',
          'requests',
      ],
      zip_safe=False)

