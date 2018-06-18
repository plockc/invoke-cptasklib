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
      entry_points={
          'console_scripts': ['cptasks = invoke_cptasklib.main:program.run']
      },
      zip_safe=False)

