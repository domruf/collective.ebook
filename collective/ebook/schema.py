# -*- coding: utf-8 -*-

from zope.interface import implements
from zope.component import adapts

from Products.Archetypes.public import BooleanField, BooleanWidget
from Products.Archetypes.interfaces import IBaseContent

from archetypes.schemaextender.interfaces import IBrowserLayerAwareExtender
from archetypes.schemaextender.field import ExtensionField

from plone.indexer import indexer

from .interfaces import IBrowserLayer

from collective.ebook import MessageFactory as _

@indexer(IBaseContent)
def indexAllowPDF(obj):
    return obj.getField('allowPDF').get(obj)


class ATBooleanField(ExtensionField, BooleanField):
    """Basic schema-extension boolean field."""


class ATExtensionSchema(object):
    adapts(IBaseContent)
    implements(IBrowserLayerAwareExtender)

    layer = IBrowserLayer

    _fields = (
        ATBooleanField(
            "allowPDF",
            schemata="default",
            default=True,
            widget=BooleanWidget(
                label="Enable this article to be included in a in a PDF-generation",
                label_msgid="Enable PDF-generation",
                description="If this is checked, the article will be included when a PDF generation of a folder is triggered",
                description_msgid="enable_pdf_help",
                i18n_domain="collective.ebook",
            ),
        ),

        ATBooleanField(
            "enablePDF",
            schemata="settings",
            default=False,
            widget=BooleanWidget(
                label="Show PDF-generation-button on this article",
                label_msgid="show_pdf_button",
                description="Select this to enable the possibilty to generate a PDF of this content, select and deselect the inclusion of subfolders and articles.",
                description_msgid="show_pdf_button_help",
                i18n_domain="collective.ebook",
            ),
        ),
    )

    def __init__(self, context):
        self.context = context

    def getFields(self):
        return self._fields
