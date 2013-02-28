Overview
========

This add-on allows the formatting of a subtree of content as a
PDF-article.


Requirements
------------

* Plone 4.1+

* An HTML-to-PDF-converter installed on your system, such as PrinceXML
  (commercial) or wkhtmltopdf (GNU Lesser GPL).


Compatibility
-------------

Plone 4.1+

While the default installation script should work in most cases, there
might be compatibility issues with some provided JavaScript libraries
– in particular, jQuery UI – if you've already got add-ons which need
to provide it, too.


Installation
------------

Add 'collective.ebook' to the eggs-section of your buildout.cfg, 
run buildout, restart instance.

Go to the quickinstaller of your site, accessible via
'yourhost.com:8080/plonesiteId/prefs_install_products_form'
and activate collective.ebooks.


Usage
-----

In editmode of a folder or article, click the tab 'Settings',
check 'Enable this article to be included in a in a PDF-generation',
hit save.

You should now see a tree-like overview of the selected items and its 
children, where you can select or deselect the items you want to be 
included in the PDG-generation.

Additonally every article has an extra-field for general, so to say global,
in- and exclusion of a PDF-generation, which is set to True by default, 
meaning included.


License
-------

GPLv3 (http://www.gnu.org/licenses/gpl.html).


Author
------

Malthe Borch <mborch@gmail.com>


Contributors
------------

Ida Ebkes <contact@ida-ebkes.eu>, translations and docs.


Further credits
---------------

dynatree is implemented to provide a nice UI and lazy loading for selecting 
arbitrary parts of subtrees.
