import os
from setuptools import setup, find_packages

def read(*pathnames):
    return open(os.path.join(os.path.dirname(__file__), *pathnames)).read()


setup(name='collective.ebook',
      version='1.0-dev',
      description="Make content available in PDF-format.",
      long_description='\n'.join([
          read('README.rst'),
          read('CHANGES.rst'),
          ]),
      author='Malthe Borch',
      author_email='mborch@gmail.com',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['collective', ],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'plone.resource',
          'plone.resourceeditor',
          'plone.app.registry',
          'BeautifulSoup',
      ],
      entry_points="""
      # -*- entry_points -*-
      [z3c.autoinclude.plugin]
      target = plone
      """
)
