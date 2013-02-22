# -*- coding: utf-8 -*-

from zope.interface import implements
from zope.component import adapts

from Products.Archetypes.public import BooleanField, BooleanWidget
from Products.Archetypes.interfaces import IBaseContent

from archetypes.schemaextender.interfaces import IBrowserLayerAwareExtender
from archetypes.schemaextender.field import ExtensionField

from plone.indexer import indexer

from .interfaces import IBrowserLayer


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
                label="Denne side kan indgå i PDF",
                description=("Hvis dette er valgt, vil en besøgende "
                             "få mulighed for at medtage siden ved "
                             "download i PDF-format."),
            ),
        ),

        ATBooleanField(
            "enablePDF",
            schemata="settings",
            default=False,
            widget=BooleanWidget(
                label="Vis PDF-værktøj på denne side.",
                description=("Hvis dette er valgt, vises en formular "
                             "under sidens almindelig indhold, som "
                             "besøgende kan benytte til at hente "
                             "en PDF-artikel bestående af et udvalg af "
                             "den valgte sektions artikler."),
            ),
        ),
    )

    def __init__(self, context):
        self.context = context

    def getFields(self):
        return self._fields
