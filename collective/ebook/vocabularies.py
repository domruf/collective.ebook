from zExceptions import NotFound

from zope.component import getUtility
from zope.component import queryUtility
from zope.interface import implements
from zope.schema.vocabulary import SimpleTerm, SimpleVocabulary
from zope.schema.interfaces import IVocabularyFactory

from plone.resource.interfaces import IResourceDirectory

from .interfaces import RELEASE
from .interfaces import RESOURCE_PATH


class TemplateVocabulary(object):
    implements(IVocabularyFactory)

    def __call__(self, context):
        persistent = queryUtility(IResourceDirectory, name="persistent")
        static = getUtility(IResourceDirectory, name="++ebook++templates")

        try:
            directory = persistent[RESOURCE_PATH]
        except NotFound:
            entries = ()
        else:
            entries = set(directory.listDirectory()) if directory is not None else ()

        templates = [(entry, entry) for entry in entries] + \
                    [(entry.encode('utf-8'),
                      u"%s (filsystem, release %s)" % (entry, RELEASE))
                     for entry in static.listDirectory()
                     if entry.encode('utf-8') not in entries]

        return SimpleVocabulary(
            [SimpleTerm(entry, entry, title) for (entry, title) in templates]
        )


Templates = TemplateVocabulary()
