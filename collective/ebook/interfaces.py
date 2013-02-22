import pkg_resources


from zope.interface import Interface
from zope import schema

from collective.ebook import MessageFactory as _

RELEASE = pkg_resources.get_distribution("collective.ebook").version
RESOURCE_PATH = "ebook/templates"


class IBrowserLayer(Interface):
    """Marker interface."""


class ISettings(Interface):
    html_to_pdf_executable = schema.TextLine(
        title=_(u"HTML to PDF executable"),
        default=u"prince --verbose --disallow-modify --input=html -",
        required=True
    )

    ssh_host = schema.TextLine(
        title=_(u"SSH host"),
        default=u"",
        required=False
    )

    template = schema.Choice(
        title=_(u"Template"),
        default="print.pt",
        required=True,
        vocabulary="collective.ebook.vocabularies.Templates",
    )
